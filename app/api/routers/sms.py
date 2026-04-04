"""
SMS verification API routes
"""
import logging
from fastapi import APIRouter, Request, status, HTTPException
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
    verify_code,
    clear_verification_code,
)
from app.services.user_service import get_user_by_email, get_user_by_id
from app.db.mongodb import get_collection, is_connected
from app.utils.password import hash_password, validate_strong_password
from app.utils.user_helpers import USERS_COLLECTION
from app.utils.sms_utils import normalize_phone_number
from app.services.telnyx_webhook_service import store_telnyx_message
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/sms", tags=["sms"])


def _enforce_strong_password_or_raise(password: str) -> None:
    if not settings.ENFORCE_STRONG_PASSWORDS:
        return
    validation_error = validate_strong_password(password)
    if validation_error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=validation_error,
        )


@router.post("/webhook/telnyx")
async def telnyx_webhook(request: Request):
    """
    Webhook endpoint for Telnyx messaging events.
    Stores raw payload in MongoDB and returns quickly with a 2xx.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON")
    try:
        inserted_id = store_telnyx_message(body)
        if inserted_id is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database unavailable",
            )
        return {"ok": True, "id": inserted_id}
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to store message",
        )


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
    
    # Find user by email or phone.
    # NOTE: forgot_password intentionally surfaces 404 so the frontend can
    # keep the user on the send-code step.  This trades anti-enumeration for UX
    # and matches the email endpoint's behaviour.
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
    _enforce_strong_password_or_raise(request.new_password)
    
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
    _enforce_strong_password_or_raise(request.new_password)
    
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
    Complete registration by verifying code sent during registration
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
    
    logger.info(f"Registration completed for user {user.id}")
    
    return RegistrationCompleteResponse(
        success=True,
        message="Registration completed successfully"
    )

