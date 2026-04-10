"""
Test script to verify subscription tier filtering on /subscriptions/plans and /subscriptions/products.

Generates a JWT for user_id 693326c07fcdaab8e81cdd2f and hits both endpoints
with and without the token, printing the results side-by-side.

Usage: python tests/test_subscription_tiers.py
"""

import sys
import os

# Ensure project root is on sys.path so app imports resolve
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import requests
from app.core.config import settings
from app.services.user_service import _make_signed_token, _apply_standard_jwt_claims
import time

BACKEND_URL = f"http://localhost:{settings.PORT}"
USER_ID = "693326c07fcdaab8e81cdd2f"


def make_token(user_id: str) -> str:
    now = int(time.time())
    payload = _apply_standard_jwt_claims({
        "sub": user_id,
        "type": "access",
        "iat": now,
        "exp": now + 3600,
    })
    return _make_signed_token(payload, settings.JWT_SECRET)


def test_endpoint(path: str, token: str | None = None):
    url = f"{BACKEND_URL}/api{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    label = "WITH token" if token else "NO token  "
    try:
        resp = requests.get(url, headers=headers, timeout=10)
    except requests.ConnectionError:
        print(f"  [{label}] Connection refused — is the server running on {BACKEND_URL}?")
        return

    data = resp.json()

    if "plans" in data:
        plans = data["plans"]
        print(f"  [{label}] {resp.status_code} — {len(plans)} plan(s)")
        for p in plans:
            print(f"      • {p.get('name', '?')}  (tier={p.get('tier', '?')}, id={p.get('productId', '?')})")
    elif "data" in data:
        products = data["data"]
        print(f"  [{label}] {resp.status_code} — {len(products)} product(s)")
        for p in products:
            meta = p.get("metadata") or {}
            print(f"      • {p.get('name', '?')}  (tier={meta.get('tier', '0')}, id={p.get('id', '?')})")
    else:
        print(f"  [{label}] {resp.status_code} — {data}")


def main():
    token = make_token(USER_ID)
    print(f"JWT generated for user {USER_ID}\n")

    print("/subscriptions/plans")
    test_endpoint("/subscriptions/plans")
    test_endpoint("/subscriptions/plans", token)

    print()
    print("/subscriptions/products")
    test_endpoint("/subscriptions/products")
    test_endpoint("/subscriptions/products", token)


if __name__ == "__main__":
    main()
