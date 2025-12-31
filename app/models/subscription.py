"""
Subscription-related Pydantic models
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SubscriptionResponse(BaseModel):
    """Subscription information response"""
    subscriptionId: Optional[str] = None
    subscriptionStatus: str = "free"  # free, active, canceled, past_due, trialing
    subscriptionPlan: str = "free"  # free, basic, premium, enterprise
    subscriptionCurrentPeriodEnd: Optional[datetime] = None
    lastPaymentDate: Optional[datetime] = None
    stripeCustomerId: Optional[str] = None


class SubscribeRequest(BaseModel):
    """Request to create a new subscription"""
    user_id: str
    price_id: str  # Stripe Price ID (e.g., price_xxx)
    payment_method_id: Optional[str] = None  # For card payment
    trial_days: Optional[int] = None


class UpgradeRequest(BaseModel):
    """Request to upgrade subscription"""
    user_id: str
    new_price_id: str  # Stripe Price ID for the new plan


class CancelRequest(BaseModel):
    """Request to cancel subscription"""
    user_id: str
    cancel_immediately: bool = False  # If True, cancel immediately; if False, cancel at period end

