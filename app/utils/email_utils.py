"""
Email utilities for email verification integration
"""

import logging
from typing import Optional

from app.utils.sms_utils import generate_verification_code

logger = logging.getLogger(__name__)

# TODO: Add email/SMTP provider integration when available
EMAIL_AVAILABLE = False


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send email message via SMTP provider (stub implementation)

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body text

    Returns:
        True if email would be sent successfully (currently always True as stub)
    """
    # TODO: Implement actual email sending when SMTP provider is configured
    logger.info(
        f"[EMAIL STUB] Would send email to {to_email} with subject '{subject}'. "
        f"Body: {body[:100]}..."
        if len(body) > 100
        else f"Body: {body}"
    )
    return True


def send_verification_code_email(email: str, code: str, purpose: str = "verification") -> bool:
    """
    Send verification code via email

    Args:
        email: Recipient email address
        code: 6-digit verification code
        purpose: Purpose of verification (forgot_password, change_password, finish_registration)

    Returns:
        True if email would be sent successfully (currently always True as stub)
    """
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

    return send_email(email, subject, body)
