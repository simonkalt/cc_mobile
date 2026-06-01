"""
User API routes
"""
import logging
from datetime import UTC, datetime
import time
from typing import Any, Dict

from fastapi import APIRouter, status, Depends, HTTPException, Request, Body
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from bson import ObjectId

from app.core.auth import (
    get_current_user,
    get_current_user_allow_pending_account_deletion,
    _verify_token,
    assert_token_not_invalidated,
)
from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.utils.user_helpers import USERS_COLLECTION

from app.models.oauth import (
    AppleOAuthLinkRequest,
    OAuthLinkResponse,
    OAuthTokenExchangeRequest,
)
from app.models.user import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
    OAuthRegistrationSendCodeRequest,
    OAuthRegistrationCompleteRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    AccountDeletionRequestResponse,
)
from app.services.oauth_login_service import (
    apple_oauth_link_provider,
    oauth_link_provider,
    oauth_unlink_provider,
)
from app.services.oauth_registration_service import (
    complete_oauth_registration,
    send_oauth_registration_verification_code,
)
from app.services.account_deletion_service import create_account_deletion_request
from app.services.user_service import (
    register_user,
    get_user_by_id,
    get_user_by_email,
    update_user,
    delete_user,
    login_user,
    _make_signed_token,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/users", tags=["users"])


class SMSOptRequest(BaseModel):
    SMSOpt: str


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


@router.post("/refresh-token", response_model=RefreshTokenResponse)
async def refresh_token_endpoint(request: RefreshTokenRequest):
    """Refresh access token using a valid refresh token."""
    payload = _verify_token(request.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )
    assert_token_not_invalidated(user_id, payload)
    now = int(time.time())
    access_ttl_seconds = 24 * 60 * 60
    access_payload = {
        "sub": user_id,
        "email": payload.get("email", ""),
        "type": "access",
        "iat": now,
        "exp": now + access_ttl_seconds,
    }
    if settings.JWT_ISSUER:
        access_payload["iss"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        access_payload["aud"] = settings.JWT_AUDIENCE
    jwt_secret = settings.JWT_SECRET
    new_access_token = _make_signed_token(access_payload, jwt_secret)
    return RefreshTokenResponse(access_token=new_access_token, token_type="bearer")


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


@router.get("/me", response_model=UserResponse)
async def get_current_user_endpoint(current_user: UserResponse = Depends(get_current_user)):
    """Get current authenticated user"""
    return get_user_by_id(current_user.id)


@router.post(
    "/me/link-oauth/apple",
    response_model=OAuthLinkResponse,
)
async def link_oauth_apple_endpoint(
    body: AppleOAuthLinkRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Link Sign in with Apple to the authenticated user (native identity token)."""
    logger.info("OAuth link request provider=apple user_id=%s", current_user.id)
    return apple_oauth_link_provider(current_user, body)


@router.post(
    "/me/link-oauth/{provider}",
    response_model=OAuthLinkResponse,
)
async def link_oauth_provider_endpoint(
    provider: str,
    body: OAuthTokenExchangeRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Link Google or LinkedIn to the authenticated user (PKCE code exchange)."""
    logger.info("OAuth link request provider=%s user_id=%s", provider, current_user.id)
    return oauth_link_provider(current_user, provider, body)


@router.delete(
    "/me/link-oauth/{provider}",
    response_model=OAuthLinkResponse,
)
async def unlink_oauth_provider_endpoint(
    provider: str,
    current_user: UserResponse = Depends(get_current_user),
):
    """Disconnect Google, LinkedIn, or Apple from the authenticated user."""
    logger.info("OAuth unlink request provider=%s user_id=%s", provider, current_user.id)
    return oauth_unlink_provider(current_user, provider)


@router.post("/me/oauth-registration/send-verification-code", status_code=status.HTTP_200_OK)
async def oauth_registration_send_code_endpoint(
    body: OAuthRegistrationSendCodeRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Send email/SMS verification code while OAuth registration is pending."""
    return send_oauth_registration_verification_code(
        current_user.id,
        delivery_method=body.delivery_method,
        phone=body.phone,
    )


@router.post("/me/oauth-registration/complete", response_model=UserResponse)
async def oauth_registration_complete_endpoint(
    body: OAuthRegistrationCompleteRequest,
    current_user: UserResponse = Depends(get_current_user),
):
    """Terms, verification, phone, and SMS consent — required after OAuth sign-up."""
    return complete_oauth_registration(
        current_user.id,
        code=body.code,
        terms_of_service_accepted=body.termsOfServiceAccepted,
        phone=body.phone,
        sms_opt_in=body.smsOptIn,
        delivery_method=body.delivery_method,
    )


@router.post(
    "/me/account-deletion-request",
    response_model=AccountDeletionRequestResponse,
    status_code=status.HTTP_200_OK,
)
async def account_deletion_request_endpoint(
    request: Request,
    _body: Dict[str, Any] = Body(default_factory=dict),
    current_user: UserResponse = Depends(get_current_user_allow_pending_account_deletion),
):
    """
    Self-service deferred account deletion (identified from JWT only).
    See documents/ACCOUNT_DELETION_API.md.
    """
    forwarded = request.headers.get("x-forwarded-for")
    client_ip = None
    if forwarded:
        client_ip = forwarded.split(",")[0].strip()
    if not client_ip and request.client:
        client_ip = request.client.host
    user_agent = request.headers.get("user-agent")
    return create_account_deletion_request(
        current_user.id,
        current_user.email,
        current_user.name,
        source="mobile_app",
        client_ip=client_ip,
        user_agent=user_agent,
        is_super_user=bool(current_user.super_user),
    )


@router.put("/me/sms-opt", response_model=UserResponse)
async def set_sms_opt_endpoint(
    body: SMSOptRequest, current_user: UserResponse = Depends(get_current_user)
):
    """
    Set SMS opt-in/out for current user.
    Persists SMSOpt ('IN' or 'OUT') and SMSOptDate timestamp.
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection",
        )

    sms_opt = (body.SMSOpt or "").strip().upper()
    if sms_opt not in {"IN", "OUT"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SMSOpt must be either 'IN' or 'OUT'",
        )

    collection.update_one(
        {"_id": ObjectId(current_user.id)},
        {"$set": {"SMSOpt": sms_opt, "SMSOptDate": datetime.now(UTC)}},
    )
    return get_user_by_id(current_user.id)


@router.put("/{user_id}", response_model=UserResponse)
async def update_user_endpoint(user_id: str, updates: UserUpdateRequest):
    """Update user"""
    # Log what's being updated, especially personalityProfiles
    if updates.preferences and isinstance(updates.preferences, dict):
        app_settings = updates.preferences.get("appSettings", {})
        if isinstance(app_settings, dict) and "personalityProfiles" in app_settings:
            personality_profiles = app_settings["personalityProfiles"]
            logger.info(
                f"Update request for user {user_id} includes personalityProfiles "
                f"type={type(personality_profiles)}, "
                f"length={len(personality_profiles) if isinstance(personality_profiles, list) else 'N/A'}"
            )
        else:
            logger.debug(f"Update request for user {user_id} does not include personalityProfiles")
    else:
        logger.debug(f"Update request for user {user_id} does not include preferences")
    
    return update_user(user_id, updates)


@router.delete("/{user_id}")
async def delete_user_endpoint(user_id: str):
    """Delete user"""
    result = delete_user(user_id)
    return JSONResponse(content=result)

