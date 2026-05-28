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
def _check_zoho_config() -> tuple[bool, list[str]]:
    """Check Zoho Mail configuration and return status with missing variables"""
    missing = []
    if not settings.ZOHO_CLIENT_ID:
        missing.append("ZOHO_CLIENT_ID")
    if not settings.ZOHO_CLIENT_SECRET:
        missing.append("ZOHO_CLIENT_SECRET")
    if not settings.ZOHO_REFRESH_TOKEN:
        missing.append("ZOHO_REFRESH_TOKEN")
    if not settings.ZOHO_ACCOUNT_ID:
        missing.append("ZOHO_ACCOUNT_ID")
    return len(missing) == 0, missing


EMAIL_AVAILABLE, missing_vars = _check_zoho_config()

if not EMAIL_AVAILABLE:
    logger.warning(
        f"Zoho Mail API not configured. Email sending will not work. "
        f"Missing environment variables: {', '.join(missing_vars)}"
    )
else:
    _cid = settings.ZOHO_CLIENT_ID or ""
    logger.info(
        "Zoho Mail API configuration check passed. "
        "client_id_prefix=%s secret_len=%s refresh_len=%s accounts_base=%s",
        _cid[:12] if len(_cid) >= 12 else _cid,
        len(settings.ZOHO_CLIENT_SECRET or ""),
        len(settings.ZOHO_REFRESH_TOKEN or ""),
        settings.ZOHO_ACCOUNTS_BASE,
    )

# Cache for access token
_access_token_cache: Optional[str] = None
_token_expires_at: Optional[datetime] = None


def zoho_config_fingerprint() -> dict:
    """Non-secret snapshot of loaded Zoho env (for UAT/debug)."""
    cid = (settings.ZOHO_CLIENT_ID or "").strip()
    secret = (settings.ZOHO_CLIENT_SECRET or "").strip()
    refresh = (settings.ZOHO_REFRESH_TOKEN or "").strip()
    return {
        "email_available": EMAIL_AVAILABLE,
        "client_id_prefix": cid[:12] if cid else "",
        "client_id_length": len(cid),
        "client_secret_length": len(secret),
        "refresh_token_length": len(refresh),
        "refresh_token_looks_like_zoho": refresh.startswith("1000.") if refresh else False,
        "accounts_base": (settings.ZOHO_ACCOUNTS_BASE or "https://accounts.zoho.com").rstrip(
            "/"
        ),
    }


def probe_zoho_refresh_token() -> dict:
    """
    Try one refresh-token exchange; return only success/error (no tokens).
    """
    fp = zoho_config_fingerprint()
    if not EMAIL_AVAILABLE:
        return {**fp, "ok": False, "error": "not_configured"}
    accounts_base = fp["accounts_base"]
    try:
        response = requests.post(
            f"{accounts_base}/oauth/v2/token",
            data={
                "grant_type": "refresh_token",
                "client_id": (settings.ZOHO_CLIENT_ID or "").strip(),
                "client_secret": (settings.ZOHO_CLIENT_SECRET or "").strip(),
                "refresh_token": (settings.ZOHO_REFRESH_TOKEN or "").strip(),
            },
            timeout=10,
        )
        data = response.json() if response.content else {}
        if response.status_code == 200 and data.get("access_token"):
            return {**fp, "ok": True, "error": None}
        err = data.get("error") or f"http_{response.status_code}"
        return {**fp, "ok": False, "error": err}
    except requests.RequestException as exc:
        return {**fp, "ok": False, "error": str(exc)}


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
        else:
            logger.info("Cached Zoho access token expired, requesting new token")

    # Check configuration
    logger.info("Checking Zoho Mail API configuration...")
    if not settings.ZOHO_CLIENT_ID:
        logger.error("ZOHO_CLIENT_ID not configured")
        return None
    if not settings.ZOHO_CLIENT_SECRET:
        logger.error("ZOHO_CLIENT_SECRET not configured")
        return None
    if not settings.ZOHO_REFRESH_TOKEN:
        logger.error("ZOHO_REFRESH_TOKEN not configured")
        return None

    logger.info(f"Zoho configuration check passed. Client ID: {settings.ZOHO_CLIENT_ID[:10]}...")
    logger.info(
        f"Refresh token present: {bool(settings.ZOHO_REFRESH_TOKEN)} (length: {len(settings.ZOHO_REFRESH_TOKEN) if settings.ZOHO_REFRESH_TOKEN else 0})"
    )

    try:
        accounts_base = (settings.ZOHO_ACCOUNTS_BASE or "https://accounts.zoho.com").rstrip(
            "/"
        )
        token_url = f"{accounts_base}/oauth/v2/token"
        form = {
            "refresh_token": (settings.ZOHO_REFRESH_TOKEN or "").strip(),
            "client_id": (settings.ZOHO_CLIENT_ID or "").strip(),
            "client_secret": (settings.ZOHO_CLIENT_SECRET or "").strip(),
            "grant_type": "refresh_token",
        }

        logger.info(f"Requesting new Zoho access token from: {token_url}")
        logger.debug(
            "Token request: grant_type=refresh_token, client_id=%s..., refresh_len=%s, secret_len=%s",
            (settings.ZOHO_CLIENT_ID or "")[:10],
            len(settings.ZOHO_REFRESH_TOKEN or ""),
            len(settings.ZOHO_CLIENT_SECRET or ""),
        )

        response = requests.post(token_url, data=form, timeout=10)

        logger.info(f"Zoho token API response status: {response.status_code}")
        logger.debug(f"Zoho token API response headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            logger.info("Zoho token API returned 200 OK")
            logger.debug(f"Zoho token API response data keys: {list(data.keys())}")

            access_token = data.get("access_token")
            expires_in = data.get("expires_in", 3600)  # Default to 1 hour
            token_type = data.get("token_type", "Bearer")

            logger.info(f"Token type: {token_type}, Expires in: {expires_in} seconds")

            if access_token:
                # Cache the token
                _access_token_cache = access_token
                _token_expires_at = datetime.now() + timedelta(seconds=expires_in)
                logger.info(
                    f"Successfully obtained Zoho access token (length: {len(access_token)}, expires at: {_token_expires_at})"
                )
                logger.debug(f"Access token preview: {access_token[:20]}...{access_token[-10:]}")
                return access_token

            oauth_error = data.get("error")
            if oauth_error == "invalid_client_secret":
                logger.error(
                    "Zoho invalid_client_secret (client_id_prefix=%s secret_len=%s refresh_len=%s "
                    "accounts=%s): client_id, client_secret, and refresh_token must be one set from "
                    "the same Zoho API client — re-run zoho_auth_helper exchange after updating Render. "
                    "On Render, ensure dashboard and /etc/secrets/.secrets do not disagree.",
                    (settings.ZOHO_CLIENT_ID or "")[:12],
                    len((settings.ZOHO_CLIENT_SECRET or "").strip()),
                    len((settings.ZOHO_REFRESH_TOKEN or "").strip()),
                    accounts_base,
                )
            logger.error(
                "Zoho token response missing access_token (error=%s). Response data: %s",
                oauth_error,
                data,
            )
            return None
        else:
            logger.error(f"Failed to get Zoho access token: HTTP {response.status_code}")
            logger.error(f"Response text: {response.text}")
            try:
                error_data = response.json()
                logger.error(f"Error response JSON: {error_data}")
            except:
                logger.error(f"Error response is not JSON")
            return None

    except requests.exceptions.Timeout as e:
        logger.error(f"Timeout requesting Zoho access token: {e}", exc_info=True)
        return None
    except requests.exceptions.ConnectionError as e:
        logger.error(f"Connection error requesting Zoho access token: {e}", exc_info=True)
        return None
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error requesting Zoho access token: {e}", exc_info=True)
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
    logger.info(f"=== Starting email send process ===")
    logger.info(f"To: {to_email}, Subject: {subject}, Body length: {len(body)} characters")

    # Re-check configuration to get current status
    is_available, missing = _check_zoho_config()
    if not is_available:
        logger.error("Zoho Mail API not configured. Cannot send email.")
        logger.error(f"EMAIL_AVAILABLE check: {is_available}")
        logger.error(f"Missing environment variables: {', '.join(missing)}")
        logger.error("Please set the following environment variables:")
        for var in missing:
            logger.error(f"  - {var}")
        return False

    if not settings.FROM_EMAIL:
        logger.error("FROM_EMAIL not configured. Cannot send email.")
        return False

    logger.info(f"From email: {settings.FROM_EMAIL}")
    logger.info(f"Zoho Account ID: {settings.ZOHO_ACCOUNT_ID}")

    # Get access token
    logger.info("Step 1: Obtaining Zoho access token...")
    access_token = get_zoho_access_token()
    if not access_token:
        logger.error("Failed to obtain Zoho access token - aborting email send")
        return False

    logger.info(f"Step 1 complete: Access token obtained (length: {len(access_token)})")

    try:
        # Zoho Mail API endpoint for sending emails
        # Based on Zoho Mail API documentation: /api/accounts/{accountId}/messages
        # Note: The exact endpoint format may vary - check Zoho Mail API docs if this doesn't work
        send_url = f"{ZOHO_MAIL_API_BASE}/accounts/{settings.ZOHO_ACCOUNT_ID}/messages"
        logger.info(f"Step 2: Preparing email request to {send_url}")

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Content-Type": "application/json",
        }
        logger.debug(
            f"Request headers: Authorization=Zoho-oauthtoken {access_token[:20]}..., Content-Type=application/json"
        )

        # Prepare email payload
        # Zoho Mail API format - based on official Zoho Mail API documentation
        # Valid fields: fromAddress, toAddress, ccAddress, bccAddress, subject, content, mailFormat
        # mailFormat can be "html" or "plaintext" (NOT "text")
        payload = {
            "fromAddress": settings.FROM_EMAIL,
            "toAddress": to_email,
            "subject": subject,
            "content": body,  # Use "content" not "textBody"
            "mailFormat": "plaintext",  # Use "mailFormat" not "contentType", values: "html" or "plaintext"
        }
        logger.info(f"Email payload: from={settings.FROM_EMAIL}, to={to_email}, subject={subject}")
        logger.debug(f"Full payload: {payload}")

        logger.info(f"Step 3: Sending POST request to Zoho Mail API...")
        response = requests.post(send_url, json=payload, headers=headers, timeout=30)

        logger.info(f"Step 4: Received response from Zoho Mail API")
        logger.info(f"Response status code: {response.status_code}")
        logger.debug(f"Response headers: {dict(response.headers)}")
        logger.debug(f"Response text: {response.text}")

        if response.status_code in [200, 201]:
            logger.info(f"✓ Email sent successfully to {to_email} with subject '{subject}'")
            try:
                response_data = response.json()
                logger.info(f"Response data: {response_data}")
            except:
                logger.debug("Response is not JSON")
            return True
        else:
            logger.error(
                f"✗ Zoho Mail API error sending email to {to_email}: HTTP {response.status_code}"
            )
            logger.error(f"Response text: {response.text}")
            try:
                error_data = response.json()
                logger.error(f"Error response JSON: {error_data}")
                more = (error_data.get("data") or {}).get("moreInfo", "")
                if more and "internal error" in str(more).lower():
                    logger.error(
                        "Zoho generic internal error often means ZOHO_ACCOUNT_ID does not "
                        "match FROM_EMAIL. Run: python scripts/zoho_auth_helper.py --mode accounts "
                        "and use the accountId on the row whose primaryEmailAddress equals FROM_EMAIL "
                        "(from=%s accountId=%s).",
                        settings.FROM_EMAIL,
                        settings.ZOHO_ACCOUNT_ID,
                    )

                # If we get an error about extra keys, try alternative payload formats
                if (
                    response.status_code == 404
                    and error_data.get("data", {}).get("errorCode") == "EXTRA_KEY_FOUND_IN_JSON"
                ):
                    logger.warning(
                        "Received EXTRA_KEY_FOUND_IN_JSON error, trying alternative payload formats..."
                    )

                    # Try alternative format 1: using "to" as array and different field names
                    alt_payload1 = {
                        "from": settings.FROM_EMAIL,
                        "to": [to_email],  # Array format
                        "subject": subject,
                        "content": body,
                        "mailFormat": "plaintext",
                    }
                    logger.info(
                        f"Trying alternative payload format 1: from={settings.FROM_EMAIL}, to=[{to_email}]"
                    )
                    alt_response1 = requests.post(
                        send_url, json=alt_payload1, headers=headers, timeout=30
                    )
                    logger.info(
                        f"Alternative payload 1 response status: {alt_response1.status_code}"
                    )
                    if alt_response1.status_code in [200, 201]:
                        logger.info(f"✓ Email sent successfully with alternative payload format 1")
                        return True

                    # Try alternative format 2: endpoint with /send suffix
                    logger.warning(
                        "Alternative payload 1 failed, trying endpoint with /send suffix..."
                    )
                    send_url_alt = (
                        f"{ZOHO_MAIL_API_BASE}/accounts/{settings.ZOHO_ACCOUNT_ID}/messages/send"
                    )
                    logger.info(f"Trying endpoint: {send_url_alt} with original payload")
                    send_response = requests.post(
                        send_url_alt, json=payload, headers=headers, timeout=30
                    )
                    logger.info(f"Send endpoint response status: {send_response.status_code}")
                    if send_response.status_code in [200, 201]:
                        logger.info(f"✓ Email sent successfully with /send endpoint")
                        return True

                    # Try alternative format 3: different field structure
                    logger.warning(
                        "Trying alternative payload format 3 with different structure..."
                    )
                    alt_payload3 = {
                        "fromAddress": settings.FROM_EMAIL,
                        "toAddress": [to_email],  # Array format for toAddress
                        "subject": subject,
                        "content": body,
                        "mailFormat": "plaintext",
                    }
                    alt_response3 = requests.post(
                        send_url, json=alt_payload3, headers=headers, timeout=30
                    )
                    logger.info(
                        f"Alternative payload 3 response status: {alt_response3.status_code}"
                    )
                    if alt_response3.status_code in [200, 201]:
                        logger.info(f"✓ Email sent successfully with alternative payload format 3")
                        return True
            except:
                logger.error("Error response is not JSON")

            # If token expired, clear cache and retry once
            if response.status_code == 401:
                logger.warning(
                    "Access token may have expired (401), clearing cache and retrying..."
                )
                global _access_token_cache, _token_expires_at
                _access_token_cache = None
                _token_expires_at = None
                # Retry once with new token
                logger.info("Retrying with new access token...")
                access_token = get_zoho_access_token()
                if access_token:
                    headers["Authorization"] = f"Zoho-oauthtoken {access_token}"
                    logger.info("Retrying email send with new token...")
                    retry_response = requests.post(
                        send_url, json=payload, headers=headers, timeout=30
                    )
                    logger.info(f"Retry response status: {retry_response.status_code}")
                    logger.debug(f"Retry response text: {retry_response.text}")
                    if retry_response.status_code in [200, 201]:
                        logger.info(f"✓ Email sent successfully on retry to {to_email}")
                        return True
                    else:
                        logger.error(
                            f"✗ Retry also failed: {retry_response.status_code} - {retry_response.text}"
                        )
                else:
                    logger.error("Failed to get new access token for retry")
            return False

    except requests.exceptions.Timeout as e:
        logger.error(f"✗ Timeout error sending email to {to_email}: {e}", exc_info=True)
        return False
    except requests.exceptions.ConnectionError as e:
        logger.error(f"✗ Connection error sending email to {to_email}: {e}", exc_info=True)
        return False
    except requests.exceptions.RequestException as e:
        logger.error(f"✗ Network error sending email to {to_email}: {e}", exc_info=True)
        return False
    except Exception as e:
        logger.error(f"✗ Unexpected error sending email to {to_email}: {e}", exc_info=True)
        return False
    finally:
        logger.info(f"=== Email send process completed ===")


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
        "complete_oauth_registration": "Registration Verification Code",
        "verification": "Verification Code",
    }

    purpose_messages = {
        "forgot_password": f"Your password reset code is: {code}. This code will expire in 10 minutes.",
        "change_password": f"Your password change verification code is: {code}. This code will expire in 10 minutes.",
        "finish_registration": f"Your registration verification code is: {code}. This code will expire in 10 minutes.",
        "complete_oauth_registration": f"Your registration verification code is: {code}. This code will expire in 10 minutes.",
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
