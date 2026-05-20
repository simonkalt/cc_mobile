"""
Identity-provider token exchange and ID token / userinfo validation for OAuth login.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

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

    def __init__(self, message: str = "Invalid authorization code") -> None:
        super().__init__(message)
        self.message = message


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
    client_id = settings.LINKEDIN_CLIENT_ID
    client_secret = settings.LINKEDIN_CLIENT_SECRET
    if not client_id or not client_secret:
        raise OAuthProviderError("LinkedIn OAuth is not configured on this server")

    try:
        response = requests.post(
            LINKEDIN_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
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
        logger.warning("LinkedIn token exchange request failed: %s", exc)
        raise OAuthProviderError() from exc

    if response.status_code != 200:
        logger.warning(
            "LinkedIn token exchange failed status=%s body=%s",
            response.status_code,
            response.text[:500],
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
