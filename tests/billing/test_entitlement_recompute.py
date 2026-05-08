"""
Step 3: Unit tests for entitlement_service.recompute_and_persist.

Verifies that the persisted fields (entitlementActive, canInitiateNewPaidSubscription,
entitlementSource, entitlementUpdatedAt) are written to MongoDB correctly for each
subscription state, and that the conflict policy (Stripe wins over Apple) is enforced.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import patch

import pytest
import mongomock
from bson import ObjectId

from tests.billing.conftest import FAKE_USER_ID, FAKE_USER_OBJ_ID


def _collection_with_user(extra=None):
    mc = mongomock.MongoClient()
    col = mc["test"]["users"]
    doc = {
        "_id": FAKE_USER_OBJ_ID,
        "subscriptionStatus": "free",
        "billingProvider": None,
    }
    if extra:
        doc.update(extra)
    col.insert_one(doc)
    return col


class TestRecomputeAndPersist:
    def _run(self, col):
        from app.services.entitlement_service import recompute_and_persist

        with (
            patch("app.db.mongodb.is_connected", return_value=True),
            patch("app.db.mongodb.get_collection", return_value=col),
        ):
            return recompute_and_persist(FAKE_USER_ID)

    def test_free_user_sets_entitlement_active_false(self):
        col = _collection_with_user()
        result = self._run(col)

        assert result is not None
        assert result["entitlement_active"] is False
        assert result["can_initiate_new_paid_subscription"] is True

        user = col.find_one({"_id": FAKE_USER_OBJ_ID})
        assert user["entitlementActive"] is False
        assert user["canInitiateNewPaidSubscription"] is True
        assert "entitlementUpdatedAt" in user

    def test_stripe_active_user_sets_entitlement_active_true(self):
        col = _collection_with_user(
            {
                "billingProvider": "stripe",
                "subscriptionStatus": "active",
                "subscriptionId": "sub_123",
            }
        )
        result = self._run(col)

        assert result["entitlement_active"] is True
        assert result["entitlement_source"] == "stripe"
        user = col.find_one({"_id": FAKE_USER_OBJ_ID})
        assert user["entitlementActive"] is True
        assert user["entitlementSource"] == "stripe"

    def test_apple_active_persists_apple_source(self):
        col = _collection_with_user(
            {
                "billingProvider": "apple",
                "subscriptionStatus": "active",
                "appleOriginalTransactionId": "ORIG-001",
            }
        )
        result = self._run(col)

        assert result["entitlement_active"] is True
        assert result["entitlement_source"] == "apple"
        user = col.find_one({"_id": FAKE_USER_OBJ_ID})
        assert user["entitlementSource"] == "apple"

    def test_canceled_sets_entitlement_active_false(self):
        col = _collection_with_user(
            {
                "billingProvider": "stripe",
                "subscriptionStatus": "canceled",
                "subscriptionId": "sub_123",
            }
        )
        result = self._run(col)
        assert result["entitlement_active"] is False

    def test_conflict_stripe_wins_over_apple(self):
        """When a user document has both Stripe and Apple billing data, Stripe wins."""
        col = _collection_with_user(
            {
                # The billing_provider field is the authority; if it says stripe, stripe wins.
                "billingProvider": "stripe",
                "subscriptionStatus": "active",
                "subscriptionId": "sub_123",
                "appleOriginalTransactionId": "ORIG-001",
            }
        )
        result = self._run(col)
        assert result["entitlement_source"] == "stripe"

    def test_invalid_user_id_returns_none(self):
        from app.services.entitlement_service import recompute_and_persist

        with (
            patch("app.db.mongodb.is_connected", return_value=True),
            patch("app.db.mongodb.get_collection", return_value=mongomock.MongoClient()["test"]["users"]),
        ):
            result = recompute_and_persist("not-a-valid-objectid")
        assert result is None

    def test_user_not_found_returns_none(self):
        from app.services.entitlement_service import recompute_and_persist

        mc = mongomock.MongoClient()
        empty_col = mc["test"]["users"]

        with (
            patch("app.db.mongodb.is_connected", return_value=True),
            patch("app.db.mongodb.get_collection", return_value=empty_col),
        ):
            result = recompute_and_persist(FAKE_USER_ID)
        assert result is None
