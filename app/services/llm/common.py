"""
Shared helpers for LLM provider adapters.
"""

from __future__ import annotations

import logging
import re
import time
from typing import Callable, Optional, TypeVar

from app.config import settings

logger = logging.getLogger("catalogiq.llm")

T = TypeVar("T")

REASONING_MODEL_MARKERS: tuple[str, ...] = (
    "gpt-oss",
    "qwen3",
    "minimax-m2",
)


def is_reasoning_model(model: str) -> bool:
    """Return True when the model uses a reasoning token budget (Groq-style)."""
    model_lower = model.lower()
    return any(marker in model_lower for marker in REASONING_MODEL_MARKERS)


def strip_reasoning_markers(text: str) -> str:
    """Remove reasoning blocks accidentally included in visible model output."""
    think_pattern = re.compile(
        rf"{'<' + 'think' + '>'}.*?{'<' + '/' + 'think' + '>'}",
        flags=re.DOTALL | re.IGNORECASE,
    )
    cleaned = think_pattern.sub("", text)
    cleaned = re.sub(
        r"<redacted_reasoning>.*?</redacted_reasoning>",
        "",
        cleaned,
        flags=re.DOTALL | re.IGNORECASE,
    )
    return cleaned.strip()


def with_retries(operation: Callable[[], T], *, label: str = "LLM") -> T:
    """Run an operation with exponential backoff using shared LLM retry settings."""
    last_error: Optional[Exception] = None

    for attempt in range(settings.GROQ_MAX_RETRIES):
        try:
            return operation()
        except Exception as exc:
            last_error = exc
            if attempt >= settings.GROQ_MAX_RETRIES - 1:
                break

            delay = settings.GROQ_RETRY_DELAY_SECONDS * (2 ** attempt)
            logger.warning(
                "%s API attempt %s/%s failed, retrying in %ss: %s",
                label,
                attempt + 1,
                settings.GROQ_MAX_RETRIES,
                delay,
                exc,
            )
            time.sleep(delay)

    raise last_error or RuntimeError(f"{label} API call failed without an error.")
