"""Persisted client-settings values served by /api/config/client-settings."""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.utils.job_share_import_sites import (
    normalize_job_share_import_sites,
    validate_job_share_import_sites_patch,
)

logger = logging.getLogger(__name__)

_CLIENT_SETTINGS_DOC_ID = "global"


def _client_settings_collection():
    if not is_connected():
        return None
    return get_collection(settings.CLIENT_SETTINGS_COLLECTION)


def get_job_share_import_sites() -> Dict[str, bool]:
    """Read toggles from MongoDB when available; otherwise return defaults."""
    coll = _client_settings_collection()
    if coll is not None:
        try:
            doc = coll.find_one({"_id": _CLIENT_SETTINGS_DOC_ID})
            if doc and isinstance(doc.get("jobShareImportSites"), dict):
                return normalize_job_share_import_sites(doc["jobShareImportSites"])
        except Exception as exc:
            logger.warning("Failed to read jobShareImportSites from MongoDB: %s", exc)
    return normalize_job_share_import_sites(None)


def patch_job_share_import_sites(partial: Dict[str, Any]) -> Dict[str, bool]:
    """Merge partial site toggles and persist (superuser PATCH)."""
    try:
        validated = validate_job_share_import_sites_patch(partial)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    coll = _client_settings_collection()
    if coll is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    merged = normalize_job_share_import_sites(
        {**get_job_share_import_sites(), **validated}
    )
    try:
        coll.update_one(
            {"_id": _CLIENT_SETTINGS_DOC_ID},
            {"$set": {"jobShareImportSites": merged}},
            upsert=True,
        )
    except Exception as exc:
        logger.error("Failed to persist jobShareImportSites: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to persist job import site settings",
        ) from exc

    return merged
