"""
Admin portal API routes.

All endpoints live under /api/admin.  Auth flow (login + 2FA) is public;
CRUD endpoints require a JWT carrying the admin_verified claim.
"""

import logging
import math
import time
from datetime import datetime
from typing import Optional

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.auth import get_current_admin_user
from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.models.admin import (
    AdminLoginRequest,
    AdminLoginResponse,
    AdminResendCodeRequest,
    AdminUserDetail,
    AdminUserListResponse,
    AdminUserSummary,
    AdminUserUpdateRequest,
    AdminVerify2FARequest,
    AdminVerify2FAResponse,
)
from app.services.verification_service import (
    send_and_store_verification_code,
    send_and_store_verification_code_email,
    verify_code,
    clear_verification_code,
)
from app.utils.password import verify_password
from app.utils.user_helpers import USERS_COLLECTION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

ADMIN_TOKEN_TTL_SECONDS = 4 * 60 * 60  # 4 hours


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_admin_token(user_id: str, email: str) -> str:
    """Issue a short-lived JWT with the admin_verified claim."""
    import base64
    import hashlib
    import hmac
    import json as _json

    def _b64url(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")

    now = int(time.time())
    payload = {
        "sub": user_id,
        "email": email,
        "type": "access",
        "admin_verified": True,
        "iat": now,
        "exp": now + ADMIN_TOKEN_TTL_SECONDS,
    }
    if settings.JWT_ISSUER:
        payload["iss"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        payload["aud"] = settings.JWT_AUDIENCE

    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url(_json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(_json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    sig = hmac.new(settings.JWT_SECRET.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{header_b64}.{payload_b64}.{_b64url(sig)}"


def _require_db():
    if not is_connected():
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Database unavailable")
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Cannot access users collection")
    return collection


def _mongo_int_credit_field(doc: dict, key: str, default: int) -> int:
    """
    Read a non-negative int from Mongo for credit fields.
    Missing or null uses default. **Zero is preserved** (do not use `x or default` — 0 is valid).
    """
    if key not in doc or doc[key] is None:
        return default
    try:
        return max(0, int(doc[key]))
    except (TypeError, ValueError):
        return default


def _user_doc_to_summary(doc: dict) -> AdminUserSummary:
    return AdminUserSummary(
        id=str(doc["_id"]),
        name=doc.get("name", ""),
        email=doc.get("email", ""),
        phone=doc.get("phone"),
        isActive=doc.get("isActive", True),
        lastLogin=doc.get("lastLogin"),
        subscriptionStatus=doc.get("subscriptionStatus"),
        archived=doc.get("archived", False),
        super_user=doc.get("super_user", False),
        generation_credits=_mongo_int_credit_field(doc, "generation_credits", 10),
        max_credits=_mongo_int_credit_field(doc, "max_credits", 10),
    )


def _user_doc_to_detail(doc: dict) -> AdminUserDetail:
    return AdminUserDetail(
        id=str(doc["_id"]),
        name=doc.get("name", ""),
        email=doc.get("email", ""),
        isActive=doc.get("isActive", True),
        isEmailVerified=doc.get("isEmailVerified", False),
        roles=doc.get("roles", ["user"]),
        phone=doc.get("phone"),
        address=doc.get("address"),
        preferences=doc.get("preferences"),
        avatarUrl=doc.get("avatarUrl"),
        dateCreated=doc.get("dateCreated"),
        dateUpdated=doc.get("dateUpdated"),
        lastLogin=doc.get("lastLogin"),
        llm_counts=doc.get("llm_counts"),
        last_llm_used=doc.get("last_llm_used"),
        generation_credits=_mongo_int_credit_field(doc, "generation_credits", 10),
        max_credits=_mongo_int_credit_field(doc, "max_credits", 10),
        SMSOpt=doc.get("SMSOpt"),
        SMSOptDate=doc.get("SMSOptDate"),
        subscriptionStatus=doc.get("subscriptionStatus"),
        subscriptionPlan=doc.get("subscriptionPlan"),
        subscriptionCurrentPeriodEnd=doc.get("subscriptionCurrentPeriodEnd"),
        super_user=doc.get("super_user", False),
        archived=doc.get("archived", False),
        stripeCustomerId=doc.get("stripeCustomerId"),
    )


# ---------------------------------------------------------------------------
# Auth flow
# ---------------------------------------------------------------------------

@router.post("/login", response_model=AdminLoginResponse)
def admin_login(body: AdminLoginRequest):
    collection = _require_db()

    user = collection.find_one({"email": body.email})
    if not user:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    if not user.get("isActive", True):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is inactive")

    if not user.get("super_user"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized for admin access")

    hashed = user.get("hashedPassword", "")
    if not verify_password(body.password, hashed):
        collection.update_one({"_id": user["_id"]}, {"$inc": {"failedLoginAttempts": 1}})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password")

    collection.update_one({"_id": user["_id"]}, {"$set": {"failedLoginAttempts": 0}})

    user_id = str(user["_id"])
    delivery = (body.delivery_method or "sms").lower()

    if delivery == "email":
        send_and_store_verification_code_email(
            user_id=user_id,
            email=user.get("email", ""),
            purpose="admin_2fa",
            delivery_method="email",
        )
    else:
        phone = user.get("phone")
        if not phone:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "No phone number on file. Use email delivery instead.",
            )
        send_and_store_verification_code(user_id=user_id, phone_number=phone, purpose="admin_2fa")
        delivery = "sms"

    logger.info("Admin 2FA code sent to %s via %s", body.email, delivery)

    return AdminLoginResponse(
        requires_2fa=True,
        user_id=user_id,
        delivery_method=delivery,
        message=f"Verification code sent via {delivery}",
    )


@router.post("/verify-2fa", response_model=AdminVerify2FAResponse)
def admin_verify_2fa(body: AdminVerify2FARequest):
    collection = _require_db()

    user = collection.find_one({"_id": ObjectId(body.user_id)})
    if not user or not user.get("super_user"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    if not verify_code(body.user_id, body.code, "admin_2fa"):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired verification code")

    clear_verification_code(body.user_id)

    token = _make_admin_token(body.user_id, user.get("email", ""))
    logger.info("Admin 2FA verified for %s", user.get("email"))

    return AdminVerify2FAResponse(
        access_token=token,
        token_type="bearer",
        expires_in=ADMIN_TOKEN_TTL_SECONDS,
    )


@router.post("/resend-code")
def admin_resend_code(body: AdminResendCodeRequest):
    collection = _require_db()

    user = collection.find_one({"_id": ObjectId(body.user_id)})
    if not user or not user.get("super_user"):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not authorized")

    delivery = (body.delivery_method or "sms").lower()
    user_id = str(user["_id"])

    if delivery == "email":
        send_and_store_verification_code_email(
            user_id=user_id,
            email=user.get("email", ""),
            purpose="admin_2fa",
            delivery_method="email",
        )
    else:
        phone = user.get("phone")
        if not phone:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "No phone number on file")
        send_and_store_verification_code(user_id=user_id, phone_number=phone, purpose="admin_2fa")
        delivery = "sms"

    return {"message": f"Code resent via {delivery}"}


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

@router.get("/users", response_model=AdminUserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=1, le=100),
    sort: str = Query("name"),
    order: str = Query("asc"),
    search: Optional[str] = Query(None),
    status_filter: Optional[str] = Query(None, alias="status"),
    _admin: dict = Depends(get_current_admin_user),
):
    collection = _require_db()

    query: dict = {}

    if status_filter:
        lf = status_filter.lower()
        if lf == "archived":
            query["archived"] = True
        elif lf == "inactive":
            query["isActive"] = False
            query.setdefault("archived", {"$ne": True})
        elif lf == "active":
            query["isActive"] = True
            query["archived"] = {"$ne": True}
        else:
            query["archived"] = {"$ne": True}
    else:
        query["archived"] = {"$ne": True}

    if search:
        regex = {"$regex": search, "$options": "i"}
        query["$or"] = [{"name": regex}, {"email": regex}, {"phone": regex}]

    allowed_sort = {
        "name",
        "email",
        "phone",
        "isActive",
        "lastLogin",
        "subscriptionStatus",
        "dateCreated",
        "generation_credits",
    }
    sort_field = sort if sort in allowed_sort else "name"
    sort_dir = -1 if order.lower() == "desc" else 1

    total = collection.count_documents(query)
    pages = max(1, math.ceil(total / per_page))
    skip = (page - 1) * per_page

    cursor = collection.find(query).sort(sort_field, sort_dir).skip(skip).limit(per_page)
    users = [_user_doc_to_summary(doc) for doc in cursor]

    return AdminUserListResponse(
        users=users,
        total=total,
        page=page,
        per_page=per_page,
        pages=pages,
    )


@router.get("/users/{user_id}", response_model=AdminUserDetail)
def get_user_detail(
    user_id: str,
    _admin: dict = Depends(get_current_admin_user),
):
    collection = _require_db()
    doc = collection.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")
    return _user_doc_to_detail(doc)


@router.put("/users/{user_id}", response_model=AdminUserDetail)
def update_user(
    user_id: str,
    body: AdminUserUpdateRequest,
    _admin: dict = Depends(get_current_admin_user),
):
    collection = _require_db()

    update_fields: dict = {}
    for field, value in body.model_dump(exclude_unset=True).items():
        if value is not None:
            update_fields[field] = value

    if not update_fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No fields to update")

    update_fields["dateUpdated"] = datetime.utcnow()

    result = collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": update_fields},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    doc = collection.find_one({"_id": ObjectId(user_id)})
    logger.info("Admin updated user %s: fields=%s", user_id, list(update_fields.keys()))
    return _user_doc_to_detail(doc)


@router.put("/users/{user_id}/archive", response_model=AdminUserDetail)
def archive_user(
    user_id: str,
    _admin: dict = Depends(get_current_admin_user),
):
    collection = _require_db()

    result = collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"archived": True, "isActive": False, "dateUpdated": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    doc = collection.find_one({"_id": ObjectId(user_id)})
    logger.info("Admin archived user %s", user_id)
    return _user_doc_to_detail(doc)


@router.put("/users/{user_id}/unarchive", response_model=AdminUserDetail)
def unarchive_user(
    user_id: str,
    _admin: dict = Depends(get_current_admin_user),
):
    collection = _require_db()

    result = collection.update_one(
        {"_id": ObjectId(user_id)},
        {"$set": {"archived": False, "isActive": True, "dateUpdated": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    doc = collection.find_one({"_id": ObjectId(user_id)})
    logger.info("Admin unarchived user %s", user_id)
    return _user_doc_to_detail(doc)


@router.get("/users/{user_id}/subscription")
def get_user_subscription(
    user_id: str,
    _admin: dict = Depends(get_current_admin_user),
):
    """Return Stripe subscription details for a user."""
    collection = _require_db()
    doc = collection.find_one({"_id": ObjectId(user_id)})
    if not doc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "User not found")

    return {
        "user_id": user_id,
        "subscriptionStatus": doc.get("subscriptionStatus"),
        "subscriptionPlan": doc.get("subscriptionPlan"),
        "subscriptionCurrentPeriodEnd": doc.get("subscriptionCurrentPeriodEnd"),
        "stripeCustomerId": doc.get("stripeCustomerId"),
        "stripeSubscriptionId": doc.get("stripeSubscriptionId"),
        "cancelAtPeriodEnd": doc.get("cancelAtPeriodEnd"),
        "canceledAt": doc.get("canceledAt"),
        "priceId": doc.get("priceId"),
    }
