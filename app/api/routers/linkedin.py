"""
LinkedIn 3-legged OAuth and jobLibrary integration.

Endpoints:
- GET /api/linkedin/auth-url: returns authorization URL for user to connect LinkedIn (requires auth).
- GET /api/linkedin/callback: OAuth callback; exchanges code for token and stores in user preferences (no auth).
- GET /api/linkedin/status: returns whether current user has a LinkedIn token (requires auth).
"""

import logging
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

from app.core.auth import get_current_user
from app.core.config import settings
from app.models.user import UserResponse
from app.services.linkedin_job_api import build_authorization_url, exchange_code_for_token
from app.services.user_service import set_linkedin_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/linkedin",
    tags=["linkedin"],
)


@router.get("/auth-url")
async def linkedin_auth_url(
    current_user: UserResponse = Depends(get_current_user),
):
    """
    Return the LinkedIn OAuth 2.0 authorization URL for 3-legged flow.
    The app should open this URL in a browser/WebView; after the user authorizes,
    LinkedIn redirects to LINKEDIN_REDIRECT_URI with ?code=...&state=user_id.
    State is set to the current user's ID so the callback can store the token for that user.
    """
    client_id = getattr(settings, "LINKEDIN_CLIENT_ID", None) or ""
    redirect_uri = getattr(settings, "LINKEDIN_REDIRECT_URI", None) or ""
    scope = getattr(settings, "LINKEDIN_SCOPE", None) or ""
    if not client_id or not redirect_uri:
        raise HTTPException(
            status_code=503,
            detail="LinkedIn OAuth not configured (LINKEDIN_CLIENT_ID, LINKEDIN_REDIRECT_URI required)",
        )
    if not scope or not scope.strip():
        raise HTTPException(
            status_code=503,
            detail=(
                "LINKEDIN_SCOPE is required. Set it to the exact scope from your LinkedIn app's Auth tab: "
                "Developer Portal → Your app → Auth tab → copy the scope for your product (e.g. jobLibrary). "
                "invalid_scope_error means the scope value is not valid for your app."
            ),
        )
    # State must be the user_id so the callback knows which user to attach the token to
    state = current_user.id
    url = build_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=state,
        scope=scope.strip(),
    )
    logger.info("LinkedIn auth URL generated for user_id=%s", current_user.id)
    return {"authorization_url": url, "state": state}


@router.get("/callback")
async def linkedin_callback(
    code: str | None = Query(None, description="Authorization code from LinkedIn"),
    state: str | None = Query(None, description="State (user_id) passed to authorization"),
    error: str | None = Query(None, description="Error from LinkedIn if user denied"),
    error_description: str | None = Query(None, description="Error description"),
):
    """
    OAuth callback. LinkedIn redirects here after user authorizes.
    Exchanges code for access token and stores it in user preferences (key: state = user_id).
    Then redirects to LINKEDIN_SUCCESS_REDIRECT or returns JSON.
    """
    if error:
        logger.warning("LinkedIn callback error: %s %s", error, error_description or "")
        # Help users fix invalid_scope_error: scope must match exactly what's in the Auth tab
        detail = error_description or error
        if error == "invalid_scope_error":
            detail = (
                "Invalid scope: LINKEDIN_SCOPE must match a scope assigned to your app. "
                "In LinkedIn Developer Portal → Your app → Auth tab, copy the exact scope string "
                "for your product (e.g. jobLibrary). Set that value in .env as LINKEDIN_SCOPE=..."
            )
        success_redirect = getattr(settings, "LINKEDIN_SUCCESS_REDIRECT", None)
        if success_redirect:
            return RedirectResponse(
                url=success_redirect
                + "?"
                + urlencode({"linkedin": "denied", "error": error, "message": detail}),
                status_code=302,
            )
        # No redirect: return HTML so browser/WebView shows a readable message (not JSON that becomes [object Object])
        html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>LinkedIn connection failed</title></head><body><p>{detail}</p><p>You can close this window.</p></body></html>"""
        return HTMLResponse(content=html, status_code=400)
    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state")
    client_id = getattr(settings, "LINKEDIN_CLIENT_ID", None) or ""
    client_secret = getattr(settings, "LINKEDIN_CLIENT_SECRET", None) or ""
    redirect_uri = getattr(settings, "LINKEDIN_REDIRECT_URI", None) or ""
    if not all([client_id, client_secret, redirect_uri]):
        raise HTTPException(status_code=503, detail="LinkedIn OAuth not configured")
    token_data = exchange_code_for_token(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
        redirect_uri=redirect_uri,
    )
    if not token_data:
        raise HTTPException(status_code=400, detail="Failed to exchange code for token")
    user_id = state
    expires_in = token_data.get("expires_in", 0)
    import time

    token_payload = {
        "access_token": token_data.get("access_token"),
        "expires_at": int(time.time()) + expires_in if expires_in else 0,
        "refresh_token": token_data.get("refresh_token"),
        "scope": token_data.get("scope"),
    }
    if not set_linkedin_token(user_id, token_payload):
        logger.warning("Could not store LinkedIn token for user_id=%s", user_id)
        raise HTTPException(status_code=500, detail="Could not store token")
    success_redirect = getattr(settings, "LINKEDIN_SUCCESS_REDIRECT", None)
    if success_redirect:
        return RedirectResponse(
            url=success_redirect + "?" + urlencode({"linkedin": "connected"}),
            status_code=302,
        )
    return {"linkedin": "connected", "user_id": user_id}


@router.get("/status")
async def linkedin_status(
    current_user: UserResponse = Depends(get_current_user),
):
    """Return whether the current user has a stored LinkedIn token (for jobLibrary)."""
    from app.services.user_service import get_linkedin_token

    token_data = get_linkedin_token(current_user.id)
    has_token = bool(token_data and token_data.get("access_token"))
    return {"linkedin_connected": has_token}
