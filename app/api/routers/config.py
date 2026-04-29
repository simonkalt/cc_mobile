"""
Configuration API routes
"""
import logging
import json
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings
from app.utils.registration_notice import load_registration_data_use_notice
from app.utils.shipped_app_version import default_play_store_url, load_shipped_version

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


class AppUpdatePolicyResponse(BaseModel):
    min_required_version: str
    latest_version: str
    update_message: Optional[str] = None
    store_android_url: str
    store_ios_url: Optional[str] = None


@router.get("/client-settings")
def get_client_settings():
    """
    Global client-consumable runtime settings.
    """
    return {
        "enforceStrongPasswords": settings.ENFORCE_STRONG_PASSWORDS,
        "passwordPolicy": {
            "minLength": 8,
            "requireUppercase": True,
            "requireLowercase": True,
            "requireNumber": True,
            "requireSpecial": True,
        },
        "privacyPolicyUrl": settings.PUBLIC_PRIVACY_POLICY_URL,
        "termsOfServiceUrl": settings.PUBLIC_TERMS_OF_SERVICE_URL,
        "registrationDataUseNotice": load_registration_data_use_notice(),
    }


@router.get("/app-update-policy", response_model=AppUpdatePolicyResponse)
def get_app_update_policy():
    """
    Layer B: optional vs required update gate for native clients. Public; no JWT.
    """
    shipped = load_shipped_version(settings.VERSION_JSON_PATH)
    ship_ver = (shipped.get("version") or "").strip() or settings.APP_VERSION

    min_v = (settings.APP_UPDATE_MIN_REQUIRED_VERSION or "").strip() or ship_ver
    latest_v = (settings.APP_UPDATE_LATEST_VERSION or "").strip() or ship_ver
    msg_raw = (settings.APP_UPDATE_MESSAGE or "").strip()
    msg: Optional[str] = msg_raw if msg_raw else None

    android = (settings.APP_UPDATE_STORE_ANDROID_URL or "").strip() or default_play_store_url()
    ios_raw = (settings.APP_UPDATE_STORE_IOS_URL or "").strip()
    ios: Optional[str] = ios_raw if ios_raw else None

    return AppUpdatePolicyResponse(
        min_required_version=min_v,
        latest_version=latest_v,
        update_message=msg,
        store_android_url=android,
        store_ios_url=ios,
    )


@router.get("/google-places-key")
def get_google_places_key():
    """JSON API endpoint to get the Google Places API key"""
    return {"apiKey": settings.GOOGLE_PLACES_API_KEY}


@router.get("/system-prompt")
def get_system_prompt():
    """JSON API endpoint to get the current system prompt"""
    try:
        # Load system prompt from file
        if settings.SYSTEM_PROMPT_PATH.exists():
            with open(settings.SYSTEM_PROMPT_PATH, 'r', encoding='utf-8') as f:
                system_prompt_data = json.load(f)
                system_message = system_prompt_data.get("system_prompt", "")
                return {"system_prompt": system_message}
        else:
            logger.warning(f"System prompt file not found at {settings.SYSTEM_PROMPT_PATH}")
            return {"system_prompt": ""}
    except Exception as e:
        logger.error(f"Error loading system prompt: {e}")
        return {"system_prompt": ""}

