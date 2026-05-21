"""
Public OAuth login routes (Google / LinkedIn).
See documentation/OAUTH_LOGIN_API.md.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse

from app.models.oauth import OAuthLoginResponse, OAuthTokenExchangeRequest
from app.services.oauth_login_service import oauth_login

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# LinkedIn Developer Portal only allows http(s) redirect URLs (no custom schemes).
# Native apps authorize with the HTTPS callback below; this route bounces to the app.
LINKEDIN_MOBILE_APP_REDIRECT = "ccmobile://oauth/linkedin"


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


@router.get("/oauth/linkedin/callback", include_in_schema=False)
async def linkedin_oauth_https_callback(request: Request):
    """
    LinkedIn OIDC redirect target (HTTPS only in the developer portal).

    Forwards query params to the mobile deep link so expo-auth-session / the app
    can read `code` and complete PKCE. The same HTTPS URL must be sent as
    redirect_uri in POST /api/auth/oauth/linkedin.
    """
    query = request.url.query
    target = LINKEDIN_MOBILE_APP_REDIRECT
    if query:
        target = f"{target}?{query}"
    logger.info("LinkedIn OAuth bridge redirect to app (query_len=%s)", len(query))
    return RedirectResponse(url=target, status_code=302)
