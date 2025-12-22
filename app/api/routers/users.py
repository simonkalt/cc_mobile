"""
User API routes
"""
import logging
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.models.user import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
)
from app.services.user_service import (
    register_user,
    get_user_by_id,
    get_user_by_email,
    update_user,
    delete_user,
    login_user,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user_endpoint(user_data: UserRegisterRequest):
    """Register a new user"""
    logger.info(f"User registration request: {user_data.email}")
    user_response = register_user(user_data)
    
    logger.info(
        f"✓ New user registered: {user_response.email} (ID: {user_response.id})"
    )
    return user_response


@router.post("/login", response_model=UserLoginResponse)
async def login_user_endpoint(login_data: UserLoginRequest):
    """Authenticate user login"""
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


@router.get("/{user_id}", response_model=UserResponse)
async def get_user_by_id_endpoint(user_id: str):
    """Get user by ID"""
    logger.info(f"Get user request: {user_id}")
    try:
        result = get_user_by_id(user_id)
        logger.info(f"Successfully retrieved user: {user_id}")
        return result
    except Exception as e:
        logger.error(f"Error getting user {user_id}: {e}", exc_info=True)
        raise


@router.get("/email/{email}", response_model=UserResponse)
async def get_user_by_email_endpoint(email: str):
    """Get user by email"""
    return get_user_by_email(email)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(user_id: str, updates: UserUpdateRequest):
    """Update user"""
    return update_user(user_id, updates)


@router.delete("/{user_id}")
async def delete_user_endpoint(user_id: str):
    """Delete user"""
    result = delete_user(user_id)
    return JSONResponse(content=result)

