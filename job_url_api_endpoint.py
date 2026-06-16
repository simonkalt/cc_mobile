"""
FastAPI endpoint for job URL analysis using hybrid BeautifulSoup + Claude Haiku approach
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
import logging
import os

from job_url_analyzer import analyze_job_url, debug_fetch_job_url

logger = logging.getLogger(__name__)

router = APIRouter()

JOB_URL_DEBUG_FETCH_ENABLED = os.getenv("JOB_URL_DEBUG_FETCH", "").lower() in (
    "1",
    "true",
    "yes",
)


class JobURLRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    html_content: Optional[str] = None  # HTML content from CAPTCHA completion


class JobURLDebugFetchRequest(BaseModel):
    url: HttpUrl


@router.post("/api/job-url/debug-fetch")
async def debug_fetch_job_url_endpoint(request: JobURLDebugFetchRequest):
    """
    Fetch a job URL server-side and return HTML diagnostics (preview, auth-wall signals).

    Gated by JOB_URL_DEBUG_FETCH=true on the server. Use to see what the backend
    actually receives before BeautifulSoup / Claude Haiku run.
    """
    if not JOB_URL_DEBUG_FETCH_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Job URL debug fetch is disabled. Set JOB_URL_DEBUG_FETCH=true on the server.",
        )

    url_str = str(request.url)
    logger.info("Debug fetch job URL: %s", url_str)
    return debug_fetch_job_url(url_str)


@router.post("/api/job-url/analyze")
async def analyze_job_url_endpoint(request: JobURLRequest):
    """
    Analyze a job posting URL and extract structured information.

    Uses hybrid approach:
    1. First tries BeautifulSoup (fast, free)
    2. Falls back to Claude Haiku 4.5 if BeautifulSoup fails
    """
    try:
        # Convert HttpUrl to string
        url_str = str(request.url)

        # Call the analyzer
        result = await analyze_job_url(
            url=url_str,
            user_id=request.user_id,
            user_email=request.user_email,
            use_llm_fallback=True,
            html_content=request.html_content,
        )

        # If CAPTCHA is required, return 200 with special response (not an error)
        if result.get("captcha_required"):
            return result

        return result

    except ValueError as e:
        # Invalid URL format
        logger.warning(f"Invalid URL format: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Other errors
        logger.error(f"Failed to analyze job URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch or analyze job URL: {str(e)}"
        )
