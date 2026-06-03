"""Short-lived OAuth code handoff for native Android when ccmobile:// is not delivered."""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

_HANDOFF_TTL_SECONDS = 600
_lock = threading.Lock()
_store: dict[str, "_HandoffEntry"] = {}


@dataclass(frozen=True)
class OAuthNativeHandoff:
    provider: str
    code: Optional[str] = None
    error: Optional[str] = None
    error_description: Optional[str] = None


@dataclass
class _HandoffEntry:
    provider: str
    code: Optional[str]
    error: Optional[str]
    error_description: Optional[str]
    expires_at: float


def _purge_expired(now: float) -> None:
    expired = [k for k, v in _store.items() if v.expires_at <= now]
    for key in expired:
        _store.pop(key, None)


def store_oauth_native_handoff(
    *,
    state: str,
    provider: str,
    code: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None,
) -> None:
    """Remember OAuth callback params until the app polls by state (Android fallback)."""
    key = (state or "").strip()
    if not key:
        return
    now = time.time()
    entry = _HandoffEntry(
        provider=provider,
        code=code,
        error=error,
        error_description=error_description,
        expires_at=now + _HANDOFF_TTL_SECONDS,
    )
    with _lock:
        _purge_expired(now)
        _store[key] = entry
    logger.info(
        "OAuth native handoff stored provider=%s state_prefix=%s has_code=%s has_error=%s",
        provider,
        key[:4],
        bool(code),
        bool(error),
    )


def consume_oauth_native_handoff(state: str, provider: str) -> Optional[OAuthNativeHandoff]:
    """One-time read; returns None when not ready or state unknown."""
    key = (state or "").strip()
    if not key:
        return None
    now = time.time()
    with _lock:
        _purge_expired(now)
        entry = _store.pop(key, None)
    if not entry:
        return None
    if entry.provider != provider:
        logger.warning(
            "OAuth handoff provider mismatch state_prefix=%s expected=%s got=%s",
            key[:4],
            provider,
            entry.provider,
        )
        return None
    return OAuthNativeHandoff(
        provider=entry.provider,
        code=entry.code,
        error=entry.error,
        error_description=entry.error_description,
    )
