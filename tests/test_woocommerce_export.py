"""
CatalogIQ — WooCommerce Product CSV mapping tests.
"""

import csv
from io import StringIO

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.schemas import Product, ProductStatus
from app.services import product_service, woocommerce_export_service


@pytest.fixture
def db_session():
    """Provide an isolated in-memory catalog with two products."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    active = Product(
        sku="SKU-001",
        title="Nike Air Max 90 Running Shoes",
        description="The Nike Air Max 90 is a classic running shoe with visible Air cushioning.",
        generated_description="SEO-ready Nike Air Max 90 description with White color and size 10.",
        category="Footwear",
        brand="Nike",
        price=129.99,
        currency="USD",
        status=ProductStatus.ACTIVE,
        attributes={"color": "White", "size": "10", "material": "Synthetic Mesh", "weight": "0.8kg"},
    )
    draft = Product(
        sku="SKU-002",
        title="Draft Camera",
        description="A camera",
        category="Electronics",
        brand="Canon",
        price=2499.0,
        currency="USD",
        status=ProductStatus.DRAFT,
        attributes={"color": "Black", "weight": "598g"},
    )
    session.add_all([active, draft])
    session.commit()
    yield session
    session.close()


def _rows(csv_text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(StringIO(csv_text)))


class TestWooCommerceMapping:
    """Map CatalogIQ products onto WooCommerce importer columns."""

    def test_active_product_uses_generated_description_and_is_published(self, db_session):
        product = db_session.query(Product).filter(Product.sku == "SKU-001").one()
        csv_text = woocommerce_export_service.build_woocommerce_csv([product])
        row = _rows(csv_text)[0]

        assert row["Type"] == "simple"
        assert row["SKU"] == "SKU-001"
        assert row["Name"] == "Nike Air Max 90 Running Shoes"
        assert row["Published"] == "1"
        assert row["Description"].startswith("SEO-ready")
        assert row["Regular price"] == "129.99"
        assert row["Categories"] == "Footwear"
        assert row["Brands"] == "Nike"
        assert row["Weight (kg)"] == "0.8"
        assert row["Attribute 1 name"] == "color"
        assert row["Attribute 1 value(s)"] == "White"
        assert row["Attribute 2 name"] == "size"
        assert row["Attribute 3 name"] == "material"

    def test_draft_is_unpublished_and_grams_convert_to_kg(self, db_session):
        product = db_session.query(Product).filter(Product.sku == "SKU-002").one()
        csv_text = woocommerce_export_service.build_woocommerce_csv([product])
        row = _rows(csv_text)[0]

        assert row["Published"] == "0"
        assert row["Description"] == "A camera"
        assert row["Weight (kg)"] == "0.598"
        assert "Attribute 2 name" not in row or row.get("Attribute 2 name") == ""

    def test_short_description_clips_long_copy(self):
        product = Product(
            sku="LONG-1",
            title="Long copy",
            description=" ".join(["word"] * 80),
            status=ProductStatus.ACTIVE,
            attributes={},
        )
        row = woocommerce_export_service.product_to_row(product, max_attributes=0)
        assert len(row["Short description"]) <= 153
        assert row["Short description"].endswith("...")

    def test_export_query_respects_status_filter(self, db_session):
        products = product_service.list_products_for_export(
            db_session, status=ProductStatus.ACTIVE
        )
        assert [item.sku for item in products] == ["SKU-001"]
