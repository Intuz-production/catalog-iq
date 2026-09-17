"""
CatalogIQ — Competitor Monitoring Tests

Tests for scraping utilities and price analysis logic.
"""

import pytest

from app.config import get_marketplace_settings
from app.config.marketplaces import load_marketplace_settings
from bs4 import BeautifulSoup

from app.utils.scraper import (
    extract_price,
    build_search_url,
    get_marketplace_config,
    ScrapedProduct,
    is_bot_or_blocked_page,
    _extract_amazon_title,
    _extract_amazon_price,
    _extract_walmart_price,
    _normalize_walmart_price_text,
    build_browser_headers,
)


@pytest.fixture(autouse=True)
def us_marketplace_env(monkeypatch):
    """Use US marketplace defaults for scraper tests."""
    monkeypatch.setenv("SCRAPE_REGION", "us")
    get_marketplace_settings.cache_clear()
    yield
    get_marketplace_settings.cache_clear()


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

    def test_flipkart_url(self, monkeypatch):
        monkeypatch.setenv("SCRAPE_REGION", "in")
        get_marketplace_settings.cache_clear()
        url = build_search_url("iphone case", "flipkart")
        assert "flipkart.com" in url
        assert "iphone+case" in url

    def test_unknown_source_raises_error(self):
        with pytest.raises(KeyError):
            build_search_url("test product", "unknown")


class TestMarketplaceSettings:
    """Tests for env-driven marketplace configuration."""

    def test_us_region_defaults(self):
        region, sources, marketplaces = load_marketplace_settings(region="us")
        assert region == "us"
        assert sources == ["amazon", "walmart"]
        assert marketplaces["amazon"].search_url_template.endswith("amazon.com/s?k={query}")
        assert marketplaces["walmart"].currency == "USD"
        assert "ebay" not in marketplaces
        assert "target" not in marketplaces

    def test_in_region_defaults(self):
        region, sources, marketplaces = load_marketplace_settings(region="in")
        assert region == "in"
        assert sources == ["amazon", "flipkart"]
        assert "amazon.in" in marketplaces["amazon"].base_url
        assert marketplaces["flipkart"].currency == "INR"

    def test_get_marketplace_config(self):
        config = get_marketplace_config("amazon")
        assert config.id == "amazon"
        assert "{query}" in config.search_url_template


class TestScraperHelpers:
    """Tests for HTTP helpers and HTML parsers."""

    def test_build_browser_headers_includes_chrome_131(self):
        headers = build_browser_headers("https://www.amazon.com/")
        assert "Chrome/131" in headers["User-Agent"]
        assert headers["Referer"] == "https://www.amazon.com/"

    def test_is_bot_or_blocked_page_detects_small_walmart_response(self):
        assert is_bot_or_blocked_page("<html>captcha</html>", "walmart") is True
        assert is_bot_or_blocked_page(
            "<html>" + ("x" * 60_000) + "data-item-id</html>",
            "walmart",
        ) is False
        assert is_bot_or_blocked_page(
            "<html>captcha" + ("x" * 60_000) + "data-item-id</html>",
            "walmart",
        ) is False

    def test_extract_amazon_title_from_title_recipe(self):
        html = """
        <div data-component-type='s-search-result'>
          <div data-cy='title-recipe'>Nike Air Max 90 Men's Shoes</div>
        </div>
        """
        item = BeautifulSoup(html, "html.parser").select_one("div[data-component-type='s-search-result']")
        assert _extract_amazon_title(item) == "Nike Air Max 90 Men's Shoes"

    def test_extract_amazon_price_from_fractional_price(self):
        html = """
        <div data-component-type='s-search-result'>
          <span class="a-price-symbol">$</span>
          <span class="a-price-whole">129</span>
          <span class="a-price-fraction">99</span>
        </div>
        """
        item = BeautifulSoup(html, "html.parser").select_one("div[data-component-type='s-search-result']")
        price, currency = _extract_amazon_price(item, "USD")
        assert price == 129.99
        assert currency == "USD"

    def test_extract_amazon_price_detects_inr(self):
        html = """
        <div data-component-type='s-search-result'>
          <span class="a-offscreen">₹47,945.00</span>
        </div>
        """
        item = BeautifulSoup(html, "html.parser").select_one("div[data-component-type='s-search-result']")
        price, currency = _extract_amazon_price(item, "USD")
        assert price == 47945.0
        assert currency == "INR"

    def test_normalize_walmart_compact_price(self):
        assert _normalize_walmart_price_text("$13495") == 134.95
        assert _normalize_walmart_price_text("$129.95") == 129.95

    def test_extract_walmart_price_from_characteristic_mantissa(self):
        html = """
        <div data-item-id="1">
          <span class="price-characteristic">118</span>
          <span class="price-mantissa">70</span>
        </div>
        """
        item = BeautifulSoup(html, "html.parser").select_one("div[data-item-id]")
        assert _extract_walmart_price(item) == 118.70


class TestScrapedProduct:
    """Tests for the ScrapedProduct data structure."""

    def test_default_values(self):
        product = ScrapedProduct()
        assert product.title is None
        assert product.price is None
        assert product.currency == "USD"
        assert product.in_stock is True
        assert product.source == ""
        assert product.is_simulated is False
        assert product.match_score is None

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
