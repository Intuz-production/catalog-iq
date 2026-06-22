"""
CatalogIQ — Content Generation Service

Pipeline 2: Generates unique, fact-grounded SEO product descriptions
using Groq LLM (LLaMA 3.3 70B). Descriptions are based strictly on
structured product attributes to prevent spec invention.
"""

import json
import logging
from typing import Optional

from groq import Groq
from sqlalchemy.orm import Session

from app.config import settings
from app.models.schemas import (
    Product, DataIssue,
    ProductStatus, IssueType, IssueSeverity,
    ContentGenerationRequest, ContentGenerationResponse, ProductUpdate,
)
from app.services.product_service import get_product_by_id, update_product

logger = logging.getLogger("catalogiq.content_service")


def _get_groq_client() -> Groq:
    """Create and return a Groq API client.

    Returns:
        Configured Groq client instance.
    """
    return Groq(api_key=settings.GROQ_API_KEY)


def _build_description_prompt(product: Product, tone: str = "professional") -> str:
    """Build an LLM prompt for generating a product description.

    The prompt instructs the model to use ONLY the provided attributes
    and never invent specifications.

    Args:
        product: Product record with attributes.
        tone: Desired writing tone.

    Returns:
        Formatted prompt string.
    """
    attributes_text = ""
    if product.attributes:
        for key, value in product.attributes.items():
            attributes_text += f"  - {key.replace('_', ' ').title()}: {value}\n"

    prompt = f"""You are an expert e-commerce copywriter. Write a compelling, SEO-optimized product description.

STRICT RULES:
1. Use ONLY the facts provided below. Do NOT invent any specifications, features, or claims.
2. If an attribute is not listed, do NOT mention it or guess it.
3. Write in a {tone} tone suitable for an e-commerce product listing.
4. Include relevant keywords naturally for SEO.
5. Structure the description with a brief opening hook, key features, and a closing statement.
6. Keep the description between 80-150 words.
7. Do NOT use markdown formatting, bullet points, or headers in the description.
8. Write in flowing paragraphs.

PRODUCT INFORMATION:
- Title: {product.title}
- SKU: {product.sku}
- Category: {product.category or 'Not specified'}
- Brand: {product.brand or 'Not specified'}
- Price: {product.price or 'Not specified'} {product.currency}
{f'- Original Description: {product.description}' if product.description else ''}

PRODUCT ATTRIBUTES:
{attributes_text if attributes_text else '  No additional attributes available.'}

Write the product description now:"""

    return prompt


def _build_seo_prompt(product: Product, description: str) -> str:
    """Build an LLM prompt for generating SEO metadata.

    Args:
        product: Product record.
        description: Generated or existing product description.

    Returns:
        Formatted prompt string for SEO metadata generation.
    """
    prompt = f"""You are an SEO specialist. Generate SEO metadata for the following e-commerce product.

PRODUCT:
- Title: {product.title}
- Category: {product.category or 'General'}
- Brand: {product.brand or 'Unknown'}
- Description: {description}

Generate the following in JSON format:
{{
  "seo_title": "An SEO-optimized title (max 60 characters, include primary keyword)",
  "seo_keywords": "Comma-separated list of 5-8 relevant search keywords"
}}

Return ONLY the JSON object, no other text."""

    return prompt


def generate_content_for_product(
    db: Session,
    product_id: int,
    tone: str = "professional",
    include_seo: bool = True,
) -> ContentGenerationResponse:
    """Generate an SEO product description for a single product.

    Uses Groq LLM to create a fact-grounded description based on
    the product's structured attributes.

    Args:
        db: Database session.
        product_id: ID of the product to generate content for.
        tone: Writing tone (professional, casual, luxury, technical).
        include_seo: Whether to also generate SEO metadata.

    Returns:
        ContentGenerationResponse with the generated content.
    """
    product = get_product_by_id(db, product_id)
    if not product:
        return ContentGenerationResponse(
            product_id=product_id,
            generated_description="",
            success=False,
            error=f"Product with ID {product_id} not found.",
        )

    try:
        client = _get_groq_client()

        # Generate description
        logger.info(f"Generating description for product {product_id} (SKU: {product.sku})")

        desc_prompt = _build_description_prompt(product, tone)
        desc_response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": "You are a professional e-commerce copywriter."},
                {"role": "user", "content": desc_prompt},
            ],
            temperature=0.7,
            max_tokens=500,
        )

        generated_description = desc_response.choices[0].message.content.strip()

        # Generate SEO metadata if requested
        seo_title: Optional[str] = None
        seo_keywords: Optional[str] = None

        if include_seo:
            logger.info(f"Generating SEO metadata for product {product_id}")
            seo_prompt = _build_seo_prompt(product, generated_description)
            seo_response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are an SEO specialist. Return only valid JSON."},
                    {"role": "user", "content": seo_prompt},
                ],
                temperature=0.3,
                max_tokens=200,
            )

            try:
                seo_text = seo_response.choices[0].message.content.strip()
                # Clean potential markdown code blocks
                if seo_text.startswith("```"):
                    seo_text = seo_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                seo_data = json.loads(seo_text)
                seo_title = seo_data.get("seo_title", "")
                seo_keywords = seo_data.get("seo_keywords", "")
            except (json.JSONDecodeError, IndexError) as e:
                logger.warning(f"Failed to parse SEO response for product {product_id}: {e}")

        # Update product in database
        update_data = ProductUpdate(
            generated_description=generated_description,
            seo_title=seo_title,
            seo_keywords=seo_keywords,
        )
        update_product(db, product_id, update_data)

        # Resolve any missing_description issues
        _resolve_content_issues(db, product_id)

        logger.info(f"Content generated successfully for product {product_id}")

        return ContentGenerationResponse(
            product_id=product_id,
            generated_description=generated_description,
            seo_title=seo_title,
            seo_keywords=seo_keywords,
            success=True,
        )

    except Exception as e:
        error_msg = f"Content generation failed for product {product_id}: {str(e)}"
        logger.error(error_msg)
        return ContentGenerationResponse(
            product_id=product_id,
            generated_description="",
            success=False,
            error=error_msg,
        )


def generate_content_batch(
    db: Session,
    request: ContentGenerationRequest,
) -> list[ContentGenerationResponse]:
    """Generate content for multiple products.

    Args:
        db: Database session.
        request: Batch content generation request.

    Returns:
        List of ContentGenerationResponse for each product.
    """
    results: list[ContentGenerationResponse] = []
    total = len(request.product_ids)

    logger.info(f"Starting batch content generation for {total} products")

    for i, product_id in enumerate(request.product_ids):
        logger.info(f"Processing product {i + 1}/{total} (ID: {product_id})")
        result = generate_content_for_product(
            db=db,
            product_id=product_id,
            tone=request.tone,
            include_seo=request.include_seo,
        )
        results.append(result)

    succeeded = sum(1 for r in results if r.success)
    logger.info(f"Batch content generation complete: {succeeded}/{total} succeeded")

    return results


def get_products_needing_content(db: Session, limit: int = 50) -> list[Product]:
    """Find products that need content generation.

    Returns products with no description or thin content.

    Args:
        db: Database session.
        limit: Maximum products to return.

    Returns:
        List of products needing content.
    """
    from sqlalchemy import or_

    return db.query(Product).filter(
        or_(
            Product.description.is_(None),
            Product.description == "",
            Product.generated_description.is_(None),
        )
    ).limit(limit).all()


def _resolve_content_issues(db: Session, product_id: int) -> None:
    """Mark content-related issues as resolved after generation.

    Args:
        db: Database session.
        product_id: Product whose issues should be resolved.
    """
    from datetime import datetime

    issues = db.query(DataIssue).filter(
        DataIssue.product_id == product_id,
        DataIssue.issue_type.in_([IssueType.MISSING_DESCRIPTION, IssueType.THIN_CONTENT]),
        DataIssue.resolved == False,
    ).all()

    for issue in issues:
        issue.resolved = True
        issue.resolved_at = datetime.utcnow()

    if issues:
        db.commit()
        logger.info(f"Resolved {len(issues)} content issues for product {product_id}")
