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

DEFAULT_TERMS_S3_BUCKET = "custom-cover-user-resumes"
DEFAULT_TERMS_S3_KEY = "policy/sAImon Software - Terms of Service.md"
DEFAULT_TERMS_PDF_KEY = "policy/sAImon Software - Terms of Service.pdf"


def _parse_s3_uri(uri: str) -> tuple[str, str]:
    path_wo_scheme = uri[5:] if uri.startswith("s3://") else uri
    parts = path_wo_scheme.split("/", 1)
    if len(parts) != 2:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return parts[0], parts[1]


def resolve_terms_markdown_s3_uri() -> str:
    """S3 URI for ToS markdown — honors TERMS_OF_SERVICE_S3_URI, else AWS_S3_BUCKET + key."""
    explicit = (settings.TERMS_OF_SERVICE_S3_URI or "").strip()
    if explicit:
        return explicit
    bucket = (settings.AWS_S3_BUCKET or "").strip() or DEFAULT_TERMS_S3_BUCKET
    key = (settings.TERMS_OF_SERVICE_S3_KEY or "").strip() or DEFAULT_TERMS_S3_KEY
    return f"s3://{bucket}/{key}"


def resolve_terms_pdf_s3_uri() -> str:
    """S3 URI for optional ToS PDF (?format=pdf)."""
    explicit = (settings.TERMS_OF_SERVICE_PDF_S3_URI or "").strip()
    if explicit:
        return explicit
    bucket = (settings.AWS_S3_BUCKET or "").strip() or DEFAULT_TERMS_S3_BUCKET
    key = (settings.TERMS_OF_SERVICE_PDF_S3_KEY or "").strip() or DEFAULT_TERMS_PDF_KEY
    return f"s3://{bucket}/{key}"


def _load_terms_markdown_from_s3(uri: str) -> Optional[str]:
    if not S3_AVAILABLE:
        logger.warning("Terms of Service: boto3 unavailable; skipping S3")
        return None
    bucket_name, object_key = _parse_s3_uri(uri)
    try:
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        text = response["Body"].read().decode("utf-8")
        if text.strip():
            logger.info(
                "Terms of Service loaded from S3 bucket=%s key=%s (%s bytes)",
                bucket_name,
                object_key,
                len(text.encode("utf-8")),
            )
            return text
        logger.warning(
            "Terms of Service object is empty in S3 bucket=%s key=%s",
            bucket_name,
            object_key,
        )
        return None
    except ClientError as e:
        code = e.response.get("Error", {}).get("Code", "Unknown")
        if code in {"NoSuchKey", "404"}:
            logger.warning(
                "Terms of Service markdown missing in S3 bucket=%s key=%s",
                bucket_name,
                object_key,
            )
            return None
        logger.error(
            "Terms of Service S3 ClientError bucket=%s key=%s code=%s",
            bucket_name,
            object_key,
            code,
        )
        raise
    except Exception as e:
        err = str(e).lower()
        if (
            "credentials" in err
            or "proxy" in err
            or "timed out" in err
            or "connection refused" in err
        ):
            logger.warning(
                "Terms of Service S3 unavailable bucket=%s key=%s: %s",
                bucket_name,
                object_key,
                e,
            )
            return None
        raise


def _load_terms_markdown_from_file(path: Path) -> Optional[str]:
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        if text.strip():
            return text
        return None
    except OSError as e:
        logger.warning("Could not read Terms of Service file %s: %s", path, e)
        return None


def load_terms_of_service_markdown() -> str:
    """
    Return Terms of Service markdown text.

    Order: S3 (resolve_terms_markdown_s3_uri) → local file (TERMS_OF_SERVICE_MD_PATH).
    """
    s3_uri = resolve_terms_markdown_s3_uri()
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
        detail=(
            "Terms of Service file not found in S3 or on disk. "
            f"Expected S3 object: {s3_uri}"
        ),
    )
