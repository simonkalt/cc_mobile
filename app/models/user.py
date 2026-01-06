"""
User-related Pydantic models
"""
from pydantic import BaseModel, EmailStr
from typing import Optional, List
from datetime import datetime


# Nested Models for Preferences
class PrintMargins(BaseModel):
    top: Optional[float] = 1.0
    right: Optional[float] = 0.75
    bottom: Optional[float] = 0.25
    left: Optional[float] = 0.75


class PageSize(BaseModel):
    width: Optional[float] = 8.5
    height: Optional[float] = 11.0


class PrintProperties(BaseModel):
    margins: Optional[PrintMargins] = None
    fontFamily: Optional[str] = "Georgia"
    fontSize: Optional[float] = 11.0
    lineHeight: Optional[float] = 1.15
    pageSize: Optional[PageSize] = None
    useDefaultFonts: Optional[bool] = False


class PersonalityProfile(BaseModel):
    id: str
    name: str
    description: str


class AppSettings(BaseModel):
    printProperties: Optional[PrintProperties] = None
    personalityProfiles: Optional[List[PersonalityProfile]] = None
    selectedModel: Optional[str] = None
    lastResumeUsed: Optional[str] = None
    last_personality_profile_used: Optional[str] = None


class UserPreferences(BaseModel):
    newsletterOptIn: Optional[bool] = False
    theme: Optional[str] = "light"
    appSettings: Optional[AppSettings] = None


# Request Models
class UserRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    address: Optional[dict] = None
    preferences: Optional[dict] = None


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    isActive: Optional[bool] = None
    isEmailVerified: Optional[bool] = None
    roles: Optional[List[str]] = None
    address: Optional[dict] = None
    preferences: Optional[dict] = None
    avatarUrl: Optional[str] = None
    last_llm_used: Optional[str] = None


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


# Response Models
class UserResponse(BaseModel):
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
    dateCreated: datetime
    dateUpdated: datetime
    lastLogin: Optional[datetime] = None
    llm_counts: Optional[dict] = None
    last_llm_used: Optional[str] = None
    generation_credits: Optional[int] = None
    max_credits: Optional[int] = None
    # Subscription fields
    subscriptionId: Optional[str] = None
    subscriptionStatus: Optional[str] = "free"  # free, active, canceled, past_due, trialing
    subscriptionPlan: Optional[str] = "free"  # free, basic, premium, enterprise
    subscriptionCurrentPeriodEnd: Optional[datetime] = None
    lastPaymentDate: Optional[datetime] = None
    stripeCustomerId: Optional[str] = None

    class Config:
        from_attributes = True


class UserLoginResponse(BaseModel):
    success: bool
    user: Optional[UserResponse] = None
    message: str
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

