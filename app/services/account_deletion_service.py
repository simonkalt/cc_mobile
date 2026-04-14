"""
Self-service account deletion requests (deferred deletion, audit, confirmation email).
See documents/ACCOUNT_DELETION_API.md.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.db.mongodb import get_collection, is_connected
from app.utils.email_utils import send_email
from app.utils.user_helpers import ACCOUNT_DELETION_REQUESTS_COLLECTION, USERS_COLLECTION

logger = logging.getLogger(__name__)

DELETION_GRACE_DAYS = 30
SUPPORT_EMAIL = "support@saimonsoft.com"


def _scheduled_completion_utc() -> datetime:
    return datetime.utcnow() + timedelta(days=DELETION_GRACE_DAYS)


def _format_scheduled_iso(dt: datetime) -> str:
    if dt.tzinfo is not None:
        dt = dt.replace(tzinfo=None)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _sync_user_document_for_pending_deletion(
    users_col,
    oid: ObjectId,
    now: datetime,
    *,
    auth_invalidated_before: Optional[int] = None,
) -> None:
    """
    Ensure the users collection row reflects a pending self-service deletion.

    When a pending request already exists (idempotent retry), we still run this so
    flags stay correct if a previous deploy skipped them or a write was inconsistent.
    """
    set_doc: Dict[str, Any] = {
        "account_deletion_pending": True,
        "archived": True,
        "isActive": False,
        "dateUpdated": now,
    }
    if auth_invalidated_before is not None:
        set_doc["auth_tokens_invalidated_before"] = auth_invalidated_before
    else:
        existing = users_col.find_one(
            {"_id": oid},
            {"auth_tokens_invalidated_before": 1},
        )
        if existing and existing.get("auth_tokens_invalidated_before") is None:
            set_doc["auth_tokens_invalidated_before"] = int(time.time())

    result = users_col.update_one({"_id": oid}, {"$set": set_doc})
    if result.matched_count == 0:
        logger.error(
            "account deletion: user update matched no document (user_id=%s)",
            str(oid),
        )
    elif result.modified_count == 0 and auth_invalidated_before is not None:
        logger.debug(
            "account deletion: user flags already matched desired state (user_id=%s)",
            str(oid),
        )


def _confirmation_email_body(name: str, scheduled_iso: str) -> str:
    who = (name or "there").strip() or "there"
    return (
        f"Hello {who},\n\n"
        "We received a request to delete your sAImon Software account and associated data.\n\n"
        f"We expect processing to complete by {scheduled_iso} (within {DELETION_GRACE_DAYS} days).\n\n"
        f"If you did not request this, contact us immediately at {SUPPORT_EMAIL}.\n\n"
        "Thank you,\n"
        "sAImon Software"
    )


def create_account_deletion_request(
    user_id: str,
    user_email: str,
    user_name: str,
    *,
    source: str = "mobile_app",
    client_ip: Optional[str] = None,
    user_agent: Optional[str] = None,
    is_super_user: bool = False,
) -> Dict[str, Any]:
    """
    Record a pending deletion request, invalidate previously issued JWTs, and email the user.

    Idempotent: if a pending request already exists for this user, returns the existing record
    without sending another email or bumping token invalidation.
    """
    if is_super_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account deletion is not available for this account type.",
        )

    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    users_col = get_collection(USERS_COLLECTION)
    adr_col = get_collection(ACCOUNT_DELETION_REQUESTS_COLLECTION)
    if users_col is None or adr_col is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access database collections",
        )

    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    user_doc = users_col.find_one({"_id": oid})
    if not user_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    existing = adr_col.find_one({"user_id": oid, "status": "pending"})
    if existing:
        req_id = str(existing["_id"])
        sched = existing.get("scheduled_completion_by")
        if isinstance(sched, datetime):
            scheduled_iso = _format_scheduled_iso(sched)
        else:
            scheduled_iso = _format_scheduled_iso(_scheduled_completion_utc())
        logger.info("Duplicate account deletion request for user %s; returning pending %s", user_id, req_id)
        _sync_user_document_for_pending_deletion(
            users_col, oid, datetime.utcnow(), auth_invalidated_before=None
        )
        return {
            "message": "Account deletion is already scheduled.",
            "deletion_request_id": req_id,
            "scheduled_completion_by": scheduled_iso,
        }

    now = datetime.utcnow()
    scheduled = _scheduled_completion_utc()
    inv_boundary = int(time.time())

    ins = adr_col.insert_one(
        {
            "user_id": oid,
            "requested_at": now,
            "source": source,
            "ip": client_ip,
            "user_agent": user_agent,
            "status": "pending",
            "scheduled_completion_by": scheduled,
        }
    )
    req_id = str(ins.inserted_id)

    _sync_user_document_for_pending_deletion(
        users_col, oid, now, auth_invalidated_before=inv_boundary
    )

    body = _confirmation_email_body(user_name, _format_scheduled_iso(scheduled))
    subject = "We received your account deletion request"
    if user_email and not send_email(user_email, subject, body):
        logger.error(
            "Account deletion request %s saved for user %s but confirmation email failed to send",
            req_id,
            user_id,
        )

    logger.info("Account deletion request %s created for user %s", req_id, user_id)
    return {
        "message": "Account deletion scheduled.",
        "deletion_request_id": req_id,
        "scheduled_completion_by": _format_scheduled_iso(scheduled),
    }
