#!/usr/bin/env python3
"""
Script to sync user subscription status with Stripe.

This script:
1. Checks a user's subscription status in MongoDB
2. Verifies it against Stripe
3. Updates MongoDB if there's a mismatch (e.g., subscription canceled in Stripe but still active in DB)

Usage:
    python scripts/sync_subscription_status.py [user_id]
    
    If user_id is not provided, it will prompt for it.
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from bson import ObjectId
from datetime import datetime
import logging
from dotenv import load_dotenv

from app.db.mongodb import get_collection, is_connected, connect_to_mongodb
from app.utils.user_helpers import USERS_COLLECTION
from app.services.subscription_service import (
    STRIPE_AVAILABLE,
    _get_stripe_module,
    update_user_subscription,
)

# Load environment variables
load_dotenv()

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def get_user_input(prompt: str, default: str = None) -> str:
    """Get user input with optional default value."""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    user_input = input(full_prompt).strip()
    return user_input if user_input else default


def sync_user_subscription(user_id: str) -> dict:
    """
    Sync a user's subscription status with Stripe.
    
    Args:
        user_id: User ID to sync
        
    Returns:
        Dictionary with sync results
    """
    if not is_connected():
        logger.info("Connecting to MongoDB...")
        connect_to_mongodb()
    
    if not is_connected():
        logger.error("Failed to connect to MongoDB")
        return {"success": False, "error": "MongoDB connection failed"}
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        logger.error("Failed to access users collection")
        return {"success": False, "error": "Failed to access users collection"}
    
    try:
        user_id_obj = ObjectId(user_id)
    except Exception as e:
        logger.error(f"Invalid user ID format: {e}")
        return {"success": False, "error": f"Invalid user ID format: {e}"}
    
    # Get user from database
    user = collection.find_one({"_id": user_id_obj})
    if not user:
        logger.error(f"User {user_id} not found in database")
        return {"success": False, "error": "User not found"}
    
    email = user.get("email", "unknown")
    logger.info(f"Checking subscription for user {user_id} ({email})")
    
    # Get current subscription data from MongoDB
    mongo_subscription_id = user.get("subscriptionId")
    mongo_status = user.get("subscriptionStatus", "free")
    mongo_plan = user.get("subscriptionPlan", "free")
    stripe_customer_id = user.get("stripeCustomerId")
    
    logger.info(f"MongoDB subscription data:")
    logger.info(f"  Subscription ID: {mongo_subscription_id}")
    logger.info(f"  Status: {mongo_status}")
    logger.info(f"  Plan: {mongo_plan}")
    logger.info(f"  Stripe Customer ID: {stripe_customer_id}")
    
    result = {
        "user_id": user_id,
        "email": email,
        "mongo_data": {
            "subscriptionId": mongo_subscription_id,
            "subscriptionStatus": mongo_status,
            "subscriptionPlan": mongo_plan,
            "stripeCustomerId": stripe_customer_id,
        },
        "stripe_data": {},
        "needs_update": False,
        "updated": False,
        "error": None,
    }
    
    # If no subscription ID in MongoDB, check if there's a subscription in Stripe
    if not mongo_subscription_id:
        logger.info("No subscription ID in MongoDB")
        
        # If we have a Stripe customer ID, check for active subscriptions
        if stripe_customer_id and STRIPE_AVAILABLE:
            logger.info(f"Checking Stripe for customer {stripe_customer_id}...")
            try:
                stripe_module = _get_stripe_module()
                if stripe_module:
                    # List all subscriptions for this customer
                    subscriptions = stripe_module.Subscription.list(
                        customer=stripe_customer_id,
                        status="all",
                        limit=10
                    )
                    
                    active_subscriptions = [s for s in subscriptions.data if s.status in ["active", "trialing", "past_due"]]
                    
                    if active_subscriptions:
                        logger.warning(f"Found {len(active_subscriptions)} active subscription(s) in Stripe but none in MongoDB!")
                        result["stripe_data"]["active_subscriptions"] = [
                            {
                                "id": s.id,
                                "status": s.status,
                                "current_period_end": datetime.fromtimestamp(s.current_period_end) if s.current_period_end else None,
                            }
                            for s in active_subscriptions
                        ]
                        result["needs_update"] = True
                    else:
                        logger.info("No active subscriptions found in Stripe (matches MongoDB)")
                        result["stripe_data"]["active_subscriptions"] = []
                else:
                    logger.warning("Stripe module not available")
            except Exception as e:
                logger.error(f"Error checking Stripe: {e}", exc_info=True)
                result["error"] = f"Error checking Stripe: {e}"
        
        # If MongoDB says "free" and no Stripe subscription, everything is in sync
        if mongo_status == "free" and not result.get("stripe_data", {}).get("active_subscriptions"):
            logger.info("✅ Subscription status is in sync (free)")
            result["success"] = True
            return result
    
    # If we have a subscription ID, verify it exists in Stripe
    if mongo_subscription_id:
        if not STRIPE_AVAILABLE:
            logger.warning("Stripe not available - cannot verify subscription")
            result["error"] = "Stripe not available"
            return result
        
        try:
            stripe_module = _get_stripe_module()
            if not stripe_module:
                logger.error("Could not get Stripe module")
                result["error"] = "Could not get Stripe module"
                return result
            
            logger.info(f"Verifying subscription {mongo_subscription_id} in Stripe...")
            
            try:
                subscription = stripe_module.Subscription.retrieve(mongo_subscription_id)
                
                # Subscription exists in Stripe
                stripe_status = subscription.status
                stripe_period_end = datetime.fromtimestamp(subscription.current_period_end) if subscription.current_period_end else None
                
                logger.info(f"Stripe subscription data:")
                logger.info(f"  Status: {stripe_status}")
                logger.info(f"  Current Period End: {stripe_period_end}")
                
                result["stripe_data"] = {
                    "subscriptionId": subscription.id,
                    "status": stripe_status,
                    "current_period_end": stripe_period_end,
                    "cancel_at_period_end": subscription.cancel_at_period_end,
                }
                
                # Check if status matches
                # Map Stripe statuses to our statuses
                status_map = {
                    "active": "active",
                    "trialing": "active",
                    "past_due": "past_due",
                    "canceled": "canceled",
                    "unpaid": "canceled",
                    "incomplete": "canceled",
                    "incomplete_expired": "canceled",
                }
                
                expected_status = status_map.get(stripe_status, "free")
                
                # If subscription is canceled in Stripe but MongoDB says active, update MongoDB
                if stripe_status in ["canceled", "unpaid", "incomplete", "incomplete_expired"]:
                    if mongo_status in ["active", "trialing", "past_due"]:
                        logger.warning(f"⚠️  MISMATCH: Stripe shows '{stripe_status}' but MongoDB shows '{mongo_status}'")
                        result["needs_update"] = True
                        result["update_reason"] = f"Subscription is {stripe_status} in Stripe but {mongo_status} in MongoDB"
                
                # If subscription is active in Stripe but MongoDB says canceled/free, update MongoDB
                elif stripe_status in ["active", "trialing"]:
                    if mongo_status in ["canceled", "free"]:
                        logger.warning(f"⚠️  MISMATCH: Stripe shows '{stripe_status}' but MongoDB shows '{mongo_status}'")
                        result["needs_update"] = True
                        result["update_reason"] = f"Subscription is {stripe_status} in Stripe but {mongo_status} in MongoDB"
                
                # If statuses match, check period end
                elif mongo_status == expected_status:
                    logger.info("✅ Subscription status matches between MongoDB and Stripe")
                    result["success"] = True
                    return result
                else:
                    logger.warning(f"⚠️  Status mismatch: MongoDB={mongo_status}, Stripe={stripe_status} (expected={expected_status})")
                    result["needs_update"] = True
                    result["update_reason"] = f"Status mismatch: MongoDB={mongo_status}, Stripe={stripe_status}"
                
            except Exception as e:
                # Check if it's a "subscription not found" error
                error_str = str(e).lower()
                if "no such subscription" in error_str or "resource_missing" in error_str or "does not exist" in error_str:
                    logger.warning(f"⚠️  Subscription {mongo_subscription_id} does not exist in Stripe!")
                    result["stripe_data"] = {"error": "Subscription not found in Stripe"}
                    result["needs_update"] = True
                    result["update_reason"] = "Subscription ID exists in MongoDB but not in Stripe"
                else:
                    # Re-raise if it's a different error
                    raise
        
        except Exception as e:
            logger.error(f"Error verifying subscription in Stripe: {e}", exc_info=True)
            result["error"] = f"Error verifying subscription: {e}"
            return result
    
    # If update is needed, ask for confirmation
    if result.get("needs_update"):
        logger.info("")
        logger.info("=" * 70)
        logger.info("SYNC REQUIRED")
        logger.info("=" * 70)
        logger.info(f"Reason: {result.get('update_reason', 'Unknown')}")
        logger.info("")
        logger.info("Current MongoDB data:")
        logger.info(f"  Status: {mongo_status}")
        logger.info(f"  Plan: {mongo_plan}")
        logger.info("")
        
        if result.get("stripe_data", {}).get("status"):
            logger.info("Stripe data:")
            logger.info(f"  Status: {result['stripe_data']['status']}")
            logger.info("")
        
        # Determine what to update
        if mongo_subscription_id and not result.get("stripe_data", {}).get("subscriptionId"):
            # Subscription doesn't exist in Stripe - set to free
            new_status = "free"
            new_plan = "free"
            new_subscription_id = None
        elif result.get("stripe_data", {}).get("status") in ["canceled", "unpaid", "incomplete", "incomplete_expired"]:
            # Subscription is canceled in Stripe
            new_status = "canceled"
            new_plan = mongo_plan  # Keep plan name
            new_subscription_id = mongo_subscription_id  # Keep subscription ID for reference
        elif result.get("stripe_data", {}).get("status") in ["active", "trialing"]:
            # Subscription is active in Stripe
            new_status = "active"
            # Try to determine plan from Stripe data
            new_plan = mongo_plan  # Keep existing plan or update if we can determine it
            new_subscription_id = result.get("stripe_data", {}).get("subscriptionId", mongo_subscription_id)
        else:
            new_status = "free"
            new_plan = "free"
            new_subscription_id = None
        
        logger.info(f"Proposed update:")
        logger.info(f"  Status: {mongo_status} → {new_status}")
        logger.info(f"  Plan: {mongo_plan} → {new_plan}")
        logger.info(f"  Subscription ID: {mongo_subscription_id} → {new_subscription_id}")
        logger.info("")
        
        confirm = input("Update MongoDB to match Stripe? (yes/no): ").strip().lower()
        if confirm in ["yes", "y"]:
            try:
                update_user_subscription(
                    user_id=user_id,
                    subscription_id=new_subscription_id,
                    subscription_status=new_status,
                    subscription_plan=new_plan,
                    current_period_end=result.get("stripe_data", {}).get("current_period_end"),
                )
                logger.info("✅ Successfully updated subscription in MongoDB")
                result["updated"] = True
                result["success"] = True
                result["new_data"] = {
                    "subscriptionId": new_subscription_id,
                    "subscriptionStatus": new_status,
                    "subscriptionPlan": new_plan,
                }
            except Exception as e:
                logger.error(f"Error updating subscription: {e}", exc_info=True)
                result["error"] = f"Error updating: {e}"
                result["success"] = False
        else:
            logger.info("Update cancelled by user")
            result["success"] = True
            result["cancelled"] = True
    else:
        result["success"] = True
    
    return result


def main():
    """Main function."""
    print("=" * 70)
    print("Subscription Status Sync Script")
    print("=" * 70)
    print()
    
    # Get user ID from command line or prompt
    user_id = None
    if len(sys.argv) > 1:
        user_id = sys.argv[1]
    else:
        user_id = get_user_input("Enter user ID to sync")
    
    if not user_id:
        print("Error: User ID is required.")
        sys.exit(1)
    
    print()
    result = sync_user_subscription(user_id)
    
    print()
    print("=" * 70)
    print("SYNC RESULT")
    print("=" * 70)
    
    if result.get("success"):
        if result.get("updated"):
            print("✅ Subscription status synced successfully!")
        elif result.get("cancelled"):
            print("ℹ️  Sync cancelled by user")
        else:
            print("✅ Subscription status is already in sync")
    else:
        print("❌ Sync failed")
        if result.get("error"):
            print(f"Error: {result['error']}")
    
    print("=" * 70)
    
    sys.exit(0 if result.get("success") else 1)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nScript interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        sys.exit(1)

