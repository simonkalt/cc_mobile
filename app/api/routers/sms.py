"""
SMS verification API routes
"""
import logging
from fastapi import APIRouter, status, HTTPException
from bson import ObjectId

from app.models.sms import (
    SendVerificationCodeRequest,
    VerifyCodeRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    CompleteRegistrationRequest,
    SendVerificationCodeResponse,
    VerifyCodeResponse,
    PasswordResetResponse,
    PasswordChangeResponse,
    RegistrationCompleteResponse,
)
from app.services.verification_service import (
    send_and_store_verification_code,
    send_and_store_verification_code_email,
    verify_code,
    verify_code_from_redis,
    complete_registration_from_redis,
    clear_verification_code,
)
from app.services.user_service import get_user_by_email, get_user_by_id, create_user_from_registration_data
from app.utils.redis_utils import delete_registration_data, delete_verification_session
from app.db.mongodb import get_collection, is_connected
from app.utils.password import hash_password
from app.utils.user_helpers import USERS_COLLECTION
from app.utils.sms_utils import normalize_phone_number

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sms", tags=["sms"])


@router.post("/send-code", response_model=SendVerificationCodeResponse)
async def send_verification_code_endpoint(request: SendVerificationCodeRequest):
    """
    Send verification code via SMS
    
    Supports:
    - forgot_password: Send code to reset password
    - change_password: Send code to change password
    - finish_registration: Send code to complete registration
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    # Validate purpose
    valid_purposes = ["forgot_password", "change_password", "finish_registration"]
    if request.purpose not in valid_purposes:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid purpose. Must be one of: {', '.join(valid_purposes)}"
        )
    
    # Handle registration flow (uses Redis)
    if request.purpose == "finish_registration" and request.registration_data:
        # Require email for registration
        if not request.email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email is required for registration"
            )
        
        # Check if user already exists
        try:
            existing_user = get_user_by_email(request.email)
            # User exists, can't register again
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User with this email already exists"
            )
        except HTTPException as e:
            if e.status_code == status.HTTP_404_NOT_FOUND:
                # User doesn't exist, proceed with registration
                pass
            else:
                raise
        
        # Get phone number from registration data or request
        phone_number = request.phone or request.registration_data.get("phone")
        if not phone_number:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Phone number is required for SMS registration"
            )
        
        # Send and store verification code with registration data in Redis
        # Use email function but with SMS delivery method
        try:
            send_and_store_verification_code_email(
                user_id=None,  # No user_id for registration flow
                email=request.email,
                purpose=request.purpose,
                registration_data=request.registration_data,
                delivery_method="sms"  # Force SMS for SMS router
            )
            
            logger.info(f"Verification code sent via SMS for registration: {request.email}")
            
            return SendVerificationCodeResponse(
                success=True,
                message="Verification code sent successfully",
                expires_in_minutes=10
            )
        except Exception as e:
            logger.error(f"Error sending verification code for registration: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to send verification code: {str(e)}"
            )
    
    # Handle existing user flows (forgot_password, change_password)
    # Find user by email or phone
    user = None
    if request.email:
        try:
            user = get_user_by_email(request.email)
        except HTTPException:
            # For forgot_password, don't reveal if user exists
            if request.purpose == "forgot_password":
                # Return success even if user doesn't exist (security best practice)
                return SendVerificationCodeResponse(
                    success=True,
                    message="If an account exists with this email, a verification code has been sent.",
                    expires_in_minutes=10
                )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
    elif request.phone:
        # Find user by phone number
        normalized_phone = normalize_phone_number(request.phone)
        user_doc = collection.find_one({"phone": normalized_phone})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = get_user_by_id(str(user_doc["_id"]))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone must be provided"
        )
    
    # Get phone number
    phone_number = user.phone
    if not phone_number:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have a phone number registered"
        )
    
    # Send and store verification code
    try:
        send_and_store_verification_code(
            user_id=user.id,
            phone_number=phone_number,
            purpose=request.purpose
        )
        
        logger.info(f"Verification code sent to user {user.id} for purpose: {request.purpose}")
        
        return SendVerificationCodeResponse(
            success=True,
            message="Verification code sent successfully",
            expires_in_minutes=10
        )
    except Exception as e:
        logger.error(f"Error sending verification code: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to send verification code: {str(e)}"
        )


@router.post("/verify-code", response_model=VerifyCodeResponse)
async def verify_code_endpoint(request: VerifyCodeRequest):
    """
    Verify a code
    
    Supports:
    - forgot_password: Verify code for password reset
    - change_password: Verify code for password change
    - finish_registration: Verify code for registration completion
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    # Find user
    user = None
    if request.email:
        user = get_user_by_email(request.email)
    elif request.phone:
        normalized_phone = normalize_phone_number(request.phone)
        user_doc = collection.find_one({"phone": normalized_phone})
        if not user_doc:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        user = get_user_by_id(str(user_doc["_id"]))
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either email or phone must be provided"
        )
    
    # Verify code
    is_valid = verify_code(user.id, request.code, request.purpose)
    
    if is_valid:
        return VerifyCodeResponse(
            success=True,
            message="Code verified successfully",
            verified=True
        )
    else:
        return VerifyCodeResponse(
            success=False,
            message="Invalid or expired code",
            verified=False
        )


@router.post("/reset-password", response_model=PasswordResetResponse)
async def reset_password_endpoint(request: ResetPasswordRequest):
    """
    Reset password using verification code (forgot password flow)
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    # Get user
    user = get_user_by_email(request.email)
    
    # Verify code
    if not verify_code(user.id, request.code, "forgot_password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )
    
    # Update password
    from datetime import datetime
    
    hashed_password = hash_password(request.new_password)
    
    collection.update_one(
        {"_id": ObjectId(user.id)},
        {
            "$set": {
                "hashedPassword": hashed_password,
                "passwordChangedAt": datetime.utcnow()
            },
            "$unset": {"verification_code": ""}
        }
    )
    
    logger.info(f"Password reset for user {user.id}")
    
    return PasswordResetResponse(
        success=True,
        message="Password reset successfully"
    )


@router.post("/change-password", response_model=PasswordChangeResponse)
async def change_password_endpoint(request: ChangePasswordRequest):
    """
    Change password using verification code
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    # Get user
    user = get_user_by_id(request.user_id)
    
    # Verify code
    if not verify_code(user.id, request.code, "change_password"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )
    
    # Update password
    from datetime import datetime
    
    hashed_password = hash_password(request.new_password)
    
    collection.update_one(
        {"_id": ObjectId(user.id)},
        {
            "$set": {
                "hashedPassword": hashed_password,
                "passwordChangedAt": datetime.utcnow()
            },
            "$unset": {"verification_code": ""}
        }
    )
    
    logger.info(f"Password changed for user {user.id}")
    
    return PasswordChangeResponse(
        success=True,
        message="Password changed successfully"
    )


@router.post("/complete-registration", response_model=RegistrationCompleteResponse)
async def complete_registration_endpoint(request: CompleteRegistrationRequest):
    """
    Complete registration by verifying code and creating user from Redis data
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    # Check if user already exists (shouldn't happen, but safety check)
    try:
        existing_user = get_user_by_email(request.email)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    except HTTPException as e:
        if e.status_code != status.HTTP_404_NOT_FOUND:
            raise
    
    # Verify code and get registration data from Redis
    try:
        registration_data = complete_registration_from_redis(request.email, request.code)
        
        # Verify the session exists
        session_data = verify_code_from_redis(request.email, request.code, "finish_registration")
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid or expired verification code"
            )
        
        # Create user from registration data
        user = create_user_from_registration_data(
            registration_data=registration_data,
            is_email_verified=True  # Mark as verified since they completed verification
        )
        
        # Clean up Redis entries
        delete_registration_data(request.email, request.code)
        delete_verification_session(request.email, request.code, "finish_registration")
        
        logger.info(f"Registration completed via SMS for user {user.id}")
        
        return RegistrationCompleteResponse(
            success=True,
            message="Registration completed successfully"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error completing registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete registration: {str(e)}"
        )

