"""
Admin portal Pydantic models
"""
from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List
from datetime import datetime


class AdminLoginRequest(BaseModel):
    email: EmailStr
    password: str
    delivery_method: Optional[str] = "sms"


class AdminVerify2FARequest(BaseModel):
    user_id: str
    code: str


class AdminResendCodeRequest(BaseModel):
    user_id: str
    delivery_method: Optional[str] = "sms"


class AdminLoginResponse(BaseModel):
    requires_2fa: bool = True
    user_id: str
    delivery_method: str
    message: str


class AdminVerify2FAResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


class AdminUserSummary(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    isActive: bool
    lastLogin: Optional[datetime] = None
    subscriptionStatus: Optional[str] = None
    archived: Optional[bool] = False
    super_user: Optional[bool] = False


class AdminUserListResponse(BaseModel):
    users: List[AdminUserSummary]
    total: int
    page: int
    per_page: int
    pages: int


class AdminUserDetail(BaseModel):
    id: str
    name: str
    email: str
    isActive: bool
    isEmailVerified: bool
    roles: List[str]
    phone: Optional[str] = None
    address: Optional[dict] = None
    preferences: Optional[dict] = None
    avatarUrl: Optional[str] = None
    dateCreated: Optional[datetime] = None
    dateUpdated: Optional[datetime] = None
    lastLogin: Optional[datetime] = None
    llm_counts: Optional[dict] = None
    last_llm_used: Optional[str] = None
    generation_credits: int = Field(default=10, ge=0)
    max_credits: int = Field(default=10, ge=0)
    SMSOpt: Optional[str] = None
    SMSOptDate: Optional[datetime] = None
    subscriptionStatus: Optional[str] = None
    subscriptionPlan: Optional[str] = None
    subscriptionCurrentPeriodEnd: Optional[datetime] = None
    super_user: Optional[bool] = False
    archived: Optional[bool] = False
    stripeCustomerId: Optional[str] = None


class AdminUserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    isActive: Optional[bool] = None
    isEmailVerified: Optional[bool] = None
    roles: Optional[List[str]] = None
    address: Optional[dict] = None
    preferences: Optional[dict] = None
    avatarUrl: Optional[str] = None
    super_user: Optional[bool] = None
    generation_credits: Optional[int] = None
    max_credits: Optional[int] = None
    subscriptionStatus: Optional[str] = None
    subscriptionPlan: Optional[str] = None
