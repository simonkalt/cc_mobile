"""
Service for storing Telnyx webhook payloads in the MongoDB sms collection.
"""
import logging
from datetime import datetime
from typing import Any, Dict, Optional

from app.db.mongodb import get_collection, is_connected

SMS_COLLECTION_NAME = "sms"
logger = logging.getLogger(__name__)


def store_telnyx_message(webhook_body: Dict[str, Any]) -> Optional[str]:
    """
    Store a Telnyx webhook payload in the MongoDB "sms" collection.

    Expects the raw JSON body from Telnyx (data + meta). Normalizes and stores
    event_type, event_id, occurred_at, full payload, and meta, plus created_at.

    Args:
        webhook_body: Raw webhook JSON, e.g. {"data": {...}, "meta": {...}}

    Returns:
        The inserted document's _id as string, or None if DB unavailable.
    """
    if not is_connected():
        logger.error("MongoDB not connected; cannot store Telnyx message")
        return None

    coll = get_collection(SMS_COLLECTION_NAME)
    if coll is None:
        logger.error("Could not get sms collection")
        return None

    data = webhook_body.get("data") or {}
    payload = data.get("payload") or {}
    meta = webhook_body.get("meta") or {}

    from_phone = None
    if isinstance(payload.get("from"), dict):
        from_phone = payload["from"].get("phone_number")

    doc = {
        "event_type": data.get("event_type"),
        "event_id": data.get("id"),
        "occurred_at": data.get("occurred_at"),
        "message_id": payload.get("id"),
        "direction": payload.get("direction"),
        "from_phone": from_phone,
        "to": payload.get("to"),  # list of {phone_number, status, ...}
        "text": payload.get("text"),
        "message_type": payload.get("type"),  # SMS | MMS
        "media": payload.get("media") or [],
        "errors": payload.get("errors") or [],
        "payload": payload,
        "meta": meta,
        "created_at": datetime.utcnow(),
    }

    try:
        result = coll.insert_one(doc)
        inserted_id = str(result.inserted_id)
        logger.info(
            "Stored Telnyx event %s (%s) as %s",
            data.get("event_type"),
            data.get("id"),
            inserted_id,
        )
        return inserted_id
    except Exception as e:
        logger.exception("Failed to store Telnyx message: %s", e)
        raise
