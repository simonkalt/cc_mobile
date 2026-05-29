"""
Public OAuth login routes (Google / LinkedIn).
See documentation/OAUTH_LOGIN_API.md.
"""

import logging

from fastapi import APIRouter, Request

from app.api.linkedin_oauth_callback import linkedin_oauth_callback_response
from app.api.native_oauth_callback import native_oauth_callback_response
from app.models.oauth import (
    AppleOAuthLoginRequest,
    OAuthLoginResponse,
    OAuthTokenExchangeRequest,
)
from app.services.oauth_login_service import apple_oauth_login, oauth_login

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


@router.get("/oauth/google/callback", include_in_schema=False)
async def google_oauth_https_callback(request: Request):
    """Google OIDC redirect target; 302 to ccmobile:// for native auth session."""
    return native_oauth_callback_response(request, "google")


@router.get("/oauth/linkedin/callback", include_in_schema=False)
async def linkedin_oauth_https_callback(request: Request):
    """LinkedIn OIDC redirect target; 302 to ccmobile:// for native auth session."""
    return linkedin_oauth_callback_response(request)
