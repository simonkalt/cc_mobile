"""
FastAPI endpoint for job URL analysis using hybrid BeautifulSoup + Grok approach

This endpoint integrates the job_url_analyzer module into a FastAPI route.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, HttpUrl
from typing import Optional
import logging

from job_url_analyzer import analyze_job_url

logger = logging.getLogger(__name__)

router = APIRouter()


class JobURLRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = None
    user_email: Optional[str] = None


@router.post("/api/job-url/analyze")
async def analyze_job_url_endpoint(request: JobURLRequest):
    """
    Analyze a job posting URL and extract structured information.

    Uses hybrid approach:
    1. First tries BeautifulSoup (fast, free)
    2. Falls back to ChatGPT AI if BeautifulSoup fails
    """
    try:
        # Convert HttpUrl to string
        url_str = str(request.url)

        # Call the analyzer
        result = await analyze_job_url(
            url=url_str,
            user_id=request.user_id,
            user_email=request.user_email,
            use_chatgpt_fallback=True,  # Enable ChatGPT fallback
        )

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
