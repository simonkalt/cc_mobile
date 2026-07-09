"""
OpenRouter client — single OpenAI-compatible gateway for cloud LLMs.

App-facing model IDs (gpt-5.5, claude-haiku-4-5, …) stay unchanged for the
mobile client, registry, and llm_counts. This module maps them to OpenRouter
slugs and issues chat.completions calls.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from app.core.config import settings
from app.utils.grok_models import GROK_MODEL_ID, is_grok_model
from app.utils.llm_token_limits import max_output_tokens_for_model

logger = logging.getLogger(__name__)

try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

# Canonical app model id → OpenRouter slug (verified against /api/v1/models)
OPENROUTER_MODEL_MAP: dict[str, str] = {
    "gpt-5.5": "openai/gpt-5.5",
    "gpt-5.2": "openai/gpt-5.5",
    "gpt-4.1": "openai/gpt-4.1",
    "claude-haiku-4-5": "anthropic/claude-haiku-4.5",
    "claude-haiku-4-5-20251001": "anthropic/claude-haiku-4.5",
    "claude-sonnet-4-6": "anthropic/claude-sonnet-4.6",
    "claude-sonnet-4-20250514": "anthropic/claude-sonnet-4.6",
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    GROK_MODEL_ID: "x-ai/grok-4.3",
    "grok-4-fast-reasoning": "x-ai/grok-4.3",
    "xai.grok-4.3": "x-ai/grok-4.3",
}

# Display-name / alias → canonical app id (before OpenRouter mapping)
_DISPLAY_ALIASES: dict[str, str] = {
    "chatgpt": "gpt-5.5",
    "claude": "claude-sonnet-4-6",
    "claude haiku": "claude-haiku-4-5",
    "gemini": "gemini-2.5-flash",
    "grok": GROK_MODEL_ID,
}


def use_openrouter() -> bool:
    """True when cloud LLMs should go through OpenRouter."""
    return (settings.LLM_PROVIDER or "openrouter").strip().lower() != "direct"


def openrouter_configured() -> bool:
    return bool((settings.OPENROUTER_API_KEY or "").strip()) and OPENAI_AVAILABLE


def canonicalize_app_model(model: str) -> str:
    """Normalize display names / aliases to a registry-style app model id."""
    raw = (model or "").strip()
    if not raw:
        return "gpt-5.5"
    lower = raw.lower()
    if lower in _DISPLAY_ALIASES:
        return _DISPLAY_ALIASES[lower]
    # Legacy OpenAI id still tracked/mapped as gpt-5.5
    if raw == "gpt-5.2" or lower == "gpt-5.2":
        return "gpt-5.5"
    if raw in OPENROUTER_MODEL_MAP:
        return raw
    if is_grok_model(raw):
        return GROK_MODEL_ID
    if lower.startswith("gpt-"):
        if raw in ("gpt-4.1", "gpt-5.5"):
            return raw
        return "gpt-5.5"
    if "haiku" in lower:
        return "claude-haiku-4-5"
    if "sonnet" in lower or lower.startswith("claude"):
        return "claude-sonnet-4-6"
    if "gemini" in lower:
        return "gemini-2.5-flash"
    return raw


def to_openrouter_model(app_model: str) -> str:
    """Map an app-facing model id to an OpenRouter slug."""
    canonical = canonicalize_app_model(app_model)
    slug = OPENROUTER_MODEL_MAP.get(canonical)
    if slug:
        return slug
    # Already an OpenRouter-style id (provider/model)
    if "/" in canonical:
        return canonical
    raise ValueError(f"No OpenRouter mapping for model: {app_model!r}")


def get_openrouter_client() -> Any:
    if not OPENAI_AVAILABLE:
        raise ImportError("openai package is required for OpenRouter calls")
    key = (settings.OPENROUTER_API_KEY or "").strip()
    if not key:
        raise ValueError("OPENROUTER_API_KEY is not set")
    return OpenAI(
        api_key=key,
        base_url=settings.OPENROUTER_BASE_URL,
    )


def openrouter_chat(
    *,
    app_model: str,
    messages: list[dict[str, Any]],
    max_tokens: Optional[int] = None,
    temperature: Optional[float] = None,
    timeout: Optional[float] = None,
) -> str:
    """
    Call OpenRouter chat.completions and return assistant text content.

    Uses OpenAI-compatible ``max_tokens`` for all models (no per-provider
    max_completion_tokens branching).
    """
    canonical = canonicalize_app_model(app_model)
    slug = to_openrouter_model(canonical)
    if max_tokens is None:
        max_tokens = max_output_tokens_for_model(canonical)

    client = get_openrouter_client()
    kwargs: dict[str, Any] = {
        "model": slug,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if temperature is not None:
        kwargs["temperature"] = temperature
    if timeout is not None:
        kwargs["timeout"] = timeout

    logger.info("OpenRouter chat: app_model=%s slug=%s max_tokens=%s", canonical, slug, max_tokens)
    response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content
    return content if content is not None else ""
