"""
Job URL analysis API routes
"""
import logging
import os

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional

from app.models.job import JobURLAnalysisRequest

try:
    from job_url_analyzer import analyze_job_url, debug_fetch_job_url

    JOB_URL_ANALYZER_AVAILABLE = True
except ImportError:
    JOB_URL_ANALYZER_AVAILABLE = False
    logging.warning("job_url_analyzer module not available")

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/job-url", tags=["job-url"])

JOB_URL_DEBUG_FETCH_ENABLED = os.getenv("JOB_URL_DEBUG_FETCH", "").lower() in (
    "1",
    "true",
    "yes",
)


class JobURLDebugFetchRequest(BaseModel):
    url: HttpUrl


@router.post("/debug-fetch")
async def debug_fetch_job_url_endpoint(request: JobURLDebugFetchRequest):
    """
    Fetch a job URL server-side and return HTML diagnostics (preview, auth-wall signals).

    Gated by JOB_URL_DEBUG_FETCH=true on the server.
    """
    if not JOB_URL_ANALYZER_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Job URL analyzer module not available",
        )
    if not JOB_URL_DEBUG_FETCH_ENABLED:
        raise HTTPException(
            status_code=403,
            detail="Job URL debug fetch is disabled. Set JOB_URL_DEBUG_FETCH=true on the server.",
        )

    url_str = str(request.url)
    logger.info("Debug fetch job URL: %s", url_str)
    return debug_fetch_job_url(url_str)


@router.post("/analyze")
async def analyze_job_url_endpoint(request: JobURLAnalysisRequest):
    """
    Analyze a job posting URL and extract structured information.

    Uses hybrid approach:
    1. First tries BeautifulSoup (fast, free)
    2. Falls back to Claude Haiku 4.5 if BeautifulSoup fails
    """
    if not JOB_URL_ANALYZER_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="Job URL analyzer module not available",
        )

    try:
        url_str = str(request.url)

        result = await analyze_job_url(
            url=url_str,
            user_id=request.user_id,
            user_email=request.user_email,
            use_llm_fallback=True,
            html_content=request.html_content,
        )

        if result.get("captcha_required"):
            return result

        return result

    except ValueError as e:
        logger.warning(f"Invalid URL format: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        logger.error(f"Failed to analyze job URL: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch or analyze job URL: {str(e)}"
        )
