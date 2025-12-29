"""
Verification code service - handles storage and validation of SMS verification codes
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_collection, is_connected
from app.utils.sms_utils import (
    generate_verification_code,
    send_verification_code,
    normalize_phone_number,
)
from app.utils.email_utils import send_verification_code_email
from app.utils.user_helpers import USERS_COLLECTION
from app.utils.redis_utils import (
    is_redis_available,
    store_registration_data,
    get_registration_data,
    delete_registration_data,
    store_verification_session,
    get_verification_session,
    delete_verification_session,
)
from app.utils.password import hash_password

logger = logging.getLogger(__name__)

# Verification code expiration time (10 minutes)
VERIFICATION_CODE_EXPIRY_MINUTES = 10


def store_verification_code(
    user_id: str,
    code: str,
    purpose: str,
    phone_number: Optional[str] = None,
    email: Optional[str] = None
) -> bool:
    """
    Store verification code in user document
    
    Args:
        user_id: User ID
        code: Verification code
        purpose: Purpose of verification
        phone_number: Phone number used (for SMS)
        email: Email address used (for email)
        
    Returns:
        True if stored successfully
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    try:
        expires_at = datetime.utcnow() + timedelta(minutes=VERIFICATION_CODE_EXPIRY_MINUTES)
        
        verification_data = {
            "code": code,
            "purpose": purpose,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "verified": False
        }
        
        # Store contact method (phone or email)
        if phone_number:
            verification_data["phone_number"] = phone_number
        if email:
            verification_data["email"] = email
        
        collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"verification_code": verification_data}}
        )
        
        logger.info(f"Stored verification code for user {user_id}, purpose: {purpose}")
        return True
        
    except Exception as e:
        logger.error(f"Error storing verification code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to store verification code: {str(e)}"
        )


def verify_code(user_id: str, code: str, purpose: str) -> bool:
    """
    Verify a code for a user
    
    Args:
        user_id: User ID
        code: Verification code to check
        purpose: Purpose of verification
        
    Returns:
        True if code is valid, False otherwise
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    try:
        user = collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        verification_data = user.get("verification_code")
        if not verification_data:
            logger.warning(f"No verification code found for user {user_id}")
            return False
        
        # Check if code matches
        if verification_data.get("code") != code:
            logger.warning(f"Invalid verification code for user {user_id}")
            return False
        
        # Check if purpose matches
        if verification_data.get("purpose") != purpose:
            logger.warning(f"Verification purpose mismatch for user {user_id}")
            return False
        
        # Check if already verified
        if verification_data.get("verified", False):
            logger.warning(f"Verification code already used for user {user_id}")
            return False
        
        # Check if expired
        expires_at = verification_data.get("expires_at")
        if expires_at and datetime.utcnow() > expires_at:
            logger.warning(f"Verification code expired for user {user_id}")
            return False
        
        # Mark as verified
        collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$set": {"verification_code.verified": True}}
        )
        
        logger.info(f"Verification code verified successfully for user {user_id}")
        return True
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to verify code: {str(e)}"
        )


def clear_verification_code(user_id: str) -> None:
    """
    Clear verification code from user document
    
    Args:
        user_id: User ID
    """
    if not is_connected():
        return
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        return
    
    try:
        collection.update_one(
            {"_id": ObjectId(user_id)},
            {"$unset": {"verification_code": ""}}
        )
        logger.info(f"Cleared verification code for user {user_id}")
    except Exception as e:
        logger.error(f"Error clearing verification code: {e}")


def send_and_store_verification_code(
    user_id: str,
    phone_number: str,
    purpose: str
) -> str:
    """
    Generate, send, and store verification code
    
    Args:
        user_id: User ID
        phone_number: Phone number to send code to
        purpose: Purpose of verification
        
    Returns:
        Generated verification code
    """
    # Generate code
    code = generate_verification_code()
    
    # Normalize phone number
    normalized_phone = normalize_phone_number(phone_number)
    
    # Send SMS
    if not send_verification_code(normalized_phone, code, purpose):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification code"
        )
    
    # Store code
    store_verification_code(user_id, code, purpose, phone_number=normalized_phone)
    
    return code


def send_and_store_verification_code_email(
    user_id: Optional[str],
    email: str,
    purpose: str,
    registration_data: Optional[dict] = None,
    delivery_method: str = "email"
) -> str:
    """
    Generate, send, and store verification code via email
    Uses Redis for registration flow, MongoDB for existing users
    
    Args:
        user_id: User ID (None for registration flow)
        email: Email address to send code to
        purpose: Purpose of verification
        registration_data: Registration data dictionary (for finish_registration)
        delivery_method: "email" or "sms"
        
    Returns:
        Generated verification code
    """
    # Generate code
    code = generate_verification_code()
    
    # For registration flow, use Redis
    if purpose == "finish_registration" and registration_data:
        # Hash password before storing in Redis
        if "password" in registration_data and registration_data["password"]:
            registration_data["password"] = hash_password(registration_data["password"])
        
        # Store registration data in Redis
        if not store_registration_data(email, code, registration_data):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to store registration data"
            )
        
        # Store verification session in Redis
        registration_key = f"registration:{email}:{code}"
        if not store_verification_session(
            email=email,
            code=code,
            purpose=purpose,
            delivery_method=delivery_method,
            registration_key=registration_key
        ):
            logger.warning(f"Failed to store verification session in Redis for {email}")
    elif user_id:
        # For existing users, use MongoDB
        # Send email (stub - just logs for now)
        if not send_verification_code_email(email, code, purpose):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification code"
            )
        
        # Store code in MongoDB
        store_verification_code(user_id, code, purpose, email=email)
    else:
        # No user_id and not registration - this shouldn't happen
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid request: user_id required for non-registration flows"
        )
    
    # Send email/SMS
    if delivery_method == "sms":
        from app.utils.sms_utils import send_verification_code, normalize_phone_number
        phone = registration_data.get("phone") if registration_data else None
        if phone:
            normalized_phone = normalize_phone_number(phone)
            if not send_verification_code(normalized_phone, code, purpose):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to send verification code"
                )
        else:
            logger.warning(f"No phone number provided for SMS delivery to {email}")
    else:
        if not send_verification_code_email(email, code, purpose):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to send verification code"
            )
    
    return code


def verify_code_from_redis(email: str, code: str, purpose: str) -> Optional[dict]:
    """
    Verify code from Redis (for registration flow)
    
    Args:
        email: User's email address
        code: Verification code
        purpose: Purpose of verification
        
    Returns:
        Verification session data if valid, None otherwise
    """
    if not is_redis_available():
        logger.warning("Redis not available for verification")
        return None
    
    session_data = get_verification_session(email, code, purpose)
    if not session_data:
        return None
    
    return session_data


def complete_registration_from_redis(email: str, code: str) -> dict:
    """
    Complete registration by retrieving data from Redis and creating user
    
    Args:
        email: User's email address
        code: Verification code
        
    Returns:
        Registration data dictionary
        
    Raises:
        HTTPException: If registration data not found or invalid
    """
    if not is_redis_available():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Redis service unavailable"
        )
    
    # Get registration data from Redis
    registration_data = get_registration_data(email, code)
    if not registration_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Registration data expired or not found. Please register again."
        )
    
    return registration_data

