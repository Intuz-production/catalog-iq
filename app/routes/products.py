"""
CatalogIQ — Product Management API Routes

CRUD endpoints for managing the product catalog.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    ProductStatus, ProductCreate, ProductUpdate,
    ProductResponse, DataIssueResponse, DashboardStats,
)
from app.services import product_service

logger = logging.getLogger("catalogiq.routes.products")

router = APIRouter(prefix="/api/products", tags=["Products"])


@router.get("/", response_model=list[ProductResponse])
def list_products(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    status: Optional[ProductStatus] = Query(None, description="Filter by status"),
    search: Optional[str] = Query(None, description="Search in title, SKU, brand"),
    category: Optional[str] = Query(None, description="Filter by category"),
    db: Session = Depends(get_db),
) -> list[ProductResponse]:
    """List products with optional filtering and pagination."""
    products = product_service.get_products(
        db, skip=skip, limit=limit, status=status, search=search, category=category
    )
    results = []
    for p in products:
        resp = ProductResponse.model_validate(p)
        resp.issue_count = len([i for i in p.issues if not i.resolved])
        results.append(resp)
    return results


@router.get("/categories", response_model=list[str])
def list_categories(db: Session = Depends(get_db)) -> list[str]:
    """Get all distinct product categories."""
    return product_service.get_categories(db)


@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db)) -> DashboardStats:
    """Get dashboard overview statistics."""
    return product_service.get_dashboard_stats(db)


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
    """Update an existing product."""
    product = product_service.update_product(db, product_id, updates)
    if not product:
        raise HTTPException(status_code=404, detail=f"Product {product_id} not found")
    return ProductResponse.model_validate(product)


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
