"""
CatalogIQ — Ingestion Pipeline Tests

Tests for CSV parsing, data normalization, and quality detection.
"""

import pytest
from app.utils.helpers import (
    normalize_text,
    normalize_attribute_value,
    detect_contradictions,
    calculate_content_score,
)


class TestNormalizeText:
    """Tests for text normalization."""

    def test_strips_whitespace(self):
        assert normalize_text("  hello world  ") == "hello world"

    def test_collapses_multiple_spaces(self):
        assert normalize_text("hello   world") == "hello world"

    def test_handles_empty_string(self):
        assert normalize_text("") == ""

    def test_handles_none(self):
        assert normalize_text(None) == ""

    def test_handles_tabs_and_newlines(self):
        assert normalize_text("hello\t\nworld") == "hello world"


class TestNormalizeAttributeValue:
    """Tests for product attribute normalization."""

    def test_size_normalization(self):
        assert normalize_attribute_value("size", "extra small") == "XS"
        assert normalize_attribute_value("size", "sm") == "S"
        assert normalize_attribute_value("size", "medium") == "M"
        assert normalize_attribute_value("size", "lg") == "L"
        assert normalize_attribute_value("size", "extra large") == "XL"

    def test_color_normalization(self):
        assert normalize_attribute_value("color", "blk") == "Black"
        assert normalize_attribute_value("color", "wht") == "White"
        assert normalize_attribute_value("color", "blu") == "Blue"

    def test_material_normalization(self):
        assert normalize_attribute_value("material", "ss") == "Stainless Steel"
        assert normalize_attribute_value("material", "ctn") == "Cotton"
        assert normalize_attribute_value("material", "nyl") == "Nylon"

    def test_unknown_values_title_cased(self):
        assert normalize_attribute_value("color", "midnight blue") == "Midnight Blue"

    def test_empty_value(self):
        assert normalize_attribute_value("size", "") == ""


class TestDetectContradictions:
    """Tests for contradiction detection between product fields."""

    def test_no_contradictions(self):
        result = detect_contradictions(
            title="Blue Nike Shoes",
            description="These blue shoes are great.",
            attributes={"color": "Blue"},
        )
        assert len(result) == 0

    def test_color_contradiction_in_title(self):
        result = detect_contradictions(
            title="Red Nike Shoes",
            description="",
            attributes={"color": "Blue"},
        )
        assert len(result) >= 1
        assert any(c["field"] == "color" for c in result)

    def test_empty_attributes(self):
        result = detect_contradictions(
            title="Some Product",
            description="A good product",
            attributes={},
        )
        assert len(result) == 0


class TestCalculateContentScore:
    """Tests for content quality scoring."""

    def test_missing_description(self):
        result = calculate_content_score("")
        assert result["score"] == 0
        assert result["label"] == "Missing"

    def test_none_description(self):
        result = calculate_content_score(None)
        assert result["score"] == 0

    def test_thin_content(self):
        result = calculate_content_score("Short text here.")
        assert result["score"] < 80
        assert result["word_count"] == 3

    def test_good_content(self):
        desc = (
            "This premium leather wallet features multiple card slots and a billfold compartment. "
            "Crafted from genuine Italian leather, it offers durability and style. "
            "The slim profile fits comfortably in any pocket while holding all your essentials. "
            "Available in classic brown and black colorways. "
            "Perfect for daily use or as a thoughtful gift."
        )
        result = calculate_content_score(desc)
        assert result["score"] >= 50
        assert result["label"] in ("Good", "Fair")

    def test_generic_content_penalized(self):
        result = calculate_content_score(
            "Buy now this high quality product. Best quality guaranteed. Click here."
        )
        assert result["score"] < 80
