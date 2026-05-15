"""
MongoDB-backed subscription product catalog (remote config).

iOS / Apple SKUs and Stripe price IDs in ``subscription_product_catalog`` — planKey, rank, labels.
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

# Apple catalog cache
_cached_doc: Optional[Dict[str, Any]] = None
_cached_key: Optional[str] = None
_cached_expiry: float = 0.0

# Stripe catalog cache
_stripe_cached_doc: Optional[Dict[str, Any]] = None
_stripe_cached_expiry: float = 0.0


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
    """Clear in-memory Apple catalog cache (tests)."""
    global _cached_doc, _cached_key, _cached_expiry
    _cached_doc = None
    _cached_key = None
    _cached_expiry = 0.0


def invalidate_stripe_catalog_cache() -> None:
    """Clear in-memory Stripe catalog cache (tests)."""
    global _stripe_cached_doc, _stripe_cached_expiry
    _stripe_cached_doc = None
    _stripe_cached_expiry = 0.0


def invalidate_all_catalog_caches() -> None:
    """Clear all in-memory catalog caches (tests)."""
    invalidate_ios_apple_catalog_cache()
    invalidate_stripe_catalog_cache()


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

    Prefer **enabled** products; if the SKU is present only on a disabled row, still resolve
    rank/key so existing subscribers keep tier UX consistent with the catalog document.
    """
    if not sku or not str(sku).strip():
        return None, None
    doc = get_ios_apple_catalog_document()
    if not doc:
        return None, None
    sku_norm = str(sku).strip()
    products = [p for p in (doc.get("products") or []) if isinstance(p, dict)]

    def _row_match(enabled_only: bool) -> Tuple[Optional[str], Optional[int]]:
        for p in products:
            if enabled_only and p.get("enabled") is False:
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

    plan_key, rank = _row_match(True)
    if plan_key is not None or rank is not None:
        return plan_key, rank
    return _row_match(False)


# ---------------------------------------------------------------------------
# Stripe catalog
# ---------------------------------------------------------------------------


def get_stripe_catalog_document(*, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
    """
    Load the catalog document for ``billingProvider=stripe``.

    Stripe plans are platform-agnostic, so the document uses ``platform: "all"``.
    Falls back to any document with ``billingProvider: "stripe"`` if the canonical
    key is missing.
    """
    global _stripe_cached_doc, _stripe_cached_expiry

    now = time.monotonic()
    if (
        not force_refresh
        and _stripe_cached_doc is not None
        and now < _stripe_cached_expiry
    ):
        return _stripe_cached_doc

    if not is_connected():
        logger.debug("subscription_product_catalog: MongoDB not connected (stripe)")
        return None

    coll = get_collection(catalog_collection_name())
    if coll is None:
        return None

    doc = coll.find_one({"platform": "all", "billingProvider": "stripe"})
    if doc is None:
        doc = coll.find_one({"billingProvider": "stripe"})

    _stripe_cached_doc = doc
    _stripe_cached_expiry = now + _CACHE_TTL_SEC
    return doc


def _parse_env_stripe_plan_map() -> Dict[str, str]:
    """Parse ``STRIPE_PRICE_PLAN_MAP_JSON`` env var: ``{ "price_xxx": "monthly" }``."""
    raw = settings.STRIPE_PRICE_PLAN_MAP_JSON
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError as e:
        logger.warning("STRIPE_PRICE_PLAN_MAP_JSON is not valid JSON: %s", e)
    return {}


def _mongo_stripe_price_to_plan_key_map() -> Dict[str, str]:
    """Build priceId -> planKey from the Stripe catalog document (enabled products only)."""
    doc = get_stripe_catalog_document()
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


def merged_stripe_price_plan_map() -> Dict[str, str]:
    """
    Stripe price ID -> planKey.

    Mongo catalog overrides ``STRIPE_PRICE_PLAN_MAP_JSON`` for the same price ID.
    """
    env_map = _parse_env_stripe_plan_map()
    mongo_map = _mongo_stripe_price_to_plan_key_map()
    merged = dict(env_map)
    merged.update(mongo_map)
    return merged


def resolve_stripe_product(
    price_id: Optional[str],
) -> Tuple[Optional[str], Optional[int]]:
    """
    Return ``(planKey, rank)`` for a Stripe price ID using the catalog.

    Checks Mongo catalog first, then env-var fallback (env gives planKey but no rank).
    Unknown price ID or missing catalog returns ``(None, None)``.
    """
    if not price_id or not str(price_id).strip():
        return None, None
    price_norm = str(price_id).strip()

    doc = get_stripe_catalog_document()
    if doc:
        for p in doc.get("products") or []:
            if not isinstance(p, dict):
                continue
            if p.get("enabled") is False:
                continue
            if str(p.get("productId") or "").strip() != price_norm:
                continue
            pk = p.get("planKey")
            rk = p.get("rank")
            rank_int: Optional[int]
            try:
                rank_int = int(rk) if rk is not None else None
            except (TypeError, ValueError):
                rank_int = None
            return (str(pk) if pk is not None else None, rank_int)

    # Env-var fallback (no rank available)
    env_map = _parse_env_stripe_plan_map()
    pk = env_map.get(price_norm)
    if pk:
        return pk, None

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
