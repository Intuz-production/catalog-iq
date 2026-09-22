"""
CatalogIQ — Content Generation Tests

Tests for LLM prompt building and content generation logic.
"""

import pytest
from unittest.mock import MagicMock, patch
from app.services.content_service import (
    _build_description_prompt,
    _build_seo_prompt,
    _extract_json_object,
    _normalize_seo_fields,
    _validate_generated_description,
    normalize_tone,
)
from app.services.llm.common import is_reasoning_model, strip_reasoning_markers
from app.services.llm.groq_adapter import build_chat_completion_kwargs
from app.config import settings


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


class TestReasoningModelSupport:
    """Tests for Groq reasoning-model request handling."""

    def test_detects_reasoning_models(self):
        assert is_reasoning_model("openai/gpt-oss-120b") is True
        assert is_reasoning_model("llama-3.3-70b-versatile") is False

    def test_builds_reasoning_model_kwargs(self):
        kwargs = build_chat_completion_kwargs(
            "openai/gpt-oss-120b",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            max_tokens=500,
        )
        assert "max_completion_tokens" in kwargs
        assert kwargs["max_completion_tokens"] >= 500
        assert kwargs["reasoning_format"] == settings.GROQ_REASONING_FORMAT
        assert kwargs["reasoning_effort"] == settings.GROQ_REASONING_EFFORT
        assert "max_tokens" not in kwargs

    def test_builds_standard_model_kwargs(self):
        kwargs = build_chat_completion_kwargs(
            "llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": "Hello"}],
            temperature=0.7,
            max_tokens=500,
        )
        assert kwargs["max_tokens"] == 500
        assert "max_completion_tokens" not in kwargs

    def test_strip_reasoning_markers(self):
        think_open = "<" + "think" + ">"
        think_close = "</" + "think" + ">"
        text = f"{think_open}internal thoughts{think_close} Final product copy here."
        assert strip_reasoning_markers(text) == "Final product copy here."


class TestContentValidation:
    """Tests for content generation validation helpers."""

    def test_normalize_tone_accepts_valid_values(self):
        assert normalize_tone("professional") == "professional"
        assert normalize_tone("CASUAL") == "casual"

    def test_normalize_tone_rejects_invalid_values(self):
        with pytest.raises(ValueError):
            normalize_tone("playful")

    def test_extract_json_object_from_code_block(self):
        data = _extract_json_object('```json\n{"seo_title": "Test", "seo_keywords": "a, b"}\n```')
        assert data["seo_title"] == "Test"

    def test_extract_json_object_from_embedded_text(self):
        data = _extract_json_object('Here is the result: {"seo_title": "Title", "seo_keywords": "kw"}')
        assert data["seo_keywords"] == "kw"

    def test_validate_generated_description_rejects_empty(self):
        with pytest.raises(ValueError):
            _validate_generated_description("")

    def test_validate_generated_description_rejects_too_short(self):
        with pytest.raises(ValueError):
            _validate_generated_description("Too short text.")

    def test_validate_generated_description_accepts_valid_copy(self):
        description = " ".join(["word"] * settings.GROQ_MIN_DESCRIPTION_WORDS)
        cleaned, word_count, warnings = _validate_generated_description(description)
        assert cleaned == description
        assert word_count == settings.GROQ_MIN_DESCRIPTION_WORDS

    def test_normalize_seo_fields_truncates_long_title(self):
        long_title = "A" * (settings.SEO_TITLE_MAX_LENGTH + 10)
        seo_title, seo_keywords, warnings = _normalize_seo_fields({
            "seo_title": long_title,
            "seo_keywords": "alpha, beta",
        })
        assert seo_title is not None
        assert len(seo_title) == settings.SEO_TITLE_MAX_LENGTH
        assert seo_keywords == "alpha, beta"
        assert any("truncated" in warning.lower() for warning in warnings)


class TestLlmFacadeRouting:
    """Tests for env-driven provider selection."""

    def test_routes_to_openai_adapter(self):
        from app.services import llm as llm_pkg

        with patch.object(llm_pkg.settings, "LLM_PROVIDER", "openai"), patch.object(
            llm_pkg.openai_adapter,
            "chat_completion",
            return_value="ok",
        ) as mock_openai, patch.object(
            llm_pkg.groq_adapter,
            "chat_completion",
        ) as mock_groq:
            result = llm_pkg.chat_completion(
                messages=[{"role": "user", "content": "hi"}],
                temperature=0.5,
                max_tokens=100,
            )
            assert result == "ok"
            mock_openai.assert_called_once()
            mock_groq.assert_not_called()

    def test_rejects_unknown_provider(self):
        from app.services import llm as llm_pkg

        with patch.object(llm_pkg.settings, "LLM_PROVIDER", "anthropic"):
            with pytest.raises(ValueError, match="Unsupported LLM_PROVIDER"):
                llm_pkg.chat_completion(
                    messages=[{"role": "user", "content": "hi"}],
                    temperature=0.5,
                    max_tokens=100,
                )
