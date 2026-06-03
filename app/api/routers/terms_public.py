"""
Public Terms of Service endpoint (lightweight router).

Registered early in main.py so OAuth first-login is not blocked when the
heavy files router bundle fails to import.
"""
from __future__ import annotations

import logging
from typing import Optional

from botocore.exceptions import ClientError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from app.core.config import settings
from app.utils.s3_utils import download_pdf_from_s3
from app.utils.terms_of_service import (
    load_terms_of_service_markdown,
    resolve_terms_pdf_s3_uri,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/files", tags=["files"])


@router.get("/terms-of-service")
async def get_terms_of_service(request: Request, format: Optional[str] = None):
    """
    Terms of Service markdown (S3 primary, bundled policy/*.md fallback).
    Public; no authentication.
    """
    try:
        markdown_text = load_terms_of_service_markdown()

        requested_format = (format or "").strip().lower()
        if requested_format == "pdf":
            pdf_bytes = download_pdf_from_s3(resolve_terms_pdf_s3_uri())
            return Response(
                content=pdf_bytes,
                media_type="application/pdf",
                headers={
                    "Content-Disposition": 'inline; filename="Terms of Service.pdf"'
                },
            )

        if requested_format in {"", "md", "markdown", "text"}:
            return PlainTextResponse(
                content=markdown_text,
                media_type="text/markdown; charset=utf-8",
            )

        try:
            import markdown as mdlib

            html_content = mdlib.markdown(
                markdown_text, extensions=["extra", "tables", "sane_lists", "nl2br"]
            )
        except Exception:
            import html as htmllib

            html_content = f"<pre>{htmllib.escape(markdown_text)}</pre>"

        return HTMLResponse(
            content=(
                "<!DOCTYPE html><html><head><meta charset='utf-8'/>"
                "<title>Terms of Service</title>"
                "<style>body{font-family:Georgia,serif;max-width:980px;margin:2rem auto;"
                "padding:0 1.25rem;line-height:1.55;color:#111;}"
                "h1,h2,h3{margin:1.25rem 0 0.75rem 0;} p{margin:0 0 1rem 0;} "
                "ul,ol{margin:0 0 1rem 1.2rem;} li{margin:0.2rem 0;}"
                "</style></head><body>"
                f"{html_content}"
                "</body></html>"
            ),
            media_type="text/html",
        )

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code in {"NoCredentialsError", "AccessDenied", "RequestTimeout"}:
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again later.",
            )
        raise HTTPException(
            status_code=500,
            detail="Server error. Please try again later or contact support.",
        )
    except Exception as e:
        err = str(e).lower()
        if (
            "credentials" in err
            or "proxy" in err
            or "timed out" in err
            or "connection refused" in err
            or "service unavailable" in err
        ):
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable. Please try again later.",
            )
        raise HTTPException(
            status_code=500,
            detail="Server error. Please try again later or contact support.",
        )
