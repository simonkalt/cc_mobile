"""HTTPS OAuth callback for native app auth sessions (Google & LinkedIn)."""

from __future__ import annotations

import json
import logging
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import settings

logger = logging.getLogger(__name__)

# Must match Expo android.package (com.saimonsoft.customcoverlettermobile.app).
_ANDROID_APP_PACKAGE = "com.saimonsoft.customcoverlettermobile.app"


def _android_intent_uri(scheme: str, provider: str, query: str) -> str:
    """Chrome Custom Tabs on many devices only open the app via intent://, not 302→scheme."""
    path = f"oauth/{provider}"
    if query:
        path = f"{path}?{query}"
    return (
        f"intent://{path}"
        f"#Intent;scheme={scheme};package={_ANDROID_APP_PACKAGE};end"
    )


def _mobile_oauth_bridge_html(
    target: str, *, android_intent: str | None = None
) -> str:
    """Custom Tab loads HTTPS first; hands off to ccmobile:// for Linking."""
    target_json = json.dumps(target)
    intent_json = json.dumps(android_intent) if android_intent else "null"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Returning to app</title>
  <script>
    (function () {{
      var target = {target_json};
      var intent = {intent_json};
      function goCustom() {{
        try {{ window.location.replace(target); }} catch (e) {{}}
      }}
      function goIntent() {{
        if (!intent) return false;
        try {{ window.location.replace(intent); return true; }} catch (e) {{}}
        return false;
      }}
      if (!goIntent()) goCustom();
      setTimeout(goCustom, 400);
    }})();
  </script>
</head>
<body style="font-family:system-ui,sans-serif;text-align:center;padding:2rem;">
  <p>Returning to the app…</p>
  <p><a id="open" href="{target}" style="font-size:1.1rem;">Open app</a></p>
  <script>
    (function () {{
      var a = document.getElementById("open");
      var intent = {intent_json};
      if (intent) {{
        var i = document.createElement("a");
        i.href = intent;
        i.textContent = "Open app (Android)";
        i.style.display = "block";
        i.style.marginTop = "1rem";
        a.parentNode.appendChild(i);
      }}
    }})();
  </script>
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

    ua_lower = ua.lower()
    is_android = "android" in ua_lower

    if use_deep_link and is_android:
        intent_uri = _android_intent_uri(scheme, provider, query)
        logger.info(
            "%s OAuth callback Android bridge (intent + %s)",
            provider.capitalize(),
            target.split("?")[0],
        )
        return HTMLResponse(
            content=_mobile_oauth_bridge_html(target, android_intent=intent_uri),
            status_code=200,
        )

    if use_deep_link:
        return RedirectResponse(url=target, status_code=302)

    intent_uri = _android_intent_uri(scheme, provider, query) if is_android else None
    return HTMLResponse(
        content=_mobile_oauth_bridge_html(target, android_intent=intent_uri),
        status_code=200,
    )
