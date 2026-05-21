"""HTTPS OAuth callback → native app deep link (Google & LinkedIn)."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import RedirectResponse

from app.core.config import settings

logger = logging.getLogger(__name__)


def native_oauth_callback_response(request: Request, provider: str) -> RedirectResponse:
    """
    Google and LinkedIn Web OAuth clients only accept https:// redirect URIs.

    Native clients authorize with the HTTPS callback on this API, then receive
    {OAUTH_NATIVE_APP_SCHEME}:// via 302 (Android Custom Tab does not complete on HTTPS alone).
    """
    scheme = settings.OAUTH_NATIVE_APP_SCHEME or "ccmobile"
    query = request.url.query
    target = f"{scheme}://oauth/{provider}"
    if query:
        target = f"{target}?{query}"

    logger.info(
        "%s OAuth callback → app (has_code=%s has_error=%s ua=%s)",
        provider.capitalize(),
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        (request.headers.get("user-agent") or "")[:120],
    )
    return RedirectResponse(url=target, status_code=302)
