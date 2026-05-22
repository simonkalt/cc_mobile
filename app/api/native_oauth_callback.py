"""HTTPS OAuth callback for native app auth sessions (Google & LinkedIn)."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)

_OAUTH_HTTPS_DONE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Signed in</title>
  <style>
    body {
      font-family: system-ui, sans-serif;
      text-align: center;
      padding: 2rem;
      background: #fff;
      color: #111;
    }
  </style>
</head>
<body>
  <p>Sign-in complete. Return to the app.</p>
</body>
</html>"""


def native_oauth_callback_response(request: Request, provider: str) -> Response:
    """
    Web OAuth clients redirect to this HTTPS URL.

    - OAUTH_CALLBACK_DEEP_LINK=false: 200 HTML so openAuthSessionAsync(https) completes
      (required for Expo development builds — ccmobile:// opens the dev launcher home).
    - OAUTH_CALLBACK_DEEP_LINK=true: 302 to {scheme}://oauth/{provider} for release builds.
    """
    scheme = settings.OAUTH_NATIVE_APP_SCHEME or "ccmobile"
    query = request.url.query
    target = f"{scheme}://oauth/{provider}"
    if query:
        target = f"{target}?{query}"

    ua = request.headers.get("user-agent") or ""
    use_deep_link = settings.OAUTH_CALLBACK_DEEP_LINK

    logger.info(
        "%s OAuth callback HTTPS %s (has_code=%s has_error=%s deep_link=%s ua=%s)",
        provider.capitalize(),
        target.split("?")[0] if use_deep_link else "finish",
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        use_deep_link,
        ua[:120],
    )

    if use_deep_link:
        return RedirectResponse(url=target, status_code=302)
    return HTMLResponse(content=_OAUTH_HTTPS_DONE_HTML, status_code=200)
