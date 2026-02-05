"""
User API routes
"""

import logging
from fastapi import APIRouter, status, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.models.user import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    SMSOptRequest,
)
from app.core.auth import get_current_user
from app.utils.jwt import create_access_token, verify_token
from app.services.user_service import (
    register_user,
    get_user_by_id,
    get_user_by_email,
    update_user,
    delete_user,
    login_user,
    set_sms_opt,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/users",
    tags=["users"],
    # No router-level dependencies - protect endpoints individually
)


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[],  # Explicitly mark as public - no authentication required
)
async def register_user_endpoint(user_data: UserRegisterRequest):
    """Register a new user"""
    logger.info(f"User registration request: {user_data.email}")
    user_response = register_user(user_data)

    logger.info(f"✓ New user registered: {user_response.email} (ID: {user_response.id})")
    return user_response


@router.post(
    "/login",
    # Removed response_model to avoid FastAPI re-serialization that might strip tokens
    # We manually return JSONResponse with all fields included
    dependencies=[],  # Explicitly mark as public - no authentication required
)
async def login_user_endpoint(login_data: UserLoginRequest):
    """Authenticate user login - PUBLIC ENDPOINT (no auth required)"""
    logger.info(f"Login attempt: {login_data.email}")
    try:
        login_response = login_user(login_data)

        if login_response.success and login_response.user:
            logger.info("=" * 80)
            logger.info(f"✓ USER LOGGED IN SUCCESSFULLY")
            logger.info(f"  User ID: {login_response.user.id}")
            logger.info(f"  Name: {login_response.user.name}")
            logger.info(f"  Email: {login_response.user.email}")
            logger.info("=" * 80)

        # Log token values for debugging
        logger.info(f"Access token present: {login_response.access_token is not None}")
        logger.info(f"Refresh token present: {login_response.refresh_token is not None}")
        if login_response.access_token:
            logger.info(f"Access token length: {len(login_response.access_token)}")
        if login_response.refresh_token:
            logger.info(f"Refresh token length: {len(login_response.refresh_token)}")

        # Explicitly serialize to ensure all fields (including tokens) are included
        # Use mode='json' for proper datetime serialization and exclude_none=False to include all fields
        response_dict = login_response.model_dump(mode="json", exclude_none=False)

        # Verify tokens are present before returning
        if not response_dict.get("access_token") or not response_dict.get("refresh_token"):
            logger.error(f"Tokens missing in login response for {login_data.email}")
            logger.error(f"Response keys: {list(response_dict.keys())}")
            logger.error(f"Access token in dict: {response_dict.get('access_token')}")
            logger.error(f"Refresh token in dict: {response_dict.get('refresh_token')}")
            logger.error(f"Full response_dict: {response_dict}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication tokens",
            )

        # Explicitly ensure tokens are in the response (defensive programming)
        response_dict["access_token"] = login_response.access_token
        response_dict["refresh_token"] = login_response.refresh_token
        response_dict["token_type"] = login_response.token_type

        logger.info(f"Final response keys: {list(response_dict.keys())}")
        return JSONResponse(content=response_dict, status_code=status.HTTP_200_OK)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during login for {login_data.email}: {e}", exc_info=True)
        raise


@router.post(
    "/refresh-token",
    response_model=RefreshTokenResponse,
    dependencies=[],  # Explicitly mark as public - no authentication required
)
async def refresh_token_endpoint(request: RefreshTokenRequest):
    """
    Refresh access token using refresh token.

    Request Body:
    {
        "refresh_token": "your_refresh_token_here"
    }
    """
    try:
        # Verify refresh token
        payload = verify_token(request.refresh_token, token_type="refresh")
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
            )

        # Generate new access token
        token_data = {"sub": user_id, "email": payload.get("email", "")}
        new_access_token = create_access_token(data=token_data)

        return RefreshTokenResponse(access_token=new_access_token, token_type="bearer")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_endpoint(current_user: UserResponse = Depends(get_current_user)):
    """Get current authenticated user"""
    return current_user


@router.put("/me/sms-opt", response_model=UserResponse)
async def set_sms_opt_endpoint(
    body: SMSOptRequest, current_user: UserResponse = Depends(get_current_user)
):
    """
    Set SMS opt-in or opt-out for the current user.
    Persists SMSOpt ('IN' or 'OUT') and SMSOptDate (timestamp) to the database.
    """
    return set_sms_opt(current_user.id, body.SMSOpt)


@router.get(
    "/email/{email}",
    dependencies=[],  # Public endpoint - no authentication required
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
)
async def get_user_by_email_endpoint(email: str):
    """
    Get user by email - PUBLIC ENDPOINT (no authentication required)

    This endpoint allows checking if a user exists by email address.
    It is public and does not require authentication.

    Args:
        email: User's email address (URL encoded)

    Returns:
        UserResponse: User object if found (200 OK)

    Raises:
        HTTPException 404: User not found
        HTTPException 503: Database unavailable
    """
    try:
        result = get_user_by_email(email)
        return result
    except HTTPException as e:
        # Re-raise HTTPException as-is (404 for not found, 503 for service unavailable)
        # Don't log 404s - they're expected when checking if user exists
        if e.status_code != status.HTTP_404_NOT_FOUND:
            logger.warning(
                f"HTTPException getting user by email {email}: {e.status_code} - {e.detail}"
            )
        raise
    except Exception as e:
        logger.error(f"Error getting user by email {email}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while retrieving user information",
        )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id_endpoint(
    user_id: str, current_user: UserResponse = Depends(get_current_user)
):
    """Get user by ID"""
    logger.info(f"Get user request: {user_id}")
    try:
        result = get_user_by_id(user_id)
        logger.info(f"Successfully retrieved user: {user_id}")
        return result
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}", exc_info=True)
        raise


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(
    user_id: str, updates: UserUpdateRequest, current_user: UserResponse = Depends(get_current_user)
):
    """Update user"""
    # Log what's being updated, especially personalityProfiles
    if updates.preferences and isinstance(updates.preferences, dict):
        app_settings = updates.preferences.get("appSettings", {})
        if isinstance(app_settings, dict) and "personalityProfiles" in app_settings:
            personality_profiles = app_settings["personalityProfiles"]
            logger.info(
                f"Update request for user {user_id} includes personalityProfiles: "
                f"type={type(personality_profiles)}, "
                f"length={len(personality_profiles) if isinstance(personality_profiles, list) else 'N/A'}, "
                f"value={personality_profiles}"
            )
        else:
            logger.debug(f"Update request for user {user_id} does not include personalityProfiles")
    else:
        logger.debug(f"Update request for user {user_id} does not include preferences")

    return update_user(user_id, updates)


@router.delete("/{user_id}")
async def delete_user_endpoint(
    user_id: str, current_user: UserResponse = Depends(get_current_user)
):
    """Delete user"""
    result = delete_user(user_id)
    return JSONResponse(content=result)
