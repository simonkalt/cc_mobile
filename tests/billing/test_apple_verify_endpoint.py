"""
Step 1: TestClient tests for POST /api/subscriptions/apple/verify.

Patches the Apple service so no real App Store connection is needed.
"""

from __future__ import annotations

from unittest.mock import patch, MagicMock

import pytest

from tests.billing.conftest import FAKE_USER_ID


@pytest.fixture
def _apple_success(mongomock_users):
    """Patch apple service to succeed; recompute_and_persist is also a no-op.

    The router imports ``verify_apple_transaction_and_grant_entitlement`` at module level,
    so we must patch the name in the ROUTER module, not in the service module.
    """
    from app.models.subscription import SubscriptionResponse

    fake_sub = SubscriptionResponse(
        subscriptionStatus="active",
        subscriptionPlan="com.example.monthly",
        billingProvider="apple",
        appleProductId="com.example.monthly",
        subscriptionId="ORIG-TX-001",
        entitlement_active=True,
        can_initiate_new_paid_subscription=False,
    )

    with (
        patch(
            "app.api.routers.subscriptions.verify_apple_transaction_and_grant_entitlement"
        ),
        patch(
            "app.api.routers.subscriptions.get_user_subscription",
            return_value=fake_sub,
        ),
    ):
        yield


class TestAppleVerifyEndpoint:
    def test_success_returns_subscription(self, client, _apple_success):
        resp = client.post(
            "/api/subscriptions/apple/verify",
            json={
                "user_id": FAKE_USER_ID,
                "signedTransaction": "dummy.jws.token",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert "subscription" in body
        assert body["subscription"]["billingProvider"] == "apple"
        assert body["subscription"]["entitlement_active"] is True
        assert body["subscription"]["can_initiate_new_paid_subscription"] is False

    def test_user_id_mismatch_returns_user_mismatch_code(self, client):
        """Authenticated user ID doesn't match the body user_id."""
        resp = client.post(
            "/api/subscriptions/apple/verify",
            json={
                "user_id": "000000000000000000000000",  # different from FAKE_USER_ID
                "signedTransaction": "dummy.jws.token",
            },
        )
        assert resp.status_code == 403
        body = resp.json()
        assert body.get("code") == "user_mismatch"

    def test_apple_billing_error_propagates_code(self, client):
        """AppleBillingError raised by the service is surfaced with its stable code."""
        from app.services.apple_subscription_service import AppleBillingError

        with patch(
            "app.api.routers.subscriptions.verify_apple_transaction_and_grant_entitlement",
            side_effect=AppleBillingError("apple_validation_failed", "Bad JWS", 400),
        ):
            resp = client.post(
                "/api/subscriptions/apple/verify",
                json={
                    "user_id": FAKE_USER_ID,
                    "signedTransaction": "bad.jws",
                },
            )
        assert resp.status_code == 400
        body = resp.json()
        assert body.get("code") == "apple_validation_failed"
        assert "detail" in body

    def test_transaction_already_consumed_409(self, client):
        from app.services.apple_subscription_service import AppleBillingError

        with patch(
            "app.api.routers.subscriptions.verify_apple_transaction_and_grant_entitlement",
            side_effect=AppleBillingError(
                "transaction_already_consumed",
                "Already linked to another account",
                409,
            ),
        ):
            resp = client.post(
                "/api/subscriptions/apple/verify",
                json={
                    "user_id": FAKE_USER_ID,
                    "signedTransaction": "consumed.jws",
                },
            )
        assert resp.status_code == 409
        assert resp.json().get("code") == "transaction_already_consumed"
