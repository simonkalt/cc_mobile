"""
JWT token generation and verification utilities
"""

import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from fastapi import HTTPException, status
from app.core.config import settings

logger = None
try:
    import logging

    logger = logging.getLogger(__name__)
except:
    pass


def create_access_token(data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
    """
    Create a JWT access token

    Args:
        data: Dictionary containing user data to encode in the token (e.g., {"sub": user_id, "email": email})
        expires_delta: Optional timedelta for token expiration. If None, uses default from settings.

    Returns:
        Encoded JWT token string

    Raises:
        ValueError: If JWT_SECRET_KEY is not configured
    """
    # Validate JWT secret key is configured
    if (
        not settings.JWT_SECRET_KEY
        or settings.JWT_SECRET_KEY == "your-secret-key-change-in-production"
    ):
        error_msg = "JWT_SECRET_KEY is not properly configured. Please set it in your environment variables."
        if logger:
            logger.error(error_msg)
        raise ValueError(error_msg)

    to_encode = data.copy()

    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "access"})

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        if not encoded_jwt:
            raise ValueError("jwt.encode returned None or empty string")

        return encoded_jwt
    except Exception as e:
        if logger:
            logger.error(f"Error encoding access token: {e}", exc_info=True)
        raise ValueError(f"Failed to create access token: {str(e)}")


def create_refresh_token(data: Dict[str, Any]) -> str:
    """
    Create a JWT refresh token

    Args:
        data: Dictionary containing user data to encode in the token

    Returns:
        Encoded JWT refresh token string

    Raises:
        ValueError: If JWT_SECRET_KEY is not configured
    """
    # Validate JWT secret key is configured
    if (
        not settings.JWT_SECRET_KEY
        or settings.JWT_SECRET_KEY == "your-secret-key-change-in-production"
    ):
        error_msg = "JWT_SECRET_KEY is not properly configured. Please set it in your environment variables."
        if logger:
            logger.error(error_msg)
        raise ValueError(error_msg)

    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)

    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "type": "refresh"})

    try:
        encoded_jwt = jwt.encode(
            to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM
        )

        if not encoded_jwt:
            raise ValueError("jwt.encode returned None or empty string")

        return encoded_jwt
    except Exception as e:
        if logger:
            logger.error(f"Error encoding refresh token: {e}", exc_info=True)
        raise ValueError(f"Failed to create refresh token: {str(e)}")


def verify_token(token: str, token_type: str = "access") -> Dict[str, Any]:
    """
    Verify and decode a JWT token

    Args:
        token: JWT token string to verify
        token_type: Expected token type ("access" or "refresh")

    Returns:
        Decoded token payload as dictionary

    Raises:
        HTTPException: If token is invalid, expired, or wrong type
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Reject empty or obviously invalid token format (JWT has 3 base64 segments separated by dots)
    if not token or not isinstance(token, str):
        if logger:
            logger.error("JWT verification error: token missing or not a string")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization token is missing. Send header: Authorization: Bearer <access_token>",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = token.strip()
    if not token or token.count(".") != 2:
        if logger:
            logger.error("JWT verification error: Not enough segments")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token format. Use the access token from login in header: Authorization: Bearer <access_token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])

        # Verify token type
        token_type_in_payload = payload.get("type")
        if token_type_in_payload != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type. Expected {token_type}, got {token_type_in_payload}",
                headers={"WWW-Authenticate": "Bearer"},
            )

        return payload

    except JWTError as e:
        if logger:
            logger.error(f"JWT verification error: {e}")
        raise credentials_exception
    except Exception as e:
        if logger:
            logger.error(f"Token verification error: {e}")
        raise credentials_exception


def get_user_id_from_token(token: str) -> Optional[str]:
    """
    Extract user ID from a JWT token

    Args:
        token: JWT token string

    Returns:
        User ID string or None if not found
    """
    try:
        payload = verify_token(token)
        user_id = payload.get("sub")  # "sub" is the standard JWT claim for subject (user ID)
        return user_id
    except HTTPException:
        return None
