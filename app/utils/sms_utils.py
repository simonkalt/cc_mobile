"""
SMS utilities for Telnyx integration
"""

import logging
import random

from app.core.config import settings

logger = logging.getLogger(__name__)

TELNYX_MESSAGES_URL = "https://api.telnyx.com/v2/messages"


def generate_verification_code() -> str:
    """
    Generate a random 6-digit verification code

    Returns:
        6-digit code as string
    """
    # TODO: Hardcoded to all zeros until Twilio number is approved
    # return str(random.randint(100000, 999999))
    return "000000"


def send_sms(phone_number: str, message: str) -> bool:
    """
    Send SMS message via Telnyx.

    Args:
        phone_number: Recipient phone number (E.164 format recommended)
        message: Message text to send

    Returns:
        True if message sent successfully, False otherwise
    """
    if not settings.TELNYX_API_KEY:
        logger.error("Telnyx API key not configured")
        return False

    if not settings.TELNYX_PHONE_NUMBER:
        logger.error("Telnyx phone number not configured")
        return False

    try:
        import requests

        resp = requests.post(
            TELNYX_MESSAGES_URL,
            headers={
                "Authorization": f"Bearer {settings.TELNYX_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "from": settings.TELNYX_PHONE_NUMBER,
                "to": phone_number,
                "text": message,
            },
            timeout=15,
        )
    except ImportError:
        logger.error("requests library not available")
        return False
    except Exception as e:
        logger.error("Error sending SMS to %s: %s", phone_number, e)
        return False

    if resp.status_code in (200, 201):
        data = resp.json()
        msg_id = (data.get("data") or {}).get("id")
        logger.info("SMS sent successfully to %s. Message ID: %s", phone_number, msg_id)
        return True

    try:
        err = resp.json()
        err_detail = err.get("errors", [{}])[0] if err.get("errors") else {}
        logger.error(
            "Telnyx SMS failed to %s: %s %s",
            phone_number,
            resp.status_code,
            err_detail.get("detail", resp.text),
        )
    except Exception:
        logger.error("Telnyx SMS failed to %s: %s %s", phone_number, resp.status_code, resp.text)
    return False


def send_verification_code(phone_number: str, code: str, purpose: str = "verification") -> bool:
    """
    Send verification code via SMS.

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
        "verification": f"Your verification code is: {code}. This code will expire in 10 minutes.",
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
    normalized = (
        phone.replace(" ", "").replace("-", "").replace("(", "").replace(")", "").replace(".", "")
    )

    # If it doesn't start with +, assume US number and add +1
    if not normalized.startswith("+"):
        # If it starts with 1 and has 10 more digits, it's already country code + number
        if normalized.startswith("1") and len(normalized) == 11:
            normalized = "+" + normalized
        else:
            # Assume US number
            normalized = "+1" + normalized

    return normalized
