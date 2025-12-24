"""
SMS utilities for Twilio integration
"""
import logging
import random
from typing import Optional
from datetime import datetime, timedelta

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import Twilio
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    TWILIO_AVAILABLE = False
    logger.warning("twilio library not available. SMS functionality will not work.")


def generate_verification_code() -> str:
    """
    Generate a random 6-digit verification code
    
    Returns:
        6-digit code as string
    """
    return str(random.randint(100000, 999999))


def send_sms(phone_number: str, message: str) -> bool:
    """
    Send SMS message via Twilio
    
    Args:
        phone_number: Recipient phone number (E.164 format recommended)
        message: Message text to send
        
    Returns:
        True if message sent successfully, False otherwise
    """
    if not TWILIO_AVAILABLE:
        logger.error("Twilio library not available")
        return False
    
    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        logger.error("Twilio credentials not configured")
        return False
    
    if not settings.TWILIO_PHONE_NUMBER:
        logger.error("Twilio phone number not configured")
        return False
    
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        
        logger.info(f"SMS sent successfully to {phone_number}. SID: {message.sid}")
        return True
        
    except Exception as e:
        logger.error(f"Error sending SMS to {phone_number}: {str(e)}")
        return False


def send_verification_code(phone_number: str, code: str, purpose: str = "verification") -> bool:
    """
    Send verification code via SMS
    
    Args:
        phone_number: Recipient phone number
        code: 6-digit verification code
        purpose: Purpose of verification (forgot_password, change_password, finish_registration)
        
    Returns:
        True if message sent successfully, False otherwise
    """
    purpose_messages = {
        "forgot_password": f"Your password reset code is: {code}. This code will expire in 10 minutes.",
        "change_password": f"Your password change verification code is: {code}. This code will expire in 10 minutes.",
        "finish_registration": f"Your registration verification code is: {code}. This code will expire in 10 minutes.",
        "verification": f"Your verification code is: {code}. This code will expire in 10 minutes."
    }
    
    message = purpose_messages.get(purpose, purpose_messages["verification"])
    return send_sms(phone_number, message)


def normalize_phone_number(phone: str) -> str:
    """
    Normalize phone number to E.164 format (basic implementation)
    Removes spaces, dashes, parentheses, and ensures + prefix
    
    Args:
        phone: Phone number in various formats
        
    Returns:
        Normalized phone number
    """
    # Remove common formatting characters
    normalized = phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
    
    # If it doesn't start with +, assume US number and add +1
    if not normalized.startswith("+"):
        # If it starts with 1 and has 10 more digits, it's already country code + number
        if normalized.startswith("1") and len(normalized) == 11:
            normalized = "+" + normalized
        else:
            # Assume US number
            normalized = "+1" + normalized
    
    return normalized

