"""
MongoDB-backed subscription product catalog (remote config).

Phase 1: iOS / Apple SKUs in ``subscription_product_catalog`` — planKey, rank, labels.
See documentation/BILLING_MONGODB_SCHEMA.md and BILLING_API_CONTRACT.md.
"""

from __future__ import annotations

import json
import logging
import time
from typing import Any, Dict, List, Optional, Tuple

from app.core.config import settings
from app.db.mongodb import get_collection, is_connected

logger = logging.getLogger(__name__)

_CACHE_TTL_SEC = 60.0
_cached_doc: Optional[Dict[str, Any]] = None
_cached_key: Optional[str] = None
_cached_expiry: float = 0.0


def catalog_collection_name() -> str:
    return (settings.MONGODB_SUBSCRIPTION_PRODUCT_CATALOG_COLLECTION or "").strip() or (
        "subscription_product_catalog"
    )


def _catalog_environment_for_apple() -> str:
    """Align catalog ``environment`` with App Store verification mode."""
    return "sandbox" if settings.APP_STORE_USE_SANDBOX else "production"


def ios_apple_catalog_environment_label() -> str:
    """Public alias for API responses (``sandbox`` | ``production``)."""
    return _catalog_environment_for_apple()


def invalidate_ios_apple_catalog_cache() -> None:
    """Clear in-memory catalog cache (tests)."""
    global _cached_doc, _cached_key, _cached_expiry
    _cached_doc = None
    _cached_key = None
    _cached_expiry = 0.0


def get_ios_apple_catalog_document(*, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Load the catalog document for ``platform=ios``, ``billingProvider=apple``.

    Selects ``environment`` from ``APP_STORE_USE_SANDBOX`` (sandbox vs production).
    If sandbox doc is missing, falls back to production (same SKUs in App Store Connect).
    """
    global _cached_doc, _cached_key, _cached_expiry

    env = _catalog_environment_for_apple()
    cache_key = f"ios:apple:{env}"
    now = time.monotonic()
    if (
        not force_refresh
        and _cached_key == cache_key
        and _cached_doc is not None
        and now < _cached_expiry
    ):
        return _cached_doc

    if not is_connected():
        logger.debug("subscription_product_catalog: MongoDB not connected")
        return None

    coll = get_collection(catalog_collection_name())
    if coll is None:
        return None

    doc = coll.find_one(
        {"platform": "ios", "billingProvider": "apple", "environment": env}
    )
    if doc is None and env == "sandbox":
        doc = coll.find_one(
            {"platform": "ios", "billingProvider": "apple", "environment": "production"}
        )
    if doc is None:
        doc = coll.find_one(
            {"platform": "ios", "billingProvider": "apple", "environment": "production"}
        )

    _cached_doc = doc
    _cached_key = cache_key
    _cached_expiry = now + _CACHE_TTL_SEC
    return doc


def _parse_env_product_plan_map() -> Dict[str, str]:
    """Same semantics as legacy ``APP_STORE_PRODUCT_PLAN_MAP_JSON``."""
    raw = settings.APP_STORE_PRODUCT_PLAN_MAP_JSON
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError as e:
        logger.warning("APP_STORE_PRODUCT_PLAN_MAP_JSON is not valid JSON: %s", e)
    return {}


def mongo_ios_apple_sku_to_plan_key_map() -> Dict[str, str]:
    """Build SKU -> planKey from the current iOS/Apple catalog document (enabled products only)."""
    doc = get_ios_apple_catalog_document()
    if not doc:
        return {}
    out: Dict[str, str] = {}
    for p in doc.get("products") or []:
        if not isinstance(p, dict):
            continue
        if p.get("enabled") is False:
            continue
        pid = p.get("productId")
        pk = p.get("planKey")
        if pid and pk:
            out[str(pid).strip()] = str(pk).strip()
    return out


def merged_apple_product_plan_map() -> Dict[str, str]:
    """
    SKU -> subscriptionPlan string for Apple verify / ASSN.

    Mongo catalog overrides ``APP_STORE_PRODUCT_PLAN_MAP_JSON`` for the same SKU.
    """
    env_map = _parse_env_product_plan_map()
    mongo_map = mongo_ios_apple_sku_to_plan_key_map()
    merged = dict(env_map)
    merged.update(mongo_map)
    return merged


def resolve_ios_apple_product(
    sku: Optional[str],
) -> Tuple[Optional[str], Optional[int]]:
    """
    Return (planKey, rank) for an App Store product id using the Mongo catalog.

    Unknown SKU or missing catalog returns (None, None).
    """
    if not sku or not str(sku).strip():
        return None, None
    doc = get_ios_apple_catalog_document()
    if not doc:
        return None, None
    sku_norm = str(sku).strip()
    for p in doc.get("products") or []:
        if not isinstance(p, dict):
            continue
        if p.get("enabled") is False:
            continue
        if str(p.get("productId") or "").strip() != sku_norm:
            continue
        pk = p.get("planKey")
        rk = p.get("rank")
        rank_int: Optional[int]
        try:
            rank_int = int(rk) if rk is not None else None
        except (TypeError, ValueError):
            rank_int = None
        return (str(pk) if pk is not None else None, rank_int)
    return None, None


def list_ios_apple_catalog_products() -> List[Dict[str, Any]]:
    """
    Products for ``GET /api/subscriptions/apple/catalog``, sorted by ``rank`` then ``productId``.
    Each item: productId, planKey, rank, enabled, label (optional).
    """
    doc = get_ios_apple_catalog_document()
    if not doc:
        return []
    raw = [p for p in (doc.get("products") or []) if isinstance(p, dict)]
    items = [p for p in raw if p.get("enabled") is not False]
    try:
        items.sort(
            key=lambda x: (
                int(x.get("rank") if x.get("rank") is not None else 999),
                str(x.get("productId") or ""),
            )
        )
    except (TypeError, ValueError):
        items.sort(key=lambda x: str(x.get("productId") or ""))
    out: List[Dict[str, Any]] = []
    for p in items:
        entry: Dict[str, Any] = {
            "productId": p.get("productId"),
            "planKey": p.get("planKey"),
            "rank": p.get("rank"),
            "enabled": p.get("enabled", True),
        }
        if p.get("label") is not None:
            entry["label"] = p.get("label")
        out.append(entry)
    return out
