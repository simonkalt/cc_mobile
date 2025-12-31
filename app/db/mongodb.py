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
            # Use database from URI if specified, otherwise use env var
            db_name = uri_db_name if uri_db_name else settings.MONGODB_DB_NAME
        else:
            db_name = settings.MONGODB_DB_NAME
        
        # Get database
        mongodb_db = mongodb_client[db_name]
        
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
    """Close MongoDB connection - non-blocking to prevent hanging on shutdown"""
    global mongodb_client, mongodb_db
    
    if mongodb_client is not None:
        # Clear references immediately to allow fast shutdown
        # The connection will be cleaned up by garbage collection
        client_to_close = mongodb_client
        mongodb_client = None
        mongodb_db = None
        
        # Try to close in background, but don't wait for it
        try:
            import threading
            def close_in_background():
                try:
                    client_to_close.close()
                    logger.debug("MongoDB connection closed successfully")
                except Exception as e:
                    logger.debug(f"MongoDB close error (non-critical): {e}")
            
            # Start close in daemon thread - won't block shutdown
            thread = threading.Thread(target=close_in_background, daemon=True)
            thread.start()
            # Don't wait for thread - allow immediate return
        except Exception as e:
            logger.debug(f"Error starting MongoDB close thread: {e}")
        
        logger.info("MongoDB connection cleanup completed")


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

