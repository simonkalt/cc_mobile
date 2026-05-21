"""LinkedIn HTTPS OAuth callback → native app deep link (shared by auth router and main.py)."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

LINKEDIN_NATIVE_RETURN_BASE = "ccmobile://oauth/linkedin"


def linkedin_oauth_callback_response(request: Request) -> RedirectResponse:
    """
    LinkedIn only allows HTTPS redirect_uri in the developer portal.

    Native clients listen for ccmobile:// (Android Custom Tab cannot complete on
    HTTPS alone). HTTP 302 to the custom scheme is more reliable than JS redirect.
    """
    query = request.url.query
    target = LINKEDIN_NATIVE_RETURN_BASE
    if query:
        target = f"{target}?{query}"

    logger.info(
        "LinkedIn OAuth callback → app (has_code=%s has_error=%s ua=%s)",
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        (request.headers.get("user-agent") or "")[:120],
    )
    return RedirectResponse(url=target, status_code=302)
