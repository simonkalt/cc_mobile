"""
Smoke script: GET /api/subscriptions/purchase-eligibility

Requires:
    BILLING_TEST_USER_ID  – MongoDB ObjectId of a test user

Run:
    python tests/test_billing_eligibility_smoke.py [ios|android]
"""

from __future__ import annotations

import os
import sys

_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import requests
from tests._billing_smoke import BACKEND_URL, make_token, pprint_json, require_user_id


def main():
    user_id = require_user_id()
    platform = sys.argv[1] if len(sys.argv) > 1 else ""

    token = make_token(user_id)
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Billing-Correlation-Id": "smoke-eligibility",
    }
    params = {}
    if platform:
        params["platform"] = platform

    url = f"{BACKEND_URL}/api/subscriptions/purchase-eligibility"
    print(f"GET {url}" + (f"?platform={platform}" if platform else ""))

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=10)
    except requests.ConnectionError:
        print(f"Connection refused — is the server running on {BACKEND_URL}?")
        sys.exit(1)

    pprint_json(f"HTTP {resp.status_code}", resp.json())
    echoed = resp.headers.get("X-Billing-Correlation-Id")
    print(f"\n  X-Billing-Correlation-Id echoed: {echoed!r}")


if __name__ == "__main__":
    main()
