"""
Subscription-related Pydantic models
"""
from pydantic import AliasChoices, BaseModel, ConfigDict, Field, computed_field, model_validator
from typing import Optional
from datetime import datetime


class SubscriptionResponse(BaseModel):
    """Subscription information response"""

    model_config = ConfigDict(populate_by_name=True)

    billingProvider: Optional[str] = None  # "stripe" | "apple" when subscribed; null/omitted for free
    appleProductId: Optional[str] = None
    subscriptionId: Optional[str] = None
    subscriptionStatus: str = "free"  # free or Stripe-native status (active, trialing, incomplete, ...)
    subscriptionPlan: str = "free"  # free, basic, premium, enterprise
    productId: Optional[str] = None  # Stripe Product ID
    priceId: Optional[str] = None  # Stripe Price ID
    subscriptionCurrentPeriodEnd: Optional[datetime] = None
    cancelAtPeriodEnd: Optional[bool] = None
    canceledAt: Optional[datetime] = None
    lastPaymentDate: Optional[datetime] = None
    stripeCustomerId: Optional[str] = None
    generation_credits: int = Field(default=10, ge=0)
    max_credits: int = Field(default=10, ge=0)
    # Unified entitlement fields (BILLING_API_CONTRACT.md).
    # Optional so older mobile clients that don't read them stay compatible.
    entitlement_active: Optional[bool] = None
    can_initiate_new_paid_subscription: Optional[bool] = None
    cross_platform_billing: Optional[bool] = None
    entitlement_source: Optional[str] = None
    # Unified plan identity — works across Apple and Stripe.
    planKey: Optional[str] = None
    planRank: Optional[int] = None
    # iOS / Apple — resolved from Mongo ``subscription_product_catalog``.
    applePlanKey: Optional[str] = None
    applePlanRank: Optional[int] = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def billing_provider(self) -> Optional[str]:
        """Snake_case duplicate of ``billingProvider`` (BILLING_API_CONTRACT)."""
        return self.billingProvider

    @computed_field  # type: ignore[prop-decorator]
    @property
    def apple_plan_key(self) -> Optional[str]:
        return self.applePlanKey

    @computed_field  # type: ignore[prop-decorator]
    @property
    def apple_plan_rank(self) -> Optional[int]:
        return self.applePlanRank

    @computed_field  # type: ignore[prop-decorator]
    @property
    def product_id(self) -> Optional[str]:
        """Snake_case duplicate of ``productId`` (BILLING_API_CONTRACT)."""
        return self.productId


class AppleCatalogProductItem(BaseModel):
    """One row from Mongo iOS/Apple subscription_product_catalog.products."""

    productId: Optional[str] = None
    planKey: Optional[str] = None
    rank: Optional[int] = None
    enabled: bool = True
    label: Optional[str] = None


class AppleCatalogResponse(BaseModel):
    """Response for GET /api/subscriptions/apple/catalog."""

    products: list[AppleCatalogProductItem]
    environment: Optional[str] = None  # catalog doc environment used (production | sandbox)


class CreatePaymentIntentRequest(BaseModel):
    """Request to create a PaymentIntent for PaymentSheet"""
    user_id: str
    price_id: str  # Stripe Price ID (e.g., price_xxx)


class CreatePaymentIntentResponse(BaseModel):
    """Response containing PaymentIntent details for PaymentSheet"""
    client_secret: Optional[str] = None
    customer_id: Optional[str] = None
    customer_ephemeral_key_secret: Optional[str] = None
    subscription_id: Optional[str] = None
    payment_intent_id: Optional[str] = None
    already_active: Optional[bool] = False


class SubscribeRequest(BaseModel):
    """Request to create a new subscription"""
    user_id: str
    price_id: str  # Stripe Price ID (e.g., price_xxx)
    subscription_id: Optional[str] = None  # Preferred for PaymentSheet finalize flow
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
    tier: Optional[int] = 0  # Access tier: 0 = public, 100+ = super_user only


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
    prices: Optional[list[dict]] = None


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


class PurchaseEligibilityResponse(BaseModel):
    """Response for GET /api/subscriptions/purchase-eligibility."""

    can_initiate_new_paid_subscription: bool
    reason: str  # "free" | "already_entitled" | "lapsed"
    billing_provider: Optional[str] = None


class AppleSubscriptionVerifyRequest(BaseModel):
    """Verify a StoreKit 2 transaction JWS and grant subscription entitlement.

    Mobile may send snake_case (contract) or camelCase; both are accepted for interoperability.
    Optional ``product_id`` / ``transaction_id`` / ``original_transaction_id`` are cross-checked
    against Apple's verified transaction payload when provided.
    """

    model_config = ConfigDict(populate_by_name=True)

    user_id: str
    signed_transaction: str = Field(
        ...,
        validation_alias=AliasChoices("signed_transaction", "signedTransaction"),
        description="StoreKit JWS string (signedTransaction / purchaseToken from the client).",
    )
    product_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("product_id", "productId"),
    )
    transaction_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices("transaction_id", "transactionId"),
    )
    original_transaction_id: Optional[str] = Field(
        None,
        validation_alias=AliasChoices(
            "original_transaction_id", "originalTransactionId"
        ),
    )


class AppleSubscriptionVerifyResponse(BaseModel):
    """Response after successful Apple subscription verification.

    ``data`` mirrors ``subscription`` when omitted so clients that unwrap ``data``
    (BILLING_API_CONTRACT.md) work without change.
    """

    ok: bool = True
    subscription: SubscriptionResponse
    data: Optional[SubscriptionResponse] = None

    @model_validator(mode="after")
    def _data_defaults_to_subscription(self):
        if self.data is None:
            object.__setattr__(self, "data", self.subscription)
        return self
