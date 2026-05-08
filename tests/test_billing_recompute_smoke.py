"""
Smoke script: unified entitlement recompute via update_user_subscription.

Requires:
    BILLING_TEST_USER_ID – MongoDB ObjectId of a test user

Run:
    python tests/test_billing_recompute_smoke.py

The script:
1. Calls update_user_subscription() directly to set the user to 'active'.
2. Queries MongoDB and prints entitlementActive / entitlementSource.
3. Calls update_user_subscription() again to set back to 'free'.
4. Verifies entitlementActive flipped to False.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from tests._billing_smoke import pprint_json, mongo_find_user, require_user_id
from app.db.mongodb import connect_to_mongodb, is_connected


def main():
    if not is_connected():
        connect_to_mongodb()

    user_id = require_user_id()

    from app.services.subscription_service import update_user_subscription

    print("\n─── Step 1: set subscription to active ───")
    update_user_subscription(
        user_id=user_id,
        subscription_id="sub_smoke_test",
        subscription_status="active",
        subscription_plan="price_smoke_monthly",
        stripe_customer_id=None,
    )
    user = mongo_find_user(user_id)
    if user:
        pprint_json(
            "Entitlement fields after activate",
            {k: user.get(k) for k in ("entitlementActive", "entitlementSource", "entitlementUpdatedAt")},
        )
        assert user.get("entitlementActive") is True, "Expected entitlementActive=True after activate"
        print("  PASS entitlementActive=True")
    else:
        print("  ERROR: user not found")
        sys.exit(1)

    print("\n─── Step 2: reset to free ───")
    update_user_subscription(
        user_id=user_id,
        subscription_id=None,
        subscription_status="free",
        subscription_plan="free",
    )
    user = mongo_find_user(user_id)
    if user:
        pprint_json(
            "Entitlement fields after reset",
            {k: user.get(k) for k in ("entitlementActive", "entitlementSource", "entitlementUpdatedAt")},
        )
        assert user.get("entitlementActive") is False, "Expected entitlementActive=False after reset"
        print("  PASS entitlementActive=False")
    else:
        print("  ERROR: user not found")
        sys.exit(1)

    print("\nSmoke test PASSED\n")


if __name__ == "__main__":
    main()
