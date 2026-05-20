#!/usr/bin/env python3
"""
Redis connection test — uses repo .env + .secrets (same as the API).

Run from repo root:
  .venv/bin/python tests/test_redis_connection.py

Or:
  python tests/test_redis_connection.py
"""
from __future__ import annotations

import argparse
import logging
import sys
import uuid
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from app.core.env_loader import load_project_env

load_project_env(_ROOT)

from app.core.config import settings
from app.utils import redis_utils

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def _mask(value: str | None) -> str:
    if not value:
        return "(not set)"
    if len(value) <= 4:
        return "***"
    return f"{value[:2]}…{value[-2:]} (len={len(value)})"


def print_config() -> bool:
    logger.info("=" * 60)
    logger.info("Redis configuration (from .env + .secrets)")
    logger.info("=" * 60)
    logger.info("REDIS_HOST:     %s", settings.REDIS_HOST or "(not set)")
    logger.info("REDIS_PORT:     %s", settings.REDIS_PORT)
    logger.info("REDIS_DB:       %s", settings.REDIS_DB)
    logger.info("REDIS_SSL:      %s", settings.REDIS_SSL)
    logger.info("REDIS_USERNAME: %s", _mask(settings.REDIS_USERNAME))
    logger.info("REDIS_PASSWORD: %s", _mask(settings.REDIS_PASSWORD))
    host = (settings.REDIS_HOST or "").lower()
    if "redislabs.com" in host and settings.REDIS_PASSWORD and not settings.REDIS_USERNAME:
        logger.info(
            "Note: Redis Cloud with no REDIS_USERNAME — app will use username 'default' at connect time"
        )
    logger.info("redis package:  %s", "installed" if redis_utils.REDIS_AVAILABLE else "MISSING")
    if settings.REDIS_API_KEY:
        logger.info(
            "REDIS_API_KEY:  %s (not used by redis_utils.py)",
            _mask(settings.REDIS_API_KEY),
        )

    if not settings.REDIS_HOST:
        logger.error("REDIS_HOST is required. Set it in .env (see .secrets.example).")
        return False
    if not redis_utils.REDIS_AVAILABLE:
        logger.error("Install redis: pip install redis")
        return False
    return True


def test_ping() -> bool:
    logger.info("")
    logger.info("Step 1: PING")
    try:
        ok = redis_utils.is_redis_available()
        if ok:
            logger.info("✓ Redis PING succeeded")
            return True
        logger.error("✗ Redis not available (is_redis_available returned False)")
        return False
    except Exception as exc:
        logger.error("✗ Redis PING failed: %s", exc)
        return False


def test_read_write_delete() -> bool:
    logger.info("")
    logger.info("Step 2: SET / GET / DEL (ephemeral test key)")
    test_key = f"cc_mobile:test:connection:{uuid.uuid4().hex}"
    test_value = "ok"
    try:
        client = redis_utils.get_redis_client()
        client.set(test_key, test_value, ex=60)
        got = client.get(test_key)
        if got != test_value:
            logger.error("✗ GET mismatch: expected %r, got %r", test_value, got)
            return False
        logger.info("✓ SET and GET OK (key=%s)", test_key)
        deleted = client.delete(test_key)
        if deleted != 1:
            logger.warning("⚠ DEL returned %s (expected 1)", deleted)
        else:
            logger.info("✓ DEL OK")
        return True
    except Exception as exc:
        logger.error("✗ Read/write test failed: %s", exc)
        return False


def test_verification_roundtrip() -> bool:
    """Exercise the same helpers used for registration / verification flows."""
    logger.info("")
    logger.info("Step 3: Verification session round-trip (app helpers)")
    email = f"redis-test-{uuid.uuid4().hex}@example.com"
    code = "123456"
    purpose = "finish_registration"
    payload = {"email": email, "name": "Redis Test", "password": "hashed-not-real"}

    try:
        if not redis_utils.store_verification_session(
            email=email,
            code=code,
            purpose=purpose,
            delivery_method="email",
            ttl_minutes=2,
        ):
            logger.error("✗ store_verification_session returned False")
            return False

        session = redis_utils.get_verification_session(email, code, purpose)
        if not session or session.get("email") != email:
            logger.error("✗ get_verification_session failed or wrong payload: %s", session)
            return False
        logger.info("✓ Verification session stored and retrieved")

        if not redis_utils.delete_verification_session(email, code, purpose):
            logger.warning("⚠ delete_verification_session returned False")
        else:
            logger.info("✓ Verification session deleted")
        return True
    except Exception as exc:
        logger.error("✗ Verification round-trip failed: %s", exc)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Test Redis using .env and .secrets")
    parser.add_argument(
        "--skip-roundtrip",
        action="store_true",
        help="Only ping + SET/GET/DEL, skip verification helper test",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="DEBUG logging")
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if not print_config():
        return 1

    results = [test_ping(), test_read_write_delete()]
    if not args.skip_roundtrip:
        results.append(test_verification_roundtrip())

    logger.info("")
    logger.info("=" * 60)
    if all(results):
        logger.info("✓ All Redis tests passed")
        return 0
    logger.error("✗ One or more Redis tests failed")
    return 1


if __name__ == "__main__":
    sys.exit(main())
