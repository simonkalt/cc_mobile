"""
Direct xAI API client for Grok 4.3 (https://api.x.ai/v1/chat/completions).
"""
from __future__ import annotations

import logging
import os
from typing import Any, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

GROK_MODEL_ID = "grok-4.3"
XAI_CHAT_COMPLETIONS_URL = "https://api.x.ai/v1/chat/completions"

LEGACY_GROK_MODEL_IDS = frozenset(
    {
        "grok-4-fast-reasoning",
        "grok-4-fast-reasoning".lower(),
        "xai.grok-4.3",
        "xai.grok-4.3".lower(),
    }
)


def is_grok_model(model: str) -> bool:
    m = (model or "").strip()
    if not m:
        return False
    if m == GROK_MODEL_ID or m.lower() == GROK_MODEL_ID.lower():
        return True
    if m in LEGACY_GROK_MODEL_IDS or m.lower() in LEGACY_GROK_MODEL_IDS:
        return True
    return "grok" in m.lower()


def resolve_grok_api_key() -> Optional[str]:
    key = (settings.XAI_API_KEY or "").strip()
    return key or None


def grok_chat_completions(
    messages: list[dict[str, Any]],
    *,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    timeout: int = 3600,
) -> str:
    """Call Grok via the direct xAI API."""
    try:
        import requests
    except ImportError as exc:
        raise ImportError("requests is required for Grok/xAI calls") from exc

    api_key = resolve_grok_api_key()
    if not api_key:
        raise ValueError("XAI_API_KEY is not set")

    model = (os.getenv("GROK_MODEL_ID") or GROK_MODEL_ID).strip()
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens if max_tokens is not None else settings.LLM_MAX_OUTPUT_TOKENS,
    }
    if temperature is not None:
        payload["temperature"] = temperature

    response = requests.post(
        XAI_CHAT_COMPLETIONS_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    response.raise_for_status()
    result = response.json()
    return result["choices"][0]["message"]["content"]


def resolve_grok_api_key_from_dotenv(project_root: Optional[str] = None) -> Optional[str]:
    """Optional .env fallback (cover letter service parity with other API keys)."""
    key = resolve_grok_api_key()
    if key:
        return key
    try:
        from dotenv import dotenv_values

        if project_root is None:
            project_root = os.path.normpath(
                os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
            )
        env_path = os.path.join(project_root, ".env")
        env_map = dotenv_values(env_path)
        fallback = str(env_map.get("XAI_API_KEY") or "").strip()
        if fallback:
            logger.warning("Using XAI_API_KEY fallback from .env file")
            return fallback
    except Exception as exc:
        logger.debug("Could not load XAI_API_KEY from .env fallback: %s", exc)
    return None
