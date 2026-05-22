"""LinkedIn HTTPS OAuth callback → native app deep link (shared by auth router and main.py)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import Response

from app.api.native_oauth_callback import native_oauth_callback_response

LINKEDIN_NATIVE_RETURN_BASE = "ccmobile://oauth/linkedin"


def linkedin_oauth_callback_response(request: Request) -> Response:
    return native_oauth_callback_response(request, "linkedin")
