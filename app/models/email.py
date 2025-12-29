"""
Email verification related Pydantic models
"""
from pydantic import BaseModel, EmailStr
from typing import Optional


class SendVerificationCodeRequest(BaseModel):
    """Request to send verification code via email"""
    email: EmailStr
    purpose: str  # "forgot_password", "change_password", "finish_registration"


class VerifyCodeRequest(BaseModel):
    """Request to verify code sent via email"""
    email: EmailStr
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

