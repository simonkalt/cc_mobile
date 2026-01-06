"""
FastAPI dependencies for JWT authentication
"""
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.utils.jwt import verify_token
from app.services.user_service import get_user_by_id
from app.models.user import UserResponse

# HTTPBearer security scheme for FastAPI
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> UserResponse:
    """
    FastAPI dependency to get the current authenticated user from JWT token.
    
    Usage:
        @router.get("/protected")
        async def protected_route(current_user: UserResponse = Depends(get_current_user)):
            return {"user_id": current_user.id}
    
    Args:
        credentials: HTTPAuthorizationCredentials from the Authorization header
        
    Returns:
        UserResponse object for the authenticated user
        
    Raises:
        HTTPException: If token is invalid, expired, or user not found
    """
    token = credentials.credentials
    
    try:
        # Verify and decode the token
        payload = verify_token(token, token_type="access")
        
        # Extract user ID from token (standard JWT claim "sub" for subject)
        user_id: Optional[str] = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token missing user ID",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        # Get user from database
        user = get_user_by_id(user_id)
        
        # Check if user is active
        if not user.isActive:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User account is inactive"
            )
        
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def get_current_active_user(
    current_user: UserResponse = Depends(get_current_user)
) -> UserResponse:
    """
    FastAPI dependency to get the current active user.
    This is a convenience wrapper that ensures the user is active.
    
    Usage:
        @router.get("/protected")
        async def protected_route(user: UserResponse = Depends(get_current_active_user)):
            return {"user_id": user.id}
    
    Args:
        current_user: UserResponse from get_current_user dependency
        
    Returns:
        UserResponse object for the active user
        
    Raises:
        HTTPException: If user is not active
    """
    if not current_user.isActive:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    return current_user


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False))
) -> Optional[UserResponse]:
    """
    FastAPI dependency to optionally get the current user.
    Returns None if no token is provided (useful for endpoints that work with or without auth).
    
    Usage:
        @router.get("/public-or-protected")
        async def flexible_route(user: Optional[UserResponse] = Depends(get_optional_user)):
            if user:
                return {"message": f"Hello {user.name}"}
            return {"message": "Hello anonymous"}
    
    Args:
        credentials: Optional HTTPAuthorizationCredentials from the Authorization header
        
    Returns:
        UserResponse object if token is valid, None otherwise
    """
    if not credentials:
        return None
    
    try:
        token = credentials.credentials
        payload = verify_token(token, token_type="access")
        user_id: Optional[str] = payload.get("sub")
        
        if user_id:
            user = get_user_by_id(user_id)
            return user if user.isActive else None
    except Exception:
        # If anything fails, return None (optional auth)
        return None
    
    return None

