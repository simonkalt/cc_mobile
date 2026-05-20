"""
Public OAuth login routes (Google / LinkedIn).
See documentation/OAUTH_LOGIN_API.md.
"""

import logging

from fastapi import APIRouter

from app.models.oauth import OAuthLoginResponse, OAuthTokenExchangeRequest
from app.services.oauth_login_service import oauth_login

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
