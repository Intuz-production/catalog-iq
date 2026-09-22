"""
CatalogIQ — Shared Utility Functions

Common helpers used across multiple services.
"""

import re
import logging
from typing import Optional

logger = logging.getLogger("catalogiq.helpers")

PLACEHOLDER_VALUES: frozenset[str] = frozenset({
    "n/a", "na", "none", "null", "nil", "-", "--", "tbd", "unknown",
    "not available", "not applicable", "description not available",
    "no description", "missing", "empty", "undefined", "nan",
})


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


def parse_catalog_price(value: Optional[str]) -> Optional[float]:
    """Parse a supplier price string into a float.

    Args:
        value: Raw price cell text (symbols and thousands separators allowed).

    Returns:
        Parsed price, or None when empty or unreadable.
    """
    cleaned = clean_text_field(value)
    if not cleaned:
        return None

    match = re.search(r"\d[\d,.]*", cleaned)
    if not match:
        return None

    number_text = match.group(0).rstrip(".").replace(",", "")
    try:
        return float(number_text)
    except ValueError:
        return None


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


def chunk_list(items: list, chunk_size: int) -> list[list]:
    """Split a list into chunks of a given size.

    Args:
        items: List to split.
        chunk_size: Maximum items per chunk.

    Returns:
        List of sublists.
    """
    return [items[i : i + chunk_size] for i in range(0, len(items), chunk_size)]
