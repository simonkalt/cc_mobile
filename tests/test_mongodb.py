"""
Test script to add a document to MongoDB Atlas
Run this script to test your MongoDB Atlas connection and add a test document.
"""
import os
import sys
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables with error handling
try:
    load_dotenv()
except Exception as e:
    print(f"⚠️  Warning: Error loading .env file: {e}")
    print("Continuing with environment variables from system...")

# Import MongoDB client from new structure
from app.db.mongodb import connect_to_mongodb, get_collection, close_mongodb_connection, is_connected

def test_add_document():
    """Test adding a document to MongoDB"""
    
    print("=" * 60)
    print("MongoDB Atlas Connection Test")
    print("=" * 60)
    
    # Connect to MongoDB
    print("\n1. Connecting to MongoDB Atlas...")
    if not connect_to_mongodb():
        print("❌ Failed to connect to MongoDB Atlas")
        print("\nPlease check:")
        print("  - MONGODB_URI is set in your .env file")
        print("  - Your MongoDB Atlas cluster is running")
        print("  - Your IP address is whitelisted in MongoDB Atlas")
        print("  - Your connection string is correct")
        return False
    
    print("✅ Successfully connected to MongoDB Atlas")
    
    # Check connection status
    print("\n2. Verifying connection...")
    if is_connected():
        print("✅ Connection is active")
    else:
        print("❌ Connection is not active")
        return False
    
    # Get collection
    print("\n3. Getting collection...")
    collection = get_collection()
    if not collection:
        print("❌ Failed to get collection")
        return False
    print(f"✅ Using collection: {collection.name}")
    
    # Create test document
    print("\n4. Creating test document...")
    test_document = {
        "test": True,
        "timestamp": datetime.utcnow(),
        "message": "This is a test document from the MongoDB connection test script",
        "metadata": {
            "created_by": "test_mongodb.py",
            "purpose": "Testing MongoDB Atlas connection"
        }
    }
    
    # Insert document
    print("\n5. Inserting document into MongoDB...")
    try:
        result = collection.insert_one(test_document)
        print(f"✅ Document inserted successfully!")
        print(f"   Document ID: {result.inserted_id}")
        print(f"   Collection: {collection.name}")
        print(f"   Database: {collection.database.name}")
        
        # Retrieve and display the inserted document
        print("\n6. Retrieving inserted document...")
        retrieved_doc = collection.find_one({"_id": result.inserted_id})
        if retrieved_doc:
            print("✅ Document retrieved successfully!")
            print("\nDocument contents:")
            print("-" * 60)
            for key, value in retrieved_doc.items():
                print(f"  {key}: {value}")
            print("-" * 60)
        else:
            print("⚠️  Document inserted but could not be retrieved")
        
        # Count documents in collection
        print("\n7. Counting documents in collection...")
        doc_count = collection.count_documents({})
        print(f"✅ Total documents in collection: {doc_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error inserting document: {e}")
        return False
    
    finally:
        # Close connection
        print("\n8. Closing MongoDB connection...")
        close_mongodb_connection()
        print("✅ Connection closed")


def test_query_documents():
    """Test querying documents from MongoDB"""
    print("\n" + "=" * 60)
    print("Testing Document Query")
    print("=" * 60)
    
    if not connect_to_mongodb():
        print("❌ Failed to connect to MongoDB Atlas")
        return False
    
    try:
        collection = get_collection()
        
        # Find all test documents
        print("\nFinding all test documents...")
        test_docs = collection.find({"test": True})
        doc_list = list(test_docs)
        
        print(f"✅ Found {len(doc_list)} test document(s)")
        
        if doc_list:
            print("\nTest documents:")
            for i, doc in enumerate(doc_list, 1):
                print(f"\n  Document {i}:")
                print(f"    ID: {doc.get('_id')}")
                print(f"    Timestamp: {doc.get('timestamp')}")
                print(f"    Message: {doc.get('message')}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error querying documents: {e}")
        return False
    
    finally:
        close_mongodb_connection()


if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("MongoDB Atlas Test Script")
    print("=" * 60)
    
    # Check if MONGODB_URI is set
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        print("\n❌ ERROR: MONGODB_URI environment variable is not set!")
        print("\nPlease:")
        print("1. Create a .env file in the project root")
        print("2. Add: MONGODB_URI=your_mongodb_atlas_connection_string")
        print("3. Optionally add: MONGODB_DB_NAME=your_database_name")
        print("4. Optionally add: MONGODB_COLLECTION_NAME=your_collection_name")
        print("\nExample format:")
        print("MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/cover_letters?retryWrites=true&w=majority")
        sys.exit(1)
    
    # Validate URI format
    if not mongodb_uri.startswith('mongodb'):
        print(f"\n⚠️  WARNING: MONGODB_URI doesn't start with 'mongodb'")
        print(f"Current value starts with: {mongodb_uri[:20]}...")
        print("Please check your connection string format.")
    
    print(f"\n✅ MONGODB_URI is set (length: {len(mongodb_uri)} characters)")
    # Don't print the full URI for security, but show the cluster name if present
    if '@' in mongodb_uri:
        cluster_part = mongodb_uri.split('@')[1].split('/')[0] if '@' in mongodb_uri else "hidden"
        print(f"   Cluster: {cluster_part.split('.')[0] if '.' in cluster_part else 'hidden'}")
    
    # Run tests
    success = test_add_document()
    
    if success:
        # Optionally test querying
        user_input = input("\nWould you like to test querying documents? (y/n): ")
        if user_input.lower() == 'y':
            test_query_documents()
    
    print("\n" + "=" * 60)
    print("Test Complete!")
    print("=" * 60)

