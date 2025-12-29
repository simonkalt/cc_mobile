"""
Email utilities for email verification integration
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

from app.utils.sms_utils import generate_verification_code
from app.core.config import settings

logger = logging.getLogger(__name__)

# Check if SMTP is configured
EMAIL_AVAILABLE = bool(settings.SMTP_SERVER and settings.SMTP_USERNAME and settings.SMTP_PASSWORD)

if not EMAIL_AVAILABLE:
    logger.warning("SMTP not configured. Email sending will not work.")


def send_email(to_email: str, subject: str, body: str) -> bool:
    """
    Send email message via SMTP provider

    Args:
        to_email: Recipient email address
        subject: Email subject line
        body: Email body text

    Returns:
        True if email sent successfully, False otherwise
    """
    if not EMAIL_AVAILABLE:
        logger.error("SMTP not configured. Cannot send email.")
        return False

    if not settings.FROM_EMAIL:
        logger.error("FROM_EMAIL not configured. Cannot send email.")
        return False

    try:
        # Create message
        msg = MIMEMultipart()
        msg["From"] = settings.FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add body to email
        msg.attach(MIMEText(body, "plain"))

        # Create SMTP connection
        if settings.SMTP_USE_SSL:
            # SSL connection (ports 465, 8465, 443)
            server = smtplib.SMTP_SSL(settings.SMTP_SERVER, settings.SMTP_PORT)
        else:
            # Regular connection (ports 2525, 8025, 587, 80, 25)
            server = smtplib.SMTP(settings.SMTP_SERVER, settings.SMTP_PORT)
            if settings.SMTP_USE_TLS:
                server.starttls()

        # Login and send
        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()

        logger.info(f"Email sent successfully to {to_email} with subject '{subject}'")
        return True

    except smtplib.SMTPAuthenticationError as e:
        logger.error(f"SMTP authentication failed: {e}")
        return False
    except smtplib.SMTPException as e:
        logger.error(f"SMTP error sending email to {to_email}: {e}")
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
