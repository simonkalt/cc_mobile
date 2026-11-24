"""Tests for OpenAI model resolution and sunset aliases."""
from __future__ import annotations

import pytest

from app.utils.llm_token_limits import (
    OPENAI_SUNSET_REPLACEMENT,
    resolve_openai_model,
    uses_openai_max_completion_tokens,
)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("gpt-5", OPENAI_SUNSET_REPLACEMENT),
        ("gpt-5-mini", OPENAI_SUNSET_REPLACEMENT),
        ("o3", OPENAI_SUNSET_REPLACEMENT),
        ("o3-pro", OPENAI_SUNSET_REPLACEMENT),
        ("gpt-5.6-sol", OPENAI_SUNSET_REPLACEMENT),
        ("gpt-5.2", "gpt-5.5"),
        ("gpt-6.2-sol", OPENAI_SUNSET_REPLACEMENT),
        ("gpt-4.1", "gpt-4.1"),
    ],
)
def test_resolve_openai_model(raw, expected):
    assert resolve_openai_model(raw) == expected


def test_uses_max_completion_tokens_for_gpt_62():
    assert uses_openai_max_completion_tokens("gpt-6.2-sol") is True