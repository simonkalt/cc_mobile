"""HTTPS OAuth callback for native app auth sessions (Google & LinkedIn)."""

from __future__ import annotations

import json
import logging

from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)


def _mobile_oauth_bridge_html(target: str) -> str:
    """Custom Tab loads HTTPS first; JS/302 hands off to ccmobile:// for Linking."""
    target_json = json.dumps(target)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Returning to app</title>
  <script>
    (function () {{
      var target = {target_json};
      try {{
        window.location.replace(target);
      }} catch (e) {{}}
    }})();
  </script>
</head>
<body>
  <p>Returning to the app…</p>
</body>
</html>"""


def native_oauth_callback_response(request: Request, provider: str) -> Response:
    """
    Web OAuth clients redirect to this HTTPS URL.

    Native apps must receive {scheme}://oauth/{provider}?... via Linking (Android) or
    ASWebAuthenticationSession (iOS). A plain 200 HTML page on https:// does not close
    the Android Custom Tab.
    """
    scheme = settings.OAUTH_NATIVE_APP_SCHEME or "ccmobile"
    query = request.url.query
    target = f"{scheme}://oauth/{provider}"
    if query:
        target = f"{target}?{query}"

    ua = request.headers.get("user-agent") or ""
    use_deep_link = settings.OAUTH_CALLBACK_DEEP_LINK

    logger.info(
        "%s OAuth callback HTTPS → %s (has_code=%s has_error=%s deep_link=%s ua=%s)",
        provider.capitalize(),
        target.split("?")[0],
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        use_deep_link,
        ua[:120],
    )

    if use_deep_link:
        return RedirectResponse(url=target, status_code=302)
    return HTMLResponse(content=_mobile_oauth_bridge_html(target), status_code=200)
