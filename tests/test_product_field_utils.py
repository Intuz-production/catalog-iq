"""Unit tests for shared product field read/write helpers."""

from app.models.schemas import Product
from app.services.product_field_utils import (
    apply_catalog_field_value,
    description_storage_column,
    effective_description_text,
    normalize_product_update_data,
    resolve_attribute_key,
)


def test_effective_description_prefers_generated_copy():
    product = Product(
        sku="SKU-1",
        title="Item",
        description="Catalog",
        generated_description="SEO copy",
    )
    assert effective_description_text(product) == "SEO copy"
    assert description_storage_column(product) == "generated_description"


def test_apply_description_updates_visible_column():
    product = Product(
        sku="SKU-2",
        title="Item",
        description="Catalog",
        generated_description="SEO copy",
    )
    apply_catalog_field_value(product, "description", "New visible text")
    assert product.generated_description == "New visible text"
    assert product.description == "Catalog"


def test_normalize_product_update_routes_description():
    product = Product(
        sku="SKU-3",
        title="Item",
        generated_description="Existing",
    )
    data = normalize_product_update_data(product, {"description": "Updated"})
    assert data == {"generated_description": "Updated"}
    assert "description" not in data


def test_resolve_attribute_key_is_case_insensitive():
    attributes = {"color": "White"}
    assert resolve_attribute_key(attributes, "Color") == "color"
