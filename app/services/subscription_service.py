"""
Subscription service - Stripe integration for subscription management
"""

import logging
from typing import Optional
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException, status

try:
    import stripe

    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False

from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.utils.user_helpers import USERS_COLLECTION
from app.models.subscription import SubscriptionResponse

logger = logging.getLogger(__name__)

# Initialize Stripe
if STRIPE_AVAILABLE:
    # Use test key if available, otherwise use production key
    stripe_api_key = settings.STRIPE_TEST_API_KEY or settings.STRIPE_API_KEY
    if stripe_api_key:
        stripe.api_key = stripe_api_key
        logger.info("Stripe API key configured")
    else:
        logger.warning("Stripe API key not found in environment variables")


def get_user_subscription(user_id: str) -> SubscriptionResponse:
    """
    Get user's subscription information from database

    Args:
        user_id: User ID

    Returns:
        SubscriptionResponse with subscription details
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection",
        )

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    user = collection.find_one({"_id": user_id_obj})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return SubscriptionResponse(
        subscriptionId=user.get("subscriptionId"),
        subscriptionStatus=user.get("subscriptionStatus", "free"),
        subscriptionPlan=user.get("subscriptionPlan", "free"),
        subscriptionCurrentPeriodEnd=user.get("subscriptionCurrentPeriodEnd"),
        lastPaymentDate=user.get("lastPaymentDate"),
        stripeCustomerId=user.get("stripeCustomerId"),
    )


def update_user_subscription(
    user_id: str,
    subscription_id: Optional[str] = None,
    subscription_status: str = "free",
    subscription_plan: str = "free",
    stripe_customer_id: Optional[str] = None,
    current_period_end: Optional[datetime] = None,
    last_payment_date: Optional[datetime] = None,
) -> None:
    """
    Update user's subscription information in database

    Args:
        user_id: User ID
        subscription_id: Stripe subscription ID
        subscription_status: Subscription status
        subscription_plan: Subscription plan name
        stripe_customer_id: Stripe customer ID
        current_period_end: Current period end date
        last_payment_date: Last payment date
    """
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection",
        )

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    update_data = {
        "subscriptionId": subscription_id,
        "subscriptionStatus": subscription_status,
        "subscriptionPlan": subscription_plan,
        "subscriptionCurrentPeriodEnd": current_period_end,
        "lastPaymentDate": last_payment_date,
        "stripeCustomerId": stripe_customer_id,
        "dateUpdated": datetime.utcnow(),
    }

    # Remove None values
    update_data = {k: v for k, v in update_data.items() if v is not None}

    result = collection.update_one({"_id": user_id_obj}, {"$set": update_data})

    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    logger.info(f"Updated subscription for user {user_id}")


def create_stripe_customer(user_id: str, email: str, name: Optional[str] = None) -> str:
    """
    Create a Stripe customer for the user

    Args:
        user_id: User ID (used as metadata)
        email: User email
        name: User name (optional)

    Returns:
        Stripe customer ID
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe library not available"
        )

    try:
        customer = stripe.Customer.create(email=email, name=name, metadata={"user_id": user_id})
        logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
        return customer.id
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Stripe customer: {str(e)}",
        )


def create_payment_intent(user_id: str, price_id: str) -> dict:
    """
    Create a PaymentIntent for PaymentSheet subscription payment.
    This is PCI compliant - card data never touches our servers.

    Args:
        user_id: User ID
        price_id: Stripe Price ID

    Returns:
        Dictionary with client_secret, customer_id, and ephemeral_key_secret
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe library not available"
        )

    # Get user info
    collection = get_collection(USERS_COLLECTION)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection",
        )

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    user = collection.find_one({"_id": user_id_obj})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        # Get or create Stripe customer
        stripe_customer_id = user.get("stripeCustomerId")
        if not stripe_customer_id:
            stripe_customer_id = create_stripe_customer(
                user_id=user_id, email=user.get("email", ""), name=user.get("name")
            )
            # Update user with customer ID
            update_user_subscription(user_id=user_id, stripe_customer_id=stripe_customer_id)

        # Get price details
        price = stripe.Price.retrieve(price_id)

        # Create PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(price.unit_amount),  # Amount in cents
            currency=price.currency,
            customer=stripe_customer_id,
            payment_method_types=["card"],
            metadata={"user_id": user_id, "price_id": price_id, "subscription_type": "new"},
        )

        # Create ephemeral key for customer (allows PaymentSheet to access customer)
        ephemeral_key = stripe.EphemeralKey.create(
            customer=stripe_customer_id,
            stripe_version="2023-10-16",  # Use latest Stripe API version
        )

        logger.info(f"Created PaymentIntent {payment_intent.id} for user {user_id}")

        return {
            "client_secret": payment_intent.client_secret,
            "customer_id": stripe_customer_id,
            "customer_ephemeral_key_secret": ephemeral_key.secret,
        }

    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating payment intent: {e}")
        error_message = (
            str(e.user_message) if hasattr(e, "user_message") else "Payment processing failed"
        )
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": error_message,
                "stripe_error": {
                    "type": e.__class__.__name__,
                    "code": getattr(e, "code", None),
                    "message": str(e),
                },
            },
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment intent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment intent: {str(e)}",
        )


def create_subscription(
    user_id: str,
    price_id: str,
    customer_id: Optional[str] = None,
    payment_intent_id: Optional[str] = None,
    payment_method_id: Optional[str] = None,
    trial_days: Optional[int] = None,
) -> dict:
    """
    Create a new subscription in Stripe

    Args:
        user_id: User ID
        price_id: Stripe Price ID
        customer_id: Stripe customer ID (will create if not provided)
        payment_intent_id: PaymentIntent ID from PaymentSheet (preferred)
        payment_method_id: Payment method ID (legacy support)
        trial_days: Trial period in days (optional)

    Returns:
        Stripe subscription object
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe library not available"
        )

    # Get user info to create customer if needed
    collection = get_collection(USERS_COLLECTION)
    if not collection:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection",
        )

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    user = collection.find_one({"_id": user_id_obj})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get or create customer
    if not customer_id:
        customer_id = user.get("stripeCustomerId")
        if not customer_id:
            customer_id = create_stripe_customer(
                user_id=user_id, email=user.get("email", ""), name=user.get("name")
            )
            # Update user with customer ID
            update_user_subscription(user_id=user_id, stripe_customer_id=customer_id)

    if not customer_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Customer ID required")

    # Handle PaymentIntent flow (PaymentSheet)
    if payment_intent_id:
        try:
            # Retrieve PaymentIntent to get payment method
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)

            if payment_intent.status != "succeeded":
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED, detail="Payment not completed"
                )

            # Get payment method from PaymentIntent
            payment_method_id = payment_intent.payment_method

            if not payment_method_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment method not found in PaymentIntent",
                )

            # Attach payment method to customer
            stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)

            # Set as default payment method
            stripe.Customer.modify(
                customer_id, invoice_settings={"default_payment_method": payment_method_id}
            )

            payment_method_id = payment_method_id  # Use this for subscription

        except stripe.error.StripeError as e:
            logger.error(f"Stripe error processing payment intent: {e}")
            error_message = (
                str(e.user_message) if hasattr(e, "user_message") else "Payment processing failed"
            )
            raise HTTPException(
                status_code=status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message": error_message,
                    "stripe_error": {
                        "type": e.__class__.__name__,
                        "code": getattr(e, "code", None),
                        "message": str(e),
                    },
                },
            )

    try:
        subscription_params = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": {"user_id": user_id},
            "payment_behavior": "default_incomplete",
            "payment_settings": {
                "payment_method_types": ["card"],
                "save_default_payment_method": "on_subscription",
            },
            "expand": ["latest_invoice.payment_intent"],
        }

        if trial_days:
            subscription_params["trial_period_days"] = trial_days

        if payment_method_id:
            subscription_params["default_payment_method"] = payment_method_id

        subscription = stripe.Subscription.create(**subscription_params)

        # Note: PaymentIntent is already confirmed by PaymentSheet before this point
        # We just need to ensure the subscription uses the payment method from the PaymentIntent

        # Update user subscription info
        current_period_end = datetime.fromtimestamp(subscription.current_period_end)
        update_user_subscription(
            user_id=user_id,
            subscription_id=subscription.id,
            subscription_status=subscription.status,
            subscription_plan=price_id,  # Store price_id as plan identifier
            stripe_customer_id=customer_id,
            current_period_end=current_period_end,
        )

        logger.info(f"Created subscription {subscription.id} for user {user_id}")
        return subscription
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error creating subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subscription: {str(e)}",
        )


def upgrade_subscription(user_id: str, new_price_id: str) -> dict:
    """
    Upgrade user's subscription to a new plan

    Args:
        user_id: User ID
        new_price_id: New Stripe Price ID

    Returns:
        Updated Stripe subscription object
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe library not available"
        )

    # Get current subscription
    subscription_info = get_user_subscription(user_id)
    if not subscription_info.subscriptionId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active subscription",
        )

    try:
        # Retrieve current subscription
        subscription = stripe.Subscription.retrieve(subscription_info.subscriptionId)

        # Update subscription with new price
        updated_subscription = stripe.Subscription.modify(
            subscription.id,
            items=[
                {
                    "id": subscription["items"]["data"][0].id,
                    "price": new_price_id,
                }
            ],
            proration_behavior="always_invoice",  # Prorate and invoice immediately
            metadata={"user_id": user_id},
        )

        # Update user subscription info
        current_period_end = datetime.fromtimestamp(updated_subscription.current_period_end)
        update_user_subscription(
            user_id=user_id,
            subscription_id=updated_subscription.id,
            subscription_status=updated_subscription.status,
            subscription_plan=new_price_id,
            current_period_end=current_period_end,
        )

        logger.info(f"Upgraded subscription {updated_subscription.id} for user {user_id}")
        return updated_subscription
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error upgrading subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upgrade subscription: {str(e)}",
        )


def cancel_subscription(user_id: str, cancel_immediately: bool = False) -> dict:
    """
    Cancel user's subscription

    Args:
        user_id: User ID
        cancel_immediately: If True, cancel immediately; if False, cancel at period end

    Returns:
        Updated Stripe subscription object
    """
    if not STRIPE_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Stripe library not available"
        )

    # Get current subscription
    subscription_info = get_user_subscription(user_id)
    if not subscription_info.subscriptionId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active subscription",
        )

    try:
        if cancel_immediately:
            # Cancel immediately
            canceled_subscription = stripe.Subscription.delete(subscription_info.subscriptionId)
            subscription_status = "canceled"
        else:
            # Cancel at period end
            canceled_subscription = stripe.Subscription.modify(
                subscription_info.subscriptionId, cancel_at_period_end=True
            )
            subscription_status = canceled_subscription.status

        # Update user subscription info
        update_user_subscription(
            user_id=user_id,
            subscription_id=canceled_subscription.id,
            subscription_status=subscription_status,
            current_period_end=(
                datetime.fromtimestamp(canceled_subscription.current_period_end)
                if canceled_subscription.current_period_end
                else None
            ),
        )

        logger.info(
            f"Canceled subscription {canceled_subscription.id} for user {user_id} (immediately={cancel_immediately})"
        )
        return canceled_subscription
    except stripe.error.StripeError as e:
        logger.error(f"Stripe error canceling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel subscription: {str(e)}",
        )
