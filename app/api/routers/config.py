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
from app.services.app_version_policy_service import build_layer_b_payload

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
    Primary: MongoDB policy document; env overrides; version.json / APP_VERSION fallback.
    """
    payload = build_layer_b_payload()
    return AppUpdatePolicyResponse(
        min_required_version=payload["min_required_version"],
        latest_version=payload["latest_version"],
        update_message=payload["update_message"],
        store_android_url=payload["store_android_url"],
        store_ios_url=payload["store_ios_url"],
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

