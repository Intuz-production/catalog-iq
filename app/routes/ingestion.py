"""
CatalogIQ — CSV Ingestion API Routes

Endpoints for uploading CSV supplier feeds and managing ingestion jobs.
"""

import json
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, UploadFile, File, Form, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    IngestionJobResponse, IngestionJobListResponse, IngestionPreviewResponse,
    IngestionJobUpdate,
    DataIssue, DataIssueResponse, DataIssueListResponse,
    IssueType, IssueSeverity,
    IngestionJobSortField, DataIssueSortField, SortOrder,
    ReviewRequest, ReviewResultResponse,
    BulkAcceptIssuesRequest, BulkAcceptIssuesResponse,
    ReviewStatus,
)
from app.services import ingestion_service
from app.services.ingestion_ai_service import run_ingestion_ai_job
from app.services.ingestion_service import CsvParseError, IngestionJobError

logger = logging.getLogger("catalogiq.routes.ingestion")

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])

MAX_CSV_BYTES = 10 * 1024 * 1024
SAMPLE_CSV_PATH = Path(__file__).resolve().parents[2] / "data" / "sample_products.csv"


async def _read_csv_upload(file: UploadFile) -> tuple[bytes, str]:
    """Validate and read an uploaded CSV file."""
    filename = file.filename or ""
    if not filename or not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV file (.csv extension)."
        )

    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    if len(content) > MAX_CSV_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {MAX_CSV_BYTES // (1024 * 1024)} MB."
        )

    return content, filename


def _parse_column_mapping(raw_mapping: Optional[str]) -> Optional[dict[str, str]]:
    """Parse confirmed column mapping JSON from the upload form."""
    if raw_mapping is None or not raw_mapping.strip():
        return None
    try:
        parsed = json.loads(raw_mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="column_mapping must be valid JSON.") from exc
    if not isinstance(parsed, dict):
        raise HTTPException(status_code=400, detail="column_mapping must be a JSON object.")
    mapping: dict[str, str] = {}
    for key, value in parsed.items():
        if value is None:
            continue
        mapping[str(key)] = str(value)
    return mapping


@router.get("/sample-csv")
def download_sample_csv() -> FileResponse:
    """Download the bundled sample product CSV for demo and AI testing."""
    if not SAMPLE_CSV_PATH.is_file():
        raise HTTPException(
            status_code=404,
            detail="Sample CSV file is not available on the server.",
        )
    return FileResponse(
        path=SAMPLE_CSV_PATH,
        media_type="text/csv; charset=utf-8",
        filename="sample_products.csv",
    )


@router.post("/preview", response_model=IngestionPreviewResponse)
async def preview_csv(
    file: UploadFile = File(..., description="CSV file with product data"),
) -> IngestionPreviewResponse:
    """Parse a CSV and return columns, suggested mapping, and sample rows."""
    content, filename = await _read_csv_upload(file)
    logger.info(f"Previewing CSV upload: {filename} ({len(content)} bytes)")
    try:
        return ingestion_service.preview_csv(content, filename)
    except CsvParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/upload", response_model=IngestionJobResponse)
async def upload_csv(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="CSV file with product data"),
    column_mapping: Optional[str] = Form(
        None,
        description="JSON object mapping standard fields to CSV column names",
    ),
    ingestion_job_id: Optional[int] = Form(
        None,
        description="Existing job ID to append products into (same group)",
    ),
    group_name: Optional[str] = Form(
        None,
        description="Merchant-facing group name for new or existing job",
    ),
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    """Upload and process a CSV supplier feed.

    Accepts a CSV file, normalizes product data, detects quality issues,
    and stores structured products in the database. Pass ingestion_job_id
    to append into an existing group.
    """
    content, filename = await _read_csv_upload(file)
    mapping = _parse_column_mapping(column_mapping)

    logger.info(f"Received CSV upload: {filename} ({len(content)} bytes)")

    try:
        result, product_ids = ingestion_service.process_csv(
            db,
            content,
            filename,
            column_mapping=mapping,
            ingestion_job_id=ingestion_job_id,
            group_name=group_name,
        )
    except IngestionJobError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc

    if result.status == "analyzing" and product_ids:
        background_tasks.add_task(run_ingestion_ai_job, result.id, product_ids)
    return result


@router.get("/jobs", response_model=IngestionJobListResponse)
def list_ingestion_jobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(15, ge=1, le=200, description="Max records to return"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    search: Optional[str] = Query(None, description="Search by group name or filename"),
    sort_by: IngestionJobSortField = Query(
        IngestionJobSortField.STARTED_AT, description="Column to sort by"
    ),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort direction"),
    db: Session = Depends(get_db),
) -> IngestionJobListResponse:
    """List ingestion job history with filtering, sorting, and pagination."""
    jobs, total = ingestion_service.get_ingestion_jobs(
        db,
        skip=skip,
        limit=limit,
        status=status,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return IngestionJobListResponse(
        items=[IngestionJobResponse.model_validate(job) for job in jobs],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
def get_ingestion_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    """Get one uploaded file / ingestion job by ID."""
    job = ingestion_service.get_ingestion_job(db, job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job {job_id} not found")
    return IngestionJobResponse.model_validate(job)


@router.patch("/jobs/{job_id}", response_model=IngestionJobResponse)
def rename_ingestion_job(
    job_id: int,
    body: IngestionJobUpdate,
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    """Rename the merchant-facing group name for an ingestion job."""
    try:
        job = ingestion_service.update_ingestion_job_group_name(
            db, job_id, body.group_name
        )
    except IngestionJobError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.message) from exc
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job {job_id} not found")
    return IngestionJobResponse.model_validate(job)


@router.delete("/jobs/{job_id}")
def delete_ingestion_job(
    job_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Delete an uploaded file and the products it created."""
    result = ingestion_service.delete_ingestion_job(db, job_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Ingestion job {job_id} not found")
    return {
        "message": f"Uploaded file {job_id} deleted.",
        **result,
    }


@router.get("/issues", response_model=DataIssueListResponse)
def list_all_issues(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    resolved: bool = Query(False, description="Filter by resolved status"),
    search: Optional[str] = Query(None, description="Search in description, field, SKU, or title"),
    severity: Optional[IssueSeverity] = Query(None, description="Filter by severity"),
    issue_type: Optional[IssueType] = Query(None, description="Filter by issue type"),
    ingestion_job_id: Optional[int] = Query(
        None, description="Limit issues to products from one uploaded file"
    ),
    sort_by: DataIssueSortField = Query(
        DataIssueSortField.CREATED_AT, description="Column to sort by"
    ),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort direction"),
    db: Session = Depends(get_db),
) -> DataIssueListResponse:
    """List data quality issues with filtering, sorting, and pagination."""
    issues, total = ingestion_service.get_data_issues(
        db,
        skip=skip,
        limit=limit,
        resolved=resolved,
        search=search,
        severity=severity,
        issue_type=issue_type,
        ingestion_job_id=ingestion_job_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return DataIssueListResponse(
        items=[DataIssueResponse.model_validate(i) for i in issues],
        total=total,
        skip=skip,
        limit=limit,
    )


@router.put("/issues/{issue_id}/resolve")
def resolve_issue(
    issue_id: int,
    db: Session = Depends(get_db),
) -> dict:
    """Mark a data quality issue as resolved."""
    from datetime import datetime

    issue = db.query(DataIssue).filter(DataIssue.id == issue_id).first()
    if not issue:
        raise HTTPException(status_code=404, detail=f"Issue {issue_id} not found")

    issue.resolved = True
    issue.resolved_at = datetime.utcnow()
    issue.review_status = ReviewStatus.REJECTED.value
    db.commit()

    new_status = ingestion_service.refresh_product_status(db, issue.product_id)

    return {
        "message": f"Issue {issue_id} marked as resolved.",
        "product_id": issue.product_id,
        "product_status": new_status.value if new_status else None,
    }


def _http_review_error(exc: Exception) -> HTTPException:
    """Map review service errors to HTTP responses."""
    if isinstance(exc, LookupError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        return HTTPException(status_code=400, detail=str(exc))
    raise exc


@router.post("/issues/accept-bulk", response_model=BulkAcceptIssuesResponse)
def accept_issues_bulk(
    payload: BulkAcceptIssuesRequest,
    db: Session = Depends(get_db),
) -> BulkAcceptIssuesResponse:
    """Accept pending quality issues for issue IDs or product IDs."""
    try:
        accepted, skipped, product_ids = ingestion_service.accept_issues_bulk(
            db,
            issue_ids=payload.issue_ids,
            product_ids=payload.product_ids,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return BulkAcceptIssuesResponse(
        accepted=accepted,
        skipped=skipped,
        product_ids=product_ids,
    )


@router.put("/issues/{issue_id}/review", response_model=ReviewResultResponse)
def review_issue(
    issue_id: int,
    payload: ReviewRequest,
    db: Session = Depends(get_db),
) -> ReviewResultResponse:
    """Accept, edit, or reject a quality issue. Reject does not change product fields."""
    try:
        issue = ingestion_service.review_data_issue(
            db,
            issue_id,
            payload.action,
            edited_value=payload.edited_value,
        )
    except (LookupError, ValueError) as exc:
        raise _http_review_error(exc) from exc

    product_status = ingestion_service.refresh_product_status(db, issue.product_id)
    return ReviewResultResponse(
        id=issue.id,
        product_id=issue.product_id,
        review_status=ReviewStatus(issue.review_status or ReviewStatus.PENDING.value),
        product_status=product_status,
        message=f"Issue {issue_id} marked as {issue.review_status}.",
    )
