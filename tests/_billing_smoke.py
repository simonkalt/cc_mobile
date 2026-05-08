"""
Shared utilities for billing smoke scripts.

Usage::

    from tests._billing_smoke import BACKEND_URL, make_token, pprint_json, mongo_find_user

Smoke scripts are run against a live server + real MongoDB.  They require:
  - A running backend (python main.py or uvicorn)
  - .env / .secrets loaded (MONGODB_URI, JWT_SECRET, etc.)
  - A real USER_ID to test against (set BILLING_TEST_USER_ID in environment)
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Dict, Optional

# Ensure project root is on path.
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from app.core.config import settings
from app.services.user_service import _make_signed_token, _apply_standard_jwt_claims

BACKEND_URL = f"http://localhost:{settings.PORT}"

# Override with env var for smoke tests that target a non-default user.
BILLING_TEST_USER_ID: str = os.environ.get("BILLING_TEST_USER_ID", "")


def make_token(user_id: str) -> str:
    """Generate a short-lived JWT for the given user_id."""
    now = int(time.time())
    payload = _apply_standard_jwt_claims(
        {
            "sub": user_id,
            "type": "access",
            "iat": now,
            "exp": now + 3600,
        }
    )
    return _make_signed_token(payload, settings.JWT_SECRET)


def pprint_json(label: str, data: Any) -> None:
    """Pretty-print a JSON-serialisable value with a label."""
    print(f"\n{'─' * 60}")
    print(f"  {label}")
    print(f"{'─' * 60}")
    try:
        print(json.dumps(data, indent=2, default=str))
    except Exception:
        print(repr(data))


def mongo_find_user(user_id: str) -> Optional[Dict[str, Any]]:
    """Return the raw MongoDB user document (for post-call inspection)."""
    from bson import ObjectId
    from app.db.mongodb import connect_to_mongodb, get_collection, is_connected
    from app.utils.user_helpers import USERS_COLLECTION

    if not is_connected():
        connect_to_mongodb()
    col = get_collection(USERS_COLLECTION)
    if col is None:
        print("ERROR: could not access users collection")
        return None
    return col.find_one({"_id": ObjectId(user_id)})


def require_user_id() -> str:
    """Return BILLING_TEST_USER_ID or abort with a helpful message."""
    uid = BILLING_TEST_USER_ID
    if not uid:
        print(
            "ERROR: set BILLING_TEST_USER_ID=<mongo_object_id> before running smoke tests."
        )
        sys.exit(1)
    return uid
