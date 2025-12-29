"""
Email verification API routes
"""
import logging
from fastapi import APIRouter, status, HTTPException
from bson import ObjectId

from app.models.email import (
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
    send_and_store_verification_code_email,
    verify_code,
    clear_verification_code,
)
from app.services.user_service import get_user_by_email, get_user_by_id
from app.db.mongodb import get_collection, is_connected
from app.utils.password import hash_password
from app.utils.user_helpers import USERS_COLLECTION

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/email", tags=["email"])


@router.post("/send-code", response_model=SendVerificationCodeResponse)
async def send_verification_code_endpoint(request: SendVerificationCodeRequest):
    """
    Send verification code via email
    
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
    
    # Find user by email
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
    
    # Send and store verification code
    try:
        send_and_store_verification_code_email(
            user_id=user.id,
            email=request.email,
            purpose=request.purpose
        )
        
        logger.info(f"Verification code sent via email to user {user.id} for purpose: {request.purpose}")
        
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
    Verify a code sent via email
    
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
    
    # Find user by email
    user = get_user_by_email(request.email)
    
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
    
    logger.info(f"Password reset via email for user {user.id}")
    
    return PasswordResetResponse(
        success=True,
        message="Password reset successfully"
    )


@router.post("/change-password", response_model=PasswordChangeResponse)
async def change_password_endpoint(request: ChangePasswordRequest):
    """
    Change password using verification code sent via email
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
    
    logger.info(f"Password changed via email for user {user.id}")
    
    return PasswordChangeResponse(
        success=True,
        message="Password changed successfully"
    )


@router.post("/complete-registration", response_model=RegistrationCompleteResponse)
async def complete_registration_endpoint(request: CompleteRegistrationRequest):
    """
    Complete registration by verifying code sent via email during registration
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
    if not verify_code(user.id, request.code, "finish_registration"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired verification code"
        )
    
    # Mark email as verified and clear verification code
    from datetime import datetime
    
    collection.update_one(
        {"_id": ObjectId(user.id)},
        {
            "$set": {
                "isEmailVerified": True,
                "dateUpdated": datetime.utcnow()
            },
            "$unset": {"verification_code": ""}
        }
    )
    
    logger.info(f"Registration completed via email for user {user.id}")
    
    return RegistrationCompleteResponse(
        success=True,
        message="Registration completed successfully"
    )

