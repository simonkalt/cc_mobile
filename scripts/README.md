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

