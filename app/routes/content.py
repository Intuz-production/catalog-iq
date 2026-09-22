"""
CatalogIQ — Content Generation API Routes

Endpoints for generating SEO product descriptions using the configured LLM.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    ContentGenerationRequest, ContentGenerationResponse, ContentTone,
    ProductResponse, ProductListResponse, ProductSortField, SortOrder,
)
from app.services import content_service

logger = logging.getLogger("catalogiq.routes.content")

router = APIRouter(prefix="/api/content", tags=["Content Generation"])


@router.post("/generate", response_model=list[ContentGenerationResponse])
def generate_content(
    request: ContentGenerationRequest,
    db: Session = Depends(get_db),
) -> list[ContentGenerationResponse]:
    """Generate SEO product descriptions for specified products.

    Uses the configured LLM provider to create fact-grounded descriptions based on
    structured product attributes.
    """
    if not request.product_ids:
        raise HTTPException(
            status_code=400,
            detail="At least one product_id is required."
        )

    if len(request.product_ids) > 20:
        raise HTTPException(
            status_code=400,
            detail="Maximum 20 products per batch request."
        )

    logger.info(
        f"Content generation request: {len(request.product_ids)} products, "
        f"tone={request.tone}, seo={request.include_seo}"
    )

    results = content_service.generate_content_batch(db, request)
    return results


@router.post("/generate/{product_id}", response_model=ContentGenerationResponse)
def generate_single(
    product_id: int,
    tone: ContentTone = ContentTone.PROFESSIONAL,
    include_seo: bool = True,
    db: Session = Depends(get_db),
) -> ContentGenerationResponse:
    """Generate content for a single product."""
    result = content_service.generate_content_for_product(
        db, product_id, tone=tone.value, include_seo=include_seo
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result


@router.get("/needs-content", response_model=ProductListResponse)
def get_products_needing_content(
    skip: int = Query(0, ge=0, description="Number of records to skip"),
    limit: int = Query(50, ge=1, le=200, description="Max records to return"),
    search: Optional[str] = Query(None, description="Search in title, SKU, brand"),
    sort_by: ProductSortField = Query(
        ProductSortField.UPDATED_AT, description="Column to sort by"
    ),
    sort_order: SortOrder = Query(SortOrder.DESC, description="Sort direction"),
    db: Session = Depends(get_db),
) -> ProductListResponse:
    """Get products that need content generation with pagination and sorting."""
    products, total = content_service.get_products_needing_content(
        db,
        skip=skip,
        limit=limit,
        search=search,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return ProductListResponse(
        items=[ProductResponse.model_validate(p) for p in products],
        total=total,
        skip=skip,
        limit=limit,
    )
