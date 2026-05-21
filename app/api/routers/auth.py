"""
Public OAuth login routes (Google / LinkedIn).
See documentation/OAUTH_LOGIN_API.md.
"""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.models.oauth import OAuthLoginResponse, OAuthTokenExchangeRequest
from app.services.oauth_login_service import oauth_login

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Minimal page so expo-auth-session (openAuthSessionAsync) can read ?code= on this URL.
# Do NOT 302 to ccmobile:// here — that breaks returnUrl matching on Android/iOS.
_LINKEDIN_CALLBACK_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Signing in</title>
  <style>
    body { font-family: system-ui, sans-serif; text-align: center; padding: 2rem; }
  </style>
</head>
<body>
  <p>Signing you in… You can close this window and return to the app.</p>
</body>
</html>
"""


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

    Returns 200 with the authorization query string still on this URL so
    expo-auth-session `openAuthSessionAsync` can match `redirect_uri` and pass
    `code` + `state` back to the app. The same HTTPS URL must be sent as
    redirect_uri in POST /api/auth/oauth/linkedin.
    """
    error = request.query_params.get("error")
    code = request.query_params.get("code")
    logger.info(
        "LinkedIn OAuth callback (has_code=%s has_error=%s)",
        bool(code),
        bool(error),
    )
    return HTMLResponse(content=_LINKEDIN_CALLBACK_HTML, status_code=200)
