"""
CatalogIQ — Competitor Monitoring Tests

Tests for scraping utilities and price analysis logic.
"""

import pytest
from app.utils.scraper import extract_price, build_search_url, ScrapedProduct


class TestExtractPrice:
    """Tests for price extraction from text."""

    def test_simple_price(self):
        assert extract_price("19.99") == 19.99

    def test_dollar_sign(self):
        assert extract_price("$129.99") == 129.99

    def test_comma_separator(self):
        assert extract_price("1,299.00") == 1299.00

    def test_rupee_symbol(self):
        result = extract_price("Rs. 45,999")
        assert result == 45999.0

    def test_empty_string(self):
        assert extract_price("") is None

    def test_none_input(self):
        assert extract_price(None) is None

    def test_no_number(self):
        assert extract_price("out of stock") is None


class TestBuildSearchUrl:
    """Tests for marketplace search URL construction."""

    def test_amazon_url(self):
        url = build_search_url("nike shoes", "amazon")
        assert "amazon.com" in url
        assert "nike+shoes" in url

    def test_walmart_url(self):
        url = build_search_url("samsung tv", "walmart")
        assert "walmart.com" in url
        assert "samsung+tv" in url

    def test_flipkart_url(self):
        url = build_search_url("iphone case", "flipkart")
        assert "flipkart.com" in url
        assert "iphone+case" in url

    def test_unknown_source_defaults_to_amazon(self):
        url = build_search_url("test product", "unknown")
        assert "amazon.com" in url


class TestScrapedProduct:
    """Tests for the ScrapedProduct data structure."""

    def test_default_values(self):
        product = ScrapedProduct()
        assert product.title is None
        assert product.price is None
        assert product.currency == "USD"
        assert product.in_stock is True
        assert product.source == ""

    def test_custom_values(self):
        product = ScrapedProduct(
            title="Test Product",
            price=29.99,
            currency="INR",
            in_stock=False,
            url="https://example.com",
            source="flipkart",
        )
        assert product.title == "Test Product"
        assert product.price == 29.99
        assert product.currency == "INR"
        assert product.in_stock is False
        assert product.source == "flipkart"
