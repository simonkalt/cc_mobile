"""
Identity-provider token exchange and ID token / userinfo validation for OAuth login.
"""

from __future__ import annotations

import base64
import hashlib
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from urllib.parse import quote

import requests
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_USERINFO_URL = "https://api.linkedin.com/v2/userinfo"

_jwks_cache: Optional[Dict[str, Any]] = None


@dataclass(frozen=True)
class OAuthIdentity:
    provider: str
    sub: str
    email: Optional[str]
    email_verified: bool
    name: Optional[str]
    picture: Optional[str]


class OAuthProviderError(Exception):
    """Raised when code exchange or token validation fails."""

    def __init__(
        self,
        message: str = "Invalid authorization code",
        *,
        error_code: str = "invalid_code",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code


def linkedin_oauth_config_fingerprint() -> dict:
    """Non-secret snapshot of loaded LinkedIn OAuth env (for UAT/debug)."""
    client_id = (settings.LINKEDIN_CLIENT_ID or "").strip()
    client_secret = (settings.LINKEDIN_CLIENT_SECRET or "").strip()
    secret_fp = ""
    if client_secret:
        secret_fp = hashlib.sha256(client_secret.encode()).hexdigest()[:12]
    return {
        "configured": bool(client_id and client_secret),
        "client_id_prefix": client_id[:6] if client_id else "",
        "client_id_length": len(client_id),
        "client_secret_length": len(client_secret),
        "client_secret_sha256_prefix": secret_fp,
        "client_secret_looks_like_linkedin": client_secret.startswith("WPL_AP1.")
        if client_secret
        else False,
        "client_secret_ends_with_equals": client_secret.endswith("=")
        if client_secret
        else False,
    }


def probe_linkedin_server_credentials() -> dict:
    """
    Validate LINKEDIN_CLIENT_ID + LINKEDIN_CLIENT_SECRET with LinkedIn (no user code).

    OIDC apps often reject client_credentials (access_denied) even when the secret is
    valid. We POST a dummy authorization_code instead: invalid_client => bad secret;
    authorization code not found / invalid_request => secret accepted.
    """
    client_id = (settings.LINKEDIN_CLIENT_ID or "").strip()
    client_secret = (settings.LINKEDIN_CLIENT_SECRET or "").strip()
    if not client_id or not client_secret:
        return {"ok": False, "error": "not_configured", "auth_method": None}

    redirect_uri = (
        (settings.LINKEDIN_REDIRECT_URI or "").strip()
        or "https://cc-mobile-uat.onrender.com/api/auth/oauth/linkedin/callback"
    )
    data = {
        "grant_type": "authorization_code",
        "code": "cc_mobile_credentials_probe_dummy",
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": "cc_mobile_credentials_probe_verifier",
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    try:
        response = requests.post(
            LINKEDIN_TOKEN_URL,
            headers=headers,
            data=data,
            timeout=15,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": str(exc), "auth_method": "client_secret_post"}

    try:
        body = response.json() or {}
    except Exception:
        body = {}

    error = body.get("error") or f"http_{response.status_code}"
    description = (body.get("error_description") or "").lower()

    if error == "invalid_client":
        return {"ok": False, "error": error, "auth_method": "client_secret_post"}

    if "authorization code not found" in description or error in (
        "invalid_request",
        "invalid_grant",
    ):
        return {"ok": True, "error": None, "auth_method": "client_secret_post"}

    return {"ok": False, "error": error, "auth_method": "client_secret_post"}


def _oauth_basic_auth_header(client_id: str, client_secret: str) -> str:
    """RFC 6749 client_secret_basic (form-urlencoded id:secret)."""
    creds = f"{quote(client_id, safe='')}:{quote(client_secret, safe='')}"
    encoded = base64.b64encode(creds.encode()).decode()
    return f"Basic {encoded}"


def _linkedin_token_exchange(
    code: str,
    redirect_uri: str,
    code_verifier: str,
    client_id: str,
    client_secret: str,
) -> Tuple[requests.Response, str]:
    """
    Exchange LinkedIn auth code for tokens. Tries POST body credentials first,
    then HTTP Basic auth (some secrets with special chars fail in form bodies).
    Returns (response, auth_method).
    """
    base_data = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "code_verifier": code_verifier,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    body_response = requests.post(
        LINKEDIN_TOKEN_URL,
        headers=headers,
        data={
            **base_data,
            "client_id": client_id,
            "client_secret": client_secret,
        },
        timeout=15,
    )
    if body_response.status_code == 200:
        return body_response, "client_secret_post"

    body_error = ""
    try:
        body_error = (body_response.json() or {}).get("error") or ""
    except Exception:
        body_error = ""

    if body_error != "invalid_client":
        return body_response, "client_secret_post"

    basic_response = requests.post(
        LINKEDIN_TOKEN_URL,
        headers={
            **headers,
            "Authorization": _oauth_basic_auth_header(client_id, client_secret),
        },
        data={**base_data, "client_id": client_id},
        timeout=15,
    )
    if basic_response.status_code == 200:
        return basic_response, "client_secret_basic"

    logger.warning(
        "LinkedIn token exchange basic auth also failed status=%s body=%s",
        basic_response.status_code,
        basic_response.text[:500],
    )
    return body_response, "client_secret_post"


def _fetch_google_jwks() -> Dict[str, Any]:
    global _jwks_cache
    if _jwks_cache is not None:
        return _jwks_cache
    response = requests.get(GOOGLE_JWKS_URL, timeout=15)
    response.raise_for_status()
    _jwks_cache = response.json()
    return _jwks_cache


def _verify_google_id_token(id_token: str, client_id: str) -> Dict[str, Any]:
    try:
        header = jwt.get_unverified_header(id_token)
    except JWTError as exc:
        raise OAuthProviderError("Invalid Google ID token") from exc

    kid = header.get("kid")
    jwks = _fetch_google_jwks()
    key = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if not key:
        raise OAuthProviderError("Google signing key not found")

    try:
        return jwt.decode(
            id_token,
            key,
            algorithms=["RS256"],
            audience=client_id,
            options={"verify_at_hash": False},
        )
    except JWTError as exc:
        raise OAuthProviderError("Google ID token validation failed") from exc


def exchange_google_code(
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> OAuthIdentity:
    client_id = settings.GOOGLE_CLIENT_ID
    client_secret = settings.GOOGLE_CLIENT_SECRET
    if not client_id or not client_secret:
        raise OAuthProviderError("Google OAuth is not configured on this server")

    try:
        response = requests.post(
            GOOGLE_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "code_verifier": code_verifier,
            },
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("Google token exchange request failed: %s", exc)
        raise OAuthProviderError() from exc

    if response.status_code != 200:
        logger.warning(
            "Google token exchange failed status=%s body=%s",
            response.status_code,
            response.text[:500],
        )
        raise OAuthProviderError()

    token_data = response.json()
    id_token = token_data.get("id_token")
    if not id_token:
        raise OAuthProviderError("Google token response missing id_token")

    claims = _verify_google_id_token(id_token, client_id)
    sub = claims.get("sub")
    if not sub:
        raise OAuthProviderError("Google ID token missing subject")

    return OAuthIdentity(
        provider="google",
        sub=str(sub),
        email=claims.get("email"),
        email_verified=bool(claims.get("email_verified")),
        name=claims.get("name"),
        picture=claims.get("picture"),
    )


def exchange_linkedin_code(
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> OAuthIdentity:
    client_id = (settings.LINKEDIN_CLIENT_ID or "").strip()
    client_secret = (settings.LINKEDIN_CLIENT_SECRET or "").strip()
    if not client_id or not client_secret:
        raise OAuthProviderError(
            "LinkedIn OAuth is not configured on this server",
            error_code="oauth_not_configured",
        )

    fp = linkedin_oauth_config_fingerprint()
    try:
        response, auth_method = _linkedin_token_exchange(
            code,
            redirect_uri,
            code_verifier,
            client_id,
            client_secret,
        )
    except requests.RequestException as exc:
        logger.warning("LinkedIn token exchange request failed: %s", exc)
        raise OAuthProviderError() from exc

    if response.status_code != 200:
        linkedin_error = ""
        try:
            linkedin_error = (response.json() or {}).get("error") or ""
        except Exception:
            pass
        logger.warning(
            "LinkedIn token exchange failed status=%s auth=%s client_id_prefix=%s "
            "secret_len=%s secret_fp=%s redirect_uri=%s code_len=%s verifier_len=%s body=%s",
            response.status_code,
            auth_method,
            fp.get("client_id_prefix"),
            fp.get("client_secret_length"),
            fp.get("client_secret_sha256_prefix"),
            redirect_uri,
            len(code or ""),
            len(code_verifier or ""),
            response.text[:500],
        )
        if linkedin_error == "invalid_client":
            raise OAuthProviderError(
                "LinkedIn rejected server credentials (invalid_client). "
                "LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET on this API host must "
                "match the same LinkedIn Developer Portal app as the mobile client ID.",
                error_code="oauth_provider_misconfigured",
            )
        raise OAuthProviderError()

    token_data = response.json()
    access_token = token_data.get("access_token")
    if not access_token:
        raise OAuthProviderError("LinkedIn token response missing access_token")

    id_token = token_data.get("id_token")
    if id_token:
        try:
            # LinkedIn OIDC id_token is a JWT; decode without signature verify then
            # confirm via userinfo for authoritative email/sub.
            claims = jwt.get_unverified_claims(id_token)
        except JWTError:
            claims = {}
    else:
        claims = {}

    try:
        userinfo_resp = requests.get(
            LINKEDIN_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.warning("LinkedIn userinfo request failed: %s", exc)
        raise OAuthProviderError() from exc

    if userinfo_resp.status_code != 200:
        logger.warning(
            "LinkedIn userinfo failed status=%s body=%s",
            userinfo_resp.status_code,
            userinfo_resp.text[:500],
        )
        raise OAuthProviderError()

    userinfo = userinfo_resp.json()
    sub = userinfo.get("sub") or claims.get("sub")
    if not sub:
        raise OAuthProviderError("LinkedIn userinfo missing subject")

    email_verified = userinfo.get("email_verified")
    if email_verified is None:
        email_verified = claims.get("email_verified", False)

    return OAuthIdentity(
        provider="linkedin",
        sub=str(sub),
        email=userinfo.get("email") or claims.get("email"),
        email_verified=bool(email_verified),
        name=userinfo.get("name") or claims.get("name"),
        picture=userinfo.get("picture") or claims.get("picture"),
    )


def resolve_oauth_identity(
    provider: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> OAuthIdentity:
    if provider == "google":
        return exchange_google_code(code, redirect_uri, code_verifier)
    if provider == "linkedin":
        return exchange_linkedin_code(code, redirect_uri, code_verifier)
    raise ValueError(f"Unsupported OAuth provider: {provider}")
