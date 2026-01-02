#!/usr/bin/env python3
"""
Test script to get user's active subscription via API endpoint
Tests the /api/subscriptions/{user_id} endpoint
"""

import sys
import os
import json
import requests
from typing import Optional

def test_get_subscription_api(user_id: str, base_url: str = "http://localhost:8000") -> None:
    """
    Test the GET /api/subscriptions/{user_id} endpoint
    
    Args:
        user_id: User ID to test
        base_url: Base URL of the API (default: http://localhost:8000)
    """
    url = f"{base_url}/api/subscriptions/{user_id}"
    
    print("=" * 80)
    print("Test: Get User Active Subscription via API")
    print("=" * 80)
    print(f"\nEndpoint: GET {url}")
    print("-" * 80)
    
    try:
        response = requests.get(url, timeout=10)
        
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
    # Get user ID from command line or use default
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = input("Enter user ID (or press Enter to use test user): ").strip()
        if not user_id:
            # Use a test user ID - replace with an actual user ID from your database
            user_id = "69542cc3cba6c3d6b28a2792"
            print(f"Using test user ID: {user_id}")
    
    # Get base URL from command line or use default
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    
    test_get_subscription_api(user_id, base_url)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)

