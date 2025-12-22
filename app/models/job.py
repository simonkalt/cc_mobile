"""
Job URL analysis related Pydantic models
"""
from pydantic import BaseModel, HttpUrl
from typing import Optional


class JobURLAnalysisRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = None
    user_email: Optional[str] = None

