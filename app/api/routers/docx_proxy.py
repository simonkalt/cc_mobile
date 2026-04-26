"""
Proxy selected Syncfusion (.NET) docx service endpoints through the FastAPI API host.

This exists primarily for **web** clients: browsers cannot rely on third-party CORS for
multipart uploads to another origin. Native apps can still call the docx service directly.

Upstream base URL: ``settings.DOCX_SERVICE_BASE_URL`` (see ``app/core/config.py``).
"""

from __future__ import annotations

import logging
from typing import Any, Dict

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status
from fastapi.responses import JSONResponse

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


@router.post("/docx-to-pdf")
async def proxy_docx_to_pdf(request: Request, file: UploadFile = File(...)) -> JSONResponse:
    """
    Multipart proxy: forwards the uploaded ``file`` field to the upstream
    ``POST {DOCX_SERVICE_BASE_URL}/api/pdf/docx-to-pdf`` and returns the JSON body.
    """
    upstream = f"{_upstream_base()}/api/pdf/docx-to-pdf"
    # Do not forward browser headers (especially Authorization / cookies / content-type).
    # The upstream .NET endpoint expects a simple multipart upload; forwarding client auth
    # headers can cause confusing failures.
    headers: Dict[str, str] = {
        "accept": "application/json",
    }

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

    raw_text = ""
    try:
        raw_text = resp.text
    except Exception:
        raw_text = ""

    payload: Any
    try:
        payload = resp.json()
    except Exception:
        # If upstream isn't JSON, don't forward opaque bytes to browsers/clients.
        snippet = (raw_text or "")[:2000]
        if not snippet:
            try:
                snippet = resp.content[:2000].decode("utf-8", errors="replace")
            except Exception:
                snippet = ""

        logger.error(
            "Upstream docx-to-pdf returned non-JSON (http=%s, content-type=%r, bytes=%s): %r",
            resp.status_code,
            resp.headers.get("content-type"),
            len(resp.content or b""),
            snippet[:500],
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={
                "message": "Upstream docx service returned a non-JSON response to docx-to-pdf",
                "upstream_status": resp.status_code,
                "upstream_content_type": resp.headers.get("content-type"),
                "upstream_url": upstream,
                "snippet": snippet,
            },
        ) from None

    if resp.status_code >= 400:
        logger.warning(
            "Upstream docx-to-pdf returned HTTP %s: %s",
            resp.status_code,
            (raw_text or "")[:2000],
        )

    return JSONResponse(status_code=resp.status_code, content=payload)
