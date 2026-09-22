"""
CatalogIQ — Product Management API Routes

CRUD endpoints for managing the product catalog.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    ProductStatus, ProductSortField, SortOrder,
    ProductCreate, ProductUpdate,
    ProductResponse, ProductListResponse, DataIssueResponse, DashboardStats,
    AiThoughtRequest, AiThoughtResponse, AiThoughtChange,
)
from app.services import product_service, ingestion_service
from app.services import woocommerce_export_service
from app.services.ingestion_ai_service import run_thought_rewrite

logger = logging.getLogger("catalogiq.routes.products")

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("/", response_model=ProductListResponse)
def list_products(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title, SKU, brand"),
    category: Optional[str] = Query(None, description="Filter by category"),
    ingestion_job_id: Optional[int] = Query(
        None, description="Limit results to products from one uploaded file"
    ),
    sort_by: ProductSortField = Query(
        ProductSortField.UPDATED_AT, description="Column to sort by"
    ),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort direction"),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    """List products with optional filtering, sorting, and pagination."""
    if ingestion_job_id is not None:
        job = ingestion_service.get_ingestion_job(db, ingestion_job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Ingestion job {ingestion_job_id} not found",
            )
    products, total = product_service.get_products(
        db,
        skip=skip,
        limit=limit,
        status=status,
        search=search,
        category=category,
        ingestion_job_id=ingestion_job_id,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    results = []
    for p in products:
        resp = ProductResponse.model_validate(p)
        resp.issue_count = len([i for i in p.issues if not i.resolved])
        results.append(resp)
    return ProductListResponse(items=results, total=total, skip=skip, limit=limit)


@router.get("/categories", response_model=list[str])
def list_categories(
    ingestion_job_id: Optional[int] = Query(None, description="Limit to job"),
    db: Session = Depends(get_db),
) -> list[str]:
    """Get all distinct product categories."""
    return product_service.get_categories(db, ingestion_job_id=ingestion_job_id)


@router.get("/statuses", response_model=list[str])
def list_statuses(
    ingestion_job_id: Optional[int] = Query(None, description="Limit to job"),
    db: Session = Depends(get_db),
) -> list[str]:
    """Get all distinct product statuses that actually exist in the database."""
    return product_service.get_statuses(db, ingestion_job_id=ingestion_job_id)


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)) -> DashboardStats:
    """Get dashboard overview statistics."""
    return product_service.get_dashboard_stats(db)


@router.get("/export/woocommerce")
def export_woocommerce_csv(
    status: Optional[str] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title, SKU, brand"),
    category: Optional[str] = Query(None, description="Filter by category"),
    ingestion_job_id: Optional[int] = Query(
        None, description="Limit export to products from one uploaded file"
    ),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    """Download a WooCommerce Product CSV for the current product filters."""
    if ingestion_job_id is not None:
        job = ingestion_service.get_ingestion_job(db, ingestion_job_id)
        if not job:
            raise HTTPException(
                status_code=404,
                detail=f"Ingestion job {ingestion_job_id} not found",
            )
    products = product_service.list_products_for_export(
        db,
        status=status,
        search=search,
        category=category,
        ingestion_job_id=ingestion_job_id,
    )
    csv_text = woocommerce_export_service.build_woocommerce_csv(products)
    return StreamingResponse(
        iter([csv_text.encode("utf-8-sig")]),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="catalogiq-woocommerce.csv"',
        },
    )


@router.get("/{product_id}", response_model=ProductResponse)
def get_product(
    product_id: int,
    db: Session = Depends(get_db),
) -> ProductResponse:
    """Get a single product by ID."""
    product = product_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    resp = ProductResponse.model_validate(product)
    resp.issue_count = len([i for i in product.issues if not i.resolved])
    return resp


@router.post("/", response_model=ProductResponse, status_code=201)
def create_product(
    product_data: ProductCreate,
    db: Session = Depends(get_db),
) -> ProductResponse:
    """Create a new product."""
    existing = product_service.get_product_by_sku(db, product_data.sku)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Product with SKU '{product_data.sku}' already exists"
        )
    product = product_service.create_product(db, product_data)
    return ProductResponse.model_validate(product)


@router.put("/{product_id}", response_model=ProductResponse)
def update_product(
    product_id: int,
    updates: ProductUpdate,
    db: Session = Depends(get_db),
) -> ProductResponse:
    """Update an existing product and re-run data quality checks."""
    product = product_service.update_product(db, product_id, updates)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    product = ingestion_service.finalize_product_edit(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    resp = ProductResponse.model_validate(product)
    resp.issue_count = len([i for i in product.issues if not i.resolved])
    return resp


@router.delete("/{product_id}", status_code=204)
def delete_product(
    product_id: int,
    db: Session = Depends(get_db),
) -> None:
    """Delete a product by ID."""
    if not product_service.delete_product(db, product_id):
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")


@router.get("/{product_id}/issues", response_model=list[DataIssueResponse])
def get_product_issues(
    product_id: int,
    db: Session = Depends(get_db),
) -> list[DataIssueResponse]:
    """Get all data quality issues for a product."""
    product = product_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return [DataIssueResponse.model_validate(i) for i in product.issues]


@router.post("/{product_id}/ai-thought", response_model=AiThoughtResponse)
def ai_thought(
    product_id: int,
    body: AiThoughtRequest,
    db: Session = Depends(get_db),
) -> AiThoughtResponse:
    """Apply a free-text merchant instruction to a product via AI and return proposed diffs.

    Does NOT persist any changes — the caller decides which diffs to accept.
    """
    product = product_service.get_product_by_id(db, product_id)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")

    try:
        result = run_thought_rewrite(product, body.prompt.strip())
    except Exception as exc:
        logger.warning("AI thought failed for product %s: %s", product_id, exc)
        raise HTTPException(
            status_code=502,
            detail="AI service unavailable. Please try again later.",
        ) from exc

    changes = [
        AiThoughtChange(
            field=c["field"],
            before=c.get("before", ""),
            after=c["after"],
            reason=c.get("reason", ""),
        )
        for c in result.get("changes") or []
    ]
    return AiThoughtResponse(changes=changes, error=result.get("error"))
