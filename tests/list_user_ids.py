#!/usr/bin/env python3
"""
Script to list all user IDs from the database
"""

import sys
import os
from bson import ObjectId

# Add parent directory to path to import app modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

try:
    from app.db.mongodb import connect_to_mongodb, is_connected, get_collection
    from app.utils.user_helpers import USERS_COLLECTION
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
    print("User IDs in Database")
    print("=" * 80)
    print()
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        print("ERROR: Could not access users collection")
        sys.exit(1)
    
    # Get all users
    users = collection.find({}, {"_id": 1, "email": 1, "name": 1, "subscriptionStatus": 1})
    
    user_list = list(users)
    total_users = len(user_list)
    
    if total_users == 0:
        print("No users found in database.")
    else:
        print(f"Found {total_users} user(s):\n")
        print(f"{'User ID':<30} {'Email':<40} {'Name':<30} {'Status':<15}")
        print("-" * 115)
        
        for user in user_list:
            user_id = str(user.get("_id", ""))
            email = user.get("email", "N/A")
            name = user.get("name", "N/A")
            status = user.get("subscriptionStatus", "free")
            
            # Truncate long values for display
            email_display = email[:37] + "..." if len(email) > 40 else email
            name_display = name[:27] + "..." if len(name) > 30 else name
            
            print(f"{user_id:<30} {email_display:<40} {name_display:<30} {status:<15}")
        
        print("\n" + "=" * 80)
        print("User IDs only (for copy/paste):")
        print("=" * 80)
        for user in user_list:
            print(str(user.get("_id", "")))
        
        print("\n" + "=" * 80)
        print("User IDs with email (for reference):")
        print("=" * 80)
        for user in user_list:
            user_id = str(user.get("_id", ""))
            email = user.get("email", "N/A")
            print(f"{user_id} - {email}")

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

