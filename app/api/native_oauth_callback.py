"""HTTPS OAuth callback → native app deep link (Google & LinkedIn)."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import RedirectResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)


def native_oauth_callback_response(request: Request, provider: str) -> Response:
    """
    Google and LinkedIn Web OAuth clients only accept https:// redirect URIs.

    Native apps authorize with the HTTPS callback on this API, then 302 to
    {OAUTH_NATIVE_APP_SCHEME}://oauth/{provider}?...
    """
    scheme = settings.OAUTH_NATIVE_APP_SCHEME or "ccmobile"
    query = request.url.query
    target = f"{scheme}://oauth/{provider}"
    if query:
        target = f"{target}?{query}"

    ua = request.headers.get("user-agent") or ""
    logger.info(
        "%s OAuth callback → %s (has_code=%s has_error=%s ua=%s)",
        provider.capitalize(),
        target.split("?")[0],
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        ua[:120],
    )

    return RedirectResponse(url=target, status_code=302)
