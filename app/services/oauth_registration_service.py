"""
Complete OAuth sign-up with the same legal steps as email registration
(terms, verification code, phone, SMS consent).
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Literal, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_collection, is_connected
from app.services.verification_service import (
    send_and_store_verification_code_email,
    verify_code,
)
from app.utils.user_helpers import user_doc_to_response

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"
OAUTH_REGISTRATION_PURPOSE = "complete_oauth_registration"


def _users_collection():
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection",
        )
    return collection


def _oauth_registration_needs_completion(user_doc: dict) -> bool:
    if user_doc.get("oauthRegistrationPending"):
        return True
    providers = user_doc.get("authProviders") or []
    has_oauth = any(
        isinstance(p, dict) and p.get("provider") in ("google", "linkedin")
        for p in providers
    )
    if not has_oauth:
        return False
    if not user_doc.get("termsOfServiceAcceptedAt"):
        return True
    if user_doc.get("isEmailVerified") is False:
        return True
    return False


def _load_pending_oauth_user(user_id: str) -> dict:
    collection = _users_collection()
    try:
        user_oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID",
        ) from exc

    user_doc = collection.find_one({"_id": user_oid})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    if not _oauth_registration_needs_completion(user_doc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OAuth registration is not pending for this account",
        )
    if not user_doc.get("oauthRegistrationPending"):
        collection.update_one(
            {"_id": user_oid},
            {"$set": {"oauthRegistrationPending": True}},
        )
        user_doc = collection.find_one({"_id": user_oid}) or user_doc
    return user_doc


def send_oauth_registration_verification_code(
    user_id: str,
    *,
    delivery_method: Literal["email", "sms"] = "email",
    phone: Optional[str] = None,
) -> dict:
    user_doc = _load_pending_oauth_user(user_id)
    email = (user_doc.get("email") or "").strip()
    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User email is required to send a verification code",
        )

    registration_data = None
    if delivery_method == "sms":
        if not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is required for SMS verification",
            )
        registration_data = {
            "email": email,
            "phone": phone,
            "name": user_doc.get("name") or "",
            "dataUseSharingNoticeAccepted": True,
        }

    from app.services.verification_service import (
        _verification_email_delivery_fail_open,
    )

    send_and_store_verification_code_email(
        user_id=user_id,
        email=email,
        purpose=OAUTH_REGISTRATION_PURPOSE,
        registration_data=registration_data,
        delivery_method=delivery_method,
    )
    logger.info(
        "OAuth registration verification sent user_id=%s method=%s",
        user_id,
        delivery_method,
    )
    result = {
        "success": True,
        "message": "Verification code sent successfully",
    }
    if delivery_method == "email" and _verification_email_delivery_fail_open():
        result["emailDeliveryWarning"] = (
            "Email delivery may be unavailable in this environment. "
            "If you do not receive a message, check server logs or try resend."
        )
    return result


def complete_oauth_registration(
    user_id: str,
    *,
    code: str,
    terms_of_service_accepted: bool,
    phone: str,
    sms_opt_in: bool,
    delivery_method: Literal["email", "sms"] = "email",
) -> dict:
    if not terms_of_service_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the Terms of Service to complete registration",
        )

    phone_normalized = (phone or "").strip()
    if not phone_normalized:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Phone number is required to complete registration",
        )

    user_doc = _load_pending_oauth_user(user_id)
    if not verify_code(user_id, code.strip(), OAUTH_REGISTRATION_PURPOSE):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code",
        )

    now = datetime.now(UTC)
    sms_opt_value = "IN" if sms_opt_in else "OUT"

    collection = _users_collection()
    collection.update_one(
        {"_id": user_doc["_id"]},
        {
            "$set": {
                "oauthRegistrationPending": False,
                "isEmailVerified": True,
                "termsOfServiceAcceptedAt": now,
                "phone": phone_normalized,
                "SMSOpt": sms_opt_value,
                "SMSOptDate": now,
                "dateUpdated": now,
            }
        },
    )

    updated = collection.find_one({"_id": user_doc["_id"]})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user after completing registration",
        )

    logger.info("OAuth registration completed for user_id=%s", user_id)
    return user_doc_to_response(updated)


def accept_user_terms(
    user_id: str,
    *,
    terms_of_service_accepted: bool,
    provider: Optional[str] = None,
) -> dict:
    """Persist Terms of Service acceptance (e.g. after social sign-in link)."""
    if not terms_of_service_accepted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You must accept the Terms of Service",
        )

    collection = _users_collection()
    try:
        user_oid = ObjectId(user_id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID",
        ) from exc

    user_doc = collection.find_one({"_id": user_oid})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    now = datetime.now(UTC)
    update_doc: dict = {
        "termsOfServiceAcceptedAt": now,
        "dateUpdated": now,
    }
    if user_doc.get("isEmailVerified") is False and not user_doc.get(
        "oauthRegistrationPending"
    ):
        update_doc["isEmailVerified"] = True

    collection.update_one({"_id": user_oid}, {"$set": update_doc})
    updated = collection.find_one({"_id": user_oid})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user after accepting terms",
        )

    if provider:
        logger.info(
            "Terms accepted provider=%s user_id=%s email=%s",
            provider,
            user_id,
            updated.get("email"),
        )
    else:
        logger.info("Terms accepted user_id=%s", user_id)

    return user_doc_to_response(updated)
