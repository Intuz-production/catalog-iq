"""
CatalogIQ — CSV Ingestion and Data Normalization Service

Pipeline 1: Ingests raw supplier CSV feeds, normalizes inconsistent
attributes, and flags hard structural data quality issues for review.
Soft quality judgment (contradictions, thin content, omissions) runs in AI.
"""

import csv
import io
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import func, or_

from app.models.schemas import (
    Product, DataIssue, IngestionJob, IngestionJobProduct,
    ProductStatus, IssueType, IssueSeverity, ProductCreate,
    IngestionJobResponse,
    IngestionPreviewResponse,
    IngestionJobSortField, DataIssueSortField, SortOrder,
    ReviewAction, ReviewStatus, SuggestionSource,
    AiAnalysisStatus,
)
from app.services.product_service import create_product, update_product
from app.models.schemas import ProductUpdate
from app.utils.helpers import (
    normalize_attribute_value,
    clean_text_field, is_placeholder_value, parse_catalog_price,
)

logger = logging.getLogger("catalogiq.ingestion_service")

PRICE_ANOMALY_MAX = 50_000.0
MAX_SKIP_SAMPLES_PER_REASON = 5
APPENDABLE_JOB_STATUSES = frozenset({
    "completed",
    "completed_with_ai_errors",
    "analyzing",
})
GROUP_NAME_MAX_LENGTH = 255


class IngestionJobError(Exception):
    """Raised when an ingestion job cannot be created or appended to."""

    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def _normalize_group_name(group_name: Optional[str], fallback: str) -> str:
    """Return a trimmed group name or the fallback filename."""
    cleaned = (group_name or "").strip()
    if cleaned:
        return cleaned[:GROUP_NAME_MAX_LENGTH]
    return (fallback or "Untitled group")[:GROUP_NAME_MAX_LENGTH]


def _merge_skip_summary(
    job: IngestionJob,
    skip_reasons: Counter[str],
    skip_samples: dict[str, list[str]],
    *,
    append: bool,
) -> None:
    """Persist skipped row counts, merging with prior summary when appending."""
    if not append:
        _apply_skip_summary(job, skip_reasons, skip_samples)
        return

    existing = _parse_skip_summary(job.skip_summary) or {}
    existing_counts = existing.get("counts") if isinstance(existing.get("counts"), dict) else {}
    existing_samples = existing.get("samples") if isinstance(existing.get("samples"), dict) else {}

    merged_counts: Counter[str] = Counter()
    for key, value in existing_counts.items():
        try:
            merged_counts[str(key)] += int(value)
        except (TypeError, ValueError):
            continue
    merged_counts.update(skip_reasons)

    merged_samples: dict[str, list[str]] = {}
    for reason, values in existing_samples.items():
        if isinstance(values, list):
            for sample in values:
                _record_skip_sample(merged_samples, str(reason), str(sample))
    for reason, values in skip_samples.items():
        for sample in values:
            _record_skip_sample(merged_samples, reason, sample)

    _apply_skip_summary(job, merged_counts, merged_samples)


def _record_skip_sample(
    samples: dict[str, list[str]],
    reason: str,
    sample: str,
) -> None:
    """Append a skip sample for a reason, capped per reason."""
    bucket = samples.setdefault(reason, [])
    if len(bucket) >= MAX_SKIP_SAMPLES_PER_REASON:
        return
    if sample not in bucket:
        bucket.append(sample)


def _apply_skip_summary(
    job: IngestionJob,
    skip_reasons: Counter[str],
    skip_samples: dict[str, list[str]],
) -> None:
    """Persist skipped row counts and sample identifiers on the job."""
    skipped_count = sum(skip_reasons.values())
    job.skipped_rows = skipped_count
    if not skipped_count:
        job.skip_summary = None
        return
    job.skip_summary = json.dumps({
        "counts": dict(skip_reasons),
        "samples": {reason: list(values) for reason, values in skip_samples.items()},
    })


@dataclass
class _PendingIssue:
    """In-memory quality issue used before syncing to the database."""
    issue_type: IssueType
    severity: IssueSeverity
    description: str
    field_name: str
    expected_value: Optional[str] = None
    actual_value: Optional[str] = None


@dataclass
class NormalizedCsvRow:
    """Normalized product fields extracted from one supplier CSV row."""
    sku: str
    title: str
    description: Optional[str]
    category: Optional[str]
    brand: Optional[str]
    price: Optional[float]
    currency: str
    attributes: dict[str, str]
    raw_data: dict
    title_from_sku: bool
    unparsed_price: bool

INGESTION_JOB_SORT_COLUMNS = {
    IngestionJobSortField.ID: IngestionJob.id,
    IngestionJobSortField.FILENAME: IngestionJob.filename,
    IngestionJobSortField.GROUP_NAME: IngestionJob.group_name,
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
    "specifications": ["specifications", "specs", "spec", "specification"],
}

STANDARD_FIELDS: tuple[str, ...] = tuple(COLUMN_MAPPINGS.keys())
CSV_DELIMITERS = ",;\t|"
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "cp1252", "latin-1")


class CsvParseError(ValueError):
    """Raised when a supplier CSV cannot be decoded or parsed."""


@dataclass
class ParsedCsv:
    """In-memory CSV parse result used by preview and ingest."""
    dataframe: pd.DataFrame
    encoding: str
    delimiter: str
    warnings: list[str]


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


def _decode_csv_bytes(file_content: bytes) -> tuple[str, str]:
    """Decode CSV bytes using common supplier encodings."""
    if not file_content or not file_content.strip():
        raise CsvParseError("Uploaded file is empty.")

    last_error: Optional[UnicodeDecodeError] = None
    for encoding in CSV_ENCODINGS:
        try:
            return file_content.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            last_error = exc
    if last_error:
        raise CsvParseError("Could not decode the CSV file. Try saving it as UTF-8.") from last_error
    raise CsvParseError("Could not decode the CSV file. Try saving it as UTF-8.")


def _detect_delimiter(text: str) -> str:
    """Detect CSV delimiter from a text sample."""
    sample = text[:8192]
    first_line = next((line for line in sample.splitlines() if line.strip()), "")
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=CSV_DELIMITERS)
        if dialect.delimiter in CSV_DELIMITERS:
            return dialect.delimiter
    except csv.Error:
        pass

    counts = {delimiter: first_line.count(delimiter) for delimiter in [",", ";", "\t", "|"]}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def parse_supplier_csv(file_content: bytes) -> ParsedCsv:
    """Parse supplier CSV bytes with encoding and delimiter detection."""
    text, encoding = _decode_csv_bytes(file_content)
    delimiter = _detect_delimiter(text)
    warnings: list[str] = []

    try:
        dataframe = pd.read_csv(
            io.StringIO(text),
            sep=delimiter,
            on_bad_lines="skip",
        )
    except pd.errors.EmptyDataError as exc:
        raise CsvParseError("CSV file is empty or contains only headers.") from exc
    except pd.errors.ParserError as exc:
        raise CsvParseError(f"Failed to parse CSV: {exc}") from exc

    dataframe.columns = [str(column).strip() for column in dataframe.columns]
    dataframe = dataframe.dropna(how="all")

    if dataframe.columns.duplicated().any():
        warnings.append("Duplicate column names were found. The first match is used for mapping.")

    return ParsedCsv(
        dataframe=dataframe,
        encoding=encoding,
        delimiter=delimiter,
        warnings=warnings,
    )


def _resolve_column_map(
    df: pd.DataFrame,
    column_mapping: Optional[dict[str, str]] = None,
) -> dict[str, str]:
    """Build a standard-field map from auto-detect or a confirmed user mapping."""
    if not column_mapping:
        return _map_columns(df)

    df_columns_lower = {col.lower().strip(): col for col in df.columns}
    resolved: dict[str, str] = {}
    for standard_name, csv_column in column_mapping.items():
        if standard_name not in COLUMN_MAPPINGS:
            continue
        if not csv_column or not str(csv_column).strip():
            continue
        lookup = str(csv_column).lower().strip()
        if lookup not in df_columns_lower:
            raise CsvParseError(
                f"Mapped column '{csv_column}' for '{standard_name}' was not found in the CSV."
            )
        resolved[standard_name] = df_columns_lower[lookup]
    return resolved


def _serialize_preview_row(row: pd.Series) -> dict[str, Optional[str]]:
    """Convert a DataFrame row to JSON-safe string values."""
    serialized: dict[str, Optional[str]] = {}
    for key, value in row.items():
        if pd.isna(value):
            serialized[str(key)] = None
        else:
            serialized[str(key)] = str(value)
    return serialized


def preview_csv(
    file_content: bytes,
    filename: str,
    sample_size: int = 5,
) -> IngestionPreviewResponse:
    """Parse a CSV and return detected columns, suggested mapping, and sample rows."""
    parsed = parse_supplier_csv(file_content)
    if parsed.dataframe.empty:
        raise CsvParseError("CSV file is empty or contains only headers.")

    suggested_mapping = _map_columns(parsed.dataframe)
    warnings = list(parsed.warnings)
    if "sku" not in suggested_mapping:
        warnings.append("No SKU column was detected. Map a CSV column to SKU before ingesting.")

    sample_rows = [
        _serialize_preview_row(row)
        for _, row in parsed.dataframe.head(sample_size).iterrows()
    ]

    return IngestionPreviewResponse(
        filename=filename,
        encoding=parsed.encoding,
        delimiter="tab" if parsed.delimiter == "\t" else parsed.delimiter,
        total_rows=len(parsed.dataframe),
        columns=[str(column) for column in parsed.dataframe.columns.tolist()],
        suggested_mapping=suggested_mapping,
        sample_rows=sample_rows,
        warnings=warnings,
        standard_fields=list(STANDARD_FIELDS),
        required_fields=["sku"],
    )


def _mapped_cell(row: pd.Series, column_map: dict[str, str], field: str) -> Optional[str]:
    """Read and clean one mapped CSV cell."""
    csv_column = column_map.get(field)
    if not csv_column or csv_column not in row.index:
        return None
    value = row[csv_column]
    if pd.isna(value):
        return None
    return clean_text_field(str(value))


def _cell_as_sku(value: object) -> Optional[str]:
    """Normalize a SKU cell, including integer values stored as floats."""
    if value is None:
        return None
    try:
        if pd.isna(value):
            return None
    except (ValueError, TypeError):
        pass
    if isinstance(value, bool):
        return clean_text_field(str(value))
    if not isinstance(value, str):
        try:
            numeric = float(value)
            if numeric.is_integer():
                return clean_text_field(str(int(numeric)))
        except (TypeError, ValueError, OverflowError):
            pass
    return clean_text_field(str(value).strip())


def _raw_data_from_row(row: pd.Series) -> dict:
    """JSON-safe copy of the original CSV row."""
    return {
        str(key): (None if pd.isna(value) else value)
        for key, value in row.items()
    }


def _extract_attributes(row: pd.Series, column_map: dict[str, str]) -> dict[str, str]:
    """Extract and normalize product attributes from a CSV row.

    Args:
        row: Single row from the CSV DataFrame.
        column_map: Column name mapping.

    Returns:
        Dictionary of normalized attribute key-value pairs.
    """
    attribute_fields = ["color", "size", "material", "weight", "upc", "specifications"]
    attributes: dict[str, str] = {}

    for field in attribute_fields:
        raw_value = _mapped_cell(row, column_map, field)
        if raw_value:
            attributes[field] = normalize_attribute_value(field, raw_value)

    known_cols = set(column_map.values())
    for col in row.index:
        if col not in known_cols:
            value = row[col]
            if pd.isna(value):
                continue
            val = clean_text_field(str(value))
            if val:
                attributes[col.lower().replace(" ", "_")] = val

    return attributes


def _normalize_csv_row(
    row: pd.Series,
    column_map: dict[str, str],
) -> tuple[Optional[NormalizedCsvRow], Optional[str]]:
    """Normalize one CSV row into product fields, or return a skip reason."""
    sku_column = column_map.get("sku")
    sku = _cell_as_sku(row[sku_column] if sku_column in row.index else None)
    if not sku:
        return None, "blank_sku"

    title = _mapped_cell(row, column_map, "title")
    title_from_sku = not title
    if title_from_sku:
        title = sku

    price: Optional[float] = None
    unparsed_price = False
    if "price" in column_map and column_map["price"] in row.index:
        raw_price = row[column_map["price"]]
        if not pd.isna(raw_price):
            price_text = str(raw_price).strip()
            if price_text and not is_placeholder_value(price_text):
                price = parse_catalog_price(price_text)
                unparsed_price = price is None

    currency = "USD"
    currency_text = _mapped_cell(row, column_map, "currency")
    if currency_text:
        currency = currency_text.upper()

    return NormalizedCsvRow(
        sku=sku,
        title=title or sku,
        description=_mapped_cell(row, column_map, "description"),
        category=_mapped_cell(row, column_map, "category"),
        brand=_mapped_cell(row, column_map, "brand"),
        price=price,
        currency=currency,
        attributes=_extract_attributes(row, column_map),
        raw_data=_raw_data_from_row(row),
        title_from_sku=title_from_sku,
        unparsed_price=unparsed_price,
    ), None


def _product_update_from_row(
    normalized: NormalizedCsvRow,
    existing: Product,
) -> ProductUpdate:
    """Build a partial update that does not overwrite catalog fields with blanks."""
    updates: dict[str, object] = {}
    if not normalized.title_from_sku:
        updates["title"] = normalized.title
    if normalized.description:
        updates["description"] = normalized.description
    if normalized.category:
        updates["category"] = normalized.category
    if normalized.brand:
        updates["brand"] = normalized.brand
    if normalized.price is not None:
        updates["price"] = normalized.price
    if normalized.attributes:
        merged = dict(existing.attributes or {})
        merged.update(normalized.attributes)
        updates["attributes"] = merged
    return ProductUpdate(**updates)


def process_csv(
    db: Session,
    file_content: bytes,
    filename: str,
    column_mapping: Optional[dict[str, str]] = None,
    ingestion_job_id: Optional[int] = None,
    group_name: Optional[str] = None,
) -> tuple[IngestionJobResponse, list[int]]:
    """Process a CSV file: parse, normalize, detect issues, and store products.

    This is the main entry point for Pipeline 1 (Data Cleanup).

    Args:
        db: Database session.
        file_content: Raw CSV file bytes.
        filename: Original filename for tracking.
        column_mapping: Optional confirmed map of standard fields to CSV columns.
        ingestion_job_id: When set, append products into this existing job/group.
        group_name: Optional merchant-facing group label.

    Returns:
        Tuple of IngestionJobResponse and product IDs processed for AI analysis.
    """
    resolved_group_name = _normalize_group_name(group_name, filename)
    is_append = ingestion_job_id is not None

    if is_append:
        job = get_ingestion_job(db, ingestion_job_id)
        if not job:
            raise IngestionJobError(
                f"Ingestion job {ingestion_job_id} not found",
                status_code=404,
            )
        if job.status not in APPENDABLE_JOB_STATUSES:
            raise IngestionJobError(
                f"Cannot add products to a job with status '{job.status}'. "
                "Choose a completed or analyzing group.",
                status_code=400,
            )
        job.filename = filename
        # Always apply a non-empty group name from the upload form on append
        # so merchants can rename the group while adding more records.
        if group_name is not None and str(group_name).strip():
            job.group_name = _normalize_group_name(group_name, job.group_name or filename)
        elif not (job.group_name or "").strip():
            job.group_name = resolved_group_name
        job.status = "processing"
        job.error_message = None
        job.completed_at = None
        db.commit()
        db.refresh(job)
        logger.info(
            "Appending to ingestion job %s from file: %s",
            job.id,
            filename,
        )
    else:
        job = IngestionJob(
            filename=filename,
            group_name=resolved_group_name,
            status="processing",
            ai_analyzed_rows=0,
            ai_error_count=0,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        logger.info(f"Starting ingestion job {job.id} for file: {filename}")

    product_ids: list[int] = []
    prior_total_rows = job.total_rows or 0
    prior_processed_rows = job.processed_rows or 0
    prior_new_products = job.new_products or 0
    prior_updated_products = job.updated_products or 0

    try:
        parsed = parse_supplier_csv(file_content)
        df = parsed.dataframe
        batch_rows = len(df)
        if is_append:
            job.total_rows = prior_total_rows + batch_rows
        else:
            job.total_rows = batch_rows

        if df.empty:
            job.status = "failed"
            job.error_message = "CSV file is empty or contains only headers."
            job.completed_at = datetime.utcnow()
            db.commit()
            return _job_to_response(job), []

        column_map = _resolve_column_map(df, column_mapping)

        if "sku" not in column_map:
            job.status = "failed"
            job.error_message = (
                "CSV must contain a SKU/product_id column. "
                f"Found columns: {', '.join(df.columns.tolist())}"
            )
            db.commit()
            return _job_to_response(job), []

        logger.info(f"Column mapping: {column_map}")

        new_count = 0
        updated_count = 0
        skip_reasons: Counter[str] = Counter()
        skip_samples: dict[str, list[str]] = {}
        normalized_rows: list[NormalizedCsvRow] = []

        for idx, row in df.iterrows():
            normalized, skip_reason = _normalize_csv_row(row, column_map)
            if skip_reason or normalized is None:
                reason = skip_reason or "invalid_row"
                skip_reasons[reason] += 1
                _record_skip_sample(skip_samples, reason, f"row:{idx}")
                logger.warning("Skipping CSV row %s: %s", idx, skip_reason)
                continue
            if normalized.unparsed_price:
                logger.warning(
                    "SKU %s has an unreadable price; storing product without price",
                    normalized.sku,
                )
            if normalized.title_from_sku:
                logger.info("SKU %s has no title; using SKU as the title", normalized.sku)
            normalized_rows.append(normalized)

        sku_list = list({row.sku for row in normalized_rows})
        existing_by_sku: dict[str, Product] = {}
        if sku_list:
            existing_by_sku = {
                product.sku: product
                for product in db.query(Product).filter(Product.sku.in_(sku_list)).all()
            }

        for normalized in normalized_rows:
            try:
                existing = existing_by_sku.get(normalized.sku)
                if existing:
                    product = update_product(
                        db,
                        existing.id,
                        _product_update_from_row(normalized, existing),
                    ) or existing
                    updated_count += 1
                else:
                    product = create_product(
                        db,
                        ProductCreate(
                            sku=normalized.sku,
                            title=normalized.title,
                            description=normalized.description,
                            category=normalized.category,
                            brand=normalized.brand,
                            price=normalized.price,
                            currency=normalized.currency,
                            attributes=normalized.attributes,
                        ),
                    )
                    new_count += 1

                product.raw_data = normalized.raw_data
                product.last_ingestion_job_id = job.id
                _link_product_to_job(db, job.id, product.id)
                existing_by_sku[normalized.sku] = product
                db.commit()

                _run_quality_checks(
                    db,
                    product,
                    dict(product.attributes or {}),
                    price_unreadable=normalized.unparsed_price,
                    ingestion_job_id=job.id,
                )
                product_ids.append(product.id)
            except Exception as e:
                logger.warning(
                    "Error processing SKU %s: %s",
                    normalized.sku,
                    str(e),
                )
                skip_reasons["row_error"] += 1
                _record_skip_sample(skip_samples, "row_error", normalized.sku)
                continue

        if is_append:
            job.processed_rows = prior_processed_rows + batch_rows
        else:
            job.processed_rows = batch_rows
        skipped_count = sum(skip_reasons.values())
        _merge_skip_summary(job, skip_reasons, skip_samples, append=is_append)

        if not product_ids:
            reason_text = ", ".join(
                f"{reason} ({count})" for reason, count in skip_reasons.items()
            ) or "no valid product rows"
            job.status = "failed"
            job.error_message = f"No products were created or updated: {reason_text}."
            if not is_append:
                job.new_products = 0
                job.updated_products = 0
                job.issues_found = 0
            job.completed_at = datetime.utcnow()
            db.commit()
            logger.warning("Ingestion job %s produced no products: %s", job.id, reason_text)
            return _job_to_response(job), []

        if skipped_count:
            logger.info(
                "Ingestion job %s skipped %s of %s rows: %s",
                job.id,
                skipped_count,
                batch_rows,
                dict(skip_reasons),
            )

        if is_append:
            job.new_products = prior_new_products + new_count
            job.updated_products = prior_updated_products + updated_count
            linked_ids = [
                row.product_id
                for row in db.query(IngestionJobProduct.product_id)
                .filter(IngestionJobProduct.ingestion_job_id == job.id)
                .all()
            ]
            job.issues_found = _count_open_issues_for_products(db, linked_ids)
        else:
            job.new_products = new_count
            job.updated_products = updated_count
            job.issues_found = _count_open_issues_for_products(db, product_ids)

        job.status = "analyzing"
        job.completed_at = None
        db.query(Product).filter(Product.id.in_(product_ids)).update(
            {Product.ai_analysis_status: AiAnalysisStatus.PENDING.value},
            synchronize_session=False,
        )
        db.commit()

        logger.info(
            f"Ingestion job {job.id} parsed: "
            f"{new_count} new, {updated_count} updated, {job.issues_found} issues, "
            f"status={job.status}"
        )

    except (pd.errors.ParserError, CsvParseError) as e:
        job.status = "failed"
        job.error_message = (
            str(e) if isinstance(e, CsvParseError) else f"Failed to parse CSV: {str(e)}"
        )
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.error(f"CSV parse error for job {job.id}: {str(e)}")

    except Exception as e:
        job.status = "failed"
        job.error_message = f"Unexpected error: {str(e)}"
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.error(f"Ingestion job {job.id} failed: {str(e)}")

    return _job_to_response(job), product_ids if job.status == "analyzing" else []


def _issue_dedup_key(
    issue_type: IssueType,
    field_name: Optional[str],
) -> tuple[str, str]:
    """Build a stable key for deduplicating unresolved quality issues."""
    return (
        issue_type.value,
        (field_name or "").strip().lower(),
    )


def _collect_pending_issues(
    db: Session,
    product: Product,
    attributes: dict[str, str],
    price_unreadable: bool = False,
    ingestion_job_id: Optional[int] = None,
) -> list[_PendingIssue]:
    """Evaluate hard structural quality rules for a product.

    Soft judgment (contradictions, thin content, missing attributes, omissions)
    is handled by the ingest AI path, not rules.

    Duplicate titles are checked only within the same upload file (ingestion job).
    """
    _ = attributes
    pending: list[_PendingIssue] = []
    description_text = (
        None
        if is_placeholder_value(product.description)
        else product.description
    )

    if not description_text:
        pending.append(_PendingIssue(
            issue_type=IssueType.MISSING_DESCRIPTION,
            severity=IssueSeverity.HIGH,
            description=(
                f"Product '{product.sku}' has no description. "
                "SEO content generation recommended."
            ),
            field_name="description",
        ))

    job_id = ingestion_job_id or product.last_ingestion_job_id
    duplicate = None
    if job_id is not None:
        duplicate = (
            db.query(Product)
            .join(
                IngestionJobProduct,
                IngestionJobProduct.product_id == Product.id,
            )
            .filter(
                IngestionJobProduct.ingestion_job_id == job_id,
                Product.id != product.id,
                func.lower(Product.title) == (product.title or "").strip().lower(),
            )
            .first()
        )
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

    if product.price is None:
        if price_unreadable:
            pending.append(_PendingIssue(
                issue_type=IssueType.PRICE_ANOMALY,
                severity=IssueSeverity.MEDIUM,
                description=(
                    f"Product '{product.sku}' has an unreadable price "
                    "and was stored without a price."
                ),
                field_name="price",
            ))
        else:
            pending.append(_PendingIssue(
                issue_type=IssueType.PRICE_ANOMALY,
                severity=IssueSeverity.MEDIUM,
                description=f"Product '{product.sku}' is missing a price.",
                field_name="price",
            ))
    elif product.price <= 0:
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
    """Create, update, or resolve quality issues without duplicating open records.

    Returns newly created DataIssue rows only.
    """
    existing_issues = db.query(DataIssue).filter(
        DataIssue.product_id == product.id,
        DataIssue.resolved == False,
    ).all()

    pending_map = {
        _issue_dedup_key(issue.issue_type, issue.field_name): issue
        for issue in pending_issues
    }
    existing_map: dict[tuple[str, str], DataIssue] = {}
    for issue in existing_issues:
        key = _issue_dedup_key(issue.issue_type, issue.field_name)
        if key in existing_map:
            issue.resolved = True
            issue.resolved_at = datetime.utcnow()
            continue
        existing_map[key] = issue

    created_issues: list[DataIssue] = []

    for key, pending_issue in pending_map.items():
        if key in existing_map:
            issue = existing_map[key]
            issue.severity = pending_issue.severity
            issue.description = pending_issue.description
            issue.expected_value = pending_issue.expected_value
            issue.actual_value = pending_issue.actual_value
            issue.suggestion_source = SuggestionSource.RULE.value
            continue

        issue = DataIssue(
            product_id=product.id,
            issue_type=pending_issue.issue_type,
            severity=pending_issue.severity,
            description=pending_issue.description,
            field_name=pending_issue.field_name,
            expected_value=pending_issue.expected_value,
            actual_value=pending_issue.actual_value,
            suggestion_source=SuggestionSource.RULE.value,
            review_status=ReviewStatus.PENDING.value,
        )
        db.add(issue)
        created_issues.append(issue)

    for key, issue in existing_map.items():
        if key not in pending_map:
            if (issue.suggestion_source or "") == SuggestionSource.AI.value:
                continue
            issue.resolved = True
            issue.resolved_at = datetime.utcnow()

    preserved_ai_count = sum(
        1
        for issue in existing_issues
        if not issue.resolved
        and (issue.suggestion_source or "") == SuggestionSource.AI.value
        and _issue_dedup_key(issue.issue_type, issue.field_name) not in pending_map
    )
    open_issue_count = len(pending_map) + preserved_ai_count
    if product.status != ProductStatus.ARCHIVED:
        product.status = ProductStatus.FLAGGED if open_issue_count > 0 else ProductStatus.ACTIVE
    db.commit()
    return created_issues


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


def _count_open_issues_for_products(db: Session, product_ids: list[int]) -> int:
    """Count unresolved quality issues for the given products."""
    if not product_ids:
        return 0
    return (
        db.query(DataIssue)
        .filter(
            DataIssue.product_id.in_(product_ids),
            DataIssue.resolved == False,  # noqa: E712
        )
        .count()
    )


def _run_quality_checks(
    db: Session,
    product: Product,
    attributes: dict[str, str],
    price_unreadable: bool = False,
    ingestion_job_id: Optional[int] = None,
) -> list[DataIssue]:
    """Run data quality checks on a product and sync issue records.

    Args:
        db: Database session.
        product: Product to check.
        attributes: Normalized product attributes.
        price_unreadable: True when the CSV price could not be parsed.
        ingestion_job_id: Upload job to scope same-file duplicate checks.

    Returns:
        Newly created DataIssue records for this run.
    """
    pending_issues = _collect_pending_issues(
        db,
        product,
        attributes,
        price_unreadable=price_unreadable,
        ingestion_job_id=ingestion_job_id,
    )
    return _sync_quality_issues(db, product, pending_issues)


def _link_product_to_job(db: Session, job_id: int, product_id: int) -> None:
    """Remember that this product belongs to the uploaded CSV job."""
    existing = (
        db.query(IngestionJobProduct)
        .filter(
            IngestionJobProduct.ingestion_job_id == job_id,
            IngestionJobProduct.product_id == product_id,
        )
        .first()
    )
    if existing:
        return
    db.add(
        IngestionJobProduct(
            ingestion_job_id=job_id,
            product_id=product_id,
        )
    )


def get_ingestion_job(db: Session, job_id: int) -> Optional[IngestionJob]:
    """Return one ingestion job by ID, or None if it does not exist."""
    return db.query(IngestionJob).filter(IngestionJob.id == job_id).first()


def update_ingestion_job_group_name(
    db: Session,
    job_id: int,
    group_name: str,
) -> Optional[IngestionJob]:
    """Rename the merchant-facing group label for an ingestion job."""
    cleaned = (group_name or "").strip()
    if not cleaned:
        raise IngestionJobError("Group name cannot be empty.", status_code=400)
    if len(cleaned) > GROUP_NAME_MAX_LENGTH:
        raise IngestionJobError(
            f"Group name must be at most {GROUP_NAME_MAX_LENGTH} characters.",
            status_code=400,
        )

    job = get_ingestion_job(db, job_id)
    if not job:
        return None
    job.group_name = cleaned
    db.commit()
    db.refresh(job)
    return job


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
        query = query.filter(
            or_(
                IngestionJob.filename.ilike(search_term),
                IngestionJob.group_name.ilike(search_term),
            )
        )

    total = query.count()
    sort_column = INGESTION_JOB_SORT_COLUMNS.get(sort_by, IngestionJob.started_at)
    if sort_order == SortOrder.ASC:
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    jobs = query.offset(skip).limit(limit).all()
    return jobs, total


def delete_ingestion_job(db: Session, job_id: int) -> Optional[dict[str, int]]:
    """Delete an uploaded file along with the products it created.

    Products that already existed before this upload are kept; they only lose
    their link to this job and its rewrite suggestions.

    Args:
        db: Database session.
        job_id: Ingestion job primary key.

    Returns:
        Counts of deleted and unlinked products, or None if the job is missing.
    """
    job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
    if not job:
        return None

    linked_product_ids = [
        row[0]
        for row in db.query(IngestionJobProduct.product_id)
        .filter(IngestionJobProduct.ingestion_job_id == job_id)
        .all()
    ]

    deleted_products = 0
    if linked_product_ids:
        # A product belongs to this upload only when this job was the first to
        # link it; later uploads matched the same SKU and only updated it.
        first_job_by_product = dict(
            db.query(
                IngestionJobProduct.product_id,
                func.min(IngestionJobProduct.ingestion_job_id),
            )
            .filter(IngestionJobProduct.product_id.in_(linked_product_ids))
            .group_by(IngestionJobProduct.product_id)
            .all()
        )
        created_ids = [
            product_id
            for product_id, first_job_id in first_job_by_product.items()
            if first_job_id == job_id
        ]
        if created_ids:
            for product in db.query(Product).filter(Product.id.in_(created_ids)).all():
                if job.started_at and product.created_at and product.created_at < job.started_at:
                    # Added outside ingestion before this run — keep it.
                    continue
                db.delete(product)
                deleted_products += 1

    db.query(Product).filter(Product.last_ingestion_job_id == job_id).update(
        {Product.last_ingestion_job_id: None}, synchronize_session=False
    )

    filename = job.filename
    db.delete(job)
    db.commit()

    unlinked_products = len(linked_product_ids) - deleted_products
    logger.info(
        "Deleted ingestion job %s (%s): %s products deleted, %s unlinked",
        job_id,
        filename,
        deleted_products,
        unlinked_products,
    )
    return {
        "deleted_products": deleted_products,
        "unlinked_products": unlinked_products,
    }


def get_data_issues(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    resolved: bool = False,
    search: Optional[str] = None,
    severity: Optional[IssueSeverity] = None,
    issue_type: Optional[IssueType] = None,
    ingestion_job_id: Optional[int] = None,
    sort_by: DataIssueSortField = DataIssueSortField.CREATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
) -> tuple[list[DataIssue], int]:
    """Retrieve data quality issues with filtering, sorting, and pagination."""
    query = db.query(DataIssue).join(Product).filter(DataIssue.resolved == resolved)

    if ingestion_job_id is not None:
        query = query.join(
            IngestionJobProduct,
            IngestionJobProduct.product_id == DataIssue.product_id,
        ).filter(IngestionJobProduct.ingestion_job_id == ingestion_job_id)
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


PRODUCT_REWRITE_FIELDS = frozenset({"title", "description", "category", "brand", "price"})
ATTRIBUTE_FIELD_PREFIX = "attributes."
LEGACY_ATTRIBUTE_FIELDS = frozenset({"color", "size", "material", "weight", "upc"})


def _matching_field_names(field_name: Optional[str]) -> set[str]:
    """Return equivalent rewrite/issue field names for one catalog field."""
    name = (field_name or "").strip()
    if not name:
        return set()
    names = {name}
    if name.startswith(ATTRIBUTE_FIELD_PREFIX):
        attr_key = name[len(ATTRIBUTE_FIELD_PREFIX):].strip()
        if attr_key:
            names.add(attr_key)
    elif name in LEGACY_ATTRIBUTE_FIELDS:
        names.add(f"{ATTRIBUTE_FIELD_PREFIX}{name}")
    return names


def _resolve_open_issues_for_field(
    db: Session,
    product_id: int,
    field_name: Optional[str],
    review_status: str,
    resolved_at: datetime,
) -> None:
    """Mark open quality issues on the same product field as resolved."""
    aliases = _matching_field_names(field_name)
    if not aliases:
        return
    issues = db.query(DataIssue).filter(
        DataIssue.product_id == product_id,
        DataIssue.resolved == False,  # noqa: E712
        DataIssue.field_name.in_(aliases),
    ).all()
    for issue in issues:
        issue.resolved = True
        issue.resolved_at = resolved_at
        issue.review_status = review_status


def _apply_field_value(product: Product, field_name: str, value: Optional[str]) -> None:
    """Write a reviewed value onto a product column or attribute.

    Args:
        product: Product to update.
        field_name: Product column or attributes.<key>. SKU is not allowed.
        value: Value to store.

    Raises:
        ValueError: If the field cannot be rewritten or the value is invalid.
    """
    normalized_name = (field_name or "").strip()
    if not normalized_name:
        raise ValueError("Field name is required.")
    if normalized_name.lower() == "sku":
        raise ValueError("SKU cannot be rewritten.")

    if normalized_name in PRODUCT_REWRITE_FIELDS:
        if normalized_name == "title":
            cleaned = (value or "").strip()
            if not cleaned:
                raise ValueError("Title cannot be empty.")
            product.title = cleaned
            return
        if normalized_name == "price":
            if value is None or str(value).strip() == "":
                product.price = None
                return
            try:
                product.price = float(str(value).strip())
            except ValueError as exc:
                raise ValueError("Price must be a number.") from exc
            return
        setattr(product, normalized_name, None if value is None else str(value).strip() or None)
        return

    if (
        normalized_name.startswith(ATTRIBUTE_FIELD_PREFIX)
        or normalized_name in LEGACY_ATTRIBUTE_FIELDS
    ):
        attr_key = (
            normalized_name[len(ATTRIBUTE_FIELD_PREFIX):].strip()
            if normalized_name.startswith(ATTRIBUTE_FIELD_PREFIX)
            else normalized_name
        )
        if not attr_key:
            raise ValueError("Attribute field name is required.")
        attributes = dict(product.attributes or {})
        if value is None or str(value).strip() == "":
            attributes.pop(attr_key, None)
        else:
            attributes[attr_key] = str(value).strip()
        product.attributes = attributes
        return

    raise ValueError(f"Unknown field '{field_name}'.")


def accept_issues_bulk(
    db: Session,
    issue_ids: Optional[list[int]] = None,
    product_ids: Optional[list[int]] = None,
) -> tuple[int, int, list[int]]:
    """Accept pending quality issues by issue ID or product ID.

    Skips issues that are already resolved or lack field_name/suggested_value.

    Returns:
        Tuple of accepted count, skipped count, and unique product IDs touched.
    """
    has_issues = bool(issue_ids)
    has_products = bool(product_ids)
    if has_issues == has_products:
        raise ValueError("Provide either issue_ids or product_ids, not both.")

    accepted = 0
    skipped = 0
    touched_products: set[int] = set()

    if issue_ids:
        for issue_id in issue_ids:
            issue = db.query(DataIssue).filter(DataIssue.id == issue_id).first()
            if (
                issue is None
                or issue.resolved
                or issue.review_status != ReviewStatus.PENDING.value
                or not issue.field_name
                or issue.suggested_value is None
            ):
                skipped += 1
                continue
            try:
                review_data_issue(db, issue_id, ReviewAction.ACCEPT)
                accepted += 1
                touched_products.add(issue.product_id)
            except ValueError:
                skipped += 1
        return accepted, skipped, sorted(touched_products)

    pending = (
        db.query(DataIssue)
        .filter(
            DataIssue.product_id.in_(product_ids or []),
            DataIssue.resolved == False,  # noqa: E712
            DataIssue.review_status == ReviewStatus.PENDING.value,
            DataIssue.field_name.isnot(None),
            DataIssue.suggested_value.isnot(None),
        )
        .order_by(DataIssue.id.asc())
        .all()
    )
    if not pending:
        return 0, 0, []

    for issue in pending:
        try:
            review_data_issue(db, issue.id, ReviewAction.ACCEPT)
            accepted += 1
            touched_products.add(issue.product_id)
        except ValueError:
            skipped += 1

    return accepted, skipped, sorted(touched_products)


def review_data_issue(
    db: Session,
    issue_id: int,
    action: ReviewAction,
    edited_value: Optional[str] = None,
) -> DataIssue:
    """Accept, edit, or reject a quality issue without auto-applying on reject."""
    issue = db.query(DataIssue).filter(DataIssue.id == issue_id).first()
    if not issue:
        raise LookupError(f"Issue {issue_id} not found")
    if issue.resolved:
        raise ValueError(f"Issue {issue_id} is already resolved.")

    product = db.query(Product).filter(Product.id == issue.product_id).first()
    if not product:
        raise LookupError(f"Product {issue.product_id} not found")

    now = datetime.utcnow()
    if action == ReviewAction.REJECT:
        issue.review_status = ReviewStatus.REJECTED.value
        issue.resolved = True
        issue.resolved_at = now
        db.commit()
        refresh_product_status(db, product.id)
        db.refresh(issue)
        return issue

    if action == ReviewAction.EDIT:
        if edited_value is None:
            raise ValueError("edited_value is required when action is edit.")
        if not issue.field_name:
            raise ValueError("Issue has no field_name to apply an edited value.")
        _apply_field_value(product, issue.field_name, edited_value)
        issue.review_status = ReviewStatus.EDITED.value
    elif action == ReviewAction.ACCEPT:
        if issue.suggested_value is None:
            raise ValueError("Issue has no suggested_value to accept.")
        if not issue.field_name:
            raise ValueError("Issue has no field_name to apply the suggested value.")
        _apply_field_value(product, issue.field_name, issue.suggested_value)
        issue.review_status = ReviewStatus.ACCEPTED.value
    else:
        raise ValueError(f"Unsupported review action '{action}'.")

    issue.resolved = True
    issue.resolved_at = now
    _resolve_open_issues_for_field(
        db,
        product.id,
        issue.field_name,
        issue.review_status,
        now,
    )
    db.commit()
    refresh_product_status(db, product.id)
    db.refresh(issue)
    return issue


def _parse_skip_summary(raw: Optional[str]) -> Optional[dict[str, object]]:
    """Parse stored skip_summary JSON into a response dict."""
    if not raw or not str(raw).strip():
        return None
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    return parsed


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
        group_name=job.group_name or job.filename,
        total_rows=job.total_rows or 0,
        processed_rows=job.processed_rows or 0,
        new_products=job.new_products or 0,
        updated_products=job.updated_products or 0,
        issues_found=job.issues_found or 0,
        skipped_rows=job.skipped_rows or 0,
        skip_summary=_parse_skip_summary(job.skip_summary),
        ai_analyzed_rows=job.ai_analyzed_rows or 0,
        ai_error_count=job.ai_error_count or 0,
        status=job.status or "unknown",
        error_message=job.error_message,
        started_at=job.started_at,
        completed_at=job.completed_at,
    )
