"""
Smoke script: POST /api/subscriptions/apple/verify

Requires:
    BILLING_TEST_USER_ID  – MongoDB ObjectId of a test user
    BILLING_TEST_SANDBOX_JWS – A real StoreKit 2 signedTransaction from the sandbox

Run:
    python tests/test_billing_apple_verify_smoke.py

The script:
1. POSTs to /api/subscriptions/apple/verify with the JWS.
2. Prints the full HTTP response.
3. Queries MongoDB directly and prints the persisted Apple fields.
4. Lists the appleOriginalTransactionId index on the users collection.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import requests
from tests._billing_smoke import (
    BACKEND_URL,
    make_token,
    pprint_json,
    mongo_find_user,
    require_user_id,
)

APPLE_NEW_FIELDS = [
    "billingProvider",
    "appleProductId",
    "appleOriginalTransactionId",
    "appleLatestTransactionId",
    "appleSubscriptionGroupId",
    "appleEnvironment",
    "appleAutoRenewStatus",
    "appleLastVerifiedAt",
    "subscriptionStatus",
    "entitlementActive",
    "canInitiateNewPaidSubscription",
    "entitlementSource",
]


def main():
    user_id = require_user_id()
    jws = os.environ.get("BILLING_TEST_SANDBOX_JWS", "")
    if not jws:
        print("ERROR: set BILLING_TEST_SANDBOX_JWS=<sandbox signedTransaction>")
        sys.exit(1)

    token = make_token(user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Billing-Correlation-Id": "smoke-test-apple-verify",
    }
    body = {
        "user_id": user_id,
        "signedTransaction": jws,
    }

    print(f"POST {BACKEND_URL}/api/subscriptions/apple/verify")
    try:
        resp = requests.post(
            f"{BACKEND_URL}/api/subscriptions/apple/verify",
            json=body,
            headers=headers,
            timeout=30,
        )
    except requests.ConnectionError:
        print(f"Connection refused — is the server running on {BACKEND_URL}?")
        sys.exit(1)

    pprint_json(f"HTTP {resp.status_code} response", resp.json())
    echoed_corr = resp.headers.get("X-Billing-Correlation-Id")
    print(f"\n  X-Billing-Correlation-Id echoed: {echoed_corr!r}")

    print("\n─── MongoDB user document (Apple fields) ───")
    user = mongo_find_user(user_id)
    if user:
        subset = {k: user.get(k) for k in APPLE_NEW_FIELDS}
        pprint_json("Apple fields", subset)
    else:
        print("  User not found in MongoDB")

    # Check unique index exists
    from app.db.mongodb import get_collection
    from app.utils.user_helpers import USERS_COLLECTION

    col = get_collection(USERS_COLLECTION)
    if col is not None:
        indexes = list(col.list_indexes())
        idx_names = [idx.get("name") for idx in indexes]
        print(f"\n  Indexes on users collection: {idx_names}")
        has_apple_idx = any("apple" in (n or "").lower() for n in idx_names)
        print(f"  Apple unique index present: {has_apple_idx}")


if __name__ == "__main__":
    main()
