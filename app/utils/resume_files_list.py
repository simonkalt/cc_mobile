"""
Shared S3 resume file listing — same semantics as GET /api/files/list.

Used by the files router and by login (``UserLoginResponse.files``) without importing
routes from services (avoids circular imports).
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from botocore.exceptions import ClientError

from app.core.config import settings
from app.utils.s3_utils import (
    S3_AVAILABLE,
    ensure_user_s3_folder,
    get_s3_client,
)

logger = logging.getLogger(__name__)


def _bucket_name_for_files() -> str | None:
    bucket_name = settings.AWS_S3_BUCKET
    if not bucket_name:
        bucket_name = (
            os.getenv("S3_BUCKET_URI", "").replace("s3://", "").split("/")[0] or None
        )
    return bucket_name


def list_user_resume_files_sync(user_id: str) -> List[Dict[str, Any]]:
    """
    List eligible resume files under ``{user_id}/`` in S3.

    Same filtering and sort as ``GET /api/files/list``: skips cover letters prefix,
    placeholders, subfolders; fields **key**, **name**, **size**, **lastModified**;
    **lastModified** descending.

    Raises:
        ValueError: If ``user_id`` is empty.
        ClientError: On S3 API failure (same as historic ``/list`` behavior).
    """
    if not user_id:
        raise ValueError("user_id is required")

    bucket_name = _bucket_name_for_files()
    if not bucket_name:
        raise ValueError("S3 bucket name not configured")

    ensure_user_s3_folder(user_id)
    s3_client = get_s3_client()

    prefix = f"{user_id}/"
    response = s3_client.list_objects_v2(Bucket=bucket_name, Prefix=prefix)

    files: List[Dict[str, Any]] = []
    cover_letters_prefix = f"{user_id}/generated_cover_letters/"
    if "Contents" in response:
        for obj in response["Contents"]:
            if obj["Key"].endswith("/") or obj["Key"].endswith(".folder_initialized"):
                continue
            if obj["Key"].startswith(cover_letters_prefix):
                continue
            key_after_prefix = obj["Key"][len(prefix) :]
            if "/" in key_after_prefix:
                continue
            filename = obj["Key"].replace(prefix, "")
            files.append(
                {
                    "key": obj["Key"],
                    "name": filename,
                    "size": obj["Size"],
                    "lastModified": obj["LastModified"].isoformat(),
                }
            )

    files.sort(key=lambda x: x["lastModified"], reverse=True)
    return files


def list_user_resume_files_for_login(user_id: str) -> List[Dict[str, Any]]:
    """
    Same list as ``list_user_resume_files_sync``, but returns ``[]`` if S3/client is
    unavailable or on any failure so login always succeeds with contract ``files: []``.
    """
    if not S3_AVAILABLE:
        return []
    if not user_id:
        return []
    try:
        return list_user_resume_files_sync(user_id)
    except (ClientError, ValueError, Exception) as e:
        logger.warning(
            "Could not attach resume files to login payload for user_id=%s: %s",
            user_id,
            e,
        )
        return []
