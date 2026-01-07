"""
User API routes
"""
import logging
from fastapi import APIRouter, status, Depends
from fastapi.responses import JSONResponse

from app.models.user import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
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
    
    logger.info(
        f"✓ New user registered: {user_response.email} (ID: {user_response.id})"
    )
    return user_response


@router.post(
    "/login",
    response_model=UserLoginResponse,
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
        
        return login_response
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
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )
        
        # Generate new access token
        token_data = {"sub": user_id, "email": payload.get("email", "")}
        new_access_token = create_access_token(data=token_data)
        
        return RefreshTokenResponse(
            access_token=new_access_token,
            token_type="bearer"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error refreshing token: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )


@router.get("/me", response_model=UserResponse)
async def get_current_user_endpoint(current_user: UserResponse = Depends(get_current_user)):
    """Get current authenticated user"""
    return current_user


@router.get("/email/{email}", response_model=UserResponse, dependencies=[])  # Public endpoint - no authentication required
async def get_user_by_email_endpoint(email: str):
    """Get user by email - PUBLIC ENDPOINT (no authentication required)"""
    logger.info(f"Get user by email request: {email}")
    try:
        result = get_user_by_email(email)
        logger.info(f"Successfully retrieved user by email: {email}")
        return result
    except Exception as e:
        logger.error(f"Error getting user by email {email}: {e}", exc_info=True)
        raise


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id_endpoint(user_id: str, current_user: UserResponse = Depends(get_current_user)):
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
async def update_user_endpoint(user_id: str, updates: UserUpdateRequest, current_user: UserResponse = Depends(get_current_user)):
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
async def delete_user_endpoint(user_id: str, current_user: UserResponse = Depends(get_current_user)):
    """Delete user"""
    result = delete_user(user_id)
    return JSONResponse(content=result)

