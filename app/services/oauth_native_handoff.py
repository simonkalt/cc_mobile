"""Short-lived OAuth code handoff for native Android when ccmobile:// is not delivered."""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass
from typing import Optional

from app.utils.redis_utils import is_redis_available

logger = logging.getLogger(__name__)

_HANDOFF_TTL_SECONDS = 600
_REDIS_KEY_PREFIX = "oauth:native-handoff:"
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


def _redis_key(state: str) -> str:
    return f"{_REDIS_KEY_PREFIX}{state}"


def _store_in_redis(
    key: str,
    *,
    provider: str,
    code: Optional[str],
    error: Optional[str],
    error_description: Optional[str],
) -> bool:
    if not is_redis_available():
        return False
    try:
        from app.utils.redis_utils import get_redis_client

        payload = json.dumps(
            {
                "provider": provider,
                "code": code,
                "error": error,
                "error_description": error_description,
            }
        )
        get_redis_client().setex(_redis_key(key), _HANDOFF_TTL_SECONDS, payload)
        return True
    except Exception as exc:
        logger.warning("OAuth native handoff Redis store failed: %s", exc)
        return False


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
    if _store_in_redis(
        key,
        provider=provider,
        code=code,
        error=error,
        error_description=error_description,
    ):
        backend = "redis"
    else:
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
        backend = "memory"
    logger.info(
        "OAuth native handoff stored backend=%s provider=%s state_prefix=%s has_code=%s has_error=%s",
        backend,
        provider,
        key[:4],
        bool(code),
        bool(error),
    )


def _consume_from_redis(key: str, provider: str) -> Optional[OAuthNativeHandoff]:
    if not is_redis_available():
        return None
    try:
        from app.utils.redis_utils import get_redis_client

        client = get_redis_client()
        redis_key = _redis_key(key)
        raw = client.get(redis_key)
        if not raw:
            return None
        client.delete(redis_key)
        data = json.loads(raw)
    except Exception as exc:
        logger.warning("OAuth native handoff Redis consume failed: %s", exc)
        return None

    if data.get("provider") != provider:
        logger.warning(
            "OAuth handoff provider mismatch state_prefix=%s expected=%s got=%s",
            key[:4],
            provider,
            data.get("provider"),
        )
        return None
    return OAuthNativeHandoff(
        provider=provider,
        code=data.get("code"),
        error=data.get("error"),
        error_description=data.get("error_description"),
    )


def consume_oauth_native_handoff(state: str, provider: str) -> Optional[OAuthNativeHandoff]:
    """One-time read; returns None when not ready or state unknown."""
    key = (state or "").strip()
    if not key:
        return None

    handoff = _consume_from_redis(key, provider)
    if handoff:
        return handoff

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
