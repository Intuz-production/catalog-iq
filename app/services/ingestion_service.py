"""
CatalogIQ — CSV Ingestion and Data Normalization Service

Pipeline 1: Ingests raw supplier CSV feeds, normalizes inconsistent
attributes, and flags data quality contradictions for review.
"""

import io
import logging
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.models.schemas import (
    Product, DataIssue, IngestionJob,
    ProductStatus, IssueType, IssueSeverity, ProductCreate,
    IngestionJobResponse,
)
from app.services.product_service import get_product_by_sku, create_product, update_product
from app.models.schemas import ProductUpdate
from app.utils.helpers import (
    normalize_text, normalize_attribute_value,
    detect_contradictions, calculate_content_score,
)

logger = logging.getLogger("catalogiq.ingestion_service")

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
            if raw_value and raw_value.lower() not in ("nan", "none", "", "n/a"):
                attributes[field] = normalize_attribute_value(field, raw_value)

    # Capture any extra columns as additional attributes
    known_cols = set(column_map.values())
    for col in row.index:
        if col not in known_cols:
            val = str(row[col]).strip()
            if val and val.lower() not in ("nan", "none", ""):
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

                title = normalize_text(str(row.get(column_map.get("title", ""), "")).strip())
                description = normalize_text(str(row.get(column_map.get("description", ""), "")).strip())
                category = normalize_text(str(row.get(column_map.get("category", ""), "")).strip())
                brand = normalize_text(str(row.get(column_map.get("brand", ""), "")).strip())

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
                title = title if title and title.lower() not in ("nan", "none") else sku
                description = description if description and description.lower() not in ("nan", "none") else None
                category = category if category and category.lower() not in ("nan", "none") else None
                brand = brand if brand and brand.lower() not in ("nan", "none") else None

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

                # Run quality checks
                product_issues = _run_quality_checks(db, product, attributes)
                issues_count += len(product_issues)

                # Update product status based on issues
                if product_issues:
                    product.status = ProductStatus.FLAGGED
                else:
                    product.status = ProductStatus.ACTIVE
                db.commit()

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


def _run_quality_checks(
    db: Session,
    product: Product,
    attributes: dict[str, str],
) -> list[DataIssue]:
    """Run data quality checks on a product and create issue records.

    Args:
        db: Database session.
        product: Product to check.
        attributes: Normalized product attributes.

    Returns:
        List of DataIssue records created.
    """
    issues: list[DataIssue] = []

    # Check for missing description
    if not product.description:
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.MISSING_DESCRIPTION,
            severity=IssueSeverity.HIGH,
            description=f"Product '{product.sku}' has no description. SEO content generation recommended.",
            field_name="description",
        )
        db.add(issue)
        issues.append(issue)

    # Check for thin content
    elif product.description:
        content_score = calculate_content_score(product.description)
        if content_score["score"] < 50:
            issue = DataIssue(
                product_id=product.id,
                issue_type=IssueType.THIN_CONTENT,
                severity=IssueSeverity.MEDIUM,
                description=(
                    f"Product '{product.sku}' has thin content "
                    f"(score: {content_score['score']}/100, {content_score['word_count']} words). "
                    f"Issues: {', '.join(content_score['issues'])}"
                ),
                field_name="description",
                actual_value=str(content_score["word_count"]) + " words",
            )
            db.add(issue)
            issues.append(issue)

    # Check for attribute contradictions
    contradictions = detect_contradictions(
        product.title or "",
        product.description or "",
        attributes,
    )
    for contradiction in contradictions:
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.ATTRIBUTE_CONTRADICTION,
            severity=IssueSeverity.HIGH,
            description=(
                f"Contradiction detected in '{contradiction['field']}': "
                f"attribute says '{contradiction['expected']}' but {contradiction['actual']}"
            ),
            field_name=contradiction["field"],
            expected_value=contradiction["expected"],
            actual_value=contradiction["actual"],
        )
        db.add(issue)
        issues.append(issue)

    # Check for missing key attributes
    required_attrs = ["color", "size", "material"]
    missing_attrs = [attr for attr in required_attrs if attr not in attributes]
    if len(missing_attrs) >= 2:
        issue = DataIssue(
            product_id=product.id,
            issue_type=IssueType.MISSING_ATTRIBUTES,
            severity=IssueSeverity.LOW,
            description=(
                f"Product '{product.sku}' is missing attributes: {', '.join(missing_attrs)}. "
                f"Adding these can improve content quality."
            ),
            field_name=", ".join(missing_attrs),
        )
        db.add(issue)
        issues.append(issue)

    if issues:
        db.commit()

    return issues


def get_ingestion_jobs(db: Session, limit: int = 20) -> list[IngestionJob]:
    """Retrieve recent ingestion job history.

    Args:
        db: Database session.
        limit: Maximum records to return.

    Returns:
        List of IngestionJob records ordered by recency.
    """
    return db.query(IngestionJob).order_by(IngestionJob.started_at.desc()).limit(limit).all()


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
