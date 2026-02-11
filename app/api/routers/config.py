"""
Configuration API routes
"""
import logging
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.core.config import settings
from app.utils.llm_utils import load_system_prompt

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/config",
    tags=["config"],
    dependencies=[Depends(get_current_user)]
)


@router.get("/google-places-key")
def get_google_places_key():
    """JSON API endpoint to get the Google Places API key"""
    return {"apiKey": settings.GOOGLE_PLACES_API_KEY}


@router.get("/system-prompt")
def get_system_prompt():
    """JSON API endpoint to get the current system prompt"""
    try:
        system_message = load_system_prompt()
        return {"system_prompt": system_message}
    except Exception as e:
        logger.error(f"Error loading system prompt: {e}")
        return {"system_prompt": ""}

