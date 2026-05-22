"""HTTPS OAuth callback for native app auth sessions (Google & LinkedIn)."""

from __future__ import annotations

import json
import logging

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)


def _mobile_oauth_bridge_html(target: str) -> str:
    """
    Google/LinkedIn redirect here over HTTPS (registered in Cloud Console).
    Android openAuthSessionAsync often does not complete on https:// alone;
    a short HTML page that jumps to ccmobile:// closes the Custom Tab.
    """
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
    Web OAuth clients redirect to this HTTPS URL. Native apps authorize with that
    URI but openAuthSessionAsync waits for {scheme}://oauth/{provider}?...
    """
    scheme = settings.OAUTH_NATIVE_APP_SCHEME or "ccmobile"
    query = request.url.query
    target = f"{scheme}://oauth/{provider}"
    if query:
        target = f"{target}?{query}"

    ua = request.headers.get("user-agent") or ""
    logger.info(
        "%s OAuth callback HTTPS → app %s (has_code=%s has_error=%s ua=%s)",
        provider.capitalize(),
        target.split("?")[0],
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        ua[:120],
    )

    return HTMLResponse(content=_mobile_oauth_bridge_html(target), status_code=200)
