"""
Mobile app semver and update-policy resolution (MongoDB primary, env overrides, version.json fallback).

See documentation/API_APP_UPDATE_AND_VERSION.md.
"""
from __future__ import annotations

import json
import logging
import time
from copy import deepcopy
from typing import Any, Dict, Optional

from app.core.config import settings
from app.db.mongodb import get_app_update_policy_collection, is_connected
from app.utils.shipped_app_version import (
    _coerce_int,
    default_play_store_url,
    load_shipped_version,
)

logger = logging.getLogger(__name__)

_policy_doc_cache: Optional[tuple[float, Optional[dict]]] = None


def _strip_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _fetch_policy_document_from_mongo_uncached() -> Optional[dict]:
    if not settings.MONGODB_URI or not is_connected():
        return None
    coll = get_app_update_policy_collection()
    if coll is None:
        return None

    doc_id = settings.APP_UPDATE_POLICY_DOC_ID
    if doc_id:
        try:
            from bson import ObjectId
            from bson.errors import InvalidId

            try:
                oid = ObjectId(doc_id)
            except InvalidId:
                oid = doc_id
            hit = coll.find_one({"_id": oid})
            if hit:
                return hit
        except Exception as e:
            logger.warning("app update policy: doc id lookup failed: %s", e)

    raw_filter = settings.APP_UPDATE_POLICY_DOC_FILTER_JSON
    if raw_filter:
        try:
            q = json.loads(raw_filter)
            if isinstance(q, dict):
                hit = coll.find_one(q)
                if hit:
                    return hit
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("app update policy: invalid APP_UPDATE_POLICY_DOC_FILTER_JSON: %s", e)

    for q in (
        {"min_required_version": {"$exists": True}},
        {"version": {"$exists": True}, "min_required_version": {"$exists": True}},
        {"latest_version": {"$exists": True}},
        {"version": {"$exists": True}},
    ):
        try:
            hit = coll.find_one(q)
            if hit:
                return hit
        except Exception as e:
            logger.debug("app update policy heuristic query failed: %s", e)

    return None


def get_cached_policy_document() -> Optional[dict]:
    """TTL-cached read of the canonical policy document."""
    global _policy_doc_cache
    ttl = max(0, settings.APP_UPDATE_POLICY_CACHE_TTL_SECONDS)
    now = time.monotonic()
    if ttl > 0 and _policy_doc_cache is not None:
        ts, cached = _policy_doc_cache
        if now - ts < ttl:
            return deepcopy(cached) if cached else None

    doc = _fetch_policy_document_from_mongo_uncached()
    _policy_doc_cache = (now, doc)
    return deepcopy(doc) if doc else None


def _file_shipped(path) -> Dict[str, Any]:
    return load_shipped_version(path)


def build_layer_a_payload() -> Dict[str, Any]:
    """GET /api/version body fields."""
    doc = get_cached_policy_document()
    file_data = _file_shipped(settings.VERSION_JSON_PATH)

    ver = None
    code: Optional[int] = None
    build: Optional[str] = None

    if doc:
        ver = _strip_str(doc.get("version"))
        code = _coerce_int(doc.get("android_version_code") or doc.get("androidVersionCode"))
        build = _strip_str(doc.get("build_number") or doc.get("buildNumber"))

    if not ver:
        ver = file_data.get("version")
    if code is None:
        code = file_data.get("androidVersionCode")
    if not build:
        build = file_data.get("buildNumber")

    if not ver:
        ver = settings.APP_VERSION

    return {
        "version": ver,
        "androidVersionCode": code,
        "buildNumber": build,
    }


def build_layer_b_payload() -> Dict[str, Any]:
    """GET /api/config/app-update-policy body fields."""
    doc = get_cached_policy_document()
    file_data = _file_shipped(settings.VERSION_JSON_PATH)
    file_ver = _strip_str(file_data.get("version")) or settings.APP_VERSION

    mongo_latest: Optional[str] = None
    mongo_min: Optional[str] = None
    mongo_msg: Optional[str] = None
    mongo_android: Optional[str] = None
    mongo_ios: Optional[str] = None

    if doc:
        mongo_latest = _strip_str(doc.get("latest_version")) or _strip_str(doc.get("version"))
        mongo_min = _strip_str(doc.get("min_required_version"))
        mongo_msg = _strip_str(doc.get("update_message"))
        mongo_android = _strip_str(doc.get("store_android_url") or doc.get("storeAndroidUrl"))
        mongo_ios = _strip_str(doc.get("store_ios_url") or doc.get("storeIosUrl"))

    min_v = (_strip_str(settings.APP_UPDATE_MIN_REQUIRED_VERSION) or mongo_min or "0.0.0")
    latest_v = (
        _strip_str(settings.APP_UPDATE_LATEST_VERSION)
        or mongo_latest
        or file_ver
        or settings.APP_VERSION
    )
    msg_raw = _strip_str(settings.APP_UPDATE_MESSAGE)
    if msg_raw:
        msg: Optional[str] = msg_raw
    else:
        msg = mongo_msg

    android = (
        _strip_str(settings.APP_UPDATE_STORE_ANDROID_URL)
        or mongo_android
        or default_play_store_url()
    )
    ios_raw = _strip_str(settings.APP_UPDATE_STORE_IOS_URL)
    if ios_raw:
        ios: Optional[str] = ios_raw
    else:
        ios = mongo_ios if mongo_ios else None

    return {
        "min_required_version": min_v,
        "latest_version": latest_v,
        "update_message": msg,
        "store_android_url": android,
        "store_ios_url": ios,
    }
