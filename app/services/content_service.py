"""
CatalogIQ — Content Generation Service

Pipeline 2: Generates unique, fact-grounded SEO product descriptions
using Groq LLM (default: openai/gpt-oss-120b). Descriptions are based strictly on
structured product attributes to prevent spec invention.
"""

import json
import logging
import re
import time
from typing import Any, Optional

from groq import Groq
from sqlalchemy.orm import Session

from app.config import settings
from app.models.schemas import (
    Product, DataIssue,
    IssueType,
    ProductSortField, SortOrder,
    ContentGenerationRequest, ContentGenerationResponse, ProductUpdate,
    ContentTone,
)
from app.services.product_service import get_product_by_id, update_product, SORT_COLUMNS

logger = logging.getLogger("catalogiq.content_service")

ALLOWED_TONES: frozenset[str] = frozenset({tone.value for tone in ContentTone})

REASONING_MODEL_MARKERS: tuple[str, ...] = (
    "gpt-oss",
    "qwen3",
    "minimax-m2",
)


def normalize_tone(tone: str) -> str:
    """Validate and normalize a content generation tone.

    Args:
        tone: Requested writing tone.

    Returns:
        Normalized tone string.

    Raises:
        ValueError: If the tone is not supported.
    """
    normalized = (tone or ContentTone.PROFESSIONAL.value).strip().lower()
    if normalized not in ALLOWED_TONES:
        allowed = ", ".join(sorted(ALLOWED_TONES))
        raise ValueError(f"Invalid tone '{tone}'. Allowed values: {allowed}")
    return normalized


def _get_groq_client() -> Groq:
    """Create and return a Groq API client."""
    return Groq(api_key=settings.GROQ_API_KEY)


def _build_description_prompt(product: Product, tone: str = "professional") -> str:
    """Build an LLM prompt for generating a product description."""
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
    """Build an LLM prompt for generating SEO metadata."""
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


def _extract_json_object(text: str) -> dict[str, Any]:
    """Parse a JSON object from raw LLM output."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        data = json.loads(match.group())
        if isinstance(data, dict):
            return data

    raise ValueError("LLM response did not contain valid JSON metadata.")


def _normalize_seo_fields(seo_data: dict[str, Any]) -> tuple[Optional[str], Optional[str], list[str]]:
    """Normalize SEO metadata and collect validation warnings."""
    warnings: list[str] = []
    seo_title = str(seo_data.get("seo_title", "")).strip() or None
    seo_keywords = str(seo_data.get("seo_keywords", "")).strip() or None

    if seo_title and len(seo_title) > settings.SEO_TITLE_MAX_LENGTH:
        warnings.append(
            f"SEO title truncated from {len(seo_title)} to {settings.SEO_TITLE_MAX_LENGTH} characters."
        )
        seo_title = seo_title[:settings.SEO_TITLE_MAX_LENGTH].rstrip()

    if not seo_title:
        warnings.append("SEO title was missing from the LLM response.")

    if not seo_keywords:
        warnings.append("SEO keywords were missing from the LLM response.")

    return seo_title, seo_keywords, warnings


def _validate_generated_description(text: str) -> tuple[str, int, list[str]]:
    """Validate LLM description output before persisting it."""
    warnings: list[str] = []
    cleaned = (text or "").strip()
    if not cleaned:
        raise ValueError("LLM returned an empty description.")

    word_count = len(cleaned.split())
    if word_count < settings.GROQ_MIN_DESCRIPTION_WORDS:
        raise ValueError(
            f"Generated description is too short ({word_count} words). "
            f"Minimum required: {settings.GROQ_MIN_DESCRIPTION_WORDS}."
        )

    if word_count < 50:
        warnings.append(f"Generated description is shorter than recommended ({word_count} words).")

    return cleaned, word_count, warnings


def _validate_product_for_generation(product: Product) -> Optional[str]:
    """Return an error message when a product cannot be generated safely."""
    if not product.title or not product.title.strip():
        return "Product title is required for content generation."
    return None


def _is_reasoning_model(model: str) -> bool:
    """Return True when the configured Groq model uses a reasoning token budget."""
    model_lower = model.lower()
    return any(marker in model_lower for marker in REASONING_MODEL_MARKERS)


def _strip_reasoning_markers(text: str) -> str:
    """Remove reasoning blocks accidentally included in visible model output."""
    think_pattern = re.compile(
        rf"{'<' + 'think' + '>'}.*?{'<' + '/' + 'think' + '>'}",
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = think_pattern.sub("", text)
    cleaned = re.sub(
        r"<redacted_reasoning>.*?</redacted_reasoning>",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


def _build_chat_completion_kwargs(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Build Groq chat completion kwargs for standard and reasoning models."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    if _is_reasoning_model(model):
        kwargs["max_completion_tokens"] = max(max_tokens, settings.GROQ_MAX_COMPLETION_TOKENS)
        kwargs["reasoning_format"] = settings.GROQ_REASONING_FORMAT
        if "gpt-oss" in model.lower():
            kwargs["reasoning_effort"] = settings.GROQ_REASONING_EFFORT
    else:
        kwargs["max_tokens"] = max_tokens

    return kwargs


def _call_groq_chat(client: Groq, **kwargs: Any) -> Any:
    """Call Groq chat completions with exponential backoff retries."""
    last_error: Optional[Exception] = None

    for attempt in range(settings.GROQ_MAX_RETRIES):
        try:
            return client.chat.completions.create(**kwargs)
        except Exception as exc:
            last_error = exc
            if attempt >= settings.GROQ_MAX_RETRIES - 1:
                break

            delay = settings.GROQ_RETRY_DELAY_SECONDS * (2 ** attempt)
            logger.warning(
                "Groq API attempt %s/%s failed, retrying in %ss: %s",
                attempt + 1,
                settings.GROQ_MAX_RETRIES,
                delay,
                exc,
            )
            time.sleep(delay)

    raise last_error or RuntimeError("Groq API call failed without an error.")


def _parse_llm_message(response: Any) -> str:
    """Extract message content from a Groq chat completion response."""
    choice = response.choices[0]
    message = choice.message
    content = _strip_reasoning_markers(message.content or "")

    if content:
        return content

    finish_reason = getattr(choice, "finish_reason", "unknown")
    reasoning_tokens: Optional[int] = None
    usage = getattr(response, "usage", None)
    if usage is not None:
        details = getattr(usage, "completion_tokens_details", None)
        if details is not None:
            reasoning_tokens = getattr(details, "reasoning_tokens", None)

    hint = ""
    if finish_reason == "length":
        hint = (
            " Token budget was exhausted before visible output was produced. "
            "For reasoning models such as openai/gpt-oss-120b, increase "
            "GROQ_MAX_COMPLETION_TOKENS or use a supported model such as openai/gpt-oss-120b."
        )
    if reasoning_tokens:
        hint += f" Reasoning tokens used: {reasoning_tokens}."

    raise ValueError(
        f"LLM returned an empty description (finish_reason={finish_reason}).{hint}"
    )


def generate_content_for_product(
    db: Session,
    product_id: int,
    tone: str = "professional",
    include_seo: bool = True,
) -> ContentGenerationResponse:
    """Generate an SEO product description for a single product."""
    product = get_product_by_id(db, product_id)
    if not product:
        return ContentGenerationResponse(
            product_id=product_id,
            generated_description="",
            success=False,
            error=f"Product with ID {product_id} not found.",
        )

    validation_error = _validate_product_for_generation(product)
    if validation_error:
        return ContentGenerationResponse(
            product_id=product_id,
            sku=product.sku,
            title=product.title,
            generated_description="",
            success=False,
            error=validation_error,
        )

    try:
        normalized_tone = normalize_tone(tone)
        warnings: list[str] = []
        client = _get_groq_client()

        logger.info(
            "Generating description for product %s (SKU: %s, tone=%s)",
            product_id,
            product.sku,
            normalized_tone,
        )

        desc_prompt = _build_description_prompt(product, normalized_tone)
        desc_response = _call_groq_chat(
            client,
            **_build_chat_completion_kwargs(
                settings.GROQ_MODEL,
                messages=[
                    {"role": "system", "content": "You are a professional e-commerce copywriter."},
                    {"role": "user", "content": desc_prompt},
                ],
                temperature=settings.GROQ_TEMPERATURE,
                max_tokens=settings.GROQ_MAX_TOKENS,
            ),
        )

        generated_description, word_count, description_warnings = _validate_generated_description(
            _parse_llm_message(desc_response)
        )
        warnings.extend(description_warnings)

        seo_title: Optional[str] = None
        seo_keywords: Optional[str] = None

        if include_seo:
            logger.info("Generating SEO metadata for product %s", product_id)
            seo_prompt = _build_seo_prompt(product, generated_description)
            seo_response = _call_groq_chat(
                client,
                **_build_chat_completion_kwargs(
                    settings.GROQ_MODEL,
                    messages=[
                        {"role": "system", "content": "You are an SEO specialist. Return only valid JSON."},
                        {"role": "user", "content": seo_prompt},
                    ],
                    temperature=settings.GROQ_SEO_TEMPERATURE,
                    max_tokens=settings.GROQ_SEO_MAX_TOKENS,
                ),
            )

            try:
                seo_data = _extract_json_object(_parse_llm_message(seo_response))
                seo_title, seo_keywords, seo_warnings = _normalize_seo_fields(seo_data)
                warnings.extend(seo_warnings)
            except (json.JSONDecodeError, ValueError, IndexError) as exc:
                warning = f"SEO metadata generation failed: {exc}"
                warnings.append(warning)
                logger.warning("Failed to parse SEO response for product %s: %s", product_id, exc)

        update_data = ProductUpdate(
            generated_description=generated_description,
            seo_title=seo_title,
            seo_keywords=seo_keywords,
        )
        update_product(db, product_id, update_data)
        _resolve_content_issues(db, product_id)

        logger.info("Content generated successfully for product %s (%s words)", product_id, word_count)

        return ContentGenerationResponse(
            product_id=product_id,
            sku=product.sku,
            title=product.title,
            generated_description=generated_description,
            seo_title=seo_title,
            seo_keywords=seo_keywords,
            word_count=word_count,
            warnings=warnings,
            success=True,
        )

    except ValueError as exc:
        error_msg = f"Content generation failed for product {product_id}: {exc}"
        logger.warning(error_msg)
        return ContentGenerationResponse(
            product_id=product_id,
            sku=product.sku,
            title=product.title,
            generated_description="",
            success=False,
            error=error_msg,
        )
    except Exception as exc:
        error_msg = f"Content generation failed for product {product_id}: {exc}"
        logger.error(error_msg)
        return ContentGenerationResponse(
            product_id=product_id,
            sku=product.sku,
            title=product.title,
            generated_description="",
            success=False,
            error=error_msg,
        )


def generate_content_batch(
    db: Session,
    request: ContentGenerationRequest,
) -> list[ContentGenerationResponse]:
    """Generate content for multiple products."""
    results: list[ContentGenerationResponse] = []
    total = len(request.product_ids)
    tone = request.tone.value if isinstance(request.tone, ContentTone) else request.tone

    logger.info("Starting batch content generation for %s products", total)

    for index, product_id in enumerate(request.product_ids):
        if index > 0 and settings.GROQ_BATCH_DELAY_MS > 0:
            time.sleep(settings.GROQ_BATCH_DELAY_MS / 1000)

        logger.info("Processing product %s/%s (ID: %s)", index + 1, total, product_id)
        result = generate_content_for_product(
            db=db,
            product_id=product_id,
            tone=tone,
            include_seo=request.include_seo,
        )
        results.append(result)

    succeeded = sum(1 for result in results if result.success)
    logger.info("Batch content generation complete: %s/%s succeeded", succeeded, total)

    return results


def get_products_needing_content(
    db: Session,
    skip: int = 0,
    limit: int = 50,
    search: Optional[str] = None,
    sort_by: ProductSortField = ProductSortField.UPDATED_AT,
    sort_order: SortOrder = SortOrder.DESC,
) -> tuple[list[Product], int]:
    """Find products that need content generation with pagination and sorting."""
    from sqlalchemy import or_

    query = db.query(Product).filter(
        or_(
            Product.generated_description.is_(None),
            Product.generated_description == "",
        )
    )

    if search:
        search_term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Product.title.ilike(search_term),
                Product.sku.ilike(search_term),
                Product.brand.ilike(search_term),
            )
        )

    total = query.count()
    sort_column = SORT_COLUMNS.get(sort_by, Product.updated_at)
    if sort_order == SortOrder.ASC:
        query = query.order_by(sort_column.asc())
    else:
        query = query.order_by(sort_column.desc())

    products = query.offset(skip).limit(limit).all()
    return products, total


def _resolve_content_issues(db: Session, product_id: int) -> None:
    """Mark content-related issues as resolved and refresh product status."""
    from datetime import datetime
    from app.services import ingestion_service

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
        logger.info("Resolved %s content issues for product %s", len(issues), product_id)

    ingestion_service.refresh_product_status(db, product_id)
