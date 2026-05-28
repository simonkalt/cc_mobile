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


@router.get("/linkedin-oauth-status")
def get_linkedin_oauth_status():
    """
    Public diagnostic: which LinkedIn OAuth env the running process sees (no secrets).
    Use on UAT to confirm Render loaded the same client id / secret as local .secrets.
    """
    from app.services.oauth_providers import linkedin_oauth_config_fingerprint

    fp = linkedin_oauth_config_fingerprint()
    return {
        "fingerprint": fp,
        "hint": (
            "If LinkedIn token exchange logs invalid_client, LINKEDIN_CLIENT_SECRET on this "
            "instance does not match LINKEDIN_CLIENT_ID (or dashboard env overrides a stale "
            "secret file on Render). Update both on Render, redeploy, and ensure "
            "EXPO_PUBLIC_LINKEDIN_CLIENT_ID on mobile matches LINKEDIN_CLIENT_ID here."
        ),
    }


@router.get("/zoho-mail-status")
def get_zoho_mail_status():
    """
    Public diagnostic: which Zoho env the running process sees (no secrets).
    Use on UAT to confirm Render loaded the same client id / secret lengths as local .secrets.
    """
    from app.utils.email_utils import probe_zoho_refresh_token, zoho_config_fingerprint

    probe = probe_zoho_refresh_token()
    return {
        "fingerprint": zoho_config_fingerprint(),
        "refresh_probe": {
            "ok": probe.get("ok"),
            "error": probe.get("error"),
        },
        "hint": (
            "If refresh_probe.error is invalid_client_secret, ZOHO_CLIENT_SECRET on this "
            "instance does not match ZOHO_CLIENT_ID (or refresh token was minted for a "
            "different client). Update all three together on Render, then redeploy."
        ),
    }


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

