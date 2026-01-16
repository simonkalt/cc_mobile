"""
Email utilities for email verification integration using Zoho Mail API
"""

import logging
import requests
from typing import Optional
from datetime import datetime, timedelta

from app.utils.sms_utils import generate_verification_code
from app.core.config import settings

logger = logging.getLogger(__name__)

# Zoho Mail API base URL
ZOHO_MAIL_API_BASE = "https://mail.zoho.com/api"

# Check if Zoho Mail is configured
EMAIL_AVAILABLE = bool(
    settings.ZOHO_CLIENT_ID
    and settings.ZOHO_CLIENT_SECRET
    and settings.ZOHO_REFRESH_TOKEN
    and settings.ZOHO_ACCOUNT_ID
)

if not EMAIL_AVAILABLE:
    logger.warning("Zoho Mail API not configured. Email sending will not work.")

# Cache for access token
_access_token_cache: Optional[str] = None
_token_expires_at: Optional[datetime] = None


def get_zoho_access_token() -> Optional[str]:
    """
    Get Zoho Mail API access token using refresh token.
    Implements token caching to avoid unnecessary API calls.

    Returns:
        Access token string or None if failed
    """
    global _access_token_cache, _token_expires_at

    # Return cached token if still valid (with 5 minute buffer)
    if _access_token_cache and _token_expires_at:
        if datetime.now() < (_token_expires_at - timedelta(minutes=5)):
            logger.debug("Using cached Zoho access token")
            return _access_token_cache

    if not settings.ZOHO_CLIENT_ID or not settings.ZOHO_CLIENT_SECRET or not settings.ZOHO_REFRESH_TOKEN:
        logger.error("Zoho Mail API credentials not configured")
        return None

    try:
        # Request new access token using refresh token
        token_url = "https://accounts.zoho.com/oauth/v2/token"
        params = {
            "refresh_token": settings.ZOHO_REFRESH_TOKEN,
            "client_id": settings.ZOHO_CLIENT_ID,
            "client_secret": settings.ZOHO_CLIENT_SECRET,
            "grant_type": "refresh_token",
        }

        logger.info("Requesting new Zoho access token")
        response = requests.post(token_url, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)  # Default to 1 hour

            if access_token:
                # Cache the token
                _access_token_cache = access_token
                _token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.info("Successfully obtained Zoho access token")
                return access_token
            else:
                logger.error(f"Zoho token response missing access_token: {data}")
                return None
        else:
            logger.error(
                f"Failed to get Zoho access token: {response.status_code} - {response.text}"
            )
            return None

    except requests.exceptions.RequestException as e:
        logger.error(f"Error requesting Zoho access token: {e}", exc_info=True)
        return None
    except Exception as e:
        logger.error(f"Unexpected error getting Zoho access token: {e}", exc_info=True)
        return None


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send email message via Zoho Mail API

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body text

    Returns:
        True if email sent successfully, False otherwise
    """
    if not EMAIL_AVAILABLE:
        logger.error("Zoho Mail API not configured. Cannot send email.")
        return False

    if not settings.FROM_EMAIL:
        logger.error("FROM_EMAIL not configured. Cannot send email.")
        return False

    # Get access token
    access_token = get_zoho_access_token()
    if not access_token:
        logger.error("Failed to obtain Zoho access token")
        return False

    try:
        # Zoho Mail API endpoint for sending emails
        # Based on Zoho Mail API documentation: /api/accounts/{accountId}/messages
        # Note: The exact endpoint format may vary - check Zoho Mail API docs if this doesn't work
        send_url = f"{ZOHO_MAIL_API_BASE}/accounts/{settings.ZOHO_ACCOUNT_ID}/messages"

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json",
        }

        # Prepare email payload
        # Zoho Mail API format - adjust fields based on actual API documentation
        # Common formats: fromAddress/toAddress or from/to, content or body or htmlBody
        payload = {
            "fromAddress": settings.FROM_EMAIL,
            "toAddress": to_email,
            "subject": subject,
            "content": body,
            "contentType": "text",  # Use "text" for plain text, "html" for HTML emails
        }

        logger.info(f"Sending email via Zoho Mail API to {to_email} with subject '{subject}'")
        response = requests.post(send_url, json=payload, headers=headers, timeout=30)

        if response.status_code in [200, 201]:
            logger.info(f"Email sent successfully to {to_email} with subject '{subject}'")
            return True
        else:
            logger.error(
                f"Zoho Mail API error sending email to {to_email}: "
                f"{response.status_code} - {response.text}"
            )
            # If token expired, clear cache and retry once
            if response.status_code == 401:
                logger.warning("Access token may have expired, clearing cache")
                global _access_token_cache, _token_expires_at
                _access_token_cache = None
                _token_expires_at = None
                # Retry once with new token
                access_token = get_zoho_access_token()
                if access_token:
                    headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
                    retry_response = requests.post(send_url, json=payload, headers=headers, timeout=30)
                    if retry_response.status_code in [200, 201]:
                        logger.info(f"Email sent successfully on retry to {to_email}")
                        return True
            return False

    except requests.exceptions.RequestException as e:
        logger.error(f"Network error sending email to {to_email}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"Unexpected error sending email to {to_email}: {e}", exc_info=True)
        return False


def send_verification_code_email(email: str, code: str, purpose: str = "verification") -> bool:
    """
    Send verification code via email

    Args:
        email: Recipient email address
        code: 6-digit verification code
        purpose: Purpose of verification (forgot_password, change_password, finish_registration)

    Returns:
        True if email sent successfully, False otherwise
    """
    logger.info(
        f"Attempting to send verification code email to {email} for purpose: {purpose}, code: {code}"
    )

    purpose_subjects = {
        "forgot_password": "Password Reset Verification Code",
        "change_password": "Password Change Verification Code",
        "finish_registration": "Registration Verification Code",
        "verification": "Verification Code",
    }

    purpose_messages = {
        "forgot_password": f"Your password reset code is: {code}. This code will expire in 10 minutes.",
        "change_password": f"Your password change verification code is: {code}. This code will expire in 10 minutes.",
        "finish_registration": f"Your registration verification code is: {code}. This code will expire in 10 minutes.",
        "verification": f"Your verification code is: {code}. This code will expire in 10 minutes.",
    }

    subject = purpose_subjects.get(purpose, purpose_subjects["verification"])
    body = purpose_messages.get(purpose, purpose_messages["verification"])

    result = send_email(email, subject, body)
    if result:
        logger.info(f"✓ Successfully sent verification code email to {email}")
    else:
        logger.error(f"✗ Failed to send verification code email to {email}")
    return result
