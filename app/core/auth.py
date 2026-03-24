"""
Authentication dependencies for protected API routes.
Compatible with the JWT-like HMAC tokens returned by login_user().
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.models.user import UserResponse
from app.services.user_service import get_user_by_id


security = HTTPBearer()


def _secure_string_compare(a: Optional[str], b: Optional[str]) -> bool:
    """Constant-time comparison for secret strings (same length only)."""
    if a is None or b is None:
        return False
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def verify_service_auth(
    x_service_auth: Optional[str] = Header(
        None,
        description="Shared secret for server-to-server integration",
    ),
) -> None:
    """
    Validate X-Service-Auth against settings.SERVICE_AUTH_KEY.
    Use for third-party or internal services that must not use end-user JWTs.
    """
    if not settings.SERVICE_AUTH_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service authentication is not configured on this server",
        )
    if not _secure_string_compare(x_service_auth, settings.SERVICE_AUTH_KEY):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-Service-Auth header",
        )


def _b64url_decode(value: str) -> bytes:
    """Decode base64url value with missing padding support."""
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def _verify_token(token: str) -> Dict[str, Any]:
    """
    Verify HS256-signed token and return payload.
    Expected compact form: <header>.<payload>.<signature>
    """
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid token format")

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
        expected_sig = hmac.new(
            settings.JWT_SECRET.encode("utf-8"),
            signing_input,
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

        if not hmac.compare_digest(signature_b64, expected_sig_b64):
            raise ValueError("Invalid token signature")

        # Parse payload
        payload = json.loads(_b64url_decode(payload_b64).decode("utf-8"))

        # Basic expiration check
        exp = payload.get("exp")
        if isinstance(exp, (int, float)) and int(exp) < int(time.time()):
            raise ValueError("Token expired")

        if settings.JWT_VALIDATE_ISSUER and settings.JWT_ISSUER:
            if payload.get("iss") != settings.JWT_ISSUER:
                raise ValueError("Invalid token issuer")

        if settings.JWT_VALIDATE_AUDIENCE and settings.JWT_AUDIENCE:
            aud = payload.get("aud")
            if isinstance(aud, list):
                if settings.JWT_AUDIENCE not in aud:
                    raise ValueError("Invalid token audience")
            elif aud != settings.JWT_AUDIENCE:
                raise ValueError("Invalid token audience")

        return payload
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> UserResponse:
    """Resolve authenticated user from bearer token."""
    payload = _verify_token(credentials.credentials)
    user_id: Optional[str] = payload.get("sub")

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing user ID",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_user_by_id(user_id)
    if not user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive",
        )
    return user

