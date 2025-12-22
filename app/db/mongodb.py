"""
MongoDB Atlas connection module for FastAPI application
"""
import re
import logging
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, ConfigurationError
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global MongoDB client and database instances
mongodb_client: Optional[MongoClient] = None
mongodb_db = None


def connect_to_mongodb() -> bool:
    """
    Connect to MongoDB Atlas
    
    Returns:
        True if connection successful, False otherwise
    """
    global mongodb_client, mongodb_db
    
    if not settings.MONGODB_URI:
        logger.warning("MONGODB_URI not set. MongoDB connection will not be established.")
        return False
    
    try:
        # Create MongoDB client
        mongodb_client = MongoClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=5000,  # 5 second timeout
            connectTimeoutMS=10000,  # 10 second connection timeout
        )
        
        # Test the connection
        mongodb_client.admin.command('ping')
        
        # Check if database name is in connection string
        uri_db_match = re.search(r'mongodb\+srv://[^/]+/([^?]+)', settings.MONGODB_URI)
        if uri_db_match:
            uri_db_name = uri_db_match.group(1)
            logger.info(f"Database name found in connection string: {uri_db_name}")
            # Use database from URI if specified, otherwise use env var
            db_name = uri_db_name if uri_db_name else settings.MONGODB_DB_NAME
        else:
            db_name = settings.MONGODB_DB_NAME
        
        # Get database
        mongodb_db = mongodb_client[db_name]
        
        # Verify database and collection access
        logger.info(f"Successfully connected to MongoDB Atlas. Using Database: {db_name}")
        logger.info(f"Collection name configured: {settings.MONGODB_COLLECTION_NAME}")
        
        # List collections to verify access
        try:
            collections = mongodb_db.list_collection_names()
            logger.info(f"Available collections in database '{db_name}': {collections}")
            if settings.MONGODB_COLLECTION_NAME in collections:
                collection = mongodb_db[settings.MONGODB_COLLECTION_NAME]
                user_count = collection.count_documents({})
                logger.info(f"Collection '{settings.MONGODB_COLLECTION_NAME}' exists with {user_count} documents")
            else:
                logger.warning(f"Collection '{settings.MONGODB_COLLECTION_NAME}' not found in database '{db_name}'")
        except Exception as e:
            logger.warning(f"Could not list collections: {e}")
        
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


def close_mongodb_connection() -> None:
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


def get_collection(collection_name: Optional[str] = None):
    """
    Get MongoDB collection instance
    
    Args:
        collection_name: Name of the collection (defaults to configured collection name)
    
    Returns:
        MongoDB collection instance or None if database not initialized
    """
    if mongodb_db is None:
        logger.error("MongoDB database not initialized. Call connect_to_mongodb() first.")
        return None
    
    collection_name_final = collection_name or settings.MONGODB_COLLECTION_NAME
    db_name = mongodb_db.name if mongodb_db is not None else "unknown"
    logger.debug(f"Accessing collection '{collection_name_final}' in database '{db_name}'")
    return mongodb_db[collection_name_final]


def is_connected() -> bool:
    """
    Check if MongoDB is connected
    
    Returns:
        True if connected, False otherwise
    """
    if mongodb_client is None:
        logger.debug("MongoDB client is None - not connected")
        return False
    
    try:
        mongodb_client.admin.command('ping')
        return True
    except Exception as e:
        logger.debug(f"MongoDB ping failed: {e}")
        return False

