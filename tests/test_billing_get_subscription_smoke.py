"""
Smoke script: GET /api/subscriptions/{user_id} — extended entitlement fields.

Requires:
    BILLING_TEST_USER_ID  – MongoDB ObjectId of a test user

Run:
    python tests/test_billing_get_subscription_smoke.py [ios|android]
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import requests
from tests._billing_smoke import BACKEND_URL, make_token, pprint_json, require_user_id

ENTITLEMENT_FIELDS = [
    "billingProvider",
    "subscriptionStatus",
    "entitlement_active",
    "can_initiate_new_paid_subscription",
    "cross_platform_billing",
    "entitlement_source",
]


def main():
    user_id = require_user_id()
    platform = sys.argv[1] if len(sys.argv) > 1 else None

    token = make_token(user_id)
    headers: dict = {"Authorization": f"Bearer {token}"}
    if platform:
        headers["X-Client-Platform"] = platform
        headers["X-Billing-Correlation-Id"] = f"smoke-get-sub-{platform}"

    url = f"{BACKEND_URL}/api/subscriptions/{user_id}"
    print(f"GET {url}")
    if platform:
        print(f"  X-Client-Platform: {platform}")

    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.ConnectionError:
        print(f"Connection refused — is the server running on {BACKEND_URL}?")
        sys.exit(1)

    pprint_json(f"HTTP {resp.status_code} — full response", resp.json())

    if resp.ok:
        data = resp.json()
        print("\n─── Entitlement fields ───")
        for field in ENTITLEMENT_FIELDS:
            print(f"  {field}: {data.get(field)}")
        echoed = resp.headers.get("X-Billing-Correlation-Id")
        print(f"\n  X-Billing-Correlation-Id echoed: {echoed!r}")


if __name__ == "__main__":
    main()
