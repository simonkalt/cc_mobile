#!/usr/bin/env python3
"""
Migration script to assign free subscription to all existing users in the database.

This script:
1. Connects to MongoDB
2. Finds all users without subscription fields or with missing subscription fields
3. Updates them to have a free subscription with 10 generation credits
4. Reports the number of users updated

Usage:
    python scripts/migrate_users_to_free_subscription.py
"""

import sys
import os
from pathlib import Path

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime
from bson import ObjectId
from app.db.mongodb import get_collection, is_connected, connect_to_mongodb
from app.utils.user_helpers import USERS_COLLECTION
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def migrate_users_to_free_subscription():
    """
    Migrate all existing users to have free subscription fields.
    Only updates users that don't have subscription fields or have null/undefined values.
    """
    # Connect to MongoDB
    if not is_connected():
        logger.info("Connecting to MongoDB...")
        connect_to_mongodb()
    
    if not is_connected():
        logger.error("Failed to connect to MongoDB. Please check your connection settings.")
        return False
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        logger.error("Failed to access users collection")
        return False
    
    # Find all users
    all_users = list(collection.find({}))
    total_users = len(all_users)
    logger.info(f"Found {total_users} total users in database")
    
    if total_users == 0:
        logger.info("No users found in database. Nothing to migrate.")
        return True
    
    # Find users that need migration
    # Users that don't have subscriptionStatus or have it set to null/undefined
    users_to_update = []
    for user in all_users:
        user_id = str(user.get("_id", ""))
        subscription_status = user.get("subscriptionStatus")
        
        # Check if user needs migration
        needs_migration = (
            subscription_status is None or
            user.get("subscriptionPlan") is None or
            user.get("subscriptionId") is None  # This is fine to be None, but we want to ensure it exists
        )
        
        if needs_migration:
            users_to_update.append({
                "user_id": user_id,
                "email": user.get("email", "unknown"),
                "current_status": subscription_status,
            })
    
    if not users_to_update:
        logger.info("All users already have subscription fields set. No migration needed.")
        return True
    
    logger.info(f"Found {len(users_to_update)} users that need migration")
    
    # Update users
    updated_count = 0
    skipped_count = 0
    
    for user_info in users_to_update:
        try:
            user_id_obj = ObjectId(user_info["user_id"])
            
            # Build update document - only set fields that are missing or null
            update_doc = {
                "dateUpdated": datetime.utcnow()
            }
            
            # Only update if field is missing or None
            current_user = collection.find_one({"_id": user_id_obj})
            if current_user:
                if current_user.get("subscriptionStatus") is None:
                    update_doc["subscriptionStatus"] = "free"
                if current_user.get("subscriptionPlan") is None:
                    update_doc["subscriptionPlan"] = "free"
                if "subscriptionId" not in current_user:
                    update_doc["subscriptionId"] = None
                if "subscriptionCurrentPeriodEnd" not in current_user:
                    update_doc["subscriptionCurrentPeriodEnd"] = None
                if "lastPaymentDate" not in current_user:
                    update_doc["lastPaymentDate"] = None
                if "stripeCustomerId" not in current_user:
                    update_doc["stripeCustomerId"] = None
                # Set generation_credits to 10 for all users
                # This will overwrite any existing credit values
                update_doc["generation_credits"] = 10
                # Set max_credits to 10 for all users (fixed maximum)
                update_doc["max_credits"] = 10
                
                # Only update if we have fields to set
                if len(update_doc) > 1:  # More than just dateUpdated
                    result = collection.update_one(
                        {"_id": user_id_obj},
                        {"$set": update_doc}
                    )
                    
                    if result.matched_count > 0:
                        updated_count += 1
                        logger.info(
                            f"Updated user {user_info['email']} ({user_info['user_id']}) "
                            f"with free subscription"
                        )
                    else:
                        skipped_count += 1
                        logger.warning(
                            f"User {user_info['email']} ({user_info['user_id']}) not found, skipping"
                        )
                else:
                    skipped_count += 1
                    logger.debug(
                        f"User {user_info['email']} ({user_info['user_id']}) already has all fields, skipping"
                    )
            else:
                skipped_count += 1
                logger.warning(
                    f"User {user_info['email']} ({user_info['user_id']}) not found in database"
                )
                
        except Exception as e:
            logger.error(
                f"Error updating user {user_info['email']} ({user_info['user_id']}): {e}"
            )
            skipped_count += 1
    
    # Summary
    logger.info("=" * 60)
    logger.info("Migration Summary:")
    logger.info(f"  Total users in database: {total_users}")
    logger.info(f"  Users needing migration: {len(users_to_update)}")
    logger.info(f"  Successfully updated: {updated_count}")
    logger.info(f"  Skipped/Failed: {skipped_count}")
    logger.info("=" * 60)
    
    return updated_count > 0


if __name__ == "__main__":
    logger.info("Starting user subscription migration...")
    logger.info("This script will assign free subscription to all users missing subscription fields.")
    logger.info("All users will be set to 10 generation credits (will overwrite existing values).")
    
    try:
        success = migrate_users_to_free_subscription()
        if success:
            logger.info("Migration completed successfully!")
            sys.exit(0)
        else:
            logger.warning("Migration completed with warnings. Check logs above.")
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nMigration interrupted by user.")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Migration failed with error: {e}", exc_info=True)
        sys.exit(1)

