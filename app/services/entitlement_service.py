"""
Unified entitlement computation and persistence.

This module is the single source of truth for the four entitlement fields exposed to mobile:

    entitlement_active              – user currently has premium access
    can_initiate_new_paid_sub       – safe to start a new paid subscription
    cross_platform_billing          – management happens on a different OS surface
    entitlement_source              – "stripe" | "apple" | None

compute_entitlement()  – pure function; call from GET /subscriptions/{user_id}
compute_eligibility()  – pure function; call from GET /subscriptions/purchase-eligibility
recompute_and_persist() – writes the platform-agnostic fields to MongoDB;
                          called from every write path (Apple verify, ASSN, Stripe webhook).

Conflict policy when both Stripe and Apple subscriptions are active simultaneously:
Stripe wins (prefer Stripe as it is the older, more-established integration).
This matches the recommended default in BILLING_UNIFIED_ENTITLEMENT_AND_ELIGIBILITY.md.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Subscription statuses that grant active entitlement.
_ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})


def _is_entitled(billing_provider: Optional[str], subscription_status: Optional[str]) -> bool:
    """Return True when the user currently has premium access."""
    if not billing_provider:
        return False
    return str(subscription_status or "").lower() in _ACTIVE_STATUSES


def compute_entitlement(
    user_doc: Dict[str, Any],
    *,
    client_platform: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute the four unified entitlement fields from a raw MongoDB user document.

    Args:
        user_doc: Raw dict from the users collection.
        client_platform: ``"ios"`` or ``"android"`` (case-insensitive).  When supplied,
            ``cross_platform_billing`` is computed; otherwise it defaults to ``False``.

    Returns:
        Dict with keys:
            entitlement_active, can_initiate_new_paid_subscription,
            cross_platform_billing, entitlement_source.
    """
    bp = user_doc.get("billingProvider")
    status_str = str(user_doc.get("subscriptionStatus") or "").lower()

    # Conflict resolution: when both providers have active-looking data, Stripe wins.
    stripe_active = bp == "stripe" and status_str in _ACTIVE_STATUSES
    apple_active = bp == "apple" and status_str in _ACTIVE_STATUSES

    if stripe_active:
        effective_bp: Optional[str] = "stripe"
        is_active = True
    elif apple_active:
        effective_bp = "apple"
        is_active = True
    else:
        effective_bp = bp if bp else None
        is_active = False

    platform = (client_platform or "").lower().strip()
    cross_platform = (
        (platform == "ios" and effective_bp == "stripe")
        or (platform == "android" and effective_bp == "apple")
    )

    return {
        "entitlement_active": bool(is_active),
        "can_initiate_new_paid_subscription": not is_active,
        "cross_platform_billing": bool(cross_platform),
        "entitlement_source": effective_bp if is_active else None,
    }


def compute_eligibility(
    user_doc: Dict[str, Any],
    platform: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute purchase eligibility for GET /api/subscriptions/purchase-eligibility.

    Returns:
        Dict with keys:
            can_initiate_new_paid_subscription (bool),
            reason ("free" | "already_entitled" | "lapsed"),
            billing_provider (str | None).
    """
    entitlement = compute_entitlement(user_doc, client_platform=platform)
    bp = user_doc.get("billingProvider")

    has_stripe = bool(user_doc.get("subscriptionId"))
    has_apple = bool(user_doc.get("appleOriginalTransactionId"))
    ever_subscribed = has_stripe or has_apple

    if entitlement["entitlement_active"]:
        reason = "already_entitled"
    elif not ever_subscribed:
        reason = "free"
    else:
        reason = "lapsed"

    return {
        "can_initiate_new_paid_subscription": entitlement["can_initiate_new_paid_subscription"],
        "reason": reason,
        "billing_provider": bp,
    }


def recompute_and_persist(user_id: str) -> Optional[Dict[str, Any]]:
    """Load the user from Mongo, recompute platform-agnostic entitlement fields, and ``$set``
    them back.  Does NOT set ``cross_platform_billing`` (caller OS is unknown here).

    Emits structured log events ``entitlement_recompute_ok`` and ``entitlement_recompute_fail``
    as required by BILLING_OBSERVABILITY.md.

    Returns the computed entitlement dict on success, or None on failure.
    """
    from bson import ObjectId

    from app.db.mongodb import get_collection, is_connected
    from app.utils.user_helpers import USERS_COLLECTION

    if not is_connected():
        logger.warning(
            "entitlement_recompute_fail user_id=%s reason=db_unavailable", user_id
        )
        return None

    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        logger.warning(
            "entitlement_recompute_fail user_id=%s reason=collection_unavailable", user_id
        )
        return None

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        logger.warning(
            "entitlement_recompute_fail user_id=%s reason=invalid_id", user_id
        )
        return None

    user_doc = collection.find_one({"_id": user_id_obj})
    if not user_doc:
        logger.warning(
            "entitlement_recompute_fail user_id=%s reason=user_not_found", user_id
        )
        return None

    try:
        result = compute_entitlement(user_doc)

        persist_fields: Dict[str, Any] = {
            "entitlementActive": result["entitlement_active"],
            "canInitiateNewPaidSubscription": result["can_initiate_new_paid_subscription"],
            "entitlementSource": result["entitlement_source"],
            "entitlementUpdatedAt": datetime.now(timezone.utc),
        }
        collection.update_one({"_id": user_id_obj}, {"$set": persist_fields})

        logger.info(
            "entitlement_recompute_ok user_id=%s entitlement_active=%s billing_provider=%s",
            user_id,
            result["entitlement_active"],
            user_doc.get("billingProvider"),
        )
        return result
    except Exception as exc:
        logger.error(
            "entitlement_recompute_fail user_id=%s error=%s",
            user_id,
            exc,
            exc_info=True,
        )
        return None
