"""Unit tests for OpenRouter model mapping and provider flags."""
from __future__ import annotations

import pytest

from app.utils.grok_models import GROK_MODEL_ID
from app.utils.openrouter_client import (
    OPENROUTER_MODEL_MAP,
    canonicalize_app_model,
    to_openrouter_model,
)


@pytest.mark.parametrize(
    "app_id,expected_slug",
    [
        ("gpt-5.5", "openai/gpt-5.5"),
        ("gpt-5.2", "openai/gpt-5.5"),
        ("gpt-4.1", "openai/gpt-4.1"),
        ("claude-haiku-4-5", "anthropic/claude-haiku-4.5"),
        ("claude-haiku-4-5-20251001", "anthropic/claude-haiku-4.5"),
        ("claude-sonnet-4-6", "anthropic/claude-sonnet-4.6"),
        ("gemini-2.5-flash", "google/gemini-2.5-flash"),
        (GROK_MODEL_ID, "x-ai/grok-4.3"),
        ("Grok", "x-ai/grok-4.3"),
        ("ChatGPT", "openai/gpt-5.5"),
        ("Claude Haiku", "anthropic/claude-haiku-4.5"),
        ("Gemini", "google/gemini-2.5-flash"),
    ],
)
def test_to_openrouter_model(app_id, expected_slug):
    assert to_openrouter_model(app_id) == expected_slug


@pytest.mark.parametrize(
    "raw,canonical",
    [
        ("ChatGPT", "gpt-5.5"),
        ("Claude Haiku", "claude-haiku-4-5"),
        ("Claude", "claude-sonnet-4-6"),
        ("Gemini", "gemini-2.5-flash"),
        ("Grok", GROK_MODEL_ID),
        ("gpt-5.2", "gpt-5.5"),
    ],
)
def test_canonicalize_app_model(raw, canonical):
    assert canonicalize_app_model(raw) == canonical


def test_registry_models_are_mapped():
    for name in ("gpt-5.5", "claude-haiku-4-5", "gemini-2.5-flash", GROK_MODEL_ID):
        assert name in OPENROUTER_MODEL_MAP
        assert "/" in OPENROUTER_MODEL_MAP[name]
