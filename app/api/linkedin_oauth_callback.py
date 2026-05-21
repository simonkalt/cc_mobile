"""LinkedIn HTTPS OAuth callback → native app deep link (shared by auth router and main.py)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.api.native_oauth_callback import native_oauth_callback_response

LINKEDIN_NATIVE_RETURN_BASE = "ccmobile://oauth/linkedin"  # prod default; UAT may use ccmobile-dev


def linkedin_oauth_callback_response(request: Request) -> RedirectResponse:
    return native_oauth_callback_response(request, "linkedin")
