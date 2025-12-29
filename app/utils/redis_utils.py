"""
Redis utilities for temporary data storage (verification codes, registration data)
"""
import logging
import json
import os
from typing import Optional, Dict, Any
from datetime import timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

# ANSI color codes for Redis logs
# Check if we're in a terminal that supports colors (not in CI/CD or when output is redirected)
SUPPORTS_COLOR = os.getenv("TERM") is not None and os.getenv("NO_COLOR") is None

# Redis log colors (magenta/red theme)
REDIS_COLOR_PREFIX = "\033[95m[REDIS]\033[0m " if SUPPORTS_COLOR else "[REDIS] "
REDIS_INFO_COLOR = "\033[96m[REDIS]\033[0m " if SUPPORTS_COLOR else "[REDIS] "
REDIS_WARN_COLOR = "\033[93m[REDIS WARN]\033[0m " if SUPPORTS_COLOR else "[REDIS WARN] "
REDIS_ERROR_COLOR = "\033[91m[REDIS ERROR]\033[0m " if SUPPORTS_COLOR else "[REDIS ERROR] "


def _redis_log_info(message: str) -> None:
    """Log Redis info message with color"""
    logger.info(f"{REDIS_INFO_COLOR}{message}")


def _redis_log_warning(message: str) -> None:
    """Log Redis warning message with color"""
    logger.warning(f"{REDIS_WARN_COLOR}{message}")


def _redis_log_error(message: str) -> None:
    """Log Redis error message with color"""
    logger.error(f"{REDIS_ERROR_COLOR}{message}")

# Try to import redis
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None
    if SUPPORTS_COLOR:
        logger.warning(f"{REDIS_WARN_COLOR}redis library not available. Redis operations will not work.")
    else:
        logger.warning("[REDIS WARN] redis library not available. Redis operations will not work.")

# Redis client instance (initialized on first use)
_redis_client: Optional[Any] = None


def get_redis_client():
    """
    Get Redis client instance (singleton pattern)
    
    Returns:
        Redis client instance
        
    Raises:
        ImportError: If redis library is not installed
        ConnectionError: If Redis connection fails
    """
    global _redis_client
    
    if not REDIS_AVAILABLE:
        raise ImportError("redis library is not installed. Cannot access Redis.")
    
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
            _redis_log_info(f"✓ Connected to Redis at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            
        except redis.ConnectionError as e:
            _redis_log_error(f"✗ Failed to connect to Redis: {e}")
            raise ConnectionError(f"Redis connection failed: {str(e)}")
        except Exception as e:
            _redis_log_error(f"✗ Unexpected error connecting to Redis: {e}")
            raise ConnectionError(f"Redis connection error: {str(e)}")
    
    return _redis_client


def is_redis_available() -> bool:
    """
    Check if Redis is available and connected
    
    Returns:
        True if Redis is available, False otherwise
    """
    if not REDIS_AVAILABLE:
        return False
    try:
        client = get_redis_client()
        client.ping()
        return True
    except Exception as e:
        _redis_log_warning(f"Redis not available: {e}")
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
        
    Raises:
        ImportError: If redis library is not installed
        ConnectionError: If Redis connection fails
    """
    if not REDIS_AVAILABLE:
        error_msg = "Redis library is not installed. Please install it with: pip install redis"
        _redis_log_error(error_msg)
        raise ImportError(error_msg)
    
    try:
        client = get_redis_client()
        key = f"registration:{email}:{code}"
        
        # Store as JSON string
        client.setex(
            key,
            timedelta(minutes=ttl_minutes),
            json.dumps(registration_data)
        )
        
        _redis_log_info(f"✓ Stored registration data in Redis for {email} (expires in {ttl_minutes} minutes)")
        return True
        
    except (ImportError, ConnectionError):
        # Re-raise these as-is
        raise
    except Exception as e:
        _redis_log_error(f"✗ Error storing registration data in Redis: {e}")
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
            _redis_log_warning(f"⚠ Registration data not found in Redis for {email}")
            return None
        
        _redis_log_info(f"✓ Retrieved registration data from Redis for {email}")
        return json.loads(data_json)
        
    except json.JSONDecodeError as e:
        _redis_log_error(f"✗ Error parsing registration data from Redis: {e}")
        return None
    except Exception as e:
        _redis_log_error(f"✗ Error retrieving registration data from Redis: {e}")
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
            _redis_log_info(f"✓ Deleted registration data from Redis for {email}")
        else:
            _redis_log_warning(f"⚠ Registration data not found in Redis for deletion: {email}")
        
        return deleted > 0
        
    except Exception as e:
        _redis_log_error(f"✗ Error deleting registration data from Redis: {e}")
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
        
        _redis_log_info(f"✓ Stored verification session in Redis for {email}, purpose: {purpose}")
        return True
        
    except Exception as e:
        _redis_log_error(f"✗ Error storing verification session in Redis: {e}")
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
            _redis_log_warning(f"⚠ Verification session not found in Redis for {email}, purpose: {purpose}")
            return None
        
        _redis_log_info(f"✓ Retrieved verification session from Redis for {email}, purpose: {purpose}")
        return json.loads(data_json)
        
    except json.JSONDecodeError as e:
        _redis_log_error(f"✗ Error parsing verification session data from Redis: {e}")
        return None
    except Exception as e:
        _redis_log_error(f"✗ Error retrieving verification session from Redis: {e}")
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
            _redis_log_info(f"✓ Deleted verification session from Redis for {email}, purpose: {purpose}")
        else:
            _redis_log_warning(f"⚠ Verification session not found in Redis for deletion: {email}, purpose: {purpose}")
        
        return deleted > 0
        
    except Exception as e:
        _redis_log_error(f"✗ Error deleting verification session from Redis: {e}")
        return False

