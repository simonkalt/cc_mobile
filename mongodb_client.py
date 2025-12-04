"""
MongoDB Atlas connection module for FastAPI application
"""
import os
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from typing import Optional

logger = logging.getLogger(__name__)

# MongoDB connection variables
MONGODB_URI = os.getenv('MONGODB_URI', '')
MONGODB_DB_NAME = os.getenv('MONGODB_DB_NAME', 'CoverLetter')
MONGODB_COLLECTION_NAME = os.getenv('MONGODB_COLLECTION_NAME', 'users')

# Global MongoDB client and database instances
mongodb_client: Optional[MongoClient] = None
mongodb_db = None


def connect_to_mongodb():
    """Connect to MongoDB Atlas"""
    global mongodb_client, mongodb_db
    
    if not MONGODB_URI:
        logger.warning("MONGODB_URI not set. MongoDB connection will not be established.")
        return False
    
    try:
        # Create MongoDB client
        mongodb_client = MongoClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=10000,  # 10 second connection timeout
        )
        
        # Test the connection
        mongodb_client.admin.command('ping')
        
        # Check if database name is in connection string
        import re
        uri_db_match = re.search(r'mongodb\+srv://[^/]+/([^?]+)', MONGODB_URI)
        if uri_db_match:
            uri_db_name = uri_db_match.group(1)
            logger.info(f"Database name found in connection string: {uri_db_name}")
            # Use database from URI if specified, otherwise use env var
            db_name = uri_db_name if uri_db_name else MONGODB_DB_NAME
        else:
            db_name = MONGODB_DB_NAME
        
        # Get database
        mongodb_db = mongodb_client[db_name]
        
        logger.info(f"Successfully connected to MongoDB Atlas. Using Database: {db_name}")
        print(f"📊 Connected to MongoDB Atlas - Database: '{db_name}'")
        return True
        
    except ConnectionFailure as e:
        logger.error(f"Failed to connect to MongoDB Atlas: {e}")
        mongodb_client = None
        mongodb_db = None
        return False
    except ConfigurationError as e:
        logger.error(f"MongoDB configuration error: {e}")
        mongodb_client = None
        mongodb_db = None
        return False
    except Exception as e:
        logger.error(f"Unexpected error connecting to MongoDB: {e}")
        mongodb_client = None
        mongodb_db = None
        return False


def close_mongodb_connection():
    """Close MongoDB connection"""
    global mongodb_client, mongodb_db
    
    if mongodb_client:
        try:
            mongodb_client.close()
            logger.info("MongoDB connection closed")
        except Exception as e:
            logger.error(f"Error closing MongoDB connection: {e}")
        finally:
            mongodb_client = None
            mongodb_db = None


def get_database():
    """Get MongoDB database instance"""
    return mongodb_db


def get_collection(collection_name: str = None):
    """Get MongoDB collection instance"""
    if mongodb_db is None:
        logger.error("MongoDB database not initialized. Call connect_to_mongodb() first.")
        return None
    
    collection = collection_name or MONGODB_COLLECTION_NAME
    return mongodb_db[collection]


def is_connected() -> bool:
    """Check if MongoDB is connected"""
    if mongodb_client is None:
        return False
    
    try:
        mongodb_client.admin.command('ping')
        return True
    except Exception:
        return False

