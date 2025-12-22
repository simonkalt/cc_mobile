"""
Test script for User CRUD operations in MongoDB Atlas
Tests: Create, Read, Update, Delete operations for user records
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv
from bson import ObjectId

# Cross-platform keypress wait
try:
    # Windows
    import msvcrt
    def wait_for_keypress(message="Press any key to continue..."):
        print(f"\n{message}")
        msvcrt.getch()
except ImportError:
    # Unix/Linux/Mac
    import termios
    import tty
    def wait_for_keypress(message="Press any key to continue..."):
        print(f"\n{message}")
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# Load environment variables
try:
    load_dotenv()
except Exception as e:
    print(f"⚠️  Warning: Error loading .env file: {e}")
    print("Continuing with environment variables from system...")

# Import MongoDB client from new structure
from app.db.mongodb import connect_to_mongodb, get_collection, close_mongodb_connection, is_connected
from app.core.config import settings

# Collection name for users
USERS_COLLECTION = "users"


def create_user(name: str, email: str, hashed_password: str, **kwargs):
    """
    Create a new user record
    
    Args:
        name: User's full name
        email: User's email address
        hashed_password: Hashed password (e.g., bcrypt hash)
        **kwargs: Additional fields (isActive, roles, preferences, etc.)
    
    Returns:
        ObjectId of the created user or None if failed
    """
    if not is_connected():
        print("❌ MongoDB not connected")
        return None
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        print("❌ Failed to get users collection")
        return None
    
    # Display database and collection info
    db_name = collection.database.name
    coll_name = collection.name
    print(f"📊 Saving to: Database='{db_name}', Collection='{coll_name}'")
    
    # Build user document
    user_doc = {
        "name": name,
        "email": email,
        "hashedPassword": hashed_password,
        "isActive": kwargs.get("isActive", True),
        "isEmailVerified": kwargs.get("isEmailVerified", False),
        "roles": kwargs.get("roles", ["user"]),
        "failedLoginAttempts": kwargs.get("failedLoginAttempts", 0),
        "lastLogin": kwargs.get("lastLogin", None),
        "passwordChangedAt": kwargs.get("passwordChangedAt", None),
        "avatarUrl": kwargs.get("avatarUrl", None),
        "phone": kwargs.get("phone", None),
        "address": {
            "street": kwargs.get("address", {}).get("street", None),
            "city": kwargs.get("address", {}).get("city", None),
            "state": kwargs.get("address", {}).get("state", None),
            "zip": kwargs.get("address", {}).get("zip", None),
            "country": kwargs.get("address", {}).get("country", None)
        },
        "dateCreated": datetime.utcnow(),
        "dateUpdated": datetime.utcnow(),
        "preferences": {
            "newsletterOptIn": kwargs.get("preferences", {}).get("newsletterOptIn", False),
            "theme": kwargs.get("preferences", {}).get("theme", "light")
        }
    }
    
    try:
        result = collection.insert_one(user_doc)
        print(f"✅ User created successfully!")
        print(f"   User ID: {result.inserted_id}")
        print(f"   Name: {name}")
        print(f"   Email: {email}")
        print(f"   Database: {db_name}")
        print(f"   Collection: {coll_name}")
        print(f"\n💡 To view in MongoDB Atlas:")
        print(f"   Navigate to: Database '{db_name}' → Collection '{coll_name}'")
        return result.inserted_id
    except Exception as e:
        print(f"❌ Error creating user: {e}")
        return None


def get_user(user_id=None, email=None):
    """
    Retrieve a user by ID or email
    
    Args:
        user_id: MongoDB ObjectId (string or ObjectId)
        email: User's email address
    
    Returns:
        User document or None if not found
    """
    if not is_connected():
        print("❌ MongoDB not connected")
        return None
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        print("❌ Failed to get users collection")
        return None
    
    try:
        if user_id:
            # Convert string to ObjectId if needed
            if isinstance(user_id, str):
                user_id = ObjectId(user_id)
            user = collection.find_one({"_id": user_id})
        elif email:
            user = collection.find_one({"email": email})
        else:
            print("❌ Must provide either user_id or email")
            return None
        
        if user:
            print(f"✅ User found:")
            print_user_details(user)
            return user
        else:
            print("❌ User not found")
            return None
    except Exception as e:
        print(f"❌ Error retrieving user: {e}")
        return None


def update_user(user_id, updates: dict):
    """
    Update a user record
    
    Args:
        user_id: MongoDB ObjectId (string or ObjectId)
        updates: Dictionary of fields to update (supports dot notation for nested fields)
    
    Returns:
        True if successful, False otherwise
    """
    if not is_connected():
        print("❌ MongoDB not connected")
        return False
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        print("❌ Failed to get users collection")
        return False
    
    try:
        # Convert string to ObjectId if needed
        if isinstance(user_id, str):
            try:
                user_id = ObjectId(user_id)
            except Exception as e:
                print(f"❌ Invalid user ID format: {e}")
                return False
        
        # Add dateUpdated timestamp
        updates["dateUpdated"] = datetime.utcnow()
        
        # Build the $set operation - MongoDB supports dot notation directly
        set_operation = {"$set": updates}
        
        result = collection.update_one(
            {"_id": user_id},
            set_operation
        )
        
        if result.matched_count == 0:
            print("❌ User not found")
            return False
        
        if result.modified_count > 0:
            print(f"✅ User updated successfully!")
            print(f"   Modified {result.modified_count} field(s)")
            # Show what was updated
            print(f"   Updated fields: {', '.join(updates.keys())}")
            return True
        else:
            print("⚠️  User found but no changes were made (values may be the same)")
            return True
    except Exception as e:
        print(f"❌ Error updating user: {e}")
        import traceback
        print(f"   Traceback: {traceback.format_exc()}")
        return False


def delete_user(user_id):
    """
    Delete a user record
    
    Args:
        user_id: MongoDB ObjectId (string or ObjectId)
    
    Returns:
        True if successful, False otherwise
    """
    if not is_connected():
        print("❌ MongoDB not connected")
        return False
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        print("❌ Failed to get users collection")
        return False
    
    try:
        # Convert string to ObjectId if needed
        if isinstance(user_id, str):
            user_id = ObjectId(user_id)
        
        # First, get user details to show what's being deleted
        user = collection.find_one({"_id": user_id})
        if user:
            print(f"⚠️  About to delete user:")
            print(f"   Name: {user.get('name')}")
            print(f"   Email: {user.get('email')}")
        
        result = collection.delete_one({"_id": user_id})
        
        if result.deleted_count > 0:
            print(f"✅ User deleted successfully!")
            return True
        else:
            print("❌ User not found or already deleted")
            return False
    except Exception as e:
        print(f"❌ Error deleting user: {e}")
        return False


def list_all_users(limit=10):
    """
    List all users (with optional limit)
    
    Args:
        limit: Maximum number of users to return
    
    Returns:
        List of user documents
    """
    if not is_connected():
        print("❌ MongoDB not connected")
        return []
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        print("❌ Failed to get users collection")
        return []
    
    try:
        users = list(collection.find().limit(limit))
        print(f"✅ Found {len(users)} user(s):")
        print("-" * 60)
        for user in users:
            print_user_summary(user)
        print("-" * 60)
        return users
    except Exception as e:
        print(f"❌ Error listing users: {e}")
        return []


def print_user_details(user):
    """Print detailed user information"""
    print("-" * 60)
    print(f"ID: {user.get('_id')}")
    print(f"Name: {user.get('name')}")
    print(f"Email: {user.get('email')}")
    print(f"Active: {user.get('isActive')}")
    print(f"Email Verified: {user.get('isEmailVerified')}")
    print(f"Roles: {', '.join(user.get('roles', []))}")
    print(f"Failed Login Attempts: {user.get('failedLoginAttempts', 0)}")
    print(f"Phone: {user.get('phone', 'N/A')}")
    
    address = user.get('address', {})
    if any(address.values()):
        print(f"Address: {address.get('street', '')}, {address.get('city', '')}, {address.get('state', '')} {address.get('zip', '')}")
    
    prefs = user.get('preferences', {})
    print(f"Theme: {prefs.get('theme', 'N/A')}")
    print(f"Newsletter: {prefs.get('newsletterOptIn', False)}")
    
    if user.get('lastLogin'):
        print(f"Last Login: {user.get('lastLogin')}")
    if user.get('dateCreated'):
        print(f"Created: {user.get('dateCreated')}")
    if user.get('dateUpdated'):
        print(f"Updated: {user.get('dateUpdated')}")
    print("-" * 60)


def print_user_summary(user):
    """Print brief user summary"""
    print(f"  • {user.get('name')} ({user.get('email')}) - ID: {user.get('_id')}")


def run_test_suite():
    """Run a complete test suite of CRUD operations"""
    print("=" * 60)
    print("User CRUD Test Suite")
    print("=" * 60)
    
    # Connect to MongoDB
    print("\n1. Connecting to MongoDB Atlas...")
    if not connect_to_mongodb():
        print("❌ Failed to connect to MongoDB Atlas")
        return
    
    print("✅ Connected to MongoDB Atlas")
    
    # Test 1: Create a user
    print("\n" + "=" * 60)
    print("TEST 1: Create User")
    print("=" * 60)
    test_user_id = create_user(
        name="Test User",
        email="testuser@example.com",
        hashed_password="$2b$12$exampleHashedPasswordValue",
        isActive=True,
        isEmailVerified=False,
        roles=["user"],
        phone="555-1234",
        address={
            "street": "123 Main St",
            "city": "Anytown",
            "state": "CA",
            "zip": "12345",
            "country": "USA"
        },
        preferences={
            "newsletterOptIn": True,
            "theme": "dark"
        }
    )
    
    if not test_user_id:
        print("❌ Test failed: Could not create user")
        close_mongodb_connection()
        return
    
    # Pause to allow inspection of the created user
    print("\n" + "=" * 60)
    print("⏸️  PAUSE: Check MongoDB Atlas to verify the user was created")
    print("=" * 60)
    wait_for_keypress("Press any key to continue with the rest of the tests...")
    print("=" * 60)
    
    # Test 2: Read the user
    print("\n" + "=" * 60)
    print("TEST 2: Read User (by ID)")
    print("=" * 60)
    user = get_user(user_id=test_user_id)
    
    if not user:
        print("❌ Test failed: Could not retrieve user")
        close_mongodb_connection()
        return
    
    # Test 3: Read by email
    print("\n" + "=" * 60)
    print("TEST 3: Read User (by Email)")
    print("=" * 60)
    user_by_email = get_user(email="testuser@example.com")
    
    # Test 4: Update the user
    print("\n" + "=" * 60)
    print("TEST 4: Update User")
    print("=" * 60)
    update_success = update_user(
        test_user_id,
        {
            "isEmailVerified": True,
            "phone": "555-9999",
            "preferences.theme": "light",
            "preferences.newsletterOptIn": False,
            "lastLogin": datetime.utcnow()
        }
    )
    
    if update_success:
        print("\nRetrieving updated user...")
        updated_user = get_user(user_id=test_user_id)
    
    # Test 5: List all users
    print("\n" + "=" * 60)
    print("TEST 5: List All Users")
    print("=" * 60)
    all_users = list_all_users(limit=5)
    
    # Test 6: Delete the test user
    print("\n" + "=" * 60)
    print("TEST 6: Delete User")
    print("=" * 60)
    delete_success = delete_user(test_user_id)
    
    # Verify deletion
    if delete_success:
        print("\nVerifying deletion...")
        deleted_user = get_user(user_id=test_user_id)
        if not deleted_user:
            print("✅ User successfully deleted (not found in database)")
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Suite Summary")
    print("=" * 60)
    print("✅ Create User: PASSED" if test_user_id else "❌ Create User: FAILED")
    print("✅ Read User: PASSED" if user else "❌ Read User: FAILED")
    print("✅ Update User: PASSED" if update_success else "❌ Update User: FAILED")
    print("✅ Delete User: PASSED" if delete_success else "❌ Delete User: FAILED")
    
    # Close connection
    print("\nClosing MongoDB connection...")
    close_mongodb_connection()
    print("✅ Connection closed")
    
    print("\n" + "=" * 60)
    print("All Tests Complete!")
    print("=" * 60)


def interactive_mode():
    """Interactive mode for manual testing"""
    print("=" * 60)
    print("User CRUD - Interactive Mode")
    print("=" * 60)
    
    if not connect_to_mongodb():
        print("❌ Failed to connect to MongoDB Atlas")
        return
    
    print("✅ Connected to MongoDB Atlas\n")
    
    while True:
        print("\n" + "=" * 60)
        print("Options:")
        print("1. Create User")
        print("2. Get User (by ID)")
        print("3. Get User (by Email)")
        print("4. Update User")
        print("5. Delete User")
        print("6. List All Users")
        print("7. Run Full Test Suite")
        print("0. Exit")
        print("=" * 60)
        
        choice = input("\nSelect an option: ").strip()
        
        if choice == "0":
            break
        elif choice == "1":
            name = input("Name: ").strip()
            email = input("Email: ").strip()
            password = input("Hashed Password (or press Enter for example): ").strip()
            if not password:
                password = "$2b$12$exampleHashedPasswordValue"
            
            is_active = input("Is Active? (y/n, default=y): ").strip().lower() == 'y'
            roles_input = input("Roles (comma-separated, default=user): ").strip()
            roles = [r.strip() for r in roles_input.split(",")] if roles_input else ["user"]
            
            user_id = create_user(name, email, password, isActive=is_active, roles=roles)
            if user_id:
                print(f"\n✅ User created with ID: {user_id}")
        
        elif choice == "2":
            user_id = input("User ID: ").strip()
            get_user(user_id=user_id)
        
        elif choice == "3":
            email = input("Email: ").strip()
            get_user(email=email)
        
        elif choice == "4":
            user_id = input("User ID: ").strip()
            print("\nEnter fields to update (press Enter to skip):")
            updates = {}
            
            name = input("Name: ").strip()
            if name:
                updates["name"] = name
            
            email = input("Email: ").strip()
            if email:
                updates["email"] = email
            
            is_active = input("Is Active? (y/n): ").strip().lower()
            if is_active:
                updates["isActive"] = is_active == 'y'
            
            phone = input("Phone: ").strip()
            if phone:
                updates["phone"] = phone
            
            theme = input("Theme (light/dark): ").strip()
            if theme:
                updates["preferences.theme"] = theme
            
            if updates:
                update_user(user_id, updates)
            else:
                print("No updates provided")
        
        elif choice == "5":
            user_id = input("User ID to delete: ").strip()
            confirm = input("Are you sure? (yes/no): ").strip().lower()
            if confirm == "yes":
                delete_user(user_id)
            else:
                print("Cancelled")
        
        elif choice == "6":
            limit = input("Limit (default=10): ").strip()
            limit = int(limit) if limit.isdigit() else 10
            list_all_users(limit=limit)
        
        elif choice == "7":
            run_test_suite()
            break
        
        else:
            print("Invalid option")
    
    close_mongodb_connection()
    print("\n✅ Connection closed. Goodbye!")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        interactive_mode()
    else:
        run_test_suite()

