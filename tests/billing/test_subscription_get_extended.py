"""
Step 2: TestClient tests for GET /api/subscriptions/{user_id} — extended fields.

Seeds mongomock with Stripe-active and Apple-active users and verifies that the four
new unified entitlement fields appear in the response with correct values.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
from bson import ObjectId

from tests.billing.conftest import FAKE_USER_ID, FAKE_USER_OBJ_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _future_ts():
    return datetime.now(timezone.utc) + timedelta(days=30)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestGetSubscriptionExtendedFields:
    def test_free_user_entitlement_fields(self, client, mongomock_users):
        resp = client.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["entitlement_active"] is False
        assert body["can_initiate_new_paid_subscription"] is True
        assert body["cross_platform_billing"] is False
        assert body["entitlement_source"] is None

    def test_stripe_active_user_entitlement_fields(self, client, mongomock_users):
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "stripe",
                    "subscriptionStatus": "active",
                    "subscriptionId": "sub_test_123",
                    "subscriptionCurrentPeriodEnd": _future_ts(),
                }
            },
        )
        # Bypass Stripe live-sync: patch _get_stripe_module to return None
        with patch("app.services.subscription_service._get_stripe_module", return_value=None):
            resp = client.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["entitlement_active"] is True
        assert body["can_initiate_new_paid_subscription"] is False
        assert body["entitlement_source"] == "stripe"

    def test_apple_active_user_entitlement_fields(self, client, mongomock_users):
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "apple",
                    "subscriptionStatus": "active",
                    "subscriptionId": "ORIG-TX-001",
                    "appleOriginalTransactionId": "ORIG-TX-001",
                    "subscriptionCurrentPeriodEnd": _future_ts(),
                }
            },
        )
        resp = client.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["entitlement_active"] is True
        assert body["entitlement_source"] == "apple"

    def test_apple_active_android_client_has_cross_platform_billing(self, client, mongomock_users):
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "apple",
                    "subscriptionStatus": "active",
                    "subscriptionId": "ORIG-TX-001",
                    "appleOriginalTransactionId": "ORIG-TX-001",
                    "subscriptionCurrentPeriodEnd": _future_ts(),
                }
            },
        )
        resp = client.get(
            f"/api/subscriptions/{FAKE_USER_ID}",
            headers={"X-Client-Platform": "android"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cross_platform_billing"] is True

    def test_apple_active_ios_client_no_cross_platform(self, client, mongomock_users):
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "apple",
                    "subscriptionStatus": "active",
                    "subscriptionId": "ORIG-TX-001",
                    "appleOriginalTransactionId": "ORIG-TX-001",
                    "subscriptionCurrentPeriodEnd": _future_ts(),
                }
            },
        )
        resp = client.get(
            f"/api/subscriptions/{FAKE_USER_ID}",
            headers={"X-Client-Platform": "ios"},
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["cross_platform_billing"] is False

    def test_invalid_user_id_returns_400(self, client):
        resp = client.get("/api/subscriptions/not-a-valid-object-id")
        assert resp.status_code in (400, 422, 404)
