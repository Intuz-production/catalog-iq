"""
CatalogIQ — CSV Ingestion API Routes

Endpoints for uploading CSV supplier feeds and managing ingestion jobs.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    IngestionJobResponse, IngestionJobListResponse,
    DataIssue, DataIssueResponse, DataIssueListResponse,
    IssueType, IssueSeverity,
    IngestionJobSortField, DataIssueSortField, SortOrder,
)
from app.services import ingestion_service

logger = logging.getLogger("catalogiq.routes.ingestion")

router = APIRouter(prefix="/api/ingestion", tags=["Ingestion"])


@router.post("/upload", response_model=IngestionJobResponse)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file with product data"),
    db: Session = Depends(get_db),
) -> IngestionJobResponse:
    """Upload and process a CSV supplier feed.

    Accepts a CSV file, normalizes product data, detects quality issues,
    and stores structured products in the database.
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=400,
            detail="File must be a CSV file (.csv extension)."
        )

    # Read file content
    content = await file.read()
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Limit file size (10 MB)
    max_size = 10 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Maximum size is {max_size // (1024 * 1024)} MB."
        )

    logger.info(f"Received CSV upload: {file.filename} ({len(content)} bytes)")

    result = ingestion_service.process_csv(db, content, file.filename)
    return result


@router.get("/jobs", response_model=IngestionJobListResponse)
def list_ingestion_jobs(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(15, ge=1, le=200, description="Max records to return"),
    status: Optional[str] = Query(None, description="Filter by job status"),
    search: Optional[str] = Query(None, description="Search by filename"),
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


@router.get("/issues", response_model=DataIssueListResponse)
def list_all_issues(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    resolved: bool = Query(False, description="Filter by resolved status"),
    search: Optional[str] = Query(None, description="Search in description, field, SKU, or title"),
    severity: Optional[IssueSeverity] = Query(None, description="Filter by severity"),
    issue_type: Optional[IssueType] = Query(None, description="Filter by issue type"),
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
    db.commit()

    new_status = ingestion_service.refresh_product_status(db, issue.product_id)

    return {
        "message": f"Issue {issue_id} marked as resolved.",
        "product_id": issue.product_id,
        "product_status": new_status.value if new_status else None,
    }
