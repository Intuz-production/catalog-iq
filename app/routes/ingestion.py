"""
CatalogIQ — CSV Ingestion API Routes

Endpoints for uploading CSV supplier feeds and managing ingestion jobs.
"""

import logging
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import IngestionJobResponse, DataIssueResponse, DataIssue
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


@router.get("/jobs", response_model=list[IngestionJobResponse])
def list_ingestion_jobs(
    limit: int = 20,
    db: Session = Depends(get_db),
) -> list[IngestionJobResponse]:
    """List recent ingestion job history."""
    jobs = ingestion_service.get_ingestion_jobs(db, limit=limit)
    return [
        IngestionJobResponse.model_validate(job)
        for job in jobs
    ]


@router.get("/issues", response_model=list[DataIssueResponse])
def list_all_issues(
    resolved: bool = False,
    limit: int = 100,
    db: Session = Depends(get_db),
) -> list[DataIssueResponse]:
    """List all data quality issues across products."""
    query = db.query(DataIssue).filter(DataIssue.resolved == resolved)
    issues = query.order_by(DataIssue.created_at.desc()).limit(limit).all()
    return [DataIssueResponse.model_validate(i) for i in issues]


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

    return {"message": f"Issue {issue_id} marked as resolved."}
