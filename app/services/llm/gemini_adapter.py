"""
Google Gemini generateContent adapter.
"""

from __future__ import annotations

from typing import Any, Optional

from google import genai
from google.genai import types

from app.config import settings
from app.services.llm.common import strip_reasoning_markers, with_retries


def _get_client() -> genai.Client:
    """Create and return a Gemini API client."""
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _split_messages(
    messages: list[dict[str, str]],
) -> tuple[Optional[str], list[types.Content]]:
    """Map OpenAI-style messages to Gemini system instruction + contents."""
    system_parts: list[str] = []
    contents: list[types.Content] = []

    for message in messages:
        role = (message.get("role") or "user").strip().lower()
        text = message.get("content") or ""
        if role == "system":
            if text.strip():
                system_parts.append(text)
            continue

        gemini_role = "model" if role == "assistant" else "user"
        contents.append(
            types.Content(
                role=gemini_role,
                parts=[types.Part.from_text(text=text)],
            )
        )

    system_instruction = "\n\n".join(system_parts) if system_parts else None
    return system_instruction, contents


def _parse_response(response: Any) -> str:
    """Extract text from a Gemini generate_content response."""
    text = ""
    try:
        text = response.text or ""
    except (AttributeError, ValueError):
        text = ""

    content = strip_reasoning_markers(text)
    if content:
        return content

    raise ValueError("LLM returned an empty response from Gemini.")


def chat_completion(
    messages: list[dict[str, str]],
    temperature: float,
    max_tokens: int,
    *,
    model: Optional[str] = None,
) -> str:
    """Call Gemini generateContent and return visible message text."""
    resolved_model = model or settings.LLM_MODEL
    client = _get_client()
    system_instruction, contents = _split_messages(messages)

    config = types.GenerateContentConfig(
        temperature=temperature,
        max_output_tokens=max_tokens,
        system_instruction=system_instruction,
    )

    def _call() -> Any:
        return client.models.generate_content(
            model=resolved_model,
            contents=contents,
            config=config,
        )

    response = with_retries(_call, label="Gemini")
    return _parse_response(response)
