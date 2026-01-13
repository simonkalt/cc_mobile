# Scripts Directory

This directory contains utility scripts for maintenance and administration tasks.

## cleanup_orphaned_s3_folders.py

A utility script to identify and remove orphaned S3 user folders that don't have corresponding users in MongoDB.

### What it does

1. **Scans S3**: Lists all user folders in the configured S3 bucket
2. **Queries MongoDB**: Gets all user IDs from the users collection
3. **Compares**: Identifies folders in S3 that don't have matching users in MongoDB
4. **Reports**: Shows a detailed summary with folder sizes and file counts
5. **Confirms**: Prompts for confirmation before deletion
6. **Deletes**: Removes orphaned folders and all their contents

### Usage

```bash
# From the project root directory
python scripts/cleanup_orphaned_s3_folders.py
```

Or if you're in the scripts directory:

```bash
python cleanup_orphaned_s3_folders.py
```

### Requirements

- Python 3.7+
- MongoDB connection configured (MONGODB_URI in .env)
- AWS S3 access configured (AWS credentials in .env or IAM role)
- Required Python packages: `boto3`, `pymongo`

### Example Output

```
================================================================================
S3 Orphaned Folders Cleanup Utility
================================================================================

Step 1: Connecting to MongoDB...
✅ Connected to MongoDB

Step 2: Getting user IDs from MongoDB...
✅ Found 150 users in MongoDB

Step 3: Scanning S3 for user folders...
✅ Found 152 user folders in S3

Step 4: Comparing S3 folders with MongoDB users...
⚠️  Found 2 orphaned folder(s)

Step 5: Gathering details about orphaned folders...

================================================================================
SUMMARY
================================================================================
Total S3 folders: 152
Total MongoDB users: 150
Orphaned folders: 2

Orphaned Folders Details:
--------------------------------------------------------------------------------
User ID                         Files      Size           
--------------------------------------------------------------------------------
507f1f77bcf86cd799439011        5          125.50 KB     
507f191e810c19729de860ea        12         2.45 MB        
--------------------------------------------------------------------------------
TOTAL                           17         2.58 MB        
================================================================================

⚠️  WARNING: This will permanently delete the orphaned folders and all their contents!
You are about to delete 2 folder(s) containing 17 file(s)
Total size: 2.58 MB

Do you want to proceed with deletion? (yes/no): 
```

### Safety Features

- **Confirmation Required**: You must explicitly type "yes" or "y" to proceed
- **Detailed Summary**: Shows exactly what will be deleted before asking for confirmation
- **Size Information**: Displays total size and file count for each folder
- **Error Handling**: Continues with other folders if one fails to delete
- **Final Report**: Shows success/failure count after deletion

### Notes

- The script validates that folder names are valid MongoDB ObjectIds (24 hex characters)
- Folders that don't match ObjectId format are skipped
- The script uses S3 pagination to handle large buckets efficiently
- Deletion is done in batches (up to 1000 objects per request)

### Troubleshooting

**"S3 is not available"**
- Make sure `boto3` is installed: `pip install boto3`
- Check your AWS credentials in `.env` or IAM role configuration

**"MongoDB is not connected"**
- Verify `MONGODB_URI` is set in your `.env` file
- Check network connectivity to MongoDB Atlas

**"Failed to access collection"**
- Ensure `MONGODB_COLLECTION_NAME` is set correctly (default: "users")
- Verify database permissions

### Related Documentation

- [S3 Setup Guide](../documentation/ENV_SETUP_S3.md)
- [MongoDB Setup Guide](../documentation/MONGODB_SETUP.md)

---

## migrate_users_to_free_subscription.py

A migration script to assign free subscription to all existing users in the database that are missing subscription fields.

### What it does

1. **Connects to MongoDB**: Uses the same connection settings as the main application
2. **Scans Users**: Finds all users in the database
3. **Identifies Missing Fields**: Finds users without subscription fields or with null/undefined values
4. **Updates Users**: Sets free subscription fields for users that need them
5. **Reports Results**: Shows summary of how many users were updated

### Usage

```bash
# From the project root directory
python scripts/migrate_users_to_free_subscription.py
```

Or if you're in the scripts directory:

```bash
python migrate_users_to_free_subscription.py
```

### Requirements

- Python 3.7+
- MongoDB connection configured (MONGODB_URI in .env)
- Required Python packages: `pymongo`

### Fields Updated

For users missing subscription fields, the script sets:
- `subscriptionStatus`: "free"
- `subscriptionPlan`: "free"
- `subscriptionId`: null
- `subscriptionCurrentPeriodEnd`: null
- `lastPaymentDate`: null
- `stripeCustomerId`: null
- `generation_credits`: 10 (if missing or null)

### Safety Features

- **Non-destructive**: Only updates users that are missing subscription fields
- **Preserves Existing Data**: Won't overwrite existing subscription information
- **Safe to Re-run**: Can be run multiple times without issues
- **Detailed Logging**: Shows which users are being updated
- **Error Handling**: Continues with other users if one fails

### Example Output

```
2024-12-31 12:00:00 - INFO - Starting user subscription migration...
2024-12-31 12:00:00 - INFO - This script will assign free subscription to all users missing subscription fields.
2024-12-31 12:00:00 - INFO - Connecting to MongoDB...
2024-12-31 12:00:00 - INFO - Found 150 total users in database
2024-12-31 12:00:00 - INFO - Found 120 users that need migration
2024-12-31 12:00:00 - INFO - Updated user user@example.com (507f1f77bcf86cd799439011) with free subscription
...
2024-12-31 12:00:01 - INFO - ============================================================
2024-12-31 12:00:01 - INFO - Migration Summary:
2024-12-31 12:00:01 - INFO -   Total users in database: 150
2024-12-31 12:00:01 - INFO -   Users needing migration: 120
2024-12-31 12:00:01 - INFO -   Successfully updated: 120
2024-12-31 12:00:01 - INFO -   Skipped/Failed: 0
2024-12-31 12:00:01 - INFO - ============================================================
2024-12-31 12:00:01 - INFO - Migration completed successfully!
```

### Notes

- The script only updates users that are missing subscription fields
- Users with existing subscription data (even if it's "free") are not modified
- The script is idempotent - safe to run multiple times
- All updates include a `dateUpdated` timestamp

### Troubleshooting

**"MongoDB is not connected"**
- Verify `MONGODB_URI` is set in your `.env` file
- Check network connectivity to MongoDB Atlas

**"Failed to access collection"**
- Ensure `MONGODB_COLLECTION_NAME` is set correctly (default: "users")
- Verify database permissions


---

## cancel_subscription.py

A script to cancel a user's subscription via the API.

### What it does

1. **Prompts for User ID**: Asks for the user ID whose subscription should be canceled
2. **Prompts for Cancel Option**: Asks whether to cancel immediately or at period end
3. **Authenticates**: Uses JWT access token for API authentication
4. **Calls API**: Makes POST request to `/api/subscriptions/cancel` endpoint
5. **Displays Result**: Shows success/failure and response details

### Usage

```bash
# From the project root directory
python scripts/cancel_subscription.py
```

### Requirements

- Python 3.7+
- API server running (local or remote)
- JWT access token (can be provided via environment variable or prompt)
- Required Python packages: `requests`, `python-dotenv`

### Environment Variables (Optional)

- `API_BASE_URL`: Base URL for the API (default: `http://localhost:8000`)
- `JWT_ACCESS_TOKEN`: JWT access token for authentication (will prompt if not set)

### Cancel Options

- **Cancel Immediately**: Subscription is canceled right away. User loses access immediately.
- **Cancel at Period End**: Subscription remains active until the end of the current billing period. User keeps access until then.

### Related Documentation

- [JWT Authentication Guide](../documentation/JWT_AUTHENTICATION.md)
- [Subscription API Documentation](../documentation/STRIPE_PAYMENTSHEET_API.md)
