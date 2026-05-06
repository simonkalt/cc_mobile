"""
Step 1: Unit tests for Apple verify — field persistence, error codes, idempotency.

These tests use mongomock so no real MongoDB or App Store connection is required.
"""

from __future__ import annotations

import importlib
from datetime import datetime, timezone, timedelta
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from tests.billing.conftest import FAKE_USER_ID, FAKE_USER_OBJ_ID


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_decoded_tx(
    transaction_id: str = "TX-001",
    original_transaction_id: str = "ORIG-TX-001",
    product_id: str = "com.example.monthly",
    subscription_group_id: str = "GROUP-1",
    expires_days: int = 30,
    revocation_date: Any = None,
    app_account_token: Any = None,
) -> MagicMock:
    future_ms = int(
        (datetime.now(timezone.utc) + timedelta(days=expires_days)).timestamp() * 1000
    )
    obj = MagicMock()
    obj.transactionId = transaction_id
    obj.originalTransactionId = original_transaction_id
    obj.productId = product_id
    obj.subscriptionGroupIdentifier = subscription_group_id
    obj.expiresDate = future_ms
    obj.revocationDate = revocation_date
    obj.appAccountToken = app_account_token
    obj.bundleId = "com.example.app"

    try:
        from appstoreserverlibrary.models.Type import Type
        obj.type = Type.AUTO_RENEWABLE_SUBSCRIPTION
    except Exception:
        obj.type = "Auto-Renewable Subscription"
    return obj


def _make_sandbox_env():
    try:
        from appstoreserverlibrary.models.Environment import Environment
        return Environment.SANDBOX
    except Exception:
        return "sandbox"


# ---------------------------------------------------------------------------
# _subscription_fields_from_verified_apple_tx — direct unit tests
# ---------------------------------------------------------------------------

class TestSubscriptionFieldsFromTx:
    """Pure unit tests for the field-builder function."""

    def test_all_new_fields_present(self):
        from app.services.apple_subscription_service import (
            _subscription_fields_from_verified_apple_tx,
        )
        decoded = _make_decoded_tx()
        env = _make_sandbox_env()

        fields = _subscription_fields_from_verified_apple_tx(decoded, None, env=env)

        assert fields["appleLatestTransactionId"] == "TX-001"
        assert fields["appleSubscriptionGroupId"] == "GROUP-1"
        assert fields["appleEnvironment"] == "sandbox"
        assert fields["appleAutoRenewStatus"] is True  # default when no renewal info
        assert isinstance(fields["appleLastVerifiedAt"], datetime)
        assert fields["billingProvider"] == "apple"
        assert fields["appleOriginalTransactionId"] == "ORIG-TX-001"

    def test_env_none_gives_none(self):
        from app.services.apple_subscription_service import (
            _subscription_fields_from_verified_apple_tx,
        )
        decoded = _make_decoded_tx()
        fields = _subscription_fields_from_verified_apple_tx(decoded, None, env=None)
        assert fields["appleEnvironment"] is None

    def test_auto_renew_status_from_renewal_off(self):
        from app.services.apple_subscription_service import (
            _subscription_fields_from_verified_apple_tx,
        )
        decoded = _make_decoded_tx()
        renewal = MagicMock()
        try:
            from appstoreserverlibrary.models.AutoRenewStatus import AutoRenewStatus
            renewal.autoRenewStatus = AutoRenewStatus.OFF
            renewal.autoRenewProductId = None
            renewal.productId = None
            renewal.isInBillingRetryPeriod = False
        except ImportError:
            pytest.skip("appstoreserverlibrary not installed")

        fields = _subscription_fields_from_verified_apple_tx(decoded, renewal)
        assert fields["appleAutoRenewStatus"] is False

    def test_expired_when_past_period_end(self):
        from app.services.apple_subscription_service import (
            _subscription_fields_from_verified_apple_tx,
        )
        decoded = _make_decoded_tx(expires_days=-1)
        fields = _subscription_fields_from_verified_apple_tx(decoded, None)
        assert fields["subscriptionStatus"] == "expired"

    def test_revoked_status(self):
        from app.services.apple_subscription_service import (
            _subscription_fields_from_verified_apple_tx,
        )
        decoded = _make_decoded_tx(revocation_date=12345678)
        fields = _subscription_fields_from_verified_apple_tx(decoded, None)
        assert fields["subscriptionStatus"] == "revoked"


# ---------------------------------------------------------------------------
# _free_tier_apple_clear_set — must null out all new fields
# ---------------------------------------------------------------------------

class TestFreeTierClearSet:
    def test_new_fields_nulled(self):
        from app.services.apple_subscription_service import _free_tier_apple_clear_set

        clear = _free_tier_apple_clear_set()
        for field in (
            "appleLatestTransactionId",
            "appleSubscriptionGroupId",
            "appleEnvironment",
            "appleAutoRenewStatus",
            "appleLastVerifiedAt",
        ):
            assert field in clear, f"Missing {field} in _free_tier_apple_clear_set"
            assert clear[field] is None, f"{field} should be None"


# ---------------------------------------------------------------------------
# verify_apple_transaction_and_grant_entitlement — error code tests
# ---------------------------------------------------------------------------

class TestVerifyErrorCodes:
    """Assert each error path raises AppleBillingError with the right code."""

    def _make_collection(self, extra=None):
        import mongomock

        client = mongomock.MongoClient()
        col = client["test"]["users"]
        doc = {
            "_id": FAKE_USER_OBJ_ID,
            "email": "test@example.com",
            "subscriptionStatus": "free",
        }
        if extra:
            doc.update(extra)
        col.insert_one(doc)
        return col

    def _apple_service_patches(self, col):
        """Return standard patches for verify_apple_transaction_and_grant_entitlement tests.

        ``apple_subscription_service`` imports ``get_collection`` and ``is_connected`` at
        module level, so we must patch the names in THAT module, not in ``app.db.mongodb``.
        ``_allowed_product_ids`` is also patched to None so no product allowlist blocks tests.
        """
        return [
            patch("app.services.apple_subscription_service.APPLE_STOREKIT_LIB_AVAILABLE", True),
            patch("app.services.apple_subscription_service.apple_subscription_configured", return_value=True),
            patch("app.services.apple_subscription_service.is_connected", return_value=True),
            patch("app.services.apple_subscription_service.get_collection", return_value=col),
            patch("app.services.apple_subscription_service._allowed_product_ids", return_value=None),
        ]

    def test_invalid_jws_gives_apple_validation_failed(self):
        from app.services.apple_subscription_service import (
            AppleBillingError,
            verify_apple_transaction_and_grant_entitlement,
        )
        col = self._make_collection()
        with (
            patch("app.services.apple_subscription_service.APPLE_STOREKIT_LIB_AVAILABLE", True),
            patch("app.services.apple_subscription_service.apple_subscription_configured", return_value=True),
            patch("app.services.apple_subscription_service.is_connected", return_value=True),
            patch("app.services.apple_subscription_service.get_collection", return_value=col),
        ):
            with pytest.raises(AppleBillingError) as exc_info:
                verify_apple_transaction_and_grant_entitlement(
                    FAKE_USER_ID, "not.a.valid.jws"
                )
        assert exc_info.value.code == "apple_validation_failed"

    def test_conflict_gives_transaction_already_consumed(self):
        from app.services.apple_subscription_service import (
            AppleBillingError,
            verify_apple_transaction_and_grant_entitlement,
        )
        import mongomock

        mc = mongomock.MongoClient()
        col = mc["test"]["users"]
        col.insert_one({"_id": FAKE_USER_OBJ_ID, "subscriptionStatus": "free"})
        other_id = ObjectId()
        col.insert_one({"_id": other_id, "appleOriginalTransactionId": "ORIG-TX-001"})

        decoded = _make_decoded_tx()
        env = _make_sandbox_env()

        patches = self._apple_service_patches(col) + [
            patch(
                "app.services.apple_subscription_service._fetch_transaction_with_fallback",
                return_value=(env, decoded),
            ),
            patch(
                "app.services.apple_subscription_service._decode_jws_payload_unverified",
                return_value={"transactionId": "TX-001"},
            ),
            patch("app.services.entitlement_service.recompute_and_persist"),
        ]
        for p in patches:
            p.start()
        try:
            with pytest.raises(AppleBillingError) as exc_info:
                verify_apple_transaction_and_grant_entitlement(FAKE_USER_ID, "dummy.jws.payload")
        finally:
            for p in patches:
                p.stop()

        assert exc_info.value.code == "transaction_already_consumed"
        assert exc_info.value.status_code == 409

    def test_user_mismatch_gives_user_mismatch(self):
        from app.services.apple_subscription_service import (
            AppleBillingError,
            verify_apple_transaction_and_grant_entitlement,
        )
        import mongomock

        mc = mongomock.MongoClient()
        col = mc["test"]["users"]
        col.insert_one(
            {
                "_id": FAKE_USER_OBJ_ID,
                "subscriptionStatus": "free",
                "appleAppAccountToken": "token-EXISTING",
            }
        )

        decoded = _make_decoded_tx(app_account_token="token-DIFFERENT")
        env = _make_sandbox_env()

        patches = self._apple_service_patches(col) + [
            patch(
                "app.services.apple_subscription_service._fetch_transaction_with_fallback",
                return_value=(env, decoded),
            ),
            patch(
                "app.services.apple_subscription_service._decode_jws_payload_unverified",
                return_value={"transactionId": "TX-001"},
            ),
        ]
        for p in patches:
            p.start()
        try:
            with pytest.raises(AppleBillingError) as exc_info:
                verify_apple_transaction_and_grant_entitlement(FAKE_USER_ID, "dummy.jws.payload")
        finally:
            for p in patches:
                p.stop()

        assert exc_info.value.code == "user_mismatch"
        assert exc_info.value.status_code == 403

    def test_client_product_id_mismatch_gives_apple_validation_failed(self):
        from app.services.apple_subscription_service import (
            AppleBillingError,
            verify_apple_transaction_and_grant_entitlement,
        )
        import mongomock

        mc = mongomock.MongoClient()
        col = mc["test"]["users"]
        col.insert_one({"_id": FAKE_USER_OBJ_ID, "subscriptionStatus": "free"})

        decoded = _make_decoded_tx(product_id="com.example.monthly")
        env = _make_sandbox_env()

        patches = self._apple_service_patches(col) + [
            patch(
                "app.services.apple_subscription_service._fetch_transaction_with_fallback",
                return_value=(env, decoded),
            ),
            patch(
                "app.services.apple_subscription_service._decode_jws_payload_unverified",
                return_value={"transactionId": "TX-001"},
            ),
        ]
        for p in patches:
            p.start()
        try:
            with pytest.raises(AppleBillingError) as exc_info:
                verify_apple_transaction_and_grant_entitlement(
                    FAKE_USER_ID,
                    "dummy.jws.payload",
                    client_product_id="wrong.product",
                )
        finally:
            for p in patches:
                p.stop()

        assert exc_info.value.code == "apple_validation_failed"
        assert exc_info.value.status_code == 400


# ---------------------------------------------------------------------------
# Full persist path — all new fields written, idempotent
# ---------------------------------------------------------------------------

def _apple_patches(col, decoded, env):
    """Convenience: standard set of patches for full-path apple verify tests."""
    return [
        patch("app.services.apple_subscription_service.APPLE_STOREKIT_LIB_AVAILABLE", True),
        patch("app.services.apple_subscription_service.apple_subscription_configured", return_value=True),
        patch("app.services.apple_subscription_service.is_connected", return_value=True),
        patch("app.services.apple_subscription_service.get_collection", return_value=col),
        patch(
            "app.services.apple_subscription_service._fetch_transaction_with_fallback",
            return_value=(env, decoded),
        ),
        patch(
            "app.services.apple_subscription_service._decode_jws_payload_unverified",
            return_value={"transactionId": "TX-001"},
        ),
        # Return None = no allowlist restriction, so any product passes
        patch("app.services.apple_subscription_service._allowed_product_ids", return_value=None),
        patch("app.services.entitlement_service.recompute_and_persist"),
    ]


class TestVerifyPersistFields:
    def test_all_apple_fields_written_to_mongo(self):
        from app.services.apple_subscription_service import verify_apple_transaction_and_grant_entitlement
        import mongomock

        mc = mongomock.MongoClient()
        col = mc["test"]["users"]
        col.insert_one({"_id": FAKE_USER_OBJ_ID, "subscriptionStatus": "free"})

        decoded = _make_decoded_tx()
        env = _make_sandbox_env()

        ps = _apple_patches(col, decoded, env)
        for p in ps:
            p.start()
        try:
            verify_apple_transaction_and_grant_entitlement(FAKE_USER_ID, "dummy.jws.payload")
        finally:
            for p in ps:
                p.stop()

        user = col.find_one({"_id": FAKE_USER_OBJ_ID})
        assert user["billingProvider"] == "apple"
        assert user["appleOriginalTransactionId"] == "ORIG-TX-001"
        assert user["appleLatestTransactionId"] == "TX-001"
        assert user["appleSubscriptionGroupId"] == "GROUP-1"
        assert user["appleEnvironment"] == "sandbox"
        assert isinstance(user["appleAutoRenewStatus"], bool)
        assert isinstance(user["appleLastVerifiedAt"], datetime)
        assert user["subscriptionStatus"] == "active"

    def test_idempotent_second_call_does_not_error(self):
        from app.services.apple_subscription_service import verify_apple_transaction_and_grant_entitlement
        import mongomock

        mc = mongomock.MongoClient()
        col = mc["test"]["users"]
        col.insert_one({"_id": FAKE_USER_OBJ_ID, "subscriptionStatus": "free"})

        decoded = _make_decoded_tx()
        env = _make_sandbox_env()

        ps = _apple_patches(col, decoded, env)
        for p in ps:
            p.start()
        try:
            verify_apple_transaction_and_grant_entitlement(FAKE_USER_ID, "dummy.jws.payload")
            verify_apple_transaction_and_grant_entitlement(FAKE_USER_ID, "dummy.jws.payload")
        finally:
            for p in ps:
                p.stop()

        assert col.count_documents({}) == 1
