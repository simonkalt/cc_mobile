"""
Shared pytest fixtures for the billing test suite.

Fixtures
--------
fake_user_id        – deterministic MongoDB ObjectId string
fake_user           – UserResponse instance (injected into the auth dependency override)
client              – FastAPI TestClient with auth bypassed and Mongo mocked
mongomock_users     – a mongomock Collection pre-seeded with one user document
fake_apple_decoded  – stub object that looks like a decoded JWSTransactionDecodedPayload
stripe_event        – factory function that builds a minimal Stripe webhook event dict
"""

from __future__ import annotations

import sys
import os
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so ``app.*`` imports resolve when tests
# are run from the repo root (pytest), as well as from this sub-directory.
# ---------------------------------------------------------------------------
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

# ---------------------------------------------------------------------------
# Attempt mongomock import — give a clear error when not installed.
# ---------------------------------------------------------------------------
try:
    import mongomock  # noqa: F401
except ImportError as _mm_err:
    raise ImportError(
        "mongomock is required for the billing test suite.\n"
        "Install it with:  pip install mongomock\n"
        f"Original error: {_mm_err}"
    ) from _mm_err

# ---------------------------------------------------------------------------
# Stable test IDs
# ---------------------------------------------------------------------------
FAKE_USER_ID = "60c72b2f9b1d8b3a2c8e1234"
FAKE_USER_OBJ_ID = ObjectId(FAKE_USER_ID)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_user_id() -> str:
    return FAKE_USER_ID


@pytest.fixture
def fake_user():
    """Minimal UserResponse for auth dependency overrides."""
    from app.models.user import UserResponse

    now = datetime.now(timezone.utc)
    return UserResponse(
        id=FAKE_USER_ID,
        name="Test User",
        email="test@example.com",
        isActive=True,
        isEmailVerified=True,
        roles=["user"],
        dateCreated=now,
        dateUpdated=now,
    )


@pytest.fixture
def mongomock_users(request):
    """A mongomock Collection pre-seeded with one user document.

    The user starts as a free-tier user.  Pass ``initial_user_fields`` via
    ``pytest.mark.parametrize`` or the ``request`` fixture to override fields.
    """
    extra: Dict[str, Any] = getattr(request, "param", {}) or {}
    client = mongomock.MongoClient()
    db = client["test_db"]
    collection = db["users"]

    base_doc: Dict[str, Any] = {
        "_id": FAKE_USER_OBJ_ID,
        "email": "test@example.com",
        "subscriptionStatus": "free",
        "subscriptionPlan": "free",
        "billingProvider": None,
        "subscriptionId": None,
        "appleOriginalTransactionId": None,
        "generation_credits": 10,
        "max_credits": 10,
    }
    base_doc.update(extra)
    collection.insert_one(base_doc)
    return collection


@pytest.fixture
def client(fake_user, mongomock_users):
    """FastAPI TestClient with:
    - ``get_current_user`` overridden to return ``fake_user``
    - ``get_collection`` patched at every module that imports it at module level
    - ``is_connected`` patched to return True everywhere

    ``subscription_service`` and ``apple_subscription_service`` import ``get_collection``
    and ``is_connected`` at the top of the module (module-level import).  When a patch
    targets only ``app.db.mongodb.get_collection``, those module-level references are
    unaffected.  We therefore patch each service module's own name binding as well.
    """
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import get_current_user

    async def _override_auth():
        return fake_user

    app.dependency_overrides[get_current_user] = _override_auth

    _col = mongomock_users
    patches = [
        # canonical source
        patch("app.db.mongodb.is_connected", return_value=True),
        patch("app.db.mongodb.get_collection", return_value=_col),
        # subscription_service imports these at module level
        patch("app.services.subscription_service.is_connected", return_value=True),
        patch("app.services.subscription_service.get_collection", return_value=_col),
        # apple_subscription_service imports these at module level
        patch("app.services.apple_subscription_service.is_connected", return_value=True),
        patch("app.services.apple_subscription_service.get_collection", return_value=_col),
    ]
    for p in patches:
        p.start()

    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        for p in patches:
            p.stop()
        app.dependency_overrides.clear()


@pytest.fixture
def fake_apple_decoded(fake_user_id):
    """Stub JWSTransactionDecodedPayload-like object returned by the App Store verifier."""
    future = datetime.now(timezone.utc) + timedelta(days=30)
    expires_ms = int(future.timestamp() * 1000)

    obj = MagicMock()
    obj.transactionId = "TX-001"
    obj.originalTransactionId = "ORIG-TX-001"
    obj.productId = "com.example.premium.monthly"
    obj.subscriptionGroupIdentifier = "GROUP-001"
    obj.expiresDate = expires_ms
    obj.revocationDate = None
    obj.appAccountToken = None
    obj.bundleId = "com.example.app"

    # type == AUTO_RENEWABLE_SUBSCRIPTION
    try:
        from appstoreserverlibrary.models.Type import Type
        obj.type = Type.AUTO_RENEWABLE_SUBSCRIPTION
    except Exception:
        obj.type = "Auto-Renewable Subscription"

    return obj


@pytest.fixture
def stripe_event():
    """Factory that builds a minimal Stripe webhook event dict."""

    def _make(
        event_type: str = "customer.subscription.created",
        status: str = "active",
        customer_id: str = "cus_TEST123",
        sub_id: str = "sub_TEST123",
        price_id: str = "price_monthly",
        cancel_at_period_end: bool = False,
        current_period_end: Optional[int] = None,
    ) -> Dict[str, Any]:
        if current_period_end is None:
            current_period_end = int(
                (datetime.now(timezone.utc) + timedelta(days=30)).timestamp()
            )
        return {
            "id": "evt_test",
            "type": event_type,
            "data": {
                "object": {
                    "id": sub_id,
                    "customer": customer_id,
                    "status": status,
                    "cancel_at_period_end": cancel_at_period_end,
                    "canceled_at": None,
                    "current_period_end": current_period_end,
                    "items": {
                        "data": [
                            {
                                "price": {
                                    "id": price_id,
                                    "product": "prod_TEST123",
                                }
                            }
                        ]
                    },
                }
            },
        }

    return _make
