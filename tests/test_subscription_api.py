#!/usr/bin/env python3
"""
Test script to get user's active subscription via API endpoint
Tests the GET /api/subscriptions/{user_id} endpoint (requires JWT).

Auth (in order):
  1. JWT_TOKEN or ACCESS_TOKEN in env
  2. JWT_SECRET_KEY in env (.env) – script creates a token for user_id
  3. JWT_EMAIL + JWT_PASSWORD in env – script logs in to get a token
"""

import sys
import os
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Load .env from project root so JWT_SECRET_KEY is available
_env_path = Path(__file__).resolve().parent.parent / ".env"
if _env_path.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv(_env_path)
    except ImportError:
        pass

import requests


def _create_token_for_user(user_id: str) -> Optional[str]:
    """Create a JWT for user_id using JWT_SECRET_KEY and JWT_ALGORITHM from env (same as app)."""
    secret = os.environ.get("JWT_SECRET_KEY")
    if not secret or secret == "your-secret-key-change-in-production":
        return None
    algorithm = os.environ.get("JWT_ALGORITHM", "HS256")
    expire_minutes = int(os.environ.get("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    try:
        from jose import jwt
        now = datetime.utcnow()
        payload = {
            "sub": user_id,
            "exp": now + timedelta(minutes=expire_minutes),
            "iat": now,
            "type": "access",
        }
        return jwt.encode(payload, secret, algorithm=algorithm)
    except Exception:
        return None


def _get_token(
    base_url: str,
    user_id: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> Optional[str]:
    token = os.environ.get("JWT_TOKEN") or os.environ.get("ACCESS_TOKEN")
    if token:
        return token.strip()
    if user_id:
        created = _create_token_for_user(user_id)
        if created:
            return created
    if email and password:
        try:
            r = requests.post(
                f"{base_url}/api/users/login",
                json={"email": email, "password": password},
                timeout=10,
            )
            if r.status_code == 200:
                data = r.json()
                return data.get("access_token")
        except Exception:
            pass
    return None


def test_get_subscription_api(
    user_id: str,
    base_url: str = "http://localhost:8000",
    token: Optional[str] = None,
    email: Optional[str] = None,
    password: Optional[str] = None,
) -> None:
    """
    Test the GET /api/subscriptions/{user_id} endpoint (requires JWT).

    Args:
        user_id: User ID to test
        base_url: Base URL of the API
        token: JWT (or set JWT_TOKEN / ACCESS_TOKEN in env)
        email: Login email (if no token)
        password: Login password (if no token)
    """
    url = f"{base_url}/api/subscriptions/{user_id}"
    auth_token = token or _get_token(base_url, user_id=user_id, email=email, password=password)

    if not auth_token:
        print("=" * 80)
        print("Test: Get User Active Subscription via API")
        print("=" * 80)
        print("\n❌ Not authenticated. This endpoint requires a JWT.")
        print("   Option 1: Set JWT_SECRET_KEY in .env (script will create a token for user_id).")
        print("   Option 2: Set JWT_TOKEN or ACCESS_TOKEN in the environment.")
        print("   Option 3: Set JWT_EMAIL + JWT_PASSWORD so the script can login.")
        return

    headers = {"Authorization": f"Bearer {auth_token}"}

    print("=" * 80)
    print("Test: Get User Active Subscription via API")
    print("=" * 80)
    print(f"\nEndpoint: GET {url}")
    print("-" * 80)

    try:
        response = requests.get(url, headers=headers, timeout=10)
        
        print(f"\nStatus Code: {response.status_code}")
        
        if response.status_code == 200:
            subscription = response.json()
            
            print("\n✅ Subscription Retrieved Successfully!")
            print("\nSubscription Details:")
            print(f"  Subscription ID:      {subscription.get('subscriptionId') or 'None'}")
            print(f"  Status:               {subscription.get('subscriptionStatus', 'free')}")
            print(f"  Plan (Price ID):      {subscription.get('subscriptionPlan', 'free')}")
            print(f"  Product ID:           {subscription.get('productId') or 'None'}")
            
            current_period_end = subscription.get('subscriptionCurrentPeriodEnd')
            if current_period_end:
                print(f"  Current Period End:   {current_period_end}")
            else:
                print(f"  Current Period End:   None")
            
            last_payment_date = subscription.get('lastPaymentDate')
            if last_payment_date:
                print(f"  Last Payment Date:    {last_payment_date}")
            else:
                print(f"  Last Payment Date:    None")
            
            print(f"  Stripe Customer ID:   {subscription.get('stripeCustomerId') or 'None'}")
            
            print("\n" + "-" * 80)
            print("Full JSON Response:")
            print("-" * 80)
            print(json.dumps(subscription, indent=2, default=str))
            
            # Check if productId is present
            if subscription.get('productId'):
                print("\n✅ Product ID is present in response!")
            else:
                print("\n⚠️  Product ID is missing from response")
                
        elif response.status_code == 401:
            print(f"\n❌ Unauthorized (401). Token may be expired or invalid.")
            print(f"Response: {response.text}")
        elif response.status_code == 404:
            print(f"\n❌ User not found: {user_id}")
            print(f"Response: {response.text}")
        elif response.status_code == 400:
            print(f"\n❌ Bad Request: Invalid user ID format")
            print(f"Response: {response.text}")
        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"Response: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print(f"\n❌ Error: Could not connect to API at {base_url}")
        print("Make sure the FastAPI server is running:")
        print("  python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000")
    except requests.exceptions.Timeout:
        print(f"\n❌ Error: Request timed out")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()


def main():
    """Main function"""
    # User ID: argv[1], or prompt, or default test user
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = input("Enter user ID (or press Enter to use test user): ").strip()
        if not user_id:
            user_id = "693326c07fcdaab8e81cdd2f"
            print(f"Using test user ID: {user_id}")

    # Base URL: argv[2] or default
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"

    # Optional: login with email/password from env (if no JWT_TOKEN/ACCESS_TOKEN)
    email = os.environ.get("JWT_EMAIL") or os.environ.get("LOGIN_EMAIL")
    password = os.environ.get("JWT_PASSWORD") or os.environ.get("LOGIN_PASSWORD")

    test_get_subscription_api(user_id, base_url, email=email, password=password)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

