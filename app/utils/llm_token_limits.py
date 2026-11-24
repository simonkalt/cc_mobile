"""
Per-model output token ceilings for non-streaming LLM API calls.

``LLM_MAX_OUTPUT_TOKENS`` is a global preference (often raised for Grok) but
each provider enforces its own maximum; applying it blindly breaks other models.
"""
from __future__ import annotations

from app.core.config import settings
from app.utils.grok_models import GROK_MODEL_ID, is_grok_model

# OpenAI API models retiring 2026-12-11 (email); route to replacement.
RETIRED_OPENAI_MODEL_IDS: frozenset[str] = frozenset(
    {
        "gpt-5",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-5-pro",
        "o3",
        "o3-pro",
    }
)
OPENAI_SUNSET_REPLACEMENT = "gpt-6.2-sol"

# App / mobile ids that should use GPT-6.2 Sol on OpenRouter.
_OPENAI_62_SOL_ALIASES: frozenset[str] = frozenset(
    {
        "gpt-5.6-sol",
        "gpt-5.6-luna",
    }
)

# Provider limits for synchronous (non-streaming) cover-letter generation.
_MODEL_OUTPUT_TOKEN_CEILINGS: dict[str, int] = {
    "gpt-5.5": 128_000,
    "gpt-6.2-sol": 128_000,
    "gpt-4.1": 16_384,
    "claude-haiku-4-5": 8_192,
    "claude-haiku-4-5-20251001": 8_192,
    "claude-sonnet-4-6": 8_192,
    "claude-sonnet-4-20250514": 8_192,
    "gemini-2.5-flash": 8_192,
    GROK_MODEL_ID: 131_072,
}

_DEFAULT_CEILING = 8_192


def resolve_openai_model(model: str, *, fallback: str = "gpt-5.5") -> str:
    """Map legacy / alias OpenAI model ids to a supported model."""
    m = (model or "").strip()
    if not m:
        return fallback
    key = m.lower()
    if key in RETIRED_OPENAI_MODEL_IDS or key in _OPENAI_62_SOL_ALIASES:
        return OPENAI_SUNSET_REPLACEMENT
    if key == OPENAI_SUNSET_REPLACEMENT:
        return OPENAI_SUNSET_REPLACEMENT
    if m == "gpt-5.2":
        return "gpt-5.5"
    if m in ("gpt-4.1", "gpt-5.5"):
        return m
    if key.startswith("gpt-"):
        return m
    return fallback


def _ceiling_for_model(model: str) -> int:
    m = (model or "").strip()
    if not m:
        return _DEFAULT_CEILING
    if is_grok_model(m):
        return _MODEL_OUTPUT_TOKEN_CEILINGS.get(GROK_MODEL_ID, 131_072)
    key = m.lower()
    if key in _MODEL_OUTPUT_TOKEN_CEILINGS:
        return _MODEL_OUTPUT_TOKEN_CEILINGS[key]
    if key.startswith("gpt-6."):
        return _MODEL_OUTPUT_TOKEN_CEILINGS.get(
            OPENAI_SUNSET_REPLACEMENT, 128_000
        )
    if key.startswith("gpt-5."):
        return _MODEL_OUTPUT_TOKEN_CEILINGS["gpt-5.5"]
    if key.startswith("gpt-"):
        return _MODEL_OUTPUT_TOKEN_CEILINGS["gpt-4.1"]
    if "haiku" in key:
        return _MODEL_OUTPUT_TOKEN_CEILINGS["claude-haiku-4-5"]
    if "sonnet" in key or key.startswith("claude-"):
        return _MODEL_OUTPUT_TOKEN_CEILINGS["claude-sonnet-4-6"]
    if "gemini" in key:
        return _MODEL_OUTPUT_TOKEN_CEILINGS["gemini-2.5-flash"]
    return _DEFAULT_CEILING


def max_output_tokens_for_model(model: str) -> int:
    """Return ``min(LLM_MAX_OUTPUT_TOKENS, provider ceiling)`` for *model*."""
    return min(settings.LLM_MAX_OUTPUT_TOKENS, _ceiling_for_model(model))


def uses_openai_max_completion_tokens(model: str) -> bool:
    """GPT-5.x+ models use ``max_completion_tokens`` instead of ``max_tokens``."""
    m = resolve_openai_model(model).lower()
    return m.startswith("gpt-5.") or m.startswith("gpt-6.")
