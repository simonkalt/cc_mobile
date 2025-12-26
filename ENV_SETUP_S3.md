# S3 Environment Variables Setup

## The Problem

Your local `.env` file is missing the S3 bucket configuration. The error:
```
"Error listing files: 500: S3 bucket name not configured"
```

## Required Environment Variables

Add these to your `.env` file:

```env
# AWS S3 Configuration
AWS_S3_BUCKET=custom-cover-user-resumes
# OR use S3_BUCKET_URI (alternative format)
S3_BUCKET_URI=s3://custom-cover-user-resumes/

# AWS Credentials (if not using IAM role)
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-2
```

## Quick Fix

### Option 1: Use AWS_S3_BUCKET (Recommended)

Add to `.env`:
```env
AWS_S3_BUCKET=custom-cover-user-resumes
AWS_REGION=us-east-2
```

### Option 2: Use S3_BUCKET_URI (Alternative)

Add to `.env`:
```env
S3_BUCKET_URI=s3://custom-cover-user-resumes/
AWS_REGION=us-east-2
```

## How the Code Works

The code checks in this order:
1. `AWS_S3_BUCKET` environment variable (preferred)
2. `S3_BUCKET_URI` environment variable (parsed to extract bucket name)
3. If both are missing → Error: "S3 bucket name not configured"

## Verify Setup

After adding to `.env`, restart your server and test:

```bash
# In WSL
cd /mnt/t/Python/cc_mobile
source ~/venvs/cc_mobile/bin/activate
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('AWS_S3_BUCKET:', os.getenv('AWS_S3_BUCKET')); print('S3_BUCKET_URI:', os.getenv('S3_BUCKET_URI'))"
```

You should see:
```
AWS_S3_BUCKET: custom-cover-user-resumes
S3_BUCKET_URI: s3://custom-cover-user-resumes/
```

## AWS Credentials

If you're using AWS credentials (not IAM role), also add:

```env
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=us-east-2
```

**Note:** Your server logs show `region=us-east-2`, so make sure `AWS_REGION` matches.

## Complete .env Example

```env
# MongoDB
MONGODB_URI=mongodb+srv://...
MONGODB_DB_NAME=CoverLetter
MONGODB_COLLECTION_NAME=users

# AWS S3
AWS_S3_BUCKET=custom-cover-user-resumes
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
AWS_REGION=us-east-2

# API Keys (your existing ones)
OPENAI_API_KEY=...
ANTHROPIC_API_KEY=...
# etc.
```

## After Adding Variables

1. **Restart your server** (the .env file is loaded on startup)
2. **Test the endpoint again:**
   ```bash
   node ./tests/debug-api-connection.js
   ```

The files list endpoint should now work!

