# MongoDB Atlas Setup Guide

This guide will walk you through setting up MongoDB Atlas for your FastAPI application.

## Prerequisites

- A MongoDB Atlas account (free tier available at [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas))
- Python 3.7+ installed
- Your FastAPI project set up

## Step 1: Create a MongoDB Atlas Account

1. Go to [mongodb.com/cloud/atlas](https://www.mongodb.com/cloud/atlas)
2. Click "Try Free" or "Sign Up"
3. Create your account (you can use Google, GitHub, or email)

## Step 2: Create a Cluster

1. After logging in, you'll be prompted to create a cluster
2. Choose the **FREE** tier (M0 Sandbox)
3. Select a cloud provider and region (choose one close to you)
4. Click "Create Cluster"
5. Wait 1-3 minutes for the cluster to be created

## Step 3: Create a Database User

1. In the left sidebar, click **"Database Access"** (under Security)
2. Click **"Add New Database User"**
3. Choose **"Password"** authentication method
4. Enter a username (e.g., `coverletter_user`)
5. Click **"Autogenerate Secure Password"** or create your own
6. **IMPORTANT**: Copy and save the password - you won't see it again!
7. Under "Database User Privileges", select **"Read and write to any database"**
8. Click **"Add User"**

## Step 4: Whitelist IP Addresses

### For Local Development:

1. In the left sidebar, click **"Network Access"** (under Security)
2. Click **"Add IP Address"**
3. Click **"Add Current IP Address"** to whitelist your local machine
4. Click **"Confirm"**

### For Render.com Deployment:

Since Render uses dynamic IP addresses, you have two options:

**Option A: Allow Access from Anywhere (Easiest for Development/Testing)**

1. In the left sidebar, click **"Network Access"** (under Security)
2. Click **"Add IP Address"**
3. Click **"Allow Access from Anywhere"** (this adds `0.0.0.0/0`)
4. Click **"Confirm"**

⚠️ **Security Note:** This allows access from any IP address. While MongoDB Atlas still requires authentication, this is less secure. Use only for development or if you have strong authentication.

**Option B: Use MongoDB Atlas IP Access List with Specific Ranges (More Secure)**

1. In the left sidebar, click **"Network Access"** (under Security)
2. Click **"Add IP Address"**
3. Enter `0.0.0.0/0` manually (or use specific IP ranges if Render provides them)
4. Add a comment like "Render.com deployment"
5. Click **"Confirm"**

**Best Practice for Production:**

- Use strong database passwords
- Enable MongoDB Atlas authentication
- Consider using MongoDB Atlas's VPC peering if available
- Regularly review and audit network access
- Use environment-specific database users with minimal permissions

## Step 5: Get Your Connection String

1. In the left sidebar, click **"Database"** (or go back to Clusters)
2. Click **"Connect"** on your cluster
3. Choose **"Connect your application"**
4. Select:
   - **Driver**: Python
   - **Version**: 3.6 or later
5. Copy the connection string (it looks like: `mongodb+srv://<username>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority`)

## Step 6: Update Your Connection String

Replace the placeholders in the connection string:

- Replace `<username>` with your database username (from Step 3)
- Replace `<password>` with your database password (from Step 3)
- Optionally add a database name: `mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/cover_letters?retryWrites=true&w=majority`

**Example:**

```
mongodb+srv://coverletter_user:MySecurePassword123@cluster0.abc123.mongodb.net/cover_letters?retryWrites=true&w=majority
```

## Step 7: Configure Environment Variables

1. Create a `.env` file in your project root (if you don't have one)
2. Add the following variables:

```env
# MongoDB Atlas Configuration
MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/CoverLetter?retryWrites=true&w=majority
MONGODB_DB_NAME=CoverLetter
MONGODB_COLLECTION_NAME=users
```

**Important Security Notes:**

- Never commit your `.env` file to version control
- Make sure `.env` is in your `.gitignore`
- For production, use environment variables or a secrets manager

## Step 8: Install Dependencies

Install the required Python package:

```bash
pip install pymongo
```

Or if using requirements.txt:

```bash
pip install -r requirements.txt
```

## Step 9: Test Your Connection

Run the test script to verify your connection:

```bash
python test_mongodb.py
```

You should see:

- ✅ Successfully connected to MongoDB Atlas
- ✅ Document inserted successfully
- ✅ Document retrieved successfully

## Step 10: Integration with FastAPI

The MongoDB connection is automatically established when your FastAPI application starts. The connection is managed in the `lifespan` function in `main.py`.

### Using MongoDB in Your API Endpoints

Here's an example of how to use MongoDB in your endpoints:

```python
from mongodb_client import get_collection, is_connected

@app.post("/api/save-cover-letter")
async def save_cover_letter(cover_letter_data: dict):
    if not is_connected():
        return {"error": "MongoDB not connected"}

    collection = get_collection("letters")

    document = {
        "cover_letter": cover_letter_data,
        "created_at": datetime.utcnow(),
        "company": cover_letter_data.get("company_name"),
        # ... other fields
    }

    result = collection.insert_one(document)
    return {"id": str(result.inserted_id), "status": "saved"}
```

## Troubleshooting

### Connection Timeout

- Check that your IP address is whitelisted in MongoDB Atlas
- Verify your connection string is correct
- Check your internet connection

### Authentication Failed

- Verify your username and password are correct
- Make sure you've URL-encoded special characters in your password
- Check that the database user has read/write permissions

### Module Not Found

- Make sure `pymongo` is installed: `pip install pymongo`
- Verify you're using the correct Python environment

### Connection String Issues

- Make sure there are no extra spaces in your connection string
- Verify the database name in the connection string matches your setup
- Check that special characters in password are URL-encoded

## Security Best Practices

1. **Never commit credentials** - Use environment variables
2. **Use strong passwords** - Generate secure passwords for database users
3. **Limit IP access** - Only whitelist IPs that need access
4. **Use read-only users** - Create separate users with minimal permissions when possible
5. **Enable encryption** - MongoDB Atlas encrypts data in transit by default
6. **Regular backups** - Set up automated backups in MongoDB Atlas

## Next Steps

- Create indexes for better query performance
- Set up database collections for different data types
- Implement data models using Pydantic
- Add error handling and retry logic
- Set up monitoring and alerts in MongoDB Atlas

## Additional Resources

- [MongoDB Atlas Documentation](https://docs.atlas.mongodb.com/)
- [PyMongo Documentation](https://pymongo.readthedocs.io/)
- [MongoDB University](https://university.mongodb.com/) - Free courses
