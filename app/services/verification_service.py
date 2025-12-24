"""
Verification code service - handles storage and validation of SMS verification codes
"""
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_collection, is_connected
from app.utils.sms_utils import (
    generate_verification_code,
    send_verification_code,
    normalize_phone_number,
)
from app.utils.user_helpers import USERS_COLLECTION

logger = logging.getLogger(__name__)

# Verification code expiration time (10 minutes)
VERIFICATION_CODE_EXPIRY_MINUTES = 10


def store_verification_code(
    user_id: str,
    code: str,
    purpose: str,
    phone_number: str
) -> bool:
    """
    Store verification code in user document
    
    Args:
        user_id: User ID
        code: Verification code
        purpose: Purpose of verification
        phone_number: Phone number used
        
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
            "phone_number": phone_number,
            "created_at": datetime.utcnow(),
            "expires_at": expires_at,
            "verified": False
        }
        
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
    store_verification_code(user_id, code, purpose, normalized_phone)
    
    return code

