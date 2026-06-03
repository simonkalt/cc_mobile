"""
Public OAuth login routes (Google / LinkedIn).
See documentation/OAUTH_LOGIN_API.md.
"""

import logging

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.linkedin_oauth_callback import linkedin_oauth_callback_response
from app.api.native_oauth_callback import native_oauth_callback_response
from app.models.oauth import (
    AppleOAuthLoginRequest,
    OAuthLoginResponse,
    OAuthTokenExchangeRequest,
)
from app.services.oauth_login_service import apple_oauth_login, oauth_login
from app.services.oauth_native_handoff import consume_oauth_native_handoff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/oauth/google", response_model=OAuthLoginResponse)
async def oauth_google_login(body: OAuthTokenExchangeRequest):
    """Exchange Google authorization code (PKCE) for app session tokens."""
    logger.info("OAuth Google login intent=%s", body.intent)
    return oauth_login("google", body)


@router.post("/oauth/linkedin", response_model=OAuthLoginResponse)
async def oauth_linkedin_login(body: OAuthTokenExchangeRequest):
    """Exchange LinkedIn authorization code (PKCE) for app session tokens."""
    logger.info("OAuth LinkedIn login intent=%s", body.intent)
    return oauth_login("linkedin", body)


@router.post("/oauth/apple", response_model=OAuthLoginResponse)
async def oauth_apple_login(body: AppleOAuthLoginRequest):
    """Verify a Sign in with Apple identity token (native iOS) for app session tokens."""
    logger.info("OAuth Apple login intent=%s", body.intent)
    return apple_oauth_login(body)


@router.get("/oauth/native-handoff", include_in_schema=False)
async def oauth_native_handoff_poll(
    state: str = Query(..., min_length=4, max_length=256),
    provider: str = Query(..., pattern="^(google|linkedin)$"),
):
    """
    Android fallback when Custom Tab cannot open ccmobile:// (no intent filter in APK).
    Populated by the HTTPS OAuth callback; one-time read keyed by authorize `state`.
    """
    handoff = consume_oauth_native_handoff(state, provider)
    if not handoff:
        raise HTTPException(status_code=404, detail="pending")
    if handoff.error:
        return {
            "error": handoff.error,
            "error_description": handoff.error_description,
        }
    if not handoff.code:
        raise HTTPException(status_code=404, detail="pending")
    return {"code": handoff.code}


@router.get("/oauth/google/callback", include_in_schema=False)
async def google_oauth_https_callback(request: Request):
    """Google OIDC redirect target; 302 to ccmobile:// for native auth session."""
    return native_oauth_callback_response(request, "google")


@router.get("/oauth/linkedin/callback", include_in_schema=False)
async def linkedin_oauth_https_callback(request: Request):
    """LinkedIn OIDC redirect target; 302 to ccmobile:// for native auth session."""
    return linkedin_oauth_callback_response(request)
