"""
CatalogIQ — AI ingest analysis

After rule-based quality checks, the configured LLM proposes a full-field rewrite
and optional extra issues. Suggestions are stored only; product columns
are not updated until a human accepts them.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Optional

from datetime import datetime

from app.config import settings
from app.models.database import SessionLocal
from app.models.schemas import (
    Product,
    DataIssue,
    IngestionJob,
    IssueType,
    IssueSeverity,
    ReviewStatus,
    SuggestionSource,
    AiAnalysisStatus,
)
from app.services.content_service import _extract_json_object, generate_content_for_product
from app.services.llm import chat_completion
from app.services.ingestion_service import (
    ATTRIBUTE_FIELD_PREFIX,
    LEGACY_ATTRIBUTE_FIELDS,
    PRODUCT_REWRITE_FIELDS,
    _count_open_issues_for_products,
    refresh_product_status,
)

logger = logging.getLogger("catalogiq.ingestion_ai_service")

NUMBER_RE = re.compile(r"\d+(?:\.\d+)?")
EXAMPLE_HINT_RE = re.compile(r"\be\.g\.?\b", re.IGNORECASE)
MAX_RECORDED_AI_FAILURES = 10
FACT_ATTRIBUTE_FIELDS = frozenset({
    "size", "sizes", "material", "materials", "fabric",
    "color", "colour", "price", "weight", "stock",
})

# Soft quality issue types owned by AI (cleared and rewritten on re-analysis).
# ATTRIBUTE_NOT_IN_COPY is retired from creation but kept here so re-analysis
# still clears legacy pending rows of that type.
AI_SOFT_ISSUE_TYPES = frozenset({
    IssueType.AI_INFERRED,
    IssueType.THIN_CONTENT,
    IssueType.ATTRIBUTE_CONTRADICTION,
    IssueType.ATTRIBUTE_NOT_IN_COPY,
    IssueType.MISSING_ATTRIBUTES,
})

# Soft extras may use any IssueType except this retired omission type.
RETIRED_SOFT_ISSUE_TYPES = frozenset({
    IssueType.ATTRIBUTE_NOT_IN_COPY,
})

REWRITE_SYSTEM_PROMPT = (
    "You are a catalog data cleaner. Given one product row, return ready-to-use "
    "e-commerce listing fields as JSON. Use only facts in the product data. "
    "Do not invent specifications, measurements, materials, warranties, or prices."
)


def _stringify(value: object) -> Optional[str]:
    """Convert a stored field value to a suggestion string."""
    if value is None:
        return None
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return str(value)
    text = str(value).strip()
    return text or None


def _source_blob(product: Product) -> str:
    """Build a lowercase blob of facts from the imported row."""
    parts = [
        product.sku or "",
        product.title or "",
        product.description or "",
        product.category or "",
        product.brand or "",
        "" if product.price is None else str(product.price),
        "" if getattr(product, "stock", None) is None else str(product.stock),
        getattr(product, "image_url", None) or "",
        json.dumps(product.attributes or {}, ensure_ascii=True),
        json.dumps(product.raw_data or {}, ensure_ascii=True),
    ]
    return " ".join(parts).lower()


def _numbers_in(text: Optional[str]) -> set[str]:
    """Extract numeric tokens from text."""
    if not text:
        return set()
    return set(NUMBER_RE.findall(str(text)))


def _numeric_token_key(token: str) -> str:
    """Normalize a numeric token so 19, 19.0, and 19.00 compare equal."""
    try:
        value = float(token)
    except ValueError:
        return token
    if value.is_integer():
        return str(int(value))
    return str(value)


def _introduces_new_numbers(suggested: Optional[str], source: str) -> bool:
    """Return True when suggested text contains digits absent from source facts."""
    source_keys = {_numeric_token_key(token) for token in _numbers_in(source)}
    suggested_keys = {_numeric_token_key(token) for token in _numbers_in(suggested)}
    return bool(suggested_keys - source_keys)


def build_ingest_prompt(product: Product, open_issues: list[DataIssue]) -> str:
    """Build the Groq prompt for one imported product."""
    issue_lines = []
    for issue in open_issues:
        issue_lines.append(
            f"- {issue.issue_type.value if hasattr(issue.issue_type, 'value') else issue.issue_type}"
            f" field={issue.field_name} {issue.description}"
        )
    issues_block = "\n".join(issue_lines) if issue_lines else "- none"

    payload = {
        "sku": product.sku,
        "title": product.title,
        "description": product.description,
        "category": product.category,
        "brand": product.brand,
        "price": product.price,
        "currency": product.currency,
        "stock": getattr(product, "stock", None),
        "in_stock": getattr(product, "in_stock", True),
        "image_url": getattr(product, "image_url", None),
        "attributes": product.attributes or {},
        "raw_data": product.raw_data or {},
    }
    return f"""You receive ONE product row. Turn it into ready-to-use catalog product
data a merchant can accept and publish. Soft quality issues should include
apply-ready suggested_value fixes whenever the row already has enough facts.

STRICT RULES:
1. Use ONLY facts in the JSON. Do not invent specs, materials, sizes, prices,
   warranties, capacities, or other claims that are not present.
2. In "rewrite", return ready-to-use title, description, category, brand, price,
   stock, in_stock, image_url, and every attribute — polished, consistent, and complete from known facts.
   Improved rewrite fields become Accept suggestions for the merchant even when
   there is no separate soft-quality problem.
3. If a field is already publish-ready, return it unchanged.
4. Never change or return a different SKU.
5. Price may only be normalized (strip currency symbols) or left as-is. Do not invent a new price.
   Category: If missing or generic, suggest an appropriate e-commerce category based on title and attributes.
   Stock: Extract integer quantity if stated in raw_data, attributes, or product info. Do NOT invent stock numbers.
   In stock: boolean (true/false). False if stock is 0 or out of stock, otherwise true.
   Image URL: Extract if present in raw_data or attributes. Never invent fake image URLs.
6. Soft quality: Review EVERY field (title, description, category, brand, price,
   and each attribute) against the FULL product JSON — not in isolation.
   Use cross-field context (attributes informing description, title vs color, etc.).
   YOU decide what is a real problem. Report findings via extra_issues ONLY when
   a human should review or apply a fix. Do not create an issue for every field.
   Do not repeat Open quality issues. If nothing soft needs attention, return [].
7. Look for real soft problems when they exist, for example: abbreviated or messy
   attributes (blk, Grn, wht, lg, med), weak or placeholder copy, title/attribute
   contradictions, and empty attributes when sibling facts imply they should exist.
   Prefer several precise findings over one vague complaint when multiple fields need work.
8. For each soft finding, set:
   - issue_type: short snake_case label (prefer ai_inferred when unsure;
     common labels: thin_content, attribute_contradiction, missing_attributes).
   - field_name: the single field to fix.
   - severity: low, medium, high, or critical.
   - description: why the current value is not publish-ready.
   - actual_value / suggested_value: suggested_value MUST be ready-to-use catalog
     text for that field whenever facts exist in the product JSON (especially
     title and description). Null ONLY when a required fact is truly absent
     from the entire product row.
9. When description or title is weak, ALWAYS provide suggested_value: a ready-to-use
   listing rewrite built only from title, brand, category, attributes, and raw_data.
   Weave in known attributes (color, size, material, weight) when present.
   Do not complain about missing warranty/capacity/etc. that are not in the JSON.
10. Do NOT invent size, material, color, weight, or price values in rewrite or suggestions.
11. Do NOT flag an attribute merely because it is absent from the title or description —
   structured attributes alone are fine.

Return JSON with this shape:
{{
  "rewrite": {{
    "title": "...",
    "description": "...",
    "category": "...",
    "brand": "...",
    "price": "...",
    "stock": 10,
    "in_stock": true,
    "image_url": "https://...",
    "attributes": {{ "color": "...", "size": "..." }}
  }},
  "field_reasons": {{ "title": "why it changed" }},
  "extra_issues": [
    {{
      "issue_type": "ai_inferred",
      "field_name": "description",
      "severity": "medium",
      "description": "...",
      "actual_value": "...",
      "suggested_value": "..."
    }}
  ]
}}

Open quality issues:
{issues_block}

Product JSON:
{json.dumps(payload, default=str, ensure_ascii=True)}
"""


def parse_ingest_payload(raw_text: str) -> dict[str, Any]:
    """Parse Groq JSON into rewrite, reasons, and extra issues."""
    data = _extract_json_object(raw_text)
    rewrite = data.get("rewrite")
    if not isinstance(rewrite, dict):
        raise ValueError("LLM response is missing a rewrite object.")
    reasons = data.get("field_reasons") or {}
    if not isinstance(reasons, dict):
        reasons = {}
    extra_issues = data.get("extra_issues") or []
    if not isinstance(extra_issues, list):
        extra_issues = []
    return {
        "rewrite": rewrite,
        "field_reasons": reasons,
        "extra_issues": extra_issues,
    }


def sanitize_rewrite(product: Product, rewrite: dict[str, Any]) -> dict[str, Optional[str]]:
    """Keep original values when the model invents numbers not in the source row."""
    source = _source_blob(product)
    sanitized: dict[str, Optional[str]] = {}

    for field_name in PRODUCT_REWRITE_FIELDS:
        original = _stringify(getattr(product, field_name, None))
        suggested = rewrite.get(field_name, original)
        suggested_text = _stringify(suggested)
        if field_name == "title" and not suggested_text:
            suggested_text = original or product.sku

        if field_name == "stock":
            if suggested_text is not None and suggested_text != "":
                try:
                    int_val = int(float(suggested_text))
                    suggested_text = str(int_val)
                except (ValueError, TypeError):
                    suggested_text = original
            if _introduces_new_numbers(suggested_text, source):
                sanitized[field_name] = original
            else:
                sanitized[field_name] = suggested_text
            continue

        if field_name == "in_stock":
            if suggested is not None:
                val_str = str(suggested).strip().lower()
                if val_str in ("false", "0", "no", "outofstock", "out of stock"):
                    sanitized[field_name] = "false"
                else:
                    sanitized[field_name] = "true"
            else:
                sanitized[field_name] = original or "true"
            continue

        if field_name == "image_url":
            if suggested_text:
                if (getattr(product, "image_url", None) and suggested_text == product.image_url) or suggested_text.lower() in source:
                    sanitized[field_name] = suggested_text
                else:
                    sanitized[field_name] = original
            else:
                sanitized[field_name] = original
            continue

        if _introduces_new_numbers(suggested_text, source):
            sanitized[field_name] = original
        else:
            sanitized[field_name] = suggested_text

    original_attrs = dict(product.attributes or {})
    suggested_attrs = rewrite.get("attributes") or {}
    if not isinstance(suggested_attrs, dict):
        suggested_attrs = {}

    attr_keys = set(original_attrs.keys()) | {str(key) for key in suggested_attrs.keys()}
    for key in sorted(attr_keys):
        field_name = f"{ATTRIBUTE_FIELD_PREFIX}{key}"
        original = _stringify(original_attrs.get(key))
        suggested_text = _stringify(suggested_attrs.get(key, original))
        if key not in original_attrs:
            value_ok = suggested_text and suggested_text.lower() in source
            if not value_ok or _introduces_new_numbers(suggested_text, source):
                continue
        elif _introduces_new_numbers(suggested_text, source):
            suggested_text = original
        sanitized[field_name] = suggested_text

    return sanitized


def _canonical_field_name(field_name: Optional[str]) -> str:
    """Normalize issue and rewrite field names for comparison."""
    name = (field_name or "").strip().lower()
    if name.startswith(ATTRIBUTE_FIELD_PREFIX):
        return name[len(ATTRIBUTE_FIELD_PREFIX):]
    return name


def _fields_overlap(left: Optional[str], right: Optional[str]) -> bool:
    """Return True when two issue fields describe the same catalog value."""
    first = _canonical_field_name(left)
    second = _canonical_field_name(right)
    if first == second:
        return True
    attr_keys = FACT_ATTRIBUTE_FIELDS | {"attributes"}
    if "attributes" in {first, second} and {first, second} <= attr_keys:
        return True
    return False


def _values_match(original: Optional[str], suggested: Optional[str]) -> bool:
    """Return True when a suggestion leaves the imported value unchanged."""
    def normalize(value: Optional[str]) -> str:
        text = (value or "").strip()
        for mark in ("\u2011", "\u2013", "\u2014", "\u2212"):
            text = text.replace(mark, "-")
        return re.sub(r"\s+", " ", text)

    left = normalize(original).lower()
    right = normalize(suggested).lower()
    if left == right:
        return True
    try:
        return float(left) == float(right)
    except ValueError:
        return False


def _suggestion_supported_by_source(
    field_name: Optional[str],
    suggested: Optional[str],
    source: str,
) -> bool:
    """Reject invented size, material, color, weight, or price suggestions."""
    if not suggested:
        return True
    if EXAMPLE_HINT_RE.search(suggested):
        return False
    field = _canonical_field_name(field_name)
    if field not in FACT_ATTRIBUTE_FIELDS:
        return True
    suggested_lower = suggested.lower()
    if suggested_lower in source:
        return True
    tokens = [token for token in re.findall(r"[a-z0-9]+", suggested_lower) if token not in {"eg", "e"}]
    if not tokens:
        return False
    return all(token in source for token in tokens)


def _changed_value_for_field(
    changed_fields: dict[str, Optional[str]],
    field_name: Optional[str],
) -> Optional[str]:
    """Find a rewrite suggestion that matches an issue field name."""
    if not field_name:
        return None
    aliases = {field_name, _canonical_field_name(field_name)}
    if not field_name.startswith(ATTRIBUTE_FIELD_PREFIX):
        canonical = _canonical_field_name(field_name)
        if canonical and canonical not in PRODUCT_REWRITE_FIELDS:
            aliases.add(f"{ATTRIBUTE_FIELD_PREFIX}{canonical}")
    for key, value in changed_fields.items():
        if key in aliases or _canonical_field_name(key) in aliases:
            return value
    return None


def _sanitize_soft_suggestion(
    field_name: Optional[str],
    suggested_value: Optional[str],
    source: str,
    changed_fields: dict[str, Optional[str]],
) -> Optional[str]:
    """Keep a soft suggested_value only when it is supported by source facts.

    If the model suggestion invents facts, fall back to the rewrite for the
    same field so thin-content cards still get an Apply fix when possible.
    """
    candidate = suggested_value
    if candidate and _introduces_new_numbers(candidate, source):
        candidate = None
    if candidate and not _suggestion_supported_by_source(field_name, candidate, source):
        candidate = None
    if candidate:
        return candidate
    fallback = _changed_value_for_field(changed_fields, field_name)
    if not fallback:
        return None
    if _introduces_new_numbers(fallback, source):
        return None
    if not _suggestion_supported_by_source(field_name, fallback, source):
        return None
    return fallback


def _parse_soft_extra_issue_type(raw: object) -> Optional[IssueType]:
    """Map an LLM issue_type; drop retired types; unknown labels become ai_inferred."""
    text = str(raw or "").strip().lower()
    if not text:
        return IssueType.AI_INFERRED
    for issue_type in IssueType:
        if issue_type.value == text:
            if issue_type in RETIRED_SOFT_ISSUE_TYPES:
                return None
            return issue_type
    return IssueType.AI_INFERRED


def _is_valid_soft_issue(_issue_type: IssueType, field_name: Optional[str]) -> bool:
    """Return True when field_name is a product field Accept/Edit can apply to."""
    name = (field_name or "").strip()
    if not name:
        return False
    canonical = _canonical_field_name(name)
    if canonical in PRODUCT_REWRITE_FIELDS:
        return True
    if canonical == "attributes":
        return True
    if name.startswith(ATTRIBUTE_FIELD_PREFIX):
        return bool(canonical)
    return canonical in FACT_ATTRIBUTE_FIELDS or canonical in LEGACY_ATTRIBUTE_FIELDS


def _coerce_severity(raw: object) -> IssueSeverity:
    """Map an LLM severity string to IssueSeverity."""
    text = str(raw or "").strip().lower()
    for severity in IssueSeverity:
        if severity.value == text:
            return severity
    return IssueSeverity.LOW


def _default_soft_severity(issue_type: IssueType, raw: object) -> IssueSeverity:
    """Prefer model severity; fall back by soft issue type."""
    if raw is not None and str(raw).strip():
        return _coerce_severity(raw)
    defaults = {
        IssueType.ATTRIBUTE_CONTRADICTION: IssueSeverity.HIGH,
        IssueType.THIN_CONTENT: IssueSeverity.MEDIUM,
        IssueType.ATTRIBUTE_NOT_IN_COPY: IssueSeverity.LOW,
        IssueType.MISSING_ATTRIBUTES: IssueSeverity.LOW,
    }
    return defaults.get(issue_type, IssueSeverity.LOW)


def _current_field_value(product: Product, field_name: str) -> Optional[str]:
    """Read the live product value for a rewrite/issue field name."""
    if field_name in PRODUCT_REWRITE_FIELDS:
        return _stringify(getattr(product, field_name, None))
    if field_name.startswith(ATTRIBUTE_FIELD_PREFIX):
        attr_key = field_name[len(ATTRIBUTE_FIELD_PREFIX):]
        return _stringify((product.attributes or {}).get(attr_key))
    canonical = _canonical_field_name(field_name)
    if canonical in PRODUCT_REWRITE_FIELDS:
        return _stringify(getattr(product, canonical, None))
    if canonical in LEGACY_ATTRIBUTE_FIELDS or canonical in FACT_ATTRIBUTE_FIELDS:
        return _stringify((product.attributes or {}).get(canonical))
    return None


def _polish_issue_description(
    field_name: str,
    field_reasons: dict[str, Any],
) -> str:
    """Build reviewer copy for a polish-only rewrite suggestion."""
    candidates = [
        field_name,
        _canonical_field_name(field_name),
    ]
    if field_name.startswith(ATTRIBUTE_FIELD_PREFIX):
        candidates.append(field_name[len(ATTRIBUTE_FIELD_PREFIX):])
    for key in candidates:
        reason = field_reasons.get(key)
        if reason is not None and str(reason).strip():
            return str(reason).strip()
    label = _canonical_field_name(field_name).replace("_", " ") or "field"
    return f"Suggested improvement for {label}."


def persist_product_analysis(
    db: Session,
    product: Product,
    job_id: int,
    sanitized_fields: dict[str, Optional[str]],
    field_reasons: dict[str, Any],
    extra_issues: list[Any],
) -> None:
    """Store AI field changes as reviewable issues. Does not update product fields.

    Attach rewrite suggestions to overlapping open issues when possible. Soft
    quality findings become AI-sourced issues. Polish-only rewrites (improved
    fields with no matching issue) are stored as low-severity ai_inferred
    suggestions so merchants can Accept the ready-to-use values.

    job_id is retained for call-site compatibility; issues are product-scoped.
    """
    _ = job_id
    reasons = field_reasons if isinstance(field_reasons, dict) else {}

    # Replace prior AI polish/soft-quality issues so a re-run does not stack duplicates.
    db.query(DataIssue).filter(
        DataIssue.product_id == product.id,
        DataIssue.issue_type.in_(list(AI_SOFT_ISSUE_TYPES)),
        DataIssue.suggestion_source == SuggestionSource.AI.value,
        DataIssue.resolved == False,  # noqa: E712
        DataIssue.review_status == ReviewStatus.PENDING.value,
    ).delete(synchronize_session=False)

    changed_fields: dict[str, Optional[str]] = {}

    for field_name, suggested in sanitized_fields.items():
        if field_name.lower() == "sku":
            continue
        original = _current_field_value(product, field_name)

        # Only fields the model actually improved are worth attaching.
        if _values_match(original, suggested):
            continue
        changed_fields[field_name] = suggested

    open_issues = db.query(DataIssue).filter(
        DataIssue.product_id == product.id,
        DataIssue.resolved == False,  # noqa: E712
    ).all()

    for field_name, suggested in changed_fields.items():
        overlapping = next(
            (
                issue for issue in open_issues
                if _fields_overlap(issue.field_name, field_name)
            ),
            None,
        )
        if overlapping:
            overlapping.suggested_value = suggested
            if not overlapping.suggestion_source:
                overlapping.suggestion_source = SuggestionSource.RULE.value

    source = _source_blob(product)
    for raw_issue in extra_issues:
        if not isinstance(raw_issue, dict):
            continue
        field_name = str(raw_issue.get("field_name") or "").strip() or None
        description = str(raw_issue.get("description") or "").strip()
        if not description:
            continue
        issue_type = _parse_soft_extra_issue_type(raw_issue.get("issue_type"))
        if issue_type is None:
            continue
        if not _is_valid_soft_issue(issue_type, field_name):
            continue
        actual_value = _stringify(raw_issue.get("actual_value"))
        suggested_value = _sanitize_soft_suggestion(
            field_name,
            _stringify(raw_issue.get("suggested_value")),
            source,
            changed_fields,
        )
        # Attach to same-type or hard rule issues. Do not swallow typed soft
        # findings into polish-only AI_INFERRED rows on the same field.
        overlapping = next(
            (
                issue for issue in open_issues
                if _fields_overlap(issue.field_name, field_name)
                and (
                    issue.issue_type == issue_type
                    or (issue.suggestion_source or "") == SuggestionSource.RULE.value
                )
            ),
            None,
        )
        if overlapping:
            if suggested_value and not overlapping.suggested_value:
                overlapping.suggested_value = suggested_value
            continue
        extra = DataIssue(
            product_id=product.id,
            issue_type=issue_type,
            severity=_default_soft_severity(issue_type, raw_issue.get("severity")),
            description=description,
            field_name=field_name,
            actual_value=actual_value,
            suggested_value=suggested_value,
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        )
        db.add(extra)
        open_issues.append(extra)

    # Polish-only rewrites: ready-to-use suggestions with no prior issue on the field.
    for field_name, suggested in changed_fields.items():
        if suggested is None or not str(suggested).strip():
            continue
        if any(_fields_overlap(issue.field_name, field_name) for issue in open_issues):
            continue
        polish = DataIssue(
            product_id=product.id,
            issue_type=IssueType.AI_INFERRED,
            severity=IssueSeverity.LOW,
            description=_polish_issue_description(field_name, reasons),
            field_name=field_name,
            actual_value=_current_field_value(product, field_name),
            suggested_value=suggested,
            suggestion_source=SuggestionSource.AI.value,
            review_status=ReviewStatus.PENDING.value,
        )
        db.add(polish)
        open_issues.append(polish)

    db.commit()
    refresh_product_status(db, product.id)


def analyze_product_with_payload(
    db: Session,
    product: Product,
    job_id: int,
    payload: dict[str, Any],
) -> None:
    """Persist a parsed LLM payload for one product."""
    sanitized = sanitize_rewrite(product, payload["rewrite"])
    persist_product_analysis(
        db,
        product,
        job_id,
        sanitized,
        payload.get("field_reasons") or {},
        payload.get("extra_issues") or [],
    )


def request_product_rewrite(product: Product, open_issues: list[DataIssue]) -> dict[str, Any]:
    """Call the configured LLM and parse the ingest rewrite JSON."""
    raw = chat_completion(
        messages=[
            {"role": "system", "content": REWRITE_SYSTEM_PROMPT},
            {"role": "user", "content": build_ingest_prompt(product, open_issues)},
        ],
        temperature=settings.GROQ_INGEST_TEMPERATURE,
        max_tokens=settings.GROQ_INGEST_MAX_TOKENS,
    )
    return parse_ingest_payload(raw)


def _set_products_ai_status(
    db,
    product_ids: list[int],
    status: str,
) -> None:
    """Bulk-update ai_analysis_status for the given product IDs."""
    if not product_ids:
        return
    db.query(Product).filter(Product.id.in_(product_ids)).update(
        {Product.ai_analysis_status: status},
        synchronize_session=False,
    )


def run_ingestion_ai_job(job_id: int, product_ids: list[int]) -> None:
    """Analyze each product in a finished parse job. Opens its own DB session."""
    db = SessionLocal()
    try:
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if not job:
            logger.error("Ingestion AI job %s not found", job_id)
            return

        analyzed = 0
        errors = 0
        unique_ids = list(dict.fromkeys(product_ids))
        failed_skus: list[str] = []

        if not settings.active_llm_api_key:
            key_env = settings.active_llm_api_key_env
            job.status = "completed_with_ai_errors"
            job.ai_analyzed_rows = 0
            job.ai_error_count = len(unique_ids)
            job.error_message = (
                (job.error_message or "")
                + f" AI analysis skipped: {key_env} is not configured."
            ).strip()
            job.completed_at = datetime.utcnow()
            _set_products_ai_status(db, unique_ids, AiAnalysisStatus.FAILED.value)
            db.commit()
            logger.warning("Ingestion AI job %s skipped: %s is empty", job_id, key_env)
            return

        for index, product_id in enumerate(unique_ids):
            product = db.query(Product).filter(Product.id == product_id).first()
            if not product:
                errors += 1
                continue
            try:
                product.ai_analysis_status = AiAnalysisStatus.ANALYZING.value
                db.commit()

                if index > 0 and settings.GROQ_BATCH_DELAY_MS > 0:
                    time.sleep(settings.GROQ_BATCH_DELAY_MS / 1000)
                open_issues = db.query(DataIssue).filter(
                    DataIssue.product_id == product.id,
                    DataIssue.resolved == False,  # noqa: E712
                ).all()
                payload = request_product_rewrite(product, open_issues)
                analyze_product_with_payload(db, product, job_id, payload)

                try:
                    generate_content_for_product(
                        db=db,
                        product_id=product.id,
                        tone="professional",
                        include_seo=True,
                    )
                except Exception as seo_exc:
                    logger.warning(
                        "SEO content generation failed for product %s in job %s: %s",
                        product.id,
                        job_id,
                        seo_exc,
                    )

                product.ai_analysis_status = AiAnalysisStatus.DONE.value
                analyzed += 1
            except Exception as exc:
                errors += 1
                product.ai_analysis_status = AiAnalysisStatus.FAILED.value
                sku_label = product.sku or str(product_id)
                if len(failed_skus) < MAX_RECORDED_AI_FAILURES:
                    failed_skus.append(sku_label)
                logger.warning(
                    "AI analysis failed for product %s in job %s: %s",
                    product_id,
                    job_id,
                    exc,
                )

            job.ai_analyzed_rows = analyzed
            job.ai_error_count = errors
            db.commit()

        if failed_skus:
            extra = f" AI analysis failed for SKU(s): {', '.join(failed_skus)}."
            if errors > len(failed_skus):
                extra += f" And {errors - len(failed_skus)} more."
            job.error_message = ((job.error_message or "") + extra).strip()

        remaining = (
            db.query(Product)
            .filter(
                Product.id.in_(unique_ids),
                Product.ai_analysis_status.in_(
                    [AiAnalysisStatus.PENDING.value, AiAnalysisStatus.ANALYZING.value]
                ),
            )
            .all()
        )
        for leftover in remaining:
            leftover.ai_analysis_status = AiAnalysisStatus.FAILED.value

        job.status = "completed" if errors == 0 else "completed_with_ai_errors"
        job.issues_found = _count_open_issues_for_products(db, unique_ids)
        job.completed_at = datetime.utcnow()
        db.commit()
        logger.info(
            "Ingestion AI job %s finished: analyzed=%s errors=%s",
            job_id,
            analyzed,
            errors,
        )
    except Exception as exc:
        logger.error("Ingestion AI job %s crashed: %s", job_id, exc)
        job = db.query(IngestionJob).filter(IngestionJob.id == job_id).first()
        if job:
            job.status = "completed_with_ai_errors"
            job.error_message = (job.error_message or "") + f" AI analysis failed: {exc}"
            job.completed_at = datetime.utcnow()
            db.query(Product).filter(
                Product.id.in_(list(dict.fromkeys(product_ids))),
                Product.ai_analysis_status.in_(
                    [AiAnalysisStatus.PENDING.value, AiAnalysisStatus.ANALYZING.value]
                ),
            ).update(
                {Product.ai_analysis_status: AiAnalysisStatus.FAILED.value},
                synchronize_session=False,
            )
            db.commit()
    finally:
        db.close()


# =============================================================================
# "Give a Thought" — Free-Text AI Product Update
# =============================================================================

THOUGHT_SYSTEM_PROMPT = (
    "You are a catalog data editor. Given a full product row and a merchant's "
    "instruction, return ONLY the fields that need changing as a JSON object. "
    "Use only facts already in the product data — never invent specs, prices, "
    "or attributes that are not present. Keep unchanged fields out of the response."
)


def build_thought_prompt(product: Product, user_prompt: str) -> str:
    """Build an LLM prompt for a free-text merchant instruction on one product.

    Only WooCommerce-exportable fields are included so the AI never proposes
    changes to fields (e.g. seo_title) that are absent from the CSV export.
    """
    payload = {
        "sku": product.sku,
        "title": product.title,
        "description": product.generated_description or product.description,
        "category": product.category,
        "brand": product.brand,
        "price": product.price,
        "currency": product.currency,
        "stock": getattr(product, "stock", None),
        "in_stock": getattr(product, "in_stock", True),
        "image_url": getattr(product, "image_url", None),
        "attributes": product.attributes or {},
    }
    return f"""You are editing a single product for an e-commerce merchant.

MERCHANT INSTRUCTION:
{user_prompt}

STRICT RULES:
1. Apply the merchant's instruction to the product data below.
2. Return ONLY fields whose values actually change — do not return unchanged fields.
3. Never invent specifications, measurements, materials, prices, or attributes not
   present in the product JSON.
4. For each changed field, explain WHY it changed (keep it short, 1-2 sentences).
5. VALID FIELD NAMES (WooCommerce export fields only):
   - title        → WooCommerce "Name"
   - description  → WooCommerce "Description" and "Short description"
   - category     → WooCommerce "Categories"
   - brand        → WooCommerce "Brands"
   - price        → WooCommerce "Regular price" (normalize only, do not invent)
   - stock        → WooCommerce "Stock" (integer, do not invent)
   - in_stock     → WooCommerce "In stock?" (true/false)
   - image_url    → WooCommerce "Images" (only if present in product data)
   - attribute:<key>  → WooCommerce "Attribute N" columns (e.g. attribute:color)
   DO NOT propose changes to seo_title, seo_keywords, or any field not listed above.
6. If the instruction cannot be applied safely without inventing facts, return
   an empty "changes" array and explain in "error".

Return JSON with this exact shape:
{{
  "changes": [
    {{
      "field": "description",
      "before": "current value here",
      "after": "improved value here",
      "reason": "Why this changed"
    }}
  ],
  "error": null
}}

Product JSON:
{json.dumps(payload, default=str, ensure_ascii=True)}
"""


def run_thought_rewrite(product: Product, user_prompt: str) -> dict:
    """Call the LLM with a merchant free-text instruction and return structured diffs.

    Returns a dict with:
      - changes: list of {{ field, before, after, reason }}
      - error: optional string if the AI declined or failed
    """
    raw = chat_completion(
        messages=[
            {"role": "system", "content": THOUGHT_SYSTEM_PROMPT},
            {"role": "user", "content": build_thought_prompt(product, user_prompt)},
        ],
        temperature=0.4,
        max_tokens=1500,
    )
    try:
        data = _extract_json_object(raw)
    except Exception:
        return {"changes": [], "error": "Could not parse AI response."}

    changes = data.get("changes") or []
    error = data.get("error") or None

    # Sanitize — strip any change that invents new numbers
    source = _source_blob(product)
    safe_changes = []
    for item in changes:
        if not isinstance(item, dict):
            continue
        field = str(item.get("field") or "").strip()
        after = str(item.get("after") or "").strip()
        before = str(item.get("before") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not field or not after:
            continue
        # Block invented numbers for fact-sensitive fields
        canonical = field.replace("attribute:", "").lower()
        if canonical in FACT_ATTRIBUTE_FIELDS and _introduces_new_numbers(after, source):
            continue

        # Hard allowlist: only WooCommerce-exported fields are returned.
        # Attribute fields pass via the "attribute:" prefix convention.
        WOO_ALLOWED = frozenset({
            "title", "description", "category", "brand",
            "price", "stock", "in_stock", "image_url",
        })
        if not field.startswith("attribute:") and field not in WOO_ALLOWED:
            continue

        safe_changes.append({
            "field": field,
            "before": before,
            "after": after,
            "reason": reason,
        })

    return {"changes": safe_changes, "error": error}
