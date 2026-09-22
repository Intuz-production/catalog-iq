"""
OpenAI chat completions adapter.
"""

from __future__ import annotations

from typing import Any, Optional

from openai import OpenAI

from app.config import settings
from app.services.llm.common import strip_reasoning_markers, with_retries


def _get_client() -> OpenAI:
    """Create and return an OpenAI API client."""
    return OpenAI(api_key=settings.OPENAI_API_KEY)


def _parse_response(response: Any) -> str:
    """Extract message content from an OpenAI chat completion response."""
    choice = response.choices[0]
    message = choice.message
    content = strip_reasoning_markers(message.content or "")

    if content:
        return content

    finish_reason = getattr(choice, "finish_reason", "unknown")
    raise ValueError(
        f"LLM returned an empty response (finish_reason={finish_reason})."
    )


def chat_completion(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    *,
    model: Optional[str] = None,
) -> str:
    """Call OpenAI chat completions and return visible message text."""
    resolved_model = model or settings.LLM_MODEL
    client = _get_client()

    def _call() -> Any:
        return client.chat.completions.create(
            model=resolved_model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    response = with_retries(_call, label="OpenAI")
    return _parse_response(response)
