# MongoDB Atlas Quick Start

## Quick Setup Steps

1. **Install dependencies:**
   ```bash
   pip install pymongo
   # or
   pip install -r requirements.txt
   ```

2. **Get your MongoDB Atlas connection string:**
   - Go to [MongoDB Atlas](https://www.mongodb.com/cloud/atlas)
   - Create a free cluster (if you don't have one)
   - Click "Connect" → "Connect your application"
   - Copy the connection string

3. **Add to your `.env` file:**
   ```env
   MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/cover_letters?retryWrites=true&w=majority
   MONGODB_DB_NAME=cover_letters
   MONGODB_COLLECTION_NAME=letters
   ```
   
   **Important:** Replace `username` and `password` with your actual credentials!

4. **Whitelist your IP address:**
   - **For local development:** In MongoDB Atlas, go to "Network Access" → "Add IP Address" → "Add Current IP Address"
   - **For Render.com:** Use "Allow Access from Anywhere" (adds `0.0.0.0/0`) - see `RENDER_DEPLOYMENT.md` for details

5. **Test the connection:**
   ```bash
   python test_mongodb.py
   ```

6. **Start your FastAPI server:**
   ```bash
   uvicorn main:app --reload
   ```

The MongoDB connection will be established automatically when the server starts.

## Files Created

- `mongodb_client.py` - MongoDB connection module
- `test_mongodb.py` - Test script to verify connection
- `MONGODB_SETUP.md` - Detailed setup guide

## Using MongoDB in Your Code

```python
from mongodb_client import get_collection, is_connected

# Check if connected
if is_connected():
    collection = get_collection("your_collection_name")
    # Insert document
    result = collection.insert_one({"key": "value"})
    # Query documents
    docs = collection.find({"key": "value"})
```

## Troubleshooting

- **Connection failed?** Check your IP is whitelisted in MongoDB Atlas
- **Authentication error?** Verify username/password in connection string
- **Module not found?** Run `pip install pymongo`

For detailed instructions, see `MONGODB_SETUP.md`.

