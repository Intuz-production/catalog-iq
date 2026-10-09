"""
CatalogIQ — Product field read/write helpers

Single place for which column stores visible description copy and how
accepted issue fixes / API updates are applied to products.
"""

from typing import Any, Optional

from app.models.schemas import Product

ATTRIBUTE_FIELD_PREFIX = "attributes."
LEGACY_ATTRIBUTE_FIELDS = frozenset({"color", "size", "material", "weight", "upc"})
CATALOG_REWRITE_FIELDS = frozenset({
    "title", "description", "category", "brand", "price",
    "stock", "in_stock", "image_url",
})


def effective_description_text(product: Product) -> Optional[str]:
    """Description text shown in the UI and WooCommerce export."""
    generated = product.generated_description
    if generated is not None and str(generated).strip():
        return str(generated).strip()
    description = product.description
    if description is not None and str(description).strip():
        return str(description).strip()
    return None


def description_storage_column(product: Product) -> str:
    """Product column to update when merchants edit visible description copy."""
    if product.generated_description:
        return "generated_description"
    return "description"


def resolve_attribute_key(attributes: dict, attr_key: str) -> str:
    """Match attribute keys case-insensitively to existing product attributes."""
    target = (attr_key or "").strip()
    if not target:
        return target
    for key in attributes:
        if key.lower() == target.lower():
            return key
    return target


def normalize_product_update_data(product: Product, update_data: dict[str, Any]) -> dict[str, Any]:
    """Route description updates to the column the product detail UI displays."""
    data = dict(update_data)
    if (
        "description" in data
        and "generated_description" not in data
        and product.generated_description
    ):
        data["generated_description"] = data.pop("description")
    return data


def apply_catalog_field_value(
    product: Product,
    field_name: str,
    value: Optional[str],
) -> None:
    """Write an accepted issue fix or edited value onto a product field.

    Raises:
        ValueError: If the field cannot be rewritten or the value is invalid.
    """
    normalized_name = (field_name or "").strip()
    if not normalized_name:
        raise ValueError("Field name is required.")
    if normalized_name.lower() == "sku":
        raise ValueError("SKU cannot be rewritten.")

    if normalized_name in CATALOG_REWRITE_FIELDS:
        if normalized_name == "title":
            cleaned = (value or "").strip()
            if not cleaned:
                raise ValueError("Title cannot be empty.")
            product.title = cleaned
            return
        if normalized_name == "price":
            if value is None or str(value).strip() == "":
                product.price = None
                return
            try:
                product.price = float(str(value).strip())
            except ValueError as exc:
                raise ValueError("Price must be a number.") from exc
            return
        if normalized_name == "stock":
            if value is None or str(value).strip() == "":
                product.stock = None
                return
            try:
                product.stock = int(float(str(value).strip()))
            except ValueError as exc:
                raise ValueError("Stock must be an integer.") from exc
            return
        if normalized_name == "in_stock":
            if value is None or str(value).strip() == "":
                product.in_stock = True
                return
            val_str = str(value).strip().lower()
            if val_str in ("false", "0", "no", "outofstock", "out of stock"):
                product.in_stock = False
            else:
                product.in_stock = True
            return
        if normalized_name == "description":
            cleaned = None if value is None else str(value).strip() or None
            column = description_storage_column(product)
            setattr(product, column, cleaned)
            return
        setattr(product, normalized_name, None if value is None else str(value).strip() or None)
        return

    if (
        normalized_name.startswith(ATTRIBUTE_FIELD_PREFIX)
        or normalized_name in LEGACY_ATTRIBUTE_FIELDS
    ):
        attr_key = (
            normalized_name[len(ATTRIBUTE_FIELD_PREFIX):].strip()
            if normalized_name.startswith(ATTRIBUTE_FIELD_PREFIX)
            else normalized_name
        )
        if not attr_key:
            raise ValueError("Attribute field name is required.")
        attributes = dict(product.attributes or {})
        resolved_key = resolve_attribute_key(attributes, attr_key)
        if value is None or str(value).strip() == "":
            attributes.pop(resolved_key, None)
        else:
            attributes[resolved_key] = str(value).strip()
        product.attributes = attributes
        return

    raise ValueError(f"Unknown field '{field_name}'.")
