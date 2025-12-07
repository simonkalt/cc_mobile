# User CRUD Operations Guide

This guide explains how to use the `test_user_crud.py` script to test Create, Read, Update, and Delete operations for user records in MongoDB Atlas.

## Quick Start

### Run Full Test Suite
```bash
python test_user_crud.py
```

This will automatically:
1. ✅ Create a test user
2. ✅ Read the user by ID
3. ✅ Read the user by email
4. ✅ Update the user
5. ✅ List all users
6. ✅ Delete the test user

### Interactive Mode
```bash
python test_user_crud.py --interactive
```

This allows you to manually perform CRUD operations with prompts.

## Available Functions

### 1. Create User

```python
from test_user_crud import create_user

user_id = create_user(
    name="John Doe",
    email="john@example.com",
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
```

**Required Parameters:**
- `name`: User's full name
- `email`: User's email address
- `hashed_password`: Hashed password (bcrypt format)

**Optional Parameters:**
- `isActive`: Boolean (default: `True`)
- `isEmailVerified`: Boolean (default: `False`)
- `roles`: List of strings (default: `["user"]`)
- `failedLoginAttempts`: Integer (default: `0`)
- `phone`: String (default: `None`)
- `address`: Dictionary with `street`, `city`, `state`, `zip`, `country`
- `preferences`: Dictionary with `newsletterOptIn`, `theme`

### 2. Get User

```python
from test_user_crud import get_user

# By ID
user = get_user(user_id="507f1f77bcf86cd799439011")

# By Email
user = get_user(email="john@example.com")
```

### 3. Update User

```python
from test_user_crud import update_user

success = update_user(
    user_id="507f1f77bcf86cd799439011",
    updates={
        "isEmailVerified": True,
        "phone": "555-9999",
        "preferences.theme": "light",
        "preferences.newsletterOptIn": False,
        "lastLogin": datetime.utcnow()
    }
)
```

**Note:** Nested fields use dot notation (e.g., `preferences.theme`)

### 4. Delete User

```python
from test_user_crud import delete_user

success = delete_user(user_id="507f1f77bcf86cd799439011")
```

### 5. List All Users

```python
from test_user_crud import list_all_users

users = list_all_users(limit=10)
```

## User Schema

The user document follows this structure:

```json
{
  "name": "John Doe",
  "email": "johndoe@email.com",
  "hashedPassword": "$2b$12$exampleHashedPasswordValue",
  "isActive": true,
  "isEmailVerified": false,
  "roles": ["user"],
  "failedLoginAttempts": 0,
  "lastLogin": null,
  "passwordChangedAt": null,
  "avatarUrl": null,
  "phone": null,
  "address": {
    "street": null,
    "city": null,
    "state": null,
    "zip": null,
    "country": null
  },
  "dateCreated": "2024-04-27T00:00:00.000Z",
  "dateUpdated": "2024-04-27T00:00:00.000Z",
  "preferences": {
    "newsletterOptIn": false,
    "theme": "light"
  }
}
```

## Examples

### Example 1: Create a Complete User Profile

```python
from test_user_crud import create_user, connect_to_mongodb, close_mongodb_connection

connect_to_mongodb()

user_id = create_user(
    name="Jane Smith",
    email="jane.smith@example.com",
    hashed_password="$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqBWVHxkd0",
    isActive=True,
    isEmailVerified=True,
    roles=["user", "premium"],
    phone="555-0100",
    address={
        "street": "456 Oak Avenue",
        "city": "Springfield",
        "state": "IL",
        "zip": "62701",
        "country": "USA"
    },
    preferences={
        "newsletterOptIn": True,
        "theme": "dark"
    }
)

print(f"Created user with ID: {user_id}")
close_mongodb_connection()
```

### Example 2: Update User Profile

```python
from test_user_crud import update_user, get_user, connect_to_mongodb, close_mongodb_connection
from datetime import datetime

connect_to_mongodb()

# Update multiple fields
update_user(
    user_id="507f1f77bcf86cd799439011",
    updates={
        "name": "Jane Smith-Updated",
        "isEmailVerified": True,
        "phone": "555-9999",
        "preferences.theme": "dark",
        "lastLogin": datetime.utcnow()
    }
)

# Verify the update
user = get_user(user_id="507f1f77bcf86cd799439011")
close_mongodb_connection()
```

### Example 3: Find and Delete Inactive Users

```python
from test_user_crud import get_collection, connect_to_mongodb, close_mongodb_connection
from mongodb_client import get_collection

connect_to_mongodb()

collection = get_collection("users")

# Find inactive users
inactive_users = collection.find({"isActive": False})

for user in inactive_users:
    print(f"Deleting inactive user: {user.get('name')} ({user.get('email')})")
    collection.delete_one({"_id": user["_id"]})

close_mongodb_connection()
```

## Interactive Mode Options

When running in interactive mode (`python test_user_crud.py --interactive`):

1. **Create User** - Prompts for user details
2. **Get User (by ID)** - Enter MongoDB ObjectId
3. **Get User (by Email)** - Enter email address
4. **Update User** - Enter user ID and fields to update
5. **Delete User** - Enter user ID (with confirmation)
6. **List All Users** - Shows all users (with optional limit)
7. **Run Full Test Suite** - Runs automated tests
0. **Exit** - Close connection and exit

## Error Handling

All functions return:
- `None` or `False` on failure
- Appropriate value on success (ObjectId for create, document for get, etc.)

The script includes error handling for:
- Connection failures
- Invalid ObjectIds
- Missing users
- Database errors

## Notes

- **ObjectId Format**: MongoDB ObjectIds can be passed as strings or ObjectId objects
- **Nested Updates**: Use dot notation for nested fields (e.g., `preferences.theme`)
- **Timestamps**: `dateCreated` and `dateUpdated` are automatically managed
- **Password Hashing**: The script doesn't hash passwords - use bcrypt or similar before calling `create_user()`

## Troubleshooting

### "MongoDB not connected"
- Make sure `MONGODB_URI` is set in your `.env` file
- Run `python test_mongodb.py` first to verify connection

### "User not found"
- Verify the user ID or email is correct
- Check that the user exists in the database

### "Invalid ObjectId"
- Make sure the ID is a valid MongoDB ObjectId format (24 hex characters)

## Next Steps

After testing CRUD operations, you can:
1. Integrate these functions into your FastAPI endpoints
2. Add validation using Pydantic models
3. Add authentication/authorization
4. Implement password hashing (bcrypt)
5. Add email verification workflows

