"""
CatalogIQ — Shared Utility Functions

Common helpers used across multiple services.
"""

import re
import logging
from typing import Any, Optional

logger = logging.getLogger("catalogiq.helpers")

PLACEHOLDER_VALUES: frozenset[str] = frozenset({
    "n/a", "na", "none", "null", "nil", "-", "--", "tbd", "unknown",
    "not available", "not applicable", "description not available",
    "no description", "missing", "empty", "undefined", "nan",
})

KNOWN_COLORS: tuple[str, ...] = (
    "black", "white", "blue", "red", "green", "grey", "gray",
    "yellow", "pink", "purple", "orange", "brown", "navy",
    "silver", "gold", "beige", "tan",
)

KNOWN_MATERIALS: tuple[str, ...] = (
    "cotton", "nylon", "polyester", "leather", "wool", "silk", "mesh",
    "stainless steel", "aluminum", "aluminium", "synthetic", "plastic",
    "cast iron", "polycarbonate", "primeknit", "eucalyptus",
)

SIZE_LABEL_TERMS: dict[str, tuple[str, ...]] = {
    "XS": ("extra small", "x-small", " xs ", "xs "),
    "S": (" small", "size s", " sm "),
    "M": (" medium", "size m", " med "),
    "L": (" large", "size l", " lg "),
    "XL": ("extra large", "x-large", "xlarge", " xl "),
    "XXL": ("xx-large", "xx large", "2xl", " xxl "),
    "XXXL": ("xxx-large", "3xl", " xxxl "),
}


def normalize_text(text: str) -> str:
    """Normalize text by stripping whitespace and standardizing spacing.

    Args:
        text: Raw text to normalize.

    Returns:
        Cleaned text with consistent spacing.
    """
    if not text:
        return ""
    text = text.strip()
    text = re.sub(r"\s+", " ", text)
    return text


def is_placeholder_value(value: Optional[str]) -> bool:
    """Return True when a supplier value should be treated as empty.

    Args:
        value: Raw field or attribute value.

    Returns:
        True if the value is blank or a known placeholder token.
    """
    if value is None:
        return True

    normalized = normalize_text(str(value)).lower().strip(".,;:-")
    if not normalized:
        return True

    return normalized in PLACEHOLDER_VALUES


def clean_text_field(value: Optional[str]) -> Optional[str]:
    """Normalize a text field and drop placeholder supplier values.

    Args:
        value: Raw text from a CSV column.

    Returns:
        Cleaned text, or None when empty/placeholder.
    """
    cleaned = normalize_text(str(value or ""))
    if not cleaned or is_placeholder_value(cleaned):
        return None
    return cleaned


def normalize_attribute_value(key: str, value: str) -> str:
    """Normalize a product attribute value based on its key.

    Standardizes common attribute variations (sizes, colors, materials)
    into consistent values.

    Args:
        key: Attribute name (e.g., "size", "color", "material").
        value: Raw attribute value to normalize.

    Returns:
        Normalized attribute value.
    """
    if not value:
        return ""

    value = normalize_text(value).lower()

    # Size normalization
    size_mappings: dict[str, str] = {
        "xs": "XS", "extra small": "XS", "x-small": "XS",
        "s": "S", "small": "S", "sm": "S",
        "m": "M", "medium": "M", "med": "M",
        "l": "L", "large": "L", "lg": "L",
        "xl": "XL", "extra large": "XL", "x-large": "XL",
        "xxl": "XXL", "2xl": "XXL", "xx-large": "XXL",
        "xxxl": "XXXL", "3xl": "XXXL",
    }

    # Color normalization
    color_mappings: dict[str, str] = {
        "blk": "Black", "bk": "Black",
        "wht": "White", "wh": "White",
        "blu": "Blue", "bl": "Blue",
        "rd": "Red",
        "grn": "Green", "gn": "Green",
        "gry": "Grey", "gray": "Grey",
        "ylw": "Yellow", "yl": "Yellow",
        "pnk": "Pink", "pk": "Pink",
        "prpl": "Purple",
        "org": "Orange",
        "brn": "Brown",
        "navy": "Navy Blue",
    }

    # Material normalization
    material_mappings: dict[str, str] = {
        "ss": "Stainless Steel", "stainless": "Stainless Steel",
        "alum": "Aluminum", "aluminium": "Aluminum",
        "poly": "Polyester",
        "ctn": "Cotton",
        "nyl": "Nylon",
        "lth": "Leather", "lthr": "Leather",
        "wl": "Wool",
        "syn": "Synthetic",
    }

    if key.lower() in ("size", "sizes"):
        return size_mappings.get(value, value.upper())
    elif key.lower() in ("color", "colour", "colors"):
        return color_mappings.get(value, value.title())
    elif key.lower() in ("material", "materials", "fabric"):
        return material_mappings.get(value, value.title())

    return value.title()


def _find_mentioned_sizes(text: str) -> set[str]:
    """Find normalized size codes mentioned in catalog copy."""
    padded = f" {text.lower()} "
    mentioned: set[str] = set()

    for size_code, terms in SIZE_LABEL_TERMS.items():
        for term in terms:
            if term in padded:
                mentioned.add(size_code)
                break

    return mentioned


def _find_mentioned_materials(text: str) -> set[str]:
    """Find material keywords mentioned in catalog copy."""
    text_lower = text.lower()
    return {material for material in KNOWN_MATERIALS if material in text_lower}


def detect_contradictions(
    title: str,
    description: str,
    attributes: dict[str, Any],
) -> list[dict[str, str]]:
    """Detect contradictions between product title, description, and attributes.

    Checks for mismatches in color, size, material, and brand mentions
    between different product data fields.

    Args:
        title: Product title text.
        description: Product description text.
        attributes: Normalized product attributes dictionary.

    Returns:
        List of contradiction details with field, expected, actual, and severity.
    """
    contradictions: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()
    combined_text = f"{title_lower} {desc_lower}".strip()

    def add_contradiction(
        field: str,
        source: str,
        expected: str,
        actual: str,
        severity: str = "high",
    ) -> None:
        key = (field.lower(), source, actual)
        if key in seen:
            return
        seen.add(key)
        contradictions.append({
            "field": field,
            "source": source,
            "expected": expected,
            "actual": actual,
            "severity": severity,
        })

    for key, value in attributes.items():
        if not value or key.lower() in ("weight", "dimensions", "upc", "ean"):
            continue

        value_lower = str(value).lower()
        field_lower = key.lower()

        if field_lower in ("color", "colour"):
            for check_field, check_text in [("title", title_lower), ("description", desc_lower)]:
                if not check_text or value_lower in check_text:
                    continue

                for color in KNOWN_COLORS:
                    if color in check_text and color != value_lower:
                        add_contradiction(
                            key,
                            check_field,
                            str(value),
                            f"'{color}' found in {check_field}",
                        )
                        break

            if combined_text and value_lower not in combined_text:
                if not any(color in combined_text for color in KNOWN_COLORS):
                    add_contradiction(
                        key,
                        "title/description",
                        str(value),
                        f"Color '{value}' not mentioned in title or description",
                        severity="medium",
                    )

        elif field_lower in ("size", "sizes"):
            size_code = str(value).upper()
            mentioned_sizes = _find_mentioned_sizes(combined_text)
            conflicting_sizes = {size for size in mentioned_sizes if size != size_code}
            if conflicting_sizes:
                add_contradiction(
                    key,
                    "title/description",
                    str(value),
                    f"Conflicting size terms found: {', '.join(sorted(conflicting_sizes))}",
                )

        elif field_lower in ("material", "materials", "fabric"):
            mentioned_materials = _find_mentioned_materials(combined_text)
            if mentioned_materials and value_lower not in mentioned_materials:
                conflicting = sorted(
                    material for material in mentioned_materials if material != value_lower
                )
                if conflicting:
                    add_contradiction(
                        key,
                        "title/description",
                        str(value),
                        f"Conflicting materials found: {', '.join(conflicting)}",
                    )
            elif combined_text and value_lower not in combined_text:
                if not mentioned_materials:
                    add_contradiction(
                        key,
                        "title/description",
                        str(value),
                        f"Material '{value}' not mentioned in title or description",
                        severity="medium",
                    )

        elif field_lower == "brand" and value_lower:
            if title_lower and value_lower not in title_lower:
                title_first_word = title_lower.split()[0] if title_lower.split() else ""
                if title_first_word and title_first_word != value_lower and len(title_first_word) > 2:
                    add_contradiction(
                        key,
                        "title",
                        str(value),
                        f"Title starts with '{title_first_word}' instead of brand",
                    )

    return contradictions


def calculate_content_score(description: str) -> dict[str, Any]:
    """Calculate a content quality score for a product description.

    Evaluates word count, sentence structure, keyword density,
    and readability indicators.

    Args:
        description: Product description to evaluate.

    Returns:
        Dictionary with score (0-100) and quality indicators.
    """
    if not description or is_placeholder_value(description):
        return {"score": 0, "label": "Missing", "word_count": 0, "issues": ["No description"]}

    words = description.split()
    word_count = len(words)
    sentences = [s.strip() for s in re.split(r"[.!?]", description) if s.strip()]
    sentence_count = len(sentences)

    issues: list[str] = []
    score = 100

    # Word count scoring
    if word_count < 20:
        score -= 40
        issues.append("Very thin content (under 20 words)")
    elif word_count < 50:
        score -= 20
        issues.append("Short content (under 50 words)")
    elif word_count > 300:
        score -= 10
        issues.append("Content may be too long (over 300 words)")

    # Sentence count
    if sentence_count < 2:
        score -= 15
        issues.append("Too few sentences")

    # Check for generic/duplicate patterns
    generic_patterns = [
        "high quality", "best quality", "buy now", "click here",
        "lorem ipsum", "description not available", "n/a",
    ]
    for pattern in generic_patterns:
        if pattern in description.lower():
            score -= 10
            issues.append(f"Generic/placeholder text detected: '{pattern}'")

    score = max(0, min(100, score))

    if score >= 80:
        label = "Good"
    elif score >= 50:
        label = "Fair"
    elif score >= 20:
        label = "Poor"
    else:
        label = "Critical"

    return {
        "score": score,
        "label": label,
        "word_count": word_count,
        "sentence_count": sentence_count,
        "issues": issues,
    }


def chunk_list(items: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of a given size.

    Args:
        items: List to split.
        chunk_size: Maximum items per chunk.

    Returns:
        List of sublists.
    """
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
