"""
Job URL analysis API routes
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.models.job import JobURLAnalysisRequest

# Import the analyzer function
try:
    from job_url_analyzer import analyze_job_url

    JOB_URL_ANALYZER_AVAILABLE = True
except ImportError:
    JOB_URL_ANALYZER_AVAILABLE = False
    logging.warning("job_url_analyzer module not available")

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/job-url", tags=["job-url"], dependencies=[Depends(get_current_user)]
)


@router.post("/analyze")
async def analyze_job_url_endpoint(request: JobURLAnalysisRequest):
    """
    Analyze a job posting URL and extract structured information.

    Uses hybrid approach:
    1. First tries BeautifulSoup (fast, free)
    2. Falls back to ChatGPT AI if BeautifulSoup fails
    """
    if not JOB_URL_ANALYZER_AVAILABLE:
        raise HTTPException(status_code=500, detail="Job URL analyzer module not available")

    try:
        # Convert HttpUrl to string
        url_str = str(request.url)

        # Call the analyzer (pass html_content if app sent it, e.g. from WebView while logged into LinkedIn)
        result = await analyze_job_url(
            url=url_str,
            user_id=request.user_id,
            user_email=request.user_email,
            use_chatgpt_fallback=True,  # Enable ChatGPT fallback
            html_content=request.html_content,
        )

        return result

    except ValueError as e:
        # Invalid URL format
        logger.warning(f"Invalid URL format: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Other errors
        logger.error(f"Failed to analyze job URL: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to fetch or analyze job URL: {str(e)}")
