#!/usr/bin/env python3
"""
Test script to get a user's active subscription(s)
Tests both the service function and the API endpoint
"""

import sys
import os
import json
from datetime import datetime

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app.services.subscription_service import get_user_subscription
    from app.db.mongodb import connect_to_mongodb, is_connected
    from dotenv import load_dotenv
    
    # Load environment variables
    load_dotenv()
    
    # Connect to MongoDB
    if not is_connected():
        print("Connecting to MongoDB...")
        connect_to_mongodb()
    
    if not is_connected():
        print("ERROR: Could not connect to MongoDB")
        sys.exit(1)
    
    print("=" * 80)
    print("Test: Get User Active Subscription")
    print("=" * 80)
    print()
    
    # Get user ID from command line or use default
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = input("Enter user ID (or press Enter to use test user): ").strip()
        if not user_id:
            # Use a test user ID - replace with an actual user ID from your database
            user_id = "69542cc3cba6c3d6b28a2792"
            print(f"Using test user ID: {user_id}")
    
    print(f"\nFetching subscription for user: {user_id}")
    print("-" * 80)
    
    try:
        # Get subscription using service function
        subscription = get_user_subscription(user_id)
        
        print("\n✅ Subscription Retrieved Successfully!")
        print("\nSubscription Details:")
        print(f"  Subscription ID:      {subscription.subscriptionId or 'None'}")
        print(f"  Status:               {subscription.subscriptionStatus}")
        print(f"  Plan (Price ID):      {subscription.subscriptionPlan}")
        print(f"  Product ID:           {subscription.productId or 'None'}")
        print(f"  Current Period End:   {subscription.subscriptionCurrentPeriodEnd or 'None'}")
        print(f"  Last Payment Date:    {subscription.lastPaymentDate or 'None'}")
        print(f"  Stripe Customer ID:   {subscription.stripeCustomerId or 'None'}")
        
        # Format as JSON for easy inspection
        print("\n" + "-" * 80)
        print("JSON Format:")
        print("-" * 80)
        subscription_dict = {
            "subscriptionId": subscription.subscriptionId,
            "subscriptionStatus": subscription.subscriptionStatus,
            "subscriptionPlan": subscription.subscriptionPlan,
            "productId": subscription.productId,
            "subscriptionCurrentPeriodEnd": (
                subscription.subscriptionCurrentPeriodEnd.isoformat() 
                if subscription.subscriptionCurrentPeriodEnd 
                else None
            ),
            "lastPaymentDate": (
                subscription.lastPaymentDate.isoformat() 
                if subscription.lastPaymentDate 
                else None
            ),
            "stripeCustomerId": subscription.stripeCustomerId,
        }
        print(json.dumps(subscription_dict, indent=2))
        
        # Test API endpoint
        print("\n" + "=" * 80)
        print("Testing API Endpoint")
        print("=" * 80)
        print(f"\nTo test the API endpoint, run:")
        print(f"  curl http://localhost:8000/api/subscriptions/{user_id}")
        print(f"\nOr use Python requests:")
        print(f"  import requests")
        print(f"  response = requests.get('http://localhost:8000/api/subscriptions/{user_id}')")
        print(f"  print(response.json())")
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

except ImportError as e:
    print(f"ERROR: Could not import required modules: {e}")
    print("\nMake sure you're running this from the project root directory")
    print("and that all dependencies are installed:")
    print("  pip install -r requirements.txt")
    sys.exit(1)

except KeyboardInterrupt:
    print("\n\nInterrupted by user")
    sys.exit(0)

