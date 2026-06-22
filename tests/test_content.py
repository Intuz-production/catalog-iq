"""
CatalogIQ — Content Generation Tests

Tests for LLM prompt building and content generation logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.content_service import _build_description_prompt, _build_seo_prompt


class TestDescriptionPrompt:
    """Tests for description prompt building."""

    def test_includes_product_title(self):
        product = MagicMock()
        product.title = "Nike Air Max 90"
        product.sku = "SKU-001"
        product.category = "Footwear"
        product.brand = "Nike"
        product.price = 129.99
        product.currency = "USD"
        product.description = "Classic running shoe"
        product.attributes = {"color": "White", "size": "10"}

        prompt = _build_description_prompt(product, "professional")

        assert "Nike Air Max 90" in prompt
        assert "SKU-001" in prompt
        assert "Footwear" in prompt
        assert "Nike" in prompt
        assert "129.99" in prompt
        assert "professional" in prompt

    def test_handles_missing_attributes(self):
        product = MagicMock()
        product.title = "Test Product"
        product.sku = "TEST-001"
        product.category = None
        product.brand = None
        product.price = None
        product.currency = "USD"
        product.description = None
        product.attributes = {}

        prompt = _build_description_prompt(product, "casual")

        assert "Test Product" in prompt
        assert "Not specified" in prompt
        assert "casual" in prompt

    def test_includes_tone(self):
        product = MagicMock()
        product.title = "Test"
        product.sku = "T"
        product.category = "Cat"
        product.brand = "Brand"
        product.price = 10
        product.currency = "USD"
        product.description = None
        product.attributes = {}

        for tone in ["professional", "casual", "luxury", "technical"]:
            prompt = _build_description_prompt(product, tone)
            assert tone in prompt

    def test_strict_rules_included(self):
        product = MagicMock()
        product.title = "Test"
        product.sku = "T"
        product.category = None
        product.brand = None
        product.price = None
        product.currency = "USD"
        product.description = None
        product.attributes = {}

        prompt = _build_description_prompt(product)
        assert "STRICT RULES" in prompt
        assert "Do NOT invent" in prompt


class TestSeoPrompt:
    """Tests for SEO prompt building."""

    def test_includes_product_details(self):
        product = MagicMock()
        product.title = "Sony WH-1000XM5"
        product.category = "Electronics"
        product.brand = "Sony"

        prompt = _build_seo_prompt(product, "Premium headphones with noise canceling.")

        assert "Sony WH-1000XM5" in prompt
        assert "Electronics" in prompt
        assert "seo_title" in prompt
        assert "seo_keywords" in prompt
        assert "JSON" in prompt

    def test_json_format_requested(self):
        product = MagicMock()
        product.title = "Test"
        product.category = "General"
        product.brand = "Test"

        prompt = _build_seo_prompt(product, "A description.")
        assert "JSON" in prompt
