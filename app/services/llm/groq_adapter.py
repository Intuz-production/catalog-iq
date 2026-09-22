"""
Groq chat completions adapter.
"""

from __future__ import annotations

from typing import Any, Optional

from groq import Groq

from app.config import settings
from app.services.llm.common import (
    is_reasoning_model,
    strip_reasoning_markers,
    with_retries,
)


def _get_client() -> Groq:
    """Create and return a Groq API client."""
    return Groq(api_key=settings.GROQ_API_KEY)


def build_chat_completion_kwargs(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    """Build Groq chat completion kwargs for standard and reasoning models."""
    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
    }

    if is_reasoning_model(model):
        kwargs["max_completion_tokens"] = max(max_tokens, settings.GROQ_MAX_COMPLETION_TOKENS)
        kwargs["reasoning_format"] = settings.GROQ_REASONING_FORMAT
        if "gpt-oss" in model.lower():
            kwargs["reasoning_effort"] = settings.GROQ_REASONING_EFFORT
    else:
        kwargs["max_tokens"] = max_tokens

    return kwargs


def _parse_response(response: Any) -> str:
    """Extract message content from a Groq chat completion response."""
    choice = response.choices[0]
    message = choice.message
    content = strip_reasoning_markers(message.content or "")

    if content:
        return content

    finish_reason = getattr(choice, "finish_reason", "unknown")
    reasoning_tokens: Optional[int] = None
    usage = getattr(response, "usage", None)
    if usage is not None:
        details = getattr(usage, "completion_tokens_details", None)
        if details is not None:
            reasoning_tokens = getattr(details, "reasoning_tokens", None)

    hint = ""
    if finish_reason == "length":
        hint = (
            " Token budget was exhausted before visible output was produced. "
            "For reasoning models such as openai/gpt-oss-120b, increase "
            "GROQ_MAX_COMPLETION_TOKENS or use a supported model."
        )
    if reasoning_tokens:
        hint += f" Reasoning tokens used: {reasoning_tokens}."

    raise ValueError(
        f"LLM returned an empty response (finish_reason={finish_reason}).{hint}"
    )


def chat_completion(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    *,
    model: Optional[str] = None,
) -> str:
    """Call Groq chat completions and return visible message text."""
    resolved_model = model or settings.LLM_MODEL
    client = _get_client()
    kwargs = build_chat_completion_kwargs(
        resolved_model,
        messages,
        temperature,
        max_tokens,
    )

    def _call() -> Any:
        return client.chat.completions.create(**kwargs)

    response = with_retries(_call, label="Groq")
    return _parse_response(response)
