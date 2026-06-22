"""
CatalogIQ — Shared Utility Functions

Common helpers used across multiple services.
"""

import re
import logging
from typing import Any, Optional

logger = logging.getLogger("catalogiq.helpers")


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
        List of contradiction details with field, expected, and actual values.
    """
    contradictions: list[dict[str, str]] = []
    title_lower = (title or "").lower()
    desc_lower = (description or "").lower()

    for key, value in attributes.items():
        if not value or key.lower() in ("weight", "dimensions", "upc", "ean"):
            continue

        value_lower = str(value).lower()

        # Check if attribute value contradicts title
        if key.lower() in ("color", "colour") and value_lower:
            # Look for any color mention in title that differs
            for check_field, check_text in [("title", title_lower), ("description", desc_lower)]:
                if check_text and value_lower not in check_text:
                    # Check if a different color from our known colors is mentioned
                    known_colors = [
                        "black", "white", "blue", "red", "green", "grey", "gray",
                        "yellow", "pink", "purple", "orange", "brown", "navy",
                        "silver", "gold", "beige", "tan",
                    ]
                    for color in known_colors:
                        if color in check_text and color != value_lower:
                            contradictions.append({
                                "field": key,
                                "source": check_field,
                                "expected": str(value),
                                "actual": f"'{color}' found in {check_field}",
                            })
                            break

        elif key.lower() == "brand" and value_lower:
            if title_lower and value_lower not in title_lower:
                # Check if a different brand-like word is at the start of title
                title_first_word = title_lower.split()[0] if title_lower.split() else ""
                if title_first_word and title_first_word != value_lower and len(title_first_word) > 2:
                    contradictions.append({
                        "field": key,
                        "source": "title",
                        "expected": str(value),
                        "actual": f"Title starts with '{title_first_word}' instead of brand",
                    })

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
    if not description:
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
