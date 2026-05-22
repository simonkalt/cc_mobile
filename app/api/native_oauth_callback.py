"""HTTPS OAuth callback for native app auth sessions (Google & LinkedIn)."""

from __future__ import annotations

import logging

from fastapi import Request
from fastapi.responses import HTMLResponse, Response

logger = logging.getLogger(__name__)

# 200 on the HTTPS callback URL — do not 302 to ccmobile://. openAuthSessionAsync closes
# when this URL (with ?code=) loads; a 302 to a custom scheme leaves the tab hanging.
_OAUTH_DONE_HTML = """<!DOCTYPE html>
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
    Google and LinkedIn Web OAuth clients redirect here (HTTPS).

    The mobile app uses openAuthSessionAsync(redirectUri) and must receive this URL
    with query params intact. A 302 to ccmobile:// breaks that flow.
    """
    ua = request.headers.get("user-agent") or ""
    logger.info(
        "%s OAuth callback HTTPS finish (has_code=%s has_error=%s ua=%s)",
        provider.capitalize(),
        bool(request.query_params.get("code")),
        bool(request.query_params.get("error")),
        ua[:120],
    )

    return HTMLResponse(content=_OAUTH_DONE_HTML, status_code=200)
