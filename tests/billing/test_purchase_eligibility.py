"""
Step 4: Tests for GET /api/subscriptions/purchase-eligibility.

Unit tests for compute_eligibility() and TestClient tests for the endpoint.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import pytest
import mongomock
from bson import ObjectId

from tests.billing.conftest import FAKE_USER_ID, FAKE_USER_OBJ_ID


# ---------------------------------------------------------------------------
# Unit tests — compute_eligibility (already covered in test_entitlement_compute;
# here we test reason strings directly on the endpoint logic)
# ---------------------------------------------------------------------------

class TestComputeEligibilityReasons:
    def _elig(self, billing_provider=None, status="free", sub_id=None, apple_tx=None):
        from app.services.entitlement_service import compute_eligibility
        doc = {
            "billingProvider": billing_provider,
            "subscriptionStatus": status,
            "subscriptionId": sub_id,
            "appleOriginalTransactionId": apple_tx,
        }
        return compute_eligibility(doc)

    def test_free(self):
        r = self._elig()
        assert r["reason"] == "free"
        assert r["can_initiate_new_paid_subscription"] is True

    def test_already_entitled_stripe(self):
        r = self._elig("stripe", "active", "sub_x")
        assert r["reason"] == "already_entitled"
        assert r["can_initiate_new_paid_subscription"] is False

    def test_already_entitled_apple(self):
        r = self._elig("apple", "active", apple_tx="ORIG-1")
        assert r["reason"] == "already_entitled"
        assert r["can_initiate_new_paid_subscription"] is False

    def test_lapsed_stripe(self):
        r = self._elig("stripe", "canceled", "sub_x")
        assert r["reason"] == "lapsed"
        assert r["can_initiate_new_paid_subscription"] is True

    def test_lapsed_apple(self):
        r = self._elig("apple", "expired", apple_tx="ORIG-1")
        assert r["reason"] == "lapsed"
        assert r["can_initiate_new_paid_subscription"] is True

    def test_billing_provider_echoed(self):
        r = self._elig("stripe", "active", "sub_x")
        assert r["billing_provider"] == "stripe"


# ---------------------------------------------------------------------------
# TestClient tests
# ---------------------------------------------------------------------------

class TestPurchaseEligibilityEndpoint:
    def test_free_user_returns_200(self, client, mongomock_users):
        resp = client.get("/api/subscriptions/purchase-eligibility")
        assert resp.status_code == 200
        body = resp.json()
        assert body["can_initiate_new_paid_subscription"] is True
        assert body["reason"] == "free"

    def test_active_apple_user_returns_already_entitled(self, client, mongomock_users):
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "apple",
                    "subscriptionStatus": "active",
                    "appleOriginalTransactionId": "ORIG-001",
                }
            },
        )
        resp = client.get("/api/subscriptions/purchase-eligibility")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reason"] == "already_entitled"
        assert body["can_initiate_new_paid_subscription"] is False

    def test_lapsed_stripe_user(self, client, mongomock_users):
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "stripe",
                    "subscriptionStatus": "canceled",
                    "subscriptionId": "sub_old",
                }
            },
        )
        resp = client.get("/api/subscriptions/purchase-eligibility")
        assert resp.status_code == 200
        assert resp.json()["reason"] == "lapsed"

    def test_unauthenticated_returns_401_or_403(self):
        """Without auth override, hitting the endpoint should fail with 4xx."""
        from fastapi.testclient import TestClient
        from app.main import app

        mc = mongomock.MongoClient()
        col = mc["test"]["users"]
        col.insert_one(
            {
                "_id": FAKE_USER_OBJ_ID,
                "subscriptionStatus": "free",
                "billingProvider": None,
            }
        )

        with (
            patch("app.db.mongodb.is_connected", return_value=True),
            patch("app.db.mongodb.get_collection", return_value=col),
        ):
            with TestClient(app) as tc:
                resp = tc.get("/api/subscriptions/purchase-eligibility")
        assert resp.status_code in (401, 403)

    def test_platform_query_param_accepted(self, client, mongomock_users):
        """?platform=ios is accepted; cross_platform_billing is not in this response
        but the endpoint should not 422 on the platform param."""
        resp = client.get(
            "/api/subscriptions/purchase-eligibility?platform=ios"
        )
        assert resp.status_code == 200
