"""
Proxy selected Syncfusion (.NET) docx service endpoints through the FastAPI API host.

This exists primarily for **web** clients: browsers cannot rely on third-party CORS for
multipart uploads to another origin. Native apps can still call the docx service directly.

Upstream base URL: ``settings.DOCX_SERVICE_BASE_URL`` (see ``app/core/config.py``).
"""

from __future__ import annotations

import logging
from typing import Dict

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pdf", tags=["docx-proxy"])


def _upstream_base() -> str:
    base = (settings.DOCX_SERVICE_BASE_URL or "").strip().rstrip("/")
    if not base:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="DOCX_SERVICE_BASE_URL is not configured on the API server.",
        )
    return base


def _forward_headers_from_request(request: Request) -> Dict[str, str]:
    hop_by_hop = {
        "host",
        "connection",
        "content-length",
        "transfer-encoding",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "upgrade",
    }
    out: Dict[str, str] = {}
    for key, value in request.headers.items():
        lk = key.lower()
        if lk in hop_by_hop:
            continue
        out[key] = value
    return out


@router.post("/docx-to-pdf")
async def proxy_docx_to_pdf(request: Request, file: UploadFile = File(...)) -> Response:
    """
    Multipart proxy: forwards the uploaded ``file`` field to the upstream
    ``POST {DOCX_SERVICE_BASE_URL}/api/pdf/docx-to-pdf`` and returns the JSON body.
    """
    upstream = f"{_upstream_base()}/api/pdf/docx-to-pdf"
    headers = _forward_headers_from_request(request)

    try:
        file_bytes = await file.read()
    except Exception as exc:  # pragma: no cover
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to read uploaded file: {exc}",
        ) from exc

    files = {
        "file": (
            file.filename or "upload.docx",
            file_bytes,
            file.content_type
            or "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
    }

    timeout = httpx.Timeout(120.0, connect=30.0)
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.post(upstream, headers=headers, files=files)
    except httpx.RequestError as exc:
        logger.warning("Upstream docx-to-pdf request failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream docx service unreachable: {exc}",
        ) from exc

    if resp.status_code >= 400:
        logger.warning(
            "Upstream docx-to-pdf returned HTTP %s: %s",
            resp.status_code,
            (resp.text or "")[:2000],
        )

    content_type = resp.headers.get("content-type") or "application/json"
    cache_control = resp.headers.get("cache-control")
    response_headers = {}
    if cache_control:
        response_headers["cache-control"] = cache_control

    return Response(
        status_code=resp.status_code,
        content=resp.content,
        media_type=content_type,
        headers=response_headers,
    )
