"""
CatalogIQ — Competitor service tests for alerts and matching integration.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.database import Base
from app.models.schemas import (
    Product,
    ProductStatus,
    CompetitorPrice,
    CompetitorAlert,
    CompetitorSource,
    AlertType,
)
from app.services.competitor_service import _analyze_and_alert, _create_or_update_alert
from app.utils.product_match import (
    pick_best_listing,
    score_listing,
    title_similarity,
    is_acceptable_competitor_price,
    infer_listing_currency,
)
from app.utils.scraper import ScrapedProduct


@pytest.fixture
def db_session():
    """Provide an isolated in-memory database session."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    product = Product(
        sku="NIKE-001",
        title="Nike Air Max 90 Running Shoes",
        brand="Nike",
        price=120.0,
        currency="USD",
        status=ProductStatus.ACTIVE,
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    yield session, product
    session.close()


class TestProductMatch:
    """Tests for competitor listing match scoring."""

    def test_title_similarity_prefers_closer_title(self):
        close = title_similarity("Nike Air Max 90", "Nike Air Max 90 Running Shoes Men's")
        far = title_similarity("Nike Air Max 90", "Samsung 55 inch Smart TV")
        assert close > far

    def test_pick_best_listing_chooses_matching_product(self):
        product = Product(
            sku="TEST",
            title="Nike Air Max 90 Running Shoes",
            brand="Nike",
            price=120.0,
            currency="USD",
            status=ProductStatus.ACTIVE,
        )
        listings = [
            ScrapedProduct(title="Random Phone Case", price=9.99, currency="USD", source="amazon"),
            ScrapedProduct(
                title="Nike Air Max 90 Running Shoes Men's Size 10",
                price=115.0,
                currency="USD",
                source="amazon",
            ),
        ]

        best, score = pick_best_listing(product, listings)
        assert best is not None
        assert "Nike Air Max 90" in best.title
        assert score > 0.3

    def test_pick_best_listing_rejects_weak_matches(self):
        product = Product(
            sku="TEST",
            title="Nike Air Max 90 Running Shoes",
            brand="Nike",
            price=120.0,
            currency="USD",
            status=ProductStatus.ACTIVE,
        )
        listings = [
            ScrapedProduct(
                title="Unrelated Kitchen Blender",
                price=9999.0,
                currency="USD",
                source="amazon",
            ),
        ]

        best, score = pick_best_listing(product, listings)
        assert best is None
        assert score < 0.15

    def test_score_listing_includes_brand_bonus(self):
        product = Product(
            sku="TEST",
            title="Air Max 90 Running Shoes",
            brand="Nike",
            price=120.0,
            currency="USD",
            status=ProductStatus.ACTIVE,
        )
        with_brand = ScrapedProduct(
            title="Nike Air Max 90 Running Shoes",
            price=118.0,
            currency="USD",
            source="amazon",
        )
        without_brand = ScrapedProduct(
            title="Air Max 90 Running Shoes",
            price=118.0,
            currency="USD",
            source="amazon",
        )

        assert score_listing(product, with_brand) > score_listing(product, without_brand)


class TestPriceValidation:
    """Tests for competitor price plausibility checks."""

    def test_rejects_implausible_usd_price(self):
        product = Product(
            sku="TEST",
            title="Apple iPad Air",
            brand="Apple",
            price=599.0,
            currency="USD",
            status=ProductStatus.ACTIVE,
        )
        assert is_acceptable_competitor_price(product, 47945.08, "USD") is False

    def test_accepts_inr_price_for_us_product(self):
        product = Product(
            sku="TEST",
            title="Apple iPad Air",
            brand="Apple",
            price=599.0,
            currency="USD",
            status=ProductStatus.ACTIVE,
        )
        assert is_acceptable_competitor_price(product, 47945.0, "INR") is True

    def test_infer_listing_currency_fixes_mislabeled_inr(self):
        product = Product(
            sku="TEST",
            title="Apple iPad Air",
            brand="Apple",
            price=599.0,
            currency="USD",
            status=ProductStatus.ACTIVE,
        )
        currency = infer_listing_currency(47945.0, "USD", product, "USD")
        assert currency == "INR"


class TestCompetitorAlerts:
    """Tests for alert generation, deduplication, and simulated filtering."""

    def test_skips_alerts_for_simulated_results(self, db_session):
        session, product = db_session
        record = CompetitorPrice(
            product_id=product.id,
            source=CompetitorSource.AMAZON,
            competitor_title="[Demo] Nike Shoes",
            competitor_price=90.0,
            competitor_currency="USD",
            in_stock=True,
            is_simulated=True,
        )
        session.add(record)
        session.commit()

        alerts = _analyze_and_alert(session, product, [record])
        assert alerts == []
        assert session.query(CompetitorAlert).count() == 0

    def test_creates_undercut_alert_for_live_results(self, db_session):
        session, product = db_session
        record = CompetitorPrice(
            product_id=product.id,
            source=CompetitorSource.AMAZON,
            competitor_title="Nike Air Max 90",
            competitor_price=100.0,
            competitor_currency="USD",
            in_stock=True,
            is_simulated=False,
            match_score=0.82,
        )
        session.add(record)
        session.commit()

        alerts = _analyze_and_alert(session, product, [record])
        assert len(alerts) == 1
        assert alerts[0].alert_type == AlertType.UNDERCUT

    def test_deduplicates_unacknowledged_alerts(self, db_session):
        session, product = db_session

        first = _create_or_update_alert(
            session,
            product.id,
            AlertType.UNDERCUT,
            CompetitorSource.AMAZON,
            "First undercut alert",
            product.price,
            95.0,
            25.0,
        )
        session.commit()
        assert first is not None

        second = _create_or_update_alert(
            session,
            product.id,
            AlertType.UNDERCUT,
            CompetitorSource.AMAZON,
            "Updated undercut alert",
            product.price,
            90.0,
            30.0,
        )
        session.commit()

        assert second is None
        alerts = session.query(CompetitorAlert).all()
        assert len(alerts) == 1
        assert alerts[0].message == "Updated undercut alert"
        assert alerts[0].competitor_price == 90.0
