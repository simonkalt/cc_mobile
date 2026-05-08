"""
Step 2: Table-driven unit tests for entitlement_service.compute_entitlement
and compute_eligibility.

No I/O — purely functional tests on the pure functions.
"""

from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta

from app.services.entitlement_service import compute_entitlement, compute_eligibility


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _user(
    billing_provider=None,
    subscription_status="free",
    subscription_id=None,
    apple_original_tx_id=None,
):
    return {
        "billingProvider": billing_provider,
        "subscriptionStatus": subscription_status,
        "subscriptionId": subscription_id,
        "appleOriginalTransactionId": apple_original_tx_id,
    }


# ---------------------------------------------------------------------------
# compute_entitlement
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "doc, platform, expected",
    [
        # 1. Free tier
        (
            _user(),
            None,
            {
                "entitlement_active": False,
                "can_initiate_new_paid_subscription": True,
                "cross_platform_billing": False,
                "entitlement_source": None,
            },
        ),
        # 2. Stripe active — iOS: iOS user cannot manage Stripe sub in the iOS app → cross_platform=True
        (
            _user("stripe", "active", "sub_123"),
            "ios",
            {
                "entitlement_active": True,
                "can_initiate_new_paid_subscription": False,
                "cross_platform_billing": True,
                "entitlement_source": "stripe",
            },
        ),
        # 3. Stripe active — Android: Android user manages via Stripe (web) → cross_platform=False
        (
            _user("stripe", "active", "sub_123"),
            "android",
            {
                "entitlement_active": True,
                "can_initiate_new_paid_subscription": False,
                "cross_platform_billing": False,
                "entitlement_source": "stripe",
            },
        ),
        # 4. Stripe trialing — iOS: same as case 2
        (
            _user("stripe", "trialing", "sub_trial"),
            "ios",
            {
                "entitlement_active": True,
                "can_initiate_new_paid_subscription": False,
                "cross_platform_billing": True,
                "entitlement_source": "stripe",
            },
        ),
        # 5. Apple active — iOS (same platform: cross_platform=False)
        (
            _user("apple", "active", apple_original_tx_id="ORIG-001"),
            "ios",
            {
                "entitlement_active": True,
                "can_initiate_new_paid_subscription": False,
                "cross_platform_billing": False,
                "entitlement_source": "apple",
            },
        ),
        # 6. Apple active — Android (management is Apple = iOS; on Android = cross_platform=True)
        (
            _user("apple", "active", apple_original_tx_id="ORIG-001"),
            "android",
            {
                "entitlement_active": True,
                "can_initiate_new_paid_subscription": False,
                "cross_platform_billing": True,
                "entitlement_source": "apple",
            },
        ),
        # 7. past_due is still entitled
        (
            _user("stripe", "past_due", "sub_123"),
            None,
            {
                "entitlement_active": True,
                "can_initiate_new_paid_subscription": False,
                "cross_platform_billing": False,
                "entitlement_source": "stripe",
            },
        ),
        # 8. canceled = not entitled
        (
            _user("stripe", "canceled", "sub_123"),
            None,
            {
                "entitlement_active": False,
                "can_initiate_new_paid_subscription": True,
                "cross_platform_billing": False,
                "entitlement_source": None,
            },
        ),
        # 9. Apple revoked = not entitled
        (
            _user("apple", "revoked", apple_original_tx_id="ORIG-001"),
            "ios",
            {
                "entitlement_active": False,
                "can_initiate_new_paid_subscription": True,
                "cross_platform_billing": False,
                "entitlement_source": None,
            },
        ),
        # 10. Stripe active on iOS — case-insensitive platform handling
        (
            _user("stripe", "active", "sub_123"),
            "IOS",
            {
                "entitlement_active": True,
                "can_initiate_new_paid_subscription": False,
                "cross_platform_billing": True,
                "entitlement_source": "stripe",
            },
        ),
    ],
    ids=[
        "free",
        "stripe_active_ios",
        "stripe_active_android",
        "stripe_trialing_ios",
        "apple_active_ios",
        "apple_active_android_cross",
        "stripe_past_due",
        "stripe_canceled",
        "apple_revoked",
        "stripe_active_ios_uppercase",
    ],
)
def test_compute_entitlement(doc, platform, expected):
    result = compute_entitlement(doc, client_platform=platform)
    assert result == expected


# ---------------------------------------------------------------------------
# cross_platform_billing matrix from spec
# BILLING_UNIFIED_ENTITLEMENT_AND_ELIGIBILITY.md:
#   iOS + stripe  → True
#   Android + apple → True
#   else → False
# ---------------------------------------------------------------------------

def test_cross_platform_ios_stripe():
    """iOS + Stripe → cross_platform_billing=True (iOS user manages on web/Stripe, not in-app)."""
    doc = _user("stripe", "active", "sub_x")
    result = compute_entitlement(doc, client_platform="ios")
    assert result["cross_platform_billing"] is True


def test_cross_platform_android_apple():
    doc = _user("apple", "active", apple_original_tx_id="ORIG-X")
    result = compute_entitlement(doc, client_platform="android")
    assert result["cross_platform_billing"] is True


# ---------------------------------------------------------------------------
# compute_eligibility
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "doc, expected_reason",
    [
        (_user(), "free"),
        (_user("stripe", "active", "sub_x"), "already_entitled"),
        (_user("apple", "active", apple_original_tx_id="ORIG-1"), "already_entitled"),
        (_user("stripe", "canceled", "sub_x"), "lapsed"),
        (_user("apple", "expired", apple_original_tx_id="ORIG-1"), "lapsed"),
    ],
    ids=["free", "stripe_entitled", "apple_entitled", "stripe_lapsed", "apple_lapsed"],
)
def test_compute_eligibility_reasons(doc, expected_reason):
    result = compute_eligibility(doc)
    assert result["reason"] == expected_reason


def test_compute_eligibility_already_entitled_blocks_purchase():
    doc = _user("apple", "active", apple_original_tx_id="ORIG-1")
    result = compute_eligibility(doc)
    assert result["can_initiate_new_paid_subscription"] is False


def test_compute_eligibility_free_allows_purchase():
    doc = _user()
    result = compute_eligibility(doc)
    assert result["can_initiate_new_paid_subscription"] is True
