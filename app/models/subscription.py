"""
Subscription-related Pydantic models
"""
from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class SubscriptionResponse(BaseModel):
    """Subscription information response. Includes generation_credits/max_credits for free tier (per BACKEND_STRIPE_REQUIREMENTS).
    Frontend matches current plan by product_id and/or price_id (BACKEND_SUBSCRIPTION_IDS_REQUIREMENT)."""
    subscriptionId: Optional[str] = None
    subscriptionStatus: str = "free"  # free, active, canceled, past_due, trialing
    subscriptionPlan: Optional[str] = None  # "monthly", "annual", or "free" — frontend expects monthly/annual for paid
    productId: Optional[str] = None  # Stripe Product ID (for plan matching)
    priceId: Optional[str] = None  # Stripe Price ID (for plan matching; app matches by product_id or price_id)
    subscriptionCurrentPeriodEnd: Optional[datetime] = None
    subscriptionEndedAt: Optional[datetime] = None  # When subscription actually ended (for canceled subscriptions)
    lastPaymentDate: Optional[datetime] = None
    stripeCustomerId: Optional[str] = None
    generation_credits: Optional[int] = None  # Remaining credits (free and paid)
    max_credits: Optional[int] = None  # Max credits for tier


class CreatePaymentIntentRequest(BaseModel):
    """Request to create a PaymentIntent for PaymentSheet"""
    user_id: str
    price_id: str  # Stripe Price ID (e.g., price_xxx)


class CreatePaymentIntentResponse(BaseModel):
    """Response containing PaymentIntent details for PaymentSheet"""
    client_secret: str
    customer_id: Optional[str] = None
    customer_ephemeral_key_secret: Optional[str] = None


class SubscribeRequest(BaseModel):
    """Request to create a new subscription"""
    user_id: str
    price_id: str  # Stripe Price ID (e.g., price_xxx)
    payment_intent_id: Optional[str] = None  # PaymentIntent ID from PaymentSheet
    payment_method_id: Optional[str] = None  # Legacy support - for card payment
    trial_days: Optional[int] = None


class UpgradeRequest(BaseModel):
    """Request to upgrade subscription"""
    user_id: str
    new_price_id: str  # Stripe Price ID for the new plan


class CancelRequest(BaseModel):
    """Request to cancel subscription"""
    user_id: str
    cancel_immediately: bool = False  # If True, cancel immediately; if False, cancel at period end


class SubscriptionPlanFeature(BaseModel):
    """Feature included in a subscription plan"""
    feature: str


class SubscriptionPlan(BaseModel):
    """Subscription plan information"""
    id: str  # e.g., "monthly", "annual", or dynamically generated from product
    name: str  # e.g., "Monthly", "Annual", or product name
    interval: str  # "month" or "year"
    interval_count: Optional[int] = 1  # Number of intervals (e.g., 3 for "every 3 months")
    description: str
    priceId: str  # Stripe Price ID
    amount: Optional[float] = None  # Price amount (in currency units)
    currency: Optional[str] = None  # Currency code (e.g., "USD")
    productId: Optional[str] = None  # Stripe Product ID
    features: list[str]
    popular: Optional[bool] = False  # Mark recommended plan


class SubscriptionPlansResponse(BaseModel):
    """Response containing available subscription plans"""
    plans: list[SubscriptionPlan]


class MarketingFeature(BaseModel):
    """Marketing feature object from Stripe"""
    name: str


class StripeProductResponse(BaseModel):
    """Raw Stripe product structure"""
    id: str
    object: str = "product"
    active: bool
    attributes: list = []
    created: int
    default_price: Optional[str] = None
    description: Optional[str] = None
    images: list[str] = []
    livemode: bool = False
    marketing_features: Optional[list[MarketingFeature]] = None
    metadata: dict = {}
    name: str
    package_dimensions: Optional[dict] = None
    shippable: Optional[bool] = None
    statement_descriptor: Optional[str] = None
    tax_code: Optional[str] = None
    type: str = "service"
    unit_label: Optional[str] = None
    updated: int
    url: Optional[str] = None


class StripeProductsResponse(BaseModel):
    """Response containing raw Stripe products"""
    object: str = "list"
    data: list[StripeProductResponse]
    has_more: bool = False
    url: str = "/v1/products"


class PaymentIntentStatusResponse(BaseModel):
    """Response containing PaymentIntent status information"""
    payment_intent_id: str
    status: str  # succeeded, requires_action, processing, requires_payment_method
    client_secret: Optional[str] = None
    next_action: Optional[dict] = None  # For 3DS authentication
    message: str  # Human-readable status message
