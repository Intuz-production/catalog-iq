"""
CatalogIQ — WooCommerce Product CSV Export

Maps catalog products to the WooCommerce Product CSV importer format
for simple products.
"""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Optional

from app.models.schemas import Product, ProductStatus

PREFERRED_ATTRIBUTE_KEYS = ("color", "size", "material")
WEIGHT_ATTRIBUTE_KEYS = {"weight", "weight_kg"}
SHORT_DESCRIPTION_LIMIT = 150

BASE_COLUMNS = [
    "Type",
    "SKU",
    "Name",
    "Published",
    "Is featured?",
    "Visibility in catalog",
    "Short description",
    "Description",
    "Tax status",
    "In stock?",
    "Weight (kg)",
    "Allow customer reviews?",
    "Regular price",
    "Categories",
    "Brands",
    "Images",
    "Stock",
    "Parent",
]


def _stringify(value: Any) -> str:
    """Return a CSV-safe string, treating None as empty."""
    if value is None:
        return ""
    return str(value).strip()


def _full_description(product: Product) -> str:
    """Prefer generated SEO copy when present, else the catalog description."""
    generated = _stringify(product.generated_description)
    if generated:
        return generated
    return _stringify(product.description)


def _short_description(full_description: str) -> str:
    """Trim a description to a WooCommerce short-description length."""
    text = " ".join(full_description.split())
    if len(text) <= SHORT_DESCRIPTION_LIMIT:
        return text
    clipped = text[:SHORT_DESCRIPTION_LIMIT].rsplit(" ", 1)[0]
    return clipped.rstrip(".,;:") + "..."


def _published_flag(status: Optional[ProductStatus]) -> str:
    """WooCommerce Published is 1 only for active catalog products."""
    if status == ProductStatus.ACTIVE:
        return "1"
    return "0"


def _in_stock_flag(in_stock: Optional[bool]) -> str:
    """WooCommerce In stock? is 1 unless explicitly marked out of stock."""
    return "0" if in_stock is False else "1"


def _parse_weight_kg(raw: Any) -> str:
    """Convert stored weight strings such as 0.8kg or 598g into kilograms."""
    text = _stringify(raw)
    if not text:
        return ""
    match = re.search(r"([\d.]+)\s*(kg|g)?", text, flags=re.IGNORECASE)
    if not match:
        return text
    amount = float(match.group(1))
    unit = (match.group(2) or "kg").lower()
    if unit == "g":
        amount = amount / 1000.0
    formatted = f"{amount:.3f}".rstrip("0").rstrip(".")
    return formatted


def _attribute_items(product: Product) -> list[tuple[str, str]]:
    """Flatten product attributes, putting common Woo fields first."""
    attributes = dict(product.attributes or {})
    items: list[tuple[str, str]] = []
    seen: set[str] = set()

    for key in PREFERRED_ATTRIBUTE_KEYS:
        value = _stringify(attributes.get(key))
        if value:
            items.append((key, value))
            seen.add(key)

    extras = []
    for key, raw in attributes.items():
        normalized = str(key).strip()
        if not normalized or normalized.lower() in WEIGHT_ATTRIBUTE_KEYS:
            continue
        if normalized in seen:
            continue
        value = _stringify(raw)
        if not value:
            continue
        extras.append((normalized, value))
        seen.add(normalized)

    extras.sort(key=lambda item: item[0].lower())
    return items + extras


def _weight_value(product: Product) -> str:
    """Read weight from known attribute keys."""
    attributes = product.attributes or {}
    for key in ("weight", "weight_kg"):
        if attributes.get(key):
            return _parse_weight_kg(attributes.get(key))
    return ""


def _attribute_headers(max_attributes: int) -> list[str]:
    """Build WooCommerce Attribute N column names for the widest product."""
    headers: list[str] = []
    for index in range(1, max_attributes + 1):
        headers.extend([
            f"Attribute {index} name",
            f"Attribute {index} value(s)",
            f"Attribute {index} visible",
            f"Attribute {index} global",
        ])
    return headers


def product_to_row(product: Product, max_attributes: int) -> dict[str, str]:
    """Map one catalog product to a WooCommerce CSV row."""
    description = _full_description(product)
    attributes = _attribute_items(product)
    row = {
        "Type": "simple",
        "SKU": _stringify(product.sku),
        "Name": _stringify(product.title),
        "Published": _published_flag(product.status),
        "Is featured?": "0",
        "Visibility in catalog": "visible",
        "Short description": _short_description(description),
        "Description": description,
        "Tax status": "taxable",
        "In stock?": _in_stock_flag(getattr(product, "in_stock", None)),
        "Weight (kg)": _weight_value(product),
        "Allow customer reviews?": "1",
        "Regular price": _stringify(product.price),
        "Categories": _stringify(product.category),
        "Brands": _stringify(product.brand),
        "Images": _stringify(getattr(product, "image_url", None)),
        "Stock": _stringify(getattr(product, "stock", None)),
        "Parent": "",
    }

    for index in range(1, max_attributes + 1):
        name_key = f"Attribute {index} name"
        value_key = f"Attribute {index} value(s)"
        visible_key = f"Attribute {index} visible"
        global_key = f"Attribute {index} global"
        if index <= len(attributes):
            name, value = attributes[index - 1]
            row[name_key] = name
            row[value_key] = value
            row[visible_key] = "1"
            row[global_key] = "1"
        else:
            row[name_key] = ""
            row[value_key] = ""
            row[visible_key] = ""
            row[global_key] = ""

    return row


def build_woocommerce_csv(products: list[Product]) -> str:
    """Serialize products to a WooCommerce Product CSV string."""
    attribute_counts = [_attribute_items(product) for product in products]
    max_attributes = max((len(items) for items in attribute_counts), default=0)
    fieldnames = BASE_COLUMNS + _attribute_headers(max_attributes)

    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, lineterminator="\n")
    writer.writeheader()
    for product in products:
        writer.writerow(product_to_row(product, max_attributes))
    return buffer.getvalue()
