"""
Load canonical Terms of Service markdown (S3 primary, bundled file fallback).
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

from botocore.exceptions import ClientError
from fastapi import HTTPException

from app.core.config import settings
from app.utils.s3_utils import S3_AVAILABLE, get_s3_client

logger = logging.getLogger(__name__)

DEFAULT_TERMS_S3_URI = (
    "s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.md"
)


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    path_wo_scheme = uri[5:] if uri.startswith("s3://") else uri
    parts = path_wo_scheme.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parts[0], parts[1]


def _load_terms_markdown_from_s3(uri: str) -> Optional[str]:
    if not S3_AVAILABLE:
        return None
    try:
        bucket_name, object_key = _parse_s3_uri(uri)
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        text = response["Body"].read().decode("utf-8")
        return text if text.strip() else None
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        if code in {"NoSuchKey", "404"}:
            logger.warning(
                "Terms of Service markdown missing in S3 (%s); trying local fallback",
                uri,
            )
            return None
        raise
    except Exception as e:
        err = str(e).lower()
        if (
            "credentials" in err
            or "proxy" in err
            or "timed out" in err
            or "connection refused" in err
        ):
            logger.warning("Terms of Service S3 unavailable (%s): %s", uri, e)
            return None
        raise


def _load_terms_markdown_from_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        return text if text.strip() else None
    except OSError as e:
        logger.warning("Could not read Terms of Service file %s: %s", path, e)
        return None


def load_terms_of_service_markdown() -> str:
    """
    Return Terms of Service markdown text.

    Order: S3 (TERMS_OF_SERVICE_S3_URI) → local file (TERMS_OF_SERVICE_MD_PATH).
    """
    s3_uri = (settings.TERMS_OF_SERVICE_S3_URI or "").strip() or DEFAULT_TERMS_S3_URI
    local_path = settings.TERMS_OF_SERVICE_MD_PATH

    text = _load_terms_markdown_from_s3(s3_uri)
    if text:
        return text

    text = _load_terms_markdown_from_file(local_path)
    if text:
        logger.info("Serving Terms of Service from local fallback: %s", local_path)
        return text

    raise HTTPException(
        status_code=404,
        detail="Terms of Service file not found. Please contact support.",
    )
