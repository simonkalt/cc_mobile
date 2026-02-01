"""
Job URL analysis related Pydantic models
"""

from pydantic import BaseModel, HttpUrl
from typing import Optional


class JobURLAnalysisRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    # If provided (e.g. from app WebView while user is logged into LinkedIn), use this instead of fetching URL
    html_content: Optional[str] = None
