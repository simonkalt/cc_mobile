"""HTTPS OAuth callback → native app deep link (Google & LinkedIn)."""

from __future__ import annotations

import html as html_module
import json
import logging

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)


def _mobile_in_app_browser(user_agent: str) -> bool:
    """Chrome Custom Tab / mobile WebView — HTML+JS redirect is more reliable than 302 alone."""
    ua = user_agent.lower()
    return (
        "android" in ua
        or "iphone" in ua
        or "ipad" in ua
        or "mobile" in ua
    )


def native_oauth_callback_response(request: Request, provider: str) -> Response:
    """
    Google and LinkedIn Web OAuth clients only accept https:// redirect URIs.

    Native clients authorize with the HTTPS callback on this API, then return to
    {OAUTH_NATIVE_APP_SCHEME}://. Mobile in-app browsers often ignore 302 to custom
    schemes; an HTML page with window.location.replace() is more reliable.
    """
    scheme = settings.OAUTH_NATIVE_APP_SCHEME or "ccmobile"
    query = request.url.query
    target = f"{scheme}://oauth/{provider}"
    if query:
        target = f"{target}?{query}"

    ua = request.headers.get("user-agent") or ""
    logger.info(
        "%s OAuth callback → %s (has_code=%s has_error=%s mobile=%s ua=%s)",
        provider.capitalize(),
        target.split("?")[0],
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        _mobile_in_app_browser(ua),
        ua[:120],
    )

    if _mobile_in_app_browser(ua):
        target_json = json.dumps(target)
        href = html_module.escape(target, quote=True)
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Returning to app</title>
  <script>window.location.replace({target_json});</script>
</head>
<body>
  <p>Returning to the app…</p>
  <p><a href="{href}">Tap here</a> if nothing happens.</p>
</body>
</html>"""
        return HTMLResponse(content=html, status_code=200)

    return RedirectResponse(url=target, status_code=302)
