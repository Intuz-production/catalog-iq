"""
CatalogIQ — CSV Ingestion and Data Normalization Service

Pipeline 1: Ingests raw supplier CSV feeds, normalizes inconsistent
attributes, and flags data quality contradictions for review.
"""

import io
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.schemas import (
    Product, DataIssue, IngestionJob,
    ProductStatus, IssueType, IssueSeverity, ProductCreate,
    IngestionJobResponse,
    IngestionJobSortField, DataIssueSortField, SortOrder,
)
from app.services.product_service import get_product_by_sku, create_product, update_product
from app.models.schemas import ProductUpdate
from app.utils.helpers import (
    normalize_text, normalize_attribute_value,
    detect_contradictions, calculate_content_score,
    clean_text_field, is_placeholder_value,
)

logger = logging.getLogger("catalogiq.ingestion_service")

PRICE_ANOMALY_MAX = 50_000.0


@dataclass
class _PendingIssue:
    """In-memory quality issue used before syncing to the database."""
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    field_name: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None

INGESTION_JOB_SORT_COLUMNS = {
    IngestionJobSortField.ID: IngestionJob.id,
    IngestionJobSortField.FILENAME: IngestionJob.filename,
    IngestionJobSortField.STATUS: IngestionJob.status,
    IngestionJobSortField.PROCESSED_ROWS: IngestionJob.processed_rows,
    IngestionJobSortField.NEW_PRODUCTS: IngestionJob.new_products,
    IngestionJobSortField.UPDATED_PRODUCTS: IngestionJob.updated_products,
    IngestionJobSortField.ISSUES_FOUND: IngestionJob.issues_found,
    IngestionJobSortField.STARTED_AT: IngestionJob.started_at,
}

DATA_ISSUE_SORT_COLUMNS = {
    DataIssueSortField.CREATED_AT: DataIssue.created_at,
    DataIssueSortField.SEVERITY: DataIssue.severity,
    DataIssueSortField.ISSUE_TYPE: DataIssue.issue_type,
    DataIssueSortField.PRODUCT_ID: DataIssue.product_id,
}

# Expected CSV column mappings (flexible — maps common supplier column names)
COLUMN_MAPPINGS: dict[str, list[str]] = {
    "sku": ["sku", "product_id", "item_id", "item_number", "product_code", "asin"],
    "title": ["title", "name", "product_name", "item_name", "product_title"],
    "description": ["description", "desc", "product_description", "long_description", "details"],
    "category": ["category", "product_category", "type", "product_type", "department"],
    "brand": ["brand", "manufacturer", "vendor", "brand_name"],
    "price": ["price", "retail_price", "list_price", "sale_price", "unit_price"],
    "currency": ["currency", "currency_code"],
    "color": ["color", "colour"],
    "size": ["size", "sizes", "dimensions"],
    "material": ["material", "materials", "fabric"],
    "weight": ["weight", "item_weight", "shipping_weight"],
    "upc": ["upc", "ean", "barcode", "gtin"],
}


def _map_columns(df: pd.DataFrame) -> dict[str, str]:
    """Map CSV column names to standardized field names.

    Args:
        df: DataFrame with raw CSV columns.

    Returns:
        Mapping from standard field names to actual CSV column names.
    """
    column_map: dict[str, str] = {}
    df_columns_lower = {col.lower().strip(): col for col in df.columns}

    for standard_name, possible_names in COLUMN_MAPPINGS.items():
        for name in possible_names:
            if name in df_columns_lower:
                column_map[standard_name] = df_columns_lower[name]
                break

    return column_map


def _extract_attributes(row: pd.Series, column_map: dict[str, str]) -> dict[str, str]:
    """Extract and normalize product attributes from a CSV row.

    Args:
        row: Single row from the CSV DataFrame.
        column_map: Column name mapping.

    Returns:
        Dictionary of normalized attribute key-value pairs.
    """
    attribute_fields = ["color", "size", "material", "weight", "upc"]
    attributes: dict[str, str] = {}

    for field in attribute_fields:
        if field in column_map:
            raw_value = str(row.get(column_map[field], "")).strip()
            if raw_value and not is_placeholder_value(raw_value):
                attributes[field] = normalize_attribute_value(field, raw_value)

    # Capture any extra columns as additional attributes
    known_cols = set(column_map.values())
    for col in row.index:
        if col not in known_cols:
            val = str(row[col]).strip()
            if val and not is_placeholder_value(val):
                attributes[col.lower().replace(" ", "_")] = val

    return attributes


def process_csv(
    db: Session,
    file_content: bytes,
    filename: str,
) -> IngestionJobResponse:
    """Process a CSV file: parse, normalize, detect issues, and store products.

    This is the main entry point for Pipeline 1 (Data Cleanup).

    Args:
        db: Database session.
        file_content: Raw CSV file bytes.
        filename: Original filename for tracking.

    Returns:
        IngestionJobResponse with processing results.
    """
    # Create ingestion job record
    job = IngestionJob(
        filename=filename,
        status="processing",
    )
    db.add(job)
    db.commit()
    db.refresh(job)

    logger.info(f"Starting ingestion job {job.id} for file: {filename}")

    try:
        # Read CSV
        df = pd.read_csv(io.BytesIO(file_content))
        df = df.dropna(how="all")  # Drop fully empty rows
        job.total_rows = len(df)

        if df.empty:
            job.status = "completed"
            job.error_message = "CSV file is empty or contains only headers."
            db.commit()
            return _job_to_response(job)

        # Map columns
        column_map = _map_columns(df)

        if "sku" not in column_map:
            job.status = "failed"
            job.error_message = (
                "CSV must contain a SKU/product_id column. "
                f"Found columns: {', '.join(df.columns.tolist())}"
            )
            db.commit()
            return _job_to_response(job)

        logger.info(f"Column mapping: {column_map}")

        new_count = 0
        updated_count = 0
        issues_count = 0

        for idx, row in df.iterrows():
            try:
                sku = str(row[column_map["sku"]]).strip()
                if not sku or sku.lower() in ("nan", "none"):
                    continue

                title = clean_text_field(str(row.get(column_map.get("title", ""), "")).strip()) or ""
                description = clean_text_field(str(row.get(column_map.get("description", ""), "")).strip())
                category = clean_text_field(str(row.get(column_map.get("category", ""), "")).strip())
                brand = clean_text_field(str(row.get(column_map.get("brand", ""), "")).strip())

                # Parse price
                price: Optional[float] = None
                if "price" in column_map:
                    try:
                        price_val = row[column_map["price"]]
                        if pd.notna(price_val):
                            price = float(str(price_val).replace(",", "").replace("$", "").strip())
                    except (ValueError, TypeError):
                        pass

                currency = "USD"
                if "currency" in column_map:
                    curr = str(row.get(column_map["currency"], "")).strip()
                    if curr and curr.lower() not in ("nan", "none"):
                        currency = curr.upper()

                # Clean empty strings
                title = title if title else sku

                # Extract and normalize attributes
                attributes = _extract_attributes(row, column_map)

                # Check if product exists
                existing = get_product_by_sku(db, sku)

                if existing:
                    # Update existing product
                    update_data = ProductUpdate(
                        title=title,
                        description=description,
                        category=category,
                        brand=brand,
                        price=price,
                        attributes=attributes,
                    )
                    update_product(db, existing.id, update_data)
                    product = existing
                    updated_count += 1
                else:
                    # Create new product
                    product_data = ProductCreate(
                        sku=sku,
                        title=title,
                        description=description,
                        category=category,
                        brand=brand,
                        price=price,
                        currency=currency,
                        attributes=attributes,
                    )
                    product = create_product(db, product_data)
                    new_count += 1

                # Store raw data for reference, converting NaN values to None for JSON compatibility
                product.raw_data = {
                    str(k): (None if pd.isna(v) else v)
                    for k, v in row.items()
                }
                db.commit()

                # Run quality checks and sync open issues
                product_issues = _run_quality_checks(db, product, attributes)
                issues_count += len(product_issues)

                job.processed_rows = idx + 1

            except Exception as e:
                logger.warning(f"Error processing row {idx}: {str(e)}")
                continue

        # Finalize job
        job.new_products = new_count
        job.updated_products = updated_count
        job.issues_found = issues_count
        job.status = "completed"
        job.completed_at = datetime.utcnow()
        db.commit()

        logger.info(
            f"Ingestion job {job.id} completed: "
            f"{new_count} new, {updated_count} updated, {issues_count} issues"
        )

    except pd.errors.ParserError as e:
        job.status = "failed"
        job.error_message = f"Failed to parse CSV: {str(e)}"
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.error(f"CSV parse error for job {job.id}: {str(e)}")

    except Exception as e:
        job.status = "failed"
        job.error_message = f"Unexpected error: {str(e)}"
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.error(f"Ingestion job {job.id} failed: {str(e)}")

    return _job_to_response(job)


def _issue_dedup_key(
    issue_type: IssueType,
    field_name: Optional[str],
    actual_value: Optional[str] = None,
) -> tuple[str, str, str]:
    """Build a stable key for deduplicating unresolved quality issues."""
    return (
        issue_type.value,
        (field_name or "").strip().lower(),
        (actual_value or "").strip().lower(),
    )


def _collect_pending_issues(
    db: Session,
    product: Product,
    attributes: dict[str, str],
) -> list[_PendingIssue]:
    """Evaluate all ingestion quality rules for a product."""
    pending: list[_PendingIssue] = []

    if not product.description:
        pending.append(_PendingIssue(
            issue_type=IssueType.MISSING_DESCRIPTION,
            severity=IssueSeverity.HIGH,
            description=(
                f"Product '{product.sku}' has no description. "
                "SEO content generation recommended."
            ),
            field_name="description",
        ))
    else:
        content_score = calculate_content_score(product.description)
        if content_score["score"] < 50:
            pending.append(_PendingIssue(
                issue_type=IssueType.THIN_CONTENT,
                severity=IssueSeverity.MEDIUM,
                description=(
                    f"Product '{product.sku}' has thin content "
                    f"(score: {content_score['score']}/100, {content_score['word_count']} words). "
                    f"Issues: {', '.join(content_score['issues'])}"
                ),
                field_name="description",
                actual_value=f"{content_score['word_count']} words",
            ))

    contradictions = detect_contradictions(
        product.title or "",
        product.description or "",
        attributes,
    )
    for contradiction in contradictions:
        severity = (
            IssueSeverity.MEDIUM
            if contradiction.get("severity") == "medium"
            else IssueSeverity.HIGH
        )
        pending.append(_PendingIssue(
            issue_type=IssueType.ATTRIBUTE_CONTRADICTION,
            severity=severity,
            description=(
                f"Contradiction detected in '{contradiction['field']}': "
                f"attribute says '{contradiction['expected']}' but {contradiction['actual']}"
            ),
            field_name=contradiction["field"],
            expected_value=contradiction["expected"],
            actual_value=contradiction["actual"],
        ))

    required_attrs = ["color", "size", "material"]
    missing_attrs = sorted(attr for attr in required_attrs if attr not in attributes)
    if len(missing_attrs) >= 2:
        pending.append(_PendingIssue(
            issue_type=IssueType.MISSING_ATTRIBUTES,
            severity=IssueSeverity.LOW,
            description=(
                f"Product '{product.sku}' is missing attributes: {', '.join(missing_attrs)}. "
                "Adding these can improve content quality."
            ),
            field_name=", ".join(missing_attrs),
        ))

    duplicate = db.query(Product).filter(
        Product.id != product.id,
        func.lower(Product.title) == (product.title or "").strip().lower(),
    ).first()
    if duplicate:
        pending.append(_PendingIssue(
            issue_type=IssueType.DUPLICATE_TITLE,
            severity=IssueSeverity.MEDIUM,
            description=(
                f"Product '{product.sku}' shares the same title as SKU '{duplicate.sku}'. "
                "Review for duplicate listings."
            ),
            field_name="title",
            actual_value=duplicate.sku,
        ))

    if product.price is not None:
        if product.price <= 0:
            pending.append(_PendingIssue(
                issue_type=IssueType.PRICE_ANOMALY,
                severity=IssueSeverity.CRITICAL,
                description=(
                    f"Product '{product.sku}' has an invalid price of "
                    f"{product.currency} {product.price:.2f}."
                ),
                field_name="price",
                actual_value=str(product.price),
            ))
        elif product.price > PRICE_ANOMALY_MAX:
            pending.append(_PendingIssue(
                issue_type=IssueType.PRICE_ANOMALY,
                severity=IssueSeverity.MEDIUM,
                description=(
                    f"Product '{product.sku}' has an unusually high price of "
                    f"{product.currency} {product.price:.2f}."
                ),
                field_name="price",
                actual_value=str(product.price),
            ))

    return pending


def _sync_quality_issues(
    db: Session,
    product: Product,
    pending_issues: list[_PendingIssue],
) -> list[DataIssue]:
    """Create, update, or resolve quality issues without duplicating open records."""
    existing_issues = db.query(DataIssue).filter(
        DataIssue.product_id == product.id,
        DataIssue.resolved == False,
    ).all()

    pending_map = {
        _issue_dedup_key(
            issue.issue_type,
            issue.field_name,
            issue.actual_value,
        ): issue
        for issue in pending_issues
    }
    existing_map = {
        _issue_dedup_key(
            issue.issue_type,
            issue.field_name,
            issue.actual_value,
        ): issue
        for issue in existing_issues
    }

    synced_issues: list[DataIssue] = []

    for key, pending_issue in pending_map.items():
        if key in existing_map:
            issue = existing_map[key]
            issue.severity = pending_issue.severity
            issue.description = pending_issue.description
            issue.expected_value = pending_issue.expected_value
            issue.actual_value = pending_issue.actual_value
            synced_issues.append(issue)
            continue

        issue = DataIssue(
            product_id=product.id,
            issue_type=pending_issue.issue_type,
            severity=pending_issue.severity,
            description=pending_issue.description,
            field_name=pending_issue.field_name,
            expected_value=pending_issue.expected_value,
            actual_value=pending_issue.actual_value,
        )
        db.add(issue)
        synced_issues.append(issue)

    for key, issue in existing_map.items():
        if key not in pending_map:
            issue.resolved = True
            issue.resolved_at = datetime.utcnow()

    if product.status != ProductStatus.ARCHIVED:
        product.status = ProductStatus.FLAGGED if pending_issues else ProductStatus.ACTIVE
    db.commit()
    return synced_issues


def finalize_product_edit(db: Session, product_id: int) -> Optional[Product]:
    """Sanitize edited product fields and re-run ingestion quality checks.

    Args:
        db: Database session.
        product_id: Product that was updated manually.

    Returns:
        Refreshed Product record or None if not found.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None

    if product.title:
        product.title = clean_text_field(product.title) or product.sku

    product.description = clean_text_field(product.description)
    product.category = clean_text_field(product.category)
    product.brand = clean_text_field(product.brand)

    normalized_attributes: dict[str, str] = {}
    for key, value in (product.attributes or {}).items():
        raw_value = str(value).strip()
        if not raw_value or is_placeholder_value(raw_value):
            continue
        if key.lower() in ("color", "colour", "size", "sizes", "material", "materials", "fabric"):
            normalized_attributes[key] = normalize_attribute_value(key, raw_value)
        else:
            normalized_attributes[key] = raw_value

    product.attributes = normalized_attributes
    db.commit()
    db.refresh(product)

    _run_quality_checks(db, product, normalized_attributes)
    db.refresh(product)
    logger.info(f"Re-ran quality checks for product {product_id} after manual edit")
    return product


def refresh_product_status(db: Session, product_id: int) -> Optional[ProductStatus]:
    """Update product status based on remaining unresolved quality issues."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return None

    open_issue_count = db.query(DataIssue).filter(
        DataIssue.product_id == product_id,
        DataIssue.resolved == False,
    ).count()

    product.status = (
        ProductStatus.FLAGGED if open_issue_count > 0 else ProductStatus.ACTIVE
    )
    db.commit()
    return product.status


def _run_quality_checks(
    db: Session,
    product: Product,
    attributes: dict[str, str],
) -> list[DataIssue]:
    """Run data quality checks on a product and sync issue records.

    Args:
        db: Database session.
        product: Product to check.
        attributes: Normalized product attributes.

    Returns:
        List of active DataIssue records after sync.
    """
    pending_issues = _collect_pending_issues(db, product, attributes)
    return _sync_quality_issues(db, product, pending_issues)


def get_ingestion_jobs(
    db: Session,
    skip: int = 0,
    limit: int = 20,
    status: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: IngestionJobSortField = IngestionJobSortField.STARTED_AT,
    sort_order: SortOrder = SortOrder.DESC,
) -> tuple[list[IngestionJob], int]:
    """Retrieve ingestion job history with filtering, sorting, and pagination."""
    query = db.query(IngestionJob)

    if status:
        query = query.filter(IngestionJob.status == status)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(IngestionJob.filename.ilike(search_term))

    total = query.count()
    sort_column = INGESTION_JOB_SORT_COLUMNS.get(sort_by, IngestionJob.started_at)
    if sort_order == SortOrder.ASC:
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    jobs = query.offset(skip).limit(limit).all()
    return jobs, total


def get_data_issues(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    resolved: bool = False,
    search: Optional[str] = None,
    severity: Optional[IssueSeverity] = None,
    issue_type: Optional[IssueType] = None,
    sort_by: DataIssueSortField = DataIssueSortField.CREATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
) -> tuple[list[DataIssue], int]:
    """Retrieve data quality issues with filtering, sorting, and pagination."""
    query = db.query(DataIssue).join(Product).filter(DataIssue.resolved == resolved)

    if severity:
        query = query.filter(DataIssue.severity == severity)
    if issue_type:
        query = query.filter(DataIssue.issue_type == issue_type)
    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                DataIssue.description.ilike(search_term),
                DataIssue.field_name.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.title.ilike(search_term),
            )
        )

    total = query.count()
    sort_column = DATA_ISSUE_SORT_COLUMNS.get(sort_by, DataIssue.created_at)
    if sort_order == SortOrder.ASC:
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    issues = query.offset(skip).limit(limit).all()
    return issues, total


def _job_to_response(job: IngestionJob) -> IngestionJobResponse:
    """Convert an IngestionJob ORM model to a response schema.

    Args:
        job: IngestionJob ORM model.

    Returns:
        IngestionJobResponse Pydantic model.
    """
    return IngestionJobResponse(
        id=job.id,
        filename=job.filename,
        total_rows=job.total_rows or 0,
        processed_rows=job.processed_rows or 0,
        new_products=job.new_products or 0,
        updated_products=job.updated_products or 0,
        issues_found=job.issues_found or 0,
        status=job.status or "unknown",
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
