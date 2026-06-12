"""HTTPS OAuth callback for native app auth sessions (Google & LinkedIn)."""

from __future__ import annotations

import json
import logging
from fastapi import Request
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.core.config import settings
from app.services.oauth_native_handoff import store_oauth_native_handoff

logger = logging.getLogger(__name__)

def _android_intent_uri(scheme: str, provider: str, query: str) -> str:
    """
    Optional manual fallback only (no package=).

    Including package=com.saimonsoft... makes Chrome open the Play Store when the
    installed dev APK does not handle the intent exactly like the store build.
    """
    path = f"oauth/{provider}"
    if query:
        path = f"{path}?{query}"
    return (
        f"intent://{path}#Intent;"
        f"scheme={scheme};"
        f"action=android.intent.action.VIEW;"
        f"category=android.intent.category.BROWSABLE;"
        f"category=android.intent.category.DEFAULT;"
        f"end"
    )


def _mobile_oauth_bridge_html(
    target: str,
    *,
    android_intent: str | None = None,
    delay_auto_redirect_ms: int = 0,
) -> str:
    """Fallback when OAUTH_CALLBACK_DEEP_LINK=false (dev / legacy). Prefer 302 when deep_link=true."""
    target_json = json.dumps(target)
    intent_json = json.dumps(android_intent) if android_intent else "null"
    delay_ms = max(0, int(delay_auto_redirect_ms))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Returning to app</title>
</head>
<body style="margin:0;background:#ffffff;color:#111111;font-family:system-ui,sans-serif;text-align:center;padding:2rem;">
  <p style="font-size:1.05rem;">Returning to the app…</p>
  <p><a id="open" href="{target}" style="font-size:1.1rem;color:#1565c0;">Tap to open the app</a></p>
  <script>
    (function () {{
      var target = {target_json};
      var intent = {intent_json};
      var delay = {delay_ms};
      function goScheme() {{
        try {{ window.location.replace(target); }} catch (e) {{}}
      }}
      function goIntent() {{
        if (!intent) return;
        try {{ window.location.href = intent; }} catch (e) {{}}
      }}
      function schedule() {{
        if (delay > 0) {{
          setTimeout(function () {{ goIntent(); goScheme(); }}, delay);
          setTimeout(goScheme, delay + 600);
          setTimeout(goScheme, delay + 1400);
          return;
        }}
        goIntent();
        goScheme();
        setTimeout(goScheme, 350);
        setTimeout(goScheme, 900);
      }}
      schedule();
      if (intent) {{
        var i = document.createElement("a");
        i.href = intent;
        i.textContent = "Still here? Try alternate link";
        i.style.display = "block";
        i.style.marginTop = "1rem";
        i.style.fontSize = "0.95rem";
        i.style.color = "#1565c0";
        document.body.appendChild(i);
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

    oauth_state = (request.query_params.get("state") or "").strip()
    if oauth_state:
        store_oauth_native_handoff(
            state=oauth_state,
            provider=provider,
            code=request.query_params.get("code"),
            error=request.query_params.get("error"),
            error_description=request.query_params.get("error_description"),
        )

    if use_deep_link:
        logger.info(
            "%s OAuth callback 302 → %s (has_code=%s android=%s handoff_stored=%s)",
            provider.capitalize(),
            target.split("?")[0],
            bool(request.query_params.get("code")),
            is_android,
            bool(oauth_state),
        )
        return RedirectResponse(url=target, status_code=302)

    intent_uri = _android_intent_uri(scheme, provider, query) if is_android else None
    logger.info(
        "%s OAuth callback HTML bridge (deep_link disabled, %s)",
        provider.capitalize(),
        target.split("?")[0],
    )
    return HTMLResponse(
        content=_mobile_oauth_bridge_html(
            target,
            android_intent=intent_uri,
            delay_auto_redirect_ms=0,
        ),
        status_code=200,
    )
