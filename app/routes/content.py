"""
CatalogIQ — Content Generation API Routes

Endpoints for generating SEO product descriptions using Groq LLM.
"""

import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.models.database import get_db
from app.models.schemas import (
    ContentGenerationRequest, ContentGenerationResponse,
    ProductResponse,
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

    Uses Groq LLM to create fact-grounded descriptions based on
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
    tone: str = "professional",
    include_seo: bool = True,
    db: Session = Depends(get_db),
) -> ContentGenerationResponse:
    """Generate content for a single product."""
    result = content_service.generate_content_for_product(
        db, product_id, tone=tone, include_seo=include_seo
    )
    if not result.success:
        raise HTTPException(status_code=400, detail=result.error)
    return result


@router.get("/needs-content", response_model=list[ProductResponse])
def get_products_needing_content(
    limit: int = 50,
    db: Session = Depends(get_db),
) -> list[ProductResponse]:
    """Get products that need content generation.

    Returns products with missing or thin descriptions.
    """
    products = content_service.get_products_needing_content(db, limit=limit)
    return [ProductResponse.model_validate(p) for p in products]
