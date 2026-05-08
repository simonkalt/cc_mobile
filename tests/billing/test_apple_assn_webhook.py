"""
App Store Server Notifications v2 — canonical webhook URL and legacy alias.
"""

from __future__ import annotations

import uuid
from unittest.mock import patch

import pytest


@pytest.fixture
def _assn_ok():
    """ASN handler succeeds without touching Mongo or Apple."""
    with (
        patch(
            "app.api.routers.subscriptions.apple_subscription_configured",
            return_value=True,
        ),
        patch(
            "app.api.routers.subscriptions.process_apple_server_notification_v2",
            return_value={"handled": True, "duplicate": True},
        ),
    ):
        yield


class TestAppleSubscriptionWebhook:
    def test_canonical_webhook_accepts_signed_payload(self, client, _assn_ok):
        resp = client.post(
            "/api/webhooks/apple/subscriptions",
            json={"signedPayload": "header.payload.sig"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("received") is True
        assert data.get("duplicate") is True

    def test_legacy_notifications_same_behavior(self, client, _assn_ok):
        resp = client.post(
            "/api/subscriptions/apple/notifications",
            json={"signedPayload": "header.payload.sig"},
        )
        assert resp.status_code == 200
        assert resp.json().get("received") is True

    def test_missing_signed_payload_400(self, client):
        with patch(
            "app.api.routers.subscriptions.apple_subscription_configured",
            return_value=True,
        ):
            resp = client.post(
                "/api/webhooks/apple/subscriptions",
                json={},
            )
        assert resp.status_code == 400

    def test_webhook_echoes_billing_correlation_id(self, client, _assn_ok):
        my_id = "asn-test-" + str(uuid.uuid4())[:8]
        resp = client.post(
            "/api/webhooks/apple/subscriptions",
            json={"signedPayload": "header.payload.sig"},
            headers={"X-Billing-Correlation-Id": my_id},
        )
        assert resp.status_code == 200
        assert resp.headers.get("X-Billing-Correlation-Id") == my_id
