"""
Env-driven LLM facade.

Selects Groq, OpenAI, or Gemini based on settings.LLM_PROVIDER and exposes
a single chat_completion(messages, temperature, max_tokens) -> str API.
"""

from __future__ import annotations

from typing import Optional

from app.config import ALLOWED_LLM_PROVIDERS, settings
from . import gemini_adapter, groq_adapter, openai_adapter


def chat_completion(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    *,
    model: Optional[str] = None,
) -> str:
    """Run a chat completion via the configured LLM provider.

    Args:
        messages: OpenAI-style chat messages (role + content).
        temperature: Sampling temperature.
        max_tokens: Max output tokens (provider-specific mapping applied).
        model: Optional model override; defaults to settings.LLM_MODEL.

    Returns:
        Visible assistant text (reasoning markers stripped when present).

    Raises:
        ValueError: If LLM_PROVIDER is unsupported.
    """
    provider = settings.LLM_PROVIDER
    if provider not in ALLOWED_LLM_PROVIDERS:
        allowed = ", ".join(sorted(ALLOWED_LLM_PROVIDERS))
        raise ValueError(
            f"Unsupported LLM_PROVIDER '{provider}'. Allowed values: {allowed}"
        )

    if provider == "openai":
        adapter = openai_adapter.chat_completion
    elif provider == "gemini":
        adapter = gemini_adapter.chat_completion
    else:
        adapter = groq_adapter.chat_completion

    return adapter(
        messages,
        temperature,
        max_tokens,
        model=model or settings.LLM_MODEL,
    )
