"""
Redis utilities for temporary data storage (verification codes, registration data)
"""
import logging
import json
import redis
from typing import Optional, Dict, Any
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis client instance (initialized on first use)
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> redis.Redis:
    """
    Get Redis client instance (singleton pattern)
    
    Returns:
        Redis client instance
        
    Raises:
        ConnectionError: If Redis connection fails
    """
    global _redis_client
    
    if _redis_client is None:
        if not settings.REDIS_HOST:
            raise ConnectionError("Redis host not configured. Set REDIS_HOST in environment variables.")
        
        try:
            # Build connection parameters
            connection_params = {
                "host": settings.REDIS_HOST,
                "port": settings.REDIS_PORT,
                "db": settings.REDIS_DB,
                "decode_responses": True,  # Automatically decode responses to strings
                "socket_connect_timeout": 5,
                "socket_timeout": 5,
            }
            
            # Add authentication if provided
            if settings.REDIS_USERNAME and settings.REDIS_PASSWORD:
                connection_params["username"] = settings.REDIS_USERNAME
                connection_params["password"] = settings.REDIS_PASSWORD
            elif settings.REDIS_PASSWORD:
                # Some Redis setups only use password (no username)
                connection_params["password"] = settings.REDIS_PASSWORD
            
            # Add SSL if configured
            if settings.REDIS_SSL:
                connection_params["ssl"] = True
                connection_params["ssl_cert_reqs"] = "required"
            
            _redis_client = redis.Redis(**connection_params)
            
            # Test connection
            _redis_client.ping()
            logger.info(f"Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
        except redis.ConnectionError as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise ConnectionError(f"Redis connection failed: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error connecting to Redis: {e}")
            raise ConnectionError(f"Redis connection error: {str(e)}")
    
    return _redis_client


def is_redis_available() -> bool:
    """
    Check if Redis is available and connected
    
    Returns:
        True if Redis is available, False otherwise
    """
    try:
        client = get_redis_client()
        client.ping()
        return True
    except Exception as e:
        logger.warning(f"Redis not available: {e}")
        return False


def store_registration_data(
    email: str,
    code: str,
    registration_data: Dict[str, Any],
    ttl_minutes: int = 10
) -> bool:
    """
    Store registration data in Redis with TTL
    
    Args:
        email: User's email address
        code: Verification code
        registration_data: Registration data dictionary (password should already be hashed)
        ttl_minutes: Time to live in minutes (default: 10)
        
    Returns:
        True if stored successfully, False otherwise
    """
    try:
        client = get_redis_client()
        key = f"registration:{email}:{code}"
        
        # Store as JSON string
        client.setex(
            key,
            timedelta(minutes=ttl_minutes),
            json.dumps(registration_data)
        )
        
        logger.info(f"Stored registration data in Redis for {email} (expires in {ttl_minutes} minutes)")
        return True
        
    except Exception as e:
        logger.error(f"Error storing registration data in Redis: {e}")
        return False


def get_registration_data(email: str, code: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve registration data from Redis
    
    Args:
        email: User's email address
        code: Verification code
        
    Returns:
        Registration data dictionary if found, None otherwise
    """
    try:
        client = get_redis_client()
        key = f"registration:{email}:{code}"
        
        data_json = client.get(key)
        if not data_json:
            logger.warning(f"Registration data not found in Redis for {email}")
            return None
        
        return json.loads(data_json)
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing registration data from Redis: {e}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving registration data from Redis: {e}")
        return None


def delete_registration_data(email: str, code: str) -> bool:
    """
    Delete registration data from Redis
    
    Args:
        email: User's email address
        code: Verification code
        
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        client = get_redis_client()
        key = f"registration:{email}:{code}"
        
        deleted = client.delete(key)
        if deleted:
            logger.info(f"Deleted registration data from Redis for {email}")
        else:
            logger.warning(f"Registration data not found in Redis for deletion: {email}")
        
        return deleted > 0
        
    except Exception as e:
        logger.error(f"Error deleting registration data from Redis: {e}")
        return False


def store_verification_session(
    email: str,
    code: str,
    purpose: str,
    phone: Optional[str] = None,
    delivery_method: str = "email",
    registration_key: Optional[str] = None,
    ttl_minutes: int = 10
) -> bool:
    """
    Store verification session data in Redis
    
    Args:
        email: User's email address
        code: Verification code
        purpose: Purpose of verification
        phone: Phone number (optional, for SMS)
        delivery_method: "email" or "sms"
        registration_key: Key to registration data (if registration flow)
        ttl_minutes: Time to live in minutes (default: 10)
        
    Returns:
        True if stored successfully, False otherwise
    """
    try:
        client = get_redis_client()
        key = f"verification:{purpose}:{email}:{code}"
        
        session_data = {
            "email": email,
            "code": code,
            "purpose": purpose,
            "delivery_method": delivery_method,
        }
        
        if phone:
            session_data["phone"] = phone
        if registration_key:
            session_data["registration_key"] = registration_key
        
        client.setex(
            key,
            timedelta(minutes=ttl_minutes),
            json.dumps(session_data)
        )
        
        logger.info(f"Stored verification session in Redis for {email}, purpose: {purpose}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing verification session in Redis: {e}")
        return False


def get_verification_session(email: str, code: str, purpose: str) -> Optional[Dict[str, Any]]:
    """
    Retrieve verification session data from Redis
    
    Args:
        email: User's email address
        code: Verification code
        purpose: Purpose of verification
        
    Returns:
        Verification session data dictionary if found, None otherwise
    """
    try:
        client = get_redis_client()
        key = f"verification:{purpose}:{email}:{code}"
        
        data_json = client.get(key)
        if not data_json:
            logger.warning(f"Verification session not found in Redis for {email}, purpose: {purpose}")
            return None
        
        return json.loads(data_json)
        
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing verification session data from Redis: {e}")
        return None
    except Exception as e:
        logger.error(f"Error retrieving verification session from Redis: {e}")
        return None


def delete_verification_session(email: str, code: str, purpose: str) -> bool:
    """
    Delete verification session data from Redis
    
    Args:
        email: User's email address
        code: Verification code
        purpose: Purpose of verification
        
    Returns:
        True if deleted successfully, False otherwise
    """
    try:
        client = get_redis_client()
        key = f"verification:{purpose}:{email}:{code}"
        
        deleted = client.delete(key)
        if deleted:
            logger.info(f"Deleted verification session from Redis for {email}, purpose: {purpose}")
        
        return deleted > 0
        
    except Exception as e:
        logger.error(f"Error deleting verification session from Redis: {e}")
        return False

