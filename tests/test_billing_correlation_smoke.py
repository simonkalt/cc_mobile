"""
Smoke script: X-Billing-Correlation-Id echo verification.

Requires:
    BILLING_TEST_USER_ID  – MongoDB ObjectId of a test user

Run:
    python tests/test_billing_correlation_smoke.py

The script:
1. Sends a fixed correlation id to GET /api/subscriptions/purchase-eligibility.
2. Asserts the server echoes the exact id.
3. Sends the same id to POST /api/subscriptions/apple/verify (even though it will fail
   the Apple check) and verifies the header is echoed.
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import requests
from tests._billing_smoke import BACKEND_URL, make_token, require_user_id

CORRELATION_HEADER = "X-Billing-Correlation-Id"
TEST_CORRELATION_ID = "smoke-correlation-fixed-id-9999"


def check(label: str, passed: bool) -> None:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}] {label}")


def main():
    user_id = require_user_id()
    token = make_token(user_id)
    auth_headers = {
        "Authorization": f"Bearer {token}",
        CORRELATION_HEADER: TEST_CORRELATION_ID,
    }

    print(f"\nTesting correlation echo on {BACKEND_URL}")

    # --- GET purchase-eligibility ---
    try:
        resp = requests.get(
            f"{BACKEND_URL}/api/subscriptions/purchase-eligibility",
            headers=auth_headers,
            timeout=10,
        )
    except requests.ConnectionError:
        print(f"Connection refused — is the server running on {BACKEND_URL}?")
        sys.exit(1)

    echoed = resp.headers.get(CORRELATION_HEADER)
    print(f"\nGET /api/subscriptions/purchase-eligibility → HTTP {resp.status_code}")
    check("Correlation id echoed", echoed == TEST_CORRELATION_ID)
    print(f"  Sent:   {TEST_CORRELATION_ID!r}")
    print(f"  Echoed: {echoed!r}")

    # --- POST apple/verify (will fail, but correlation header should still be echoed) ---
    resp2 = requests.post(
        f"{BACKEND_URL}/api/subscriptions/apple/verify",
        json={"user_id": user_id, "signedTransaction": "smoke.x.y"},
        headers={**auth_headers, "Content-Type": "application/json"},
        timeout=10,
    )
    echoed2 = resp2.headers.get(CORRELATION_HEADER)
    print(f"\nPOST /api/subscriptions/apple/verify → HTTP {resp2.status_code}")
    check("Correlation id echoed on error response", echoed2 == TEST_CORRELATION_ID)
    print(f"  Sent:   {TEST_CORRELATION_ID!r}")
    print(f"  Echoed: {echoed2!r}")

    # --- Non-billing path should not have the header set by our middleware ---
    resp3 = requests.get(f"{BACKEND_URL}/api/version", timeout=5)
    has_on_non_billing = CORRELATION_HEADER in resp3.headers
    print(f"\nGET /api/version → HTTP {resp3.status_code}")
    check("Correlation header absent on non-billing path", not has_on_non_billing)

    print()


if __name__ == "__main__":
    main()
