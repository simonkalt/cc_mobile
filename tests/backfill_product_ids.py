#!/usr/bin/env python3
"""
Script to backfill product IDs for existing subscriptions that don't have them
"""

import sys
import os
from bson import ObjectId

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app.services.subscription_service import _get_stripe_module, STRIPE_AVAILABLE
    from app.db.mongodb import connect_to_mongodb, is_connected, get_collection
    from app.utils.user_helpers import USERS_COLLECTION
    from dotenv import load_dotenv
    import logging
    
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    
    # Load environment variables
    load_dotenv()
    
    # Connect to MongoDB
    if not is_connected():
        print("Connecting to MongoDB...")
        connect_to_mongodb()
    
    if not is_connected():
        print("ERROR: Could not connect to MongoDB")
        sys.exit(1)
    
    if not STRIPE_AVAILABLE:
        print("ERROR: Stripe library not available")
        print("\nTo fix this:")
        print("1. Make sure you're in the correct Python environment (WSL venv)")
        print("2. Install Stripe: pip install stripe>=7.0.0")
        print("3. Make sure STRIPE_API_KEY or STRIPE_TEST_API_KEY is set in .env")
        sys.exit(1)
    
    print("=" * 80)
    print("Backfill Product IDs for Existing Subscriptions")
    print("=" * 80)
    print()
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        print("ERROR: Could not access users collection")
        sys.exit(1)
    
    stripe_to_use = _get_stripe_module()
    if not stripe_to_use:
        print("ERROR: Could not get Stripe module")
        print("\nMake sure:")
        print("1. Stripe is installed: pip install stripe>=7.0.0")
        print("2. STRIPE_API_KEY or STRIPE_TEST_API_KEY is set in .env")
        sys.exit(1)
    
    # Verify API key is configured
    from app.core.config import settings
    stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
    if not stripe_api_key:
        print("ERROR: Stripe API key not configured")
        print("\nPlease set STRIPE_API_KEY or STRIPE_TEST_API_KEY in your .env file")
        sys.exit(1)
    
    # Find all users with subscriptions but no product ID
    users = collection.find({
        "subscriptionId": {"$exists": True, "$ne": None},
        "$or": [
            {"subscriptionProductId": {"$exists": False}},
            {"subscriptionProductId": None}
        ]
    })
    
    user_list = list(users)
    total_users = len(user_list)
    
    if total_users == 0:
        print("No users found that need product ID backfill.")
    else:
        print(f"Found {total_users} user(s) with subscriptions missing product IDs:\n")
        
        updated_count = 0
        failed_count = 0
        
        for user in user_list:
            user_id = str(user.get("_id", ""))
            subscription_id = user.get("subscriptionId")
            price_id = user.get("subscriptionPlan")
            
            print(f"Processing user {user_id}...")
            print(f"  Subscription ID: {subscription_id}")
            print(f"  Price ID: {price_id}")
            
            try:
                product_id = None
                
                # Try to get product ID from subscription
                if subscription_id:
                    try:
                        subscription = stripe_to_use.Subscription.retrieve(
                            subscription_id,
                            expand=["items.data.price.product"]
                        )
                        
                        if subscription.items.data and len(subscription.items.data) > 0:
                            price_obj = subscription.items.data[0].price
                            
                            # Try to get product ID from expanded price object
                            if hasattr(price_obj, "product") and price_obj.product:
                                if isinstance(price_obj.product, str):
                                    product_id = price_obj.product
                                elif hasattr(price_obj.product, "id"):
                                    product_id = price_obj.product.id
                    except Exception as e:
                        logger.warning(f"Could not retrieve subscription {subscription_id}: {e}")
                
                # Fallback: try to get from price ID directly
                if not product_id and price_id and price_id != "free":
                    try:
                        price = stripe_to_use.Price.retrieve(price_id, expand=["product"])
                        if hasattr(price, "product"):
                            if isinstance(price.product, str):
                                product_id = price.product
                            elif hasattr(price.product, "id"):
                                product_id = price.product.id
                    except Exception as e:
                        logger.warning(f"Could not retrieve price {price_id}: {e}")
                
                if product_id:
                    # Update database
                    collection.update_one(
                        {"_id": ObjectId(user_id)},
                        {"$set": {"subscriptionProductId": product_id}}
                    )
                    print(f"  ✅ Updated with product ID: {product_id}")
                    updated_count += 1
                else:
                    print(f"  ❌ Could not find product ID")
                    failed_count += 1
                    
            except Exception as e:
                print(f"  ❌ Error: {e}")
                failed_count += 1
                import traceback
                traceback.print_exc()
            
            print()
        
        print("=" * 80)
        print(f"Summary: {updated_count} updated, {failed_count} failed")
        print("=" * 80)

except ImportError as e:
    print(f"ERROR: Could not import required modules: {e}")
    print("\nMake sure you're running this from the project root directory")
    print("and that all dependencies are installed:")
    print("  pip install -r requirements.txt")
    sys.exit(1)
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

