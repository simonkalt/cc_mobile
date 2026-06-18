"""
Configuration API routes
"""
import logging
import json
import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict

from app.core.config import settings
from app.core.auth import get_current_user
from app.models.user import UserResponse
from app.utils.registration_notice import load_registration_data_use_notice
from app.services.app_version_policy_service import build_layer_b_payload
from app.services.client_settings_service import (
    get_job_share_import_sites,
    patch_job_share_import_sites,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/config", tags=["config"])


class AppUpdatePolicyResponse(BaseModel):
    min_required_version: str
    latest_version: str
    update_message: Optional[str] = None
    store_android_url: str
    store_ios_url: Optional[str] = None


class JobShareImportSitesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    linkedin: Optional[bool] = None
    indeed: Optional[bool] = None
    glassdoor: Optional[bool] = None
    ziprecruiter: Optional[bool] = None
    generic: Optional[bool] = None


class JobShareImportSitesResponse(BaseModel):
    jobShareImportSites: dict


async def require_super_user(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    if not current_user.super_user:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized",
        )
    return current_user


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
        "jobShareImportSites": get_job_share_import_sites(),
    }


@router.patch(
    "/client-settings/job-share-sites",
    response_model=JobShareImportSitesResponse,
)
def patch_job_share_import_sites_endpoint(
    body: JobShareImportSitesPatch,
    _super_user: UserResponse = Depends(require_super_user),
):
    """
    Superuser only — merge job share import site toggles into global client settings.
    """
    partial = body.model_dump(exclude_none=True)
    merged = patch_job_share_import_sites(partial)
    return JobShareImportSitesResponse(jobShareImportSites=merged)


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


@router.get("/oauth-native-callback-status")
def get_oauth_native_callback_status():
    """
    Public diagnostic: native OAuth bridge settings for mobile Custom Tab handoff.
    curl UAT after deploy — oauth_callback_deep_link should be true for ccmobile:// HTML bridge.
    """
    on_render = bool(os.getenv("RENDER") or os.getenv("RENDER_EXTERNAL_URL"))
    return {
        "oauth_callback_deep_link": settings.OAUTH_CALLBACK_DEEP_LINK,
        "native_app_scheme": settings.OAUTH_NATIVE_APP_SCHEME,
        "on_render": bool(on_render),
        "hint": (
            "When oauth_callback_deep_link is true, Android OAuth callback returns HTML that "
            "redirects to {scheme}://oauth/{provider}. When false, callback stays on HTTPS and "
            "the app may never receive ccmobile://. On Render, dashboard Environment variables "
            "override /etc/secrets/.secrets — set OAUTH_CALLBACK_DEEP_LINK=true there if needed."
        ),
    }


@router.get("/linkedin-oauth-status")
def get_linkedin_oauth_status():
    """
    Public diagnostic: which LinkedIn OAuth env the running process sees (no secrets).
    Use on UAT to confirm Render loaded the same client id / secret as local .secrets.
    """
    from app.services.oauth_providers import (
        linkedin_oauth_config_fingerprint,
        probe_linkedin_server_credentials,
    )

    fp = linkedin_oauth_config_fingerprint()
    probe = probe_linkedin_server_credentials()
    return {
        "fingerprint": fp,
        "credentials_probe": probe,
        "hint": (
            "credentials_probe.ok=false with invalid_client means the running process has a "
            "bad id/secret pair (regenerate in LinkedIn portal, update Render, redeploy). "
            "On Render, delete LINKEDIN_CLIENT_SECRET from the Environment tab if it duplicates "
            ".secrets — dashboard vars override the secret file. "
            "After rotating, client_secret_sha256_prefix must change. "
            "credentials_probe.ok=true but login still fails → PKCE/code/redirect_uri, not secret."
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

