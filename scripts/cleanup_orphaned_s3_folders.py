#!/usr/bin/env python3
"""
S3 Orphaned Folders Cleanup Utility

This script scans S3 for user folders and compares them with MongoDB user records.
It identifies orphaned folders (S3 folders without corresponding users) and allows
you to delete them after confirmation.

Usage:
    python scripts/cleanup_orphaned_s3_folders.py
"""

import sys
import os
from pathlib import Path
from typing import Set, List, Dict
from bson import ObjectId
from botocore.exceptions import ClientError

# Add parent directory to path to import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.mongodb import connect_to_mongodb, close_mongodb_connection, get_collection, is_connected
from app.utils.s3_utils import get_s3_client, S3_AVAILABLE
from app.core.config import settings
import logging

# Import USERS_COLLECTION - try from user_helpers first, fallback to config
try:
    from app.utils.user_helpers import USERS_COLLECTION
except ImportError:
    # Fallback to config if user_helpers not available
    USERS_COLLECTION = settings.MONGODB_COLLECTION_NAME or "users"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger(__name__)


def get_s3_user_folders() -> Set[str]:
    """
    Scan S3 bucket and extract all user folder names (user IDs).
    
    Returns:
        Set of user IDs found in S3
    """
    if not S3_AVAILABLE:
        raise RuntimeError("S3 is not available. boto3 is not installed.")
    
    bucket_name = settings.AWS_S3_BUCKET
    if not bucket_name:
        raise RuntimeError("AWS_S3_BUCKET is not configured.")
    
    logger.info(f"Scanning S3 bucket '{bucket_name}' for user folders...")
    
    s3_client = get_s3_client()
    user_ids = set()
    
    try:
        # List all objects in the bucket
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Delimiter='/')
        
        for page in pages:
            # Get common prefixes (folders)
            if 'CommonPrefixes' in page:
                for prefix_info in page['CommonPrefixes']:
                    prefix = prefix_info['Prefix']
                    # Extract user ID from prefix (format: "user_id/")
                    user_id = prefix.rstrip('/')
                    
                    # Validate that it looks like a MongoDB ObjectId (24 hex chars)
                    if user_id and len(user_id) == 24:
                        try:
                            # Try to create ObjectId to validate format
                            ObjectId(user_id)
                            user_ids.add(user_id)
                            logger.debug(f"Found user folder: {user_id}")
                        except Exception:
                            # Not a valid ObjectId, skip
                            logger.debug(f"Skipping non-ObjectId prefix: {user_id}")
            
            # Also check objects directly (in case folders don't show up as prefixes)
            if 'Contents' in page:
                for obj in page['Contents']:
                    key = obj['Key']
                    # Extract user ID from key (format: "user_id/filename")
                    if '/' in key:
                        user_id = key.split('/')[0]
                        if user_id and len(user_id) == 24:
                            try:
                                ObjectId(user_id)
                                user_ids.add(user_id)
                            except Exception:
                                pass
        
        logger.info(f"Found {len(user_ids)} user folders in S3")
        return user_ids
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        raise RuntimeError(f"S3 error: {error_code} - {str(e)}")
    except Exception as e:
        raise RuntimeError(f"Error scanning S3: {str(e)}")


def get_mongodb_user_ids() -> Set[str]:
    """
    Get all user IDs from MongoDB.
    
    Returns:
        Set of user IDs (as strings) from MongoDB
    """
    if not is_connected():
        raise RuntimeError("MongoDB is not connected.")
    
    logger.info("Querying MongoDB for all user IDs...")
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise RuntimeError(f"Failed to access collection: {USERS_COLLECTION}")
    
    try:
        # Get all user IDs
        users = collection.find({}, {"_id": 1})
        user_ids = set()
        
        for user in users:
            user_id = str(user["_id"])
            user_ids.add(user_id)
        
        logger.info(f"Found {len(user_ids)} users in MongoDB")
        return user_ids
        
    except Exception as e:
        raise RuntimeError(f"Error querying MongoDB: {str(e)}")


def get_folder_size(s3_client, bucket_name: str, user_id: str) -> Dict[str, int]:
    """
    Get the size and file count of a user folder in S3.
    
    Returns:
        Dict with 'size' (bytes) and 'count' (file count)
    """
    total_size = 0
    file_count = 0
    
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=f"{user_id}/")
        
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    total_size += obj.get('Size', 0)
                    file_count += 1
        
        return {'size': total_size, 'count': file_count}
    except Exception as e:
        logger.warning(f"Error getting size for folder {user_id}: {e}")
        return {'size': 0, 'count': 0}


def delete_user_folder(s3_client, bucket_name: str, user_id: str) -> bool:
    """
    Delete all objects in a user folder (and the folder itself).
    
    Returns:
        True if successful, False otherwise
    """
    try:
        # List all objects with this prefix
        paginator = s3_client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=f"{user_id}/")
        
        objects_to_delete = []
        for page in pages:
            if 'Contents' in page:
                for obj in page['Contents']:
                    objects_to_delete.append({'Key': obj['Key']})
        
        if not objects_to_delete:
            logger.info(f"No objects found for user {user_id}")
            return True
        
        # Delete objects in batches (S3 allows up to 1000 per request)
        batch_size = 1000
        for i in range(0, len(objects_to_delete), batch_size):
            batch = objects_to_delete[i:i + batch_size]
            s3_client.delete_objects(
                Bucket=bucket_name,
                Delete={'Objects': batch}
            )
        
        logger.info(f"Deleted {len(objects_to_delete)} objects for user {user_id}")
        return True
        
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        logger.error(f"Error deleting folder {user_id}: {error_code} - {str(e)}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error deleting folder {user_id}: {str(e)}")
        return False


def format_size(size_bytes: int) -> str:
    """Format bytes to human-readable size"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"


def main():
    """Main cleanup workflow"""
    print("=" * 80)
    print("S3 Orphaned Folders Cleanup Utility")
    print("=" * 80)
    print()
    
    # Step 1: Connect to MongoDB
    print("Step 1: Connecting to MongoDB...")
    try:
        if not connect_to_mongodb():
            print("❌ Failed to connect to MongoDB. Please check your MONGODB_URI.")
            return 1
        print("✅ Connected to MongoDB")
    except Exception as e:
        print(f"❌ Error connecting to MongoDB: {e}")
        return 1
    
    # Step 2: Get user IDs from MongoDB
    print("\nStep 2: Getting user IDs from MongoDB...")
    try:
        mongodb_user_ids = get_mongodb_user_ids()
        print(f"✅ Found {len(mongodb_user_ids)} users in MongoDB")
    except Exception as e:
        print(f"❌ Error getting MongoDB user IDs: {e}")
        close_mongodb_connection()
        return 1
    
    # Step 3: Get user folders from S3
    print("\nStep 3: Scanning S3 for user folders...")
    try:
        s3_user_ids = get_s3_user_folders()
        print(f"✅ Found {len(s3_user_ids)} user folders in S3")
    except Exception as e:
        print(f"❌ Error scanning S3: {e}")
        close_mongodb_connection()
        return 1
    
    # Step 4: Find orphaned folders
    print("\nStep 4: Comparing S3 folders with MongoDB users...")
    orphaned_folders = s3_user_ids - mongodb_user_ids
    
    if not orphaned_folders:
        print("✅ No orphaned folders found. All S3 folders have corresponding users.")
        close_mongodb_connection()
        return 0
    
    print(f"⚠️  Found {len(orphaned_folders)} orphaned folder(s)")
    
    # Step 5: Get details about orphaned folders
    print("\nStep 5: Gathering details about orphaned folders...")
    bucket_name = settings.AWS_S3_BUCKET
    s3_client = get_s3_client()
    
    orphaned_details = []
    for user_id in sorted(orphaned_folders):
        details = get_folder_size(s3_client, bucket_name, user_id)
        orphaned_details.append({
            'user_id': user_id,
            'size': details['size'],
            'count': details['count']
        })
    
    # Step 6: Display summary
    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total S3 folders: {len(s3_user_ids)}")
    print(f"Total MongoDB users: {len(mongodb_user_ids)}")
    print(f"Orphaned folders: {len(orphaned_folders)}")
    print()
    print("Orphaned Folders Details:")
    print("-" * 80)
    print(f"{'User ID':<30} {'Files':<10} {'Size':<15}")
    print("-" * 80)
    
    total_size = 0
    total_files = 0
    for details in orphaned_details:
        print(f"{details['user_id']:<30} {details['count']:<10} {format_size(details['size']):<15}")
        total_size += details['size']
        total_files += details['count']
    
    print("-" * 80)
    print(f"{'TOTAL':<30} {total_files:<10} {format_size(total_size):<15}")
    print("=" * 80)
    
    # Step 7: Confirmation prompt
    print("\n⚠️  WARNING: This will permanently delete the orphaned folders and all their contents!")
    print(f"You are about to delete {len(orphaned_folders)} folder(s) containing {total_files} file(s)")
    print(f"Total size: {format_size(total_size)}")
    print()
    
    response = input("Do you want to proceed with deletion? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("❌ Deletion cancelled.")
        close_mongodb_connection()
        return 0
    
    # Step 8: Delete folders
    print("\nStep 6: Deleting orphaned folders...")
    print("-" * 80)
    
    success_count = 0
    fail_count = 0
    
    for i, details in enumerate(orphaned_details, 1):
        user_id = details['user_id']
        print(f"[{i}/{len(orphaned_details)}] Deleting folder {user_id}...", end=" ")
        
        if delete_user_folder(s3_client, bucket_name, user_id):
            print("✅")
            success_count += 1
        else:
            print("❌")
            fail_count += 1
    
    # Final summary
    print("\n" + "=" * 80)
    print("DELETION SUMMARY")
    print("=" * 80)
    print(f"Successfully deleted: {success_count}")
    print(f"Failed to delete: {fail_count}")
    print("=" * 80)
    
    # Cleanup
    close_mongodb_connection()
    
    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        print("\n\n❌ Interrupted by user")
        close_mongodb_connection()
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        logger.exception("Unexpected error in cleanup script")
        close_mongodb_connection()
        sys.exit(1)

