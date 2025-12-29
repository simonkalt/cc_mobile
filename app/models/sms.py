"""
SMS verification related Pydantic models
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, Dict, Any


class SendVerificationCodeRequest(BaseModel):
    """Request to send verification code"""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    purpose: str  # "forgot_password", "change_password", "finish_registration"
    registration_data: Optional[Dict[str, Any]] = None  # For finish_registration flow
    delivery_method: Optional[str] = "sms"  # "email" or "sms"


class VerifyCodeRequest(BaseModel):
    """Request to verify code"""
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    code: str
    purpose: str  # "forgot_password", "change_password", "finish_registration"


class ResetPasswordRequest(BaseModel):
    """Request to reset password (forgot password flow)"""
    email: EmailStr
    code: str
    new_password: str


class ChangePasswordRequest(BaseModel):
    """Request to change password (requires verification code)"""
    user_id: str
    code: str
    new_password: str


class CompleteRegistrationRequest(BaseModel):
    """Request to complete registration with verification code"""
    email: EmailStr
    code: str


class SendVerificationCodeResponse(BaseModel):
    """Response after sending verification code"""
    success: bool
    message: str
    expires_in_minutes: int = 10


class VerifyCodeResponse(BaseModel):
    """Response after verifying code"""
    success: bool
    message: str
    verified: bool = False


class PasswordResetResponse(BaseModel):
    """Response after password reset"""
    success: bool
    message: str


class PasswordChangeResponse(BaseModel):
    """Response after password change"""
    success: bool
    message: str


class RegistrationCompleteResponse(BaseModel):
    """Response after completing registration"""
    success: bool
    message: str

