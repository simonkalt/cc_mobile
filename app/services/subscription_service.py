"""
Subscription service - Stripe integration for subscription management
"""

import logging
from typing import Optional, Dict, List
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException, status

try:
    import stripe  # type: ignore[import-untyped]

    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    stripe = None  # type: ignore[assignment]

from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.utils.user_helpers import USERS_COLLECTION
from app.models.subscription import SubscriptionResponse

logger = logging.getLogger(__name__)

# Stripe API version - must be consistent across all endpoints
STRIPE_API_VERSION = "2023-10-16"

# Simple in-memory cache for Stripe products/prices
_stripe_plans_cache: Optional[Dict] = None
_stripe_plans_cache_time: Optional[datetime] = None
_stripe_plans_cache_ttl: timedelta = timedelta(minutes=5)  # Cache for 5 minutes


def _get_stripe_module():
    """
    Helper function to get the Stripe module dynamically.
    Avoids scope issues with local imports.

    Returns:
        Stripe module or None if not available
    """
    import importlib
    import sys

    if STRIPE_AVAILABLE:
        # stripe is already available at module level - get it via sys.modules to avoid scope issues
        stripe_module = sys.modules.get("stripe")
        if stripe_module is None:
            # Fallback: import it
            stripe_module = importlib.import_module("stripe")
        # Ensure API key is set - prioritize production key over test key
        stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
        if stripe_api_key:
            stripe_module.api_key = stripe_api_key
            # Set API version for consistency
            stripe_module.api_version = STRIPE_API_VERSION
        return stripe_module
    else:
        # Try runtime import in case Stripe was installed after server startup
        try:
            stripe_module = importlib.import_module("stripe")
            # Set API key if available - prioritize production key over test key
            stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
            if stripe_api_key:
                stripe_module.api_key = stripe_api_key
                # Set API version for consistency
                stripe_module.api_version = STRIPE_API_VERSION
            return stripe_module
        except ImportError:
            return None


# Initialize Stripe
if STRIPE_AVAILABLE:
    # Prioritize production key over test key
    stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
    if stripe_api_key:
        stripe.api_key = stripe_api_key
        # Set global Stripe API version for consistency across all endpoints
        stripe.api_version = STRIPE_API_VERSION
        # Log which key type is being used (without exposing the key)
        key_type = "production" if settings.STRIPE_API_KEY else "test"
        logger.info(
            f"Stripe API key configured ({key_type} mode), API version: {STRIPE_API_VERSION}"
        )
        # Verify the key format (sk_ = secret, rk_ = restricted; _live_ or _test_)
        if stripe_api_key.startswith("sk_live_") or stripe_api_key.startswith("rk_live_"):
            logger.info("Using Stripe PRODUCTION API key")
        elif stripe_api_key.startswith("sk_test_") or stripe_api_key.startswith("rk_test_"):
            logger.info("Using Stripe TEST API key (or restricted test key)")
        else:
            logger.warning(
                f"Stripe API key format unexpected (starts with: {stripe_api_key[:7]}...)"
            )
    else:
        logger.warning(
            "Stripe API key not found in environment variables (STRIPE_TEST_API_KEY or STRIPE_API_KEY)"
        )
else:
    logger.warning("Stripe library not available - subscription features will not work")


def _price_id_to_plan_name(price_id: Optional[str]) -> str:
    """Map Stripe price_id to frontend plan name 'monthly' | 'annual' per BACKEND_STRIPE_REQUIREMENTS."""
    if not price_id:
        return "free"
    if settings.STRIPE_PRICE_ID_MONTHLY and price_id == settings.STRIPE_PRICE_ID_MONTHLY:
        return "monthly"
    if settings.STRIPE_PRICE_ID_ANNUAL and price_id == settings.STRIPE_PRICE_ID_ANNUAL:
        return "annual"
    return price_id


def get_user_subscription(user_id: str) -> SubscriptionResponse:
    """
    Get user's subscription information from database, automatically syncing with Stripe.

    This function:
    1. Reads subscription data from MongoDB
    2. Verifies subscription status with Stripe
    3. Automatically updates MongoDB if there's a mismatch

    Args:
        user_id: User ID

    Returns:
        SubscriptionResponse with subscription details (synced with Stripe)
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

    # Get current subscription data from MongoDB
    mongo_subscription_id = user.get("subscriptionId")
    mongo_status = user.get("subscriptionStatus", "free")
    mongo_plan = user.get("subscriptionPlan", "free")
    product_id = user.get("subscriptionProductId")
    price_id = user.get("subscriptionPriceId") or (
        mongo_plan if mongo_plan and str(mongo_plan).startswith("price_") else None
    )
    stripe_customer_id = user.get("stripeCustomerId")
    current_period_end = user.get("subscriptionCurrentPeriodEnd")
    subscription_ended_at = user.get("subscriptionEndedAt")
    last_payment_date = user.get("lastPaymentDate")

    # Map Stripe statuses to our internal statuses
    def map_stripe_status(stripe_status: str) -> str:
        """Map Stripe subscription status to our internal status."""
        status_map = {
            "active": "active",
            "trialing": "active",
            "past_due": "past_due",
            "canceled": "canceled",
            "unpaid": "canceled",
            "incomplete": "canceled",
            "incomplete_expired": "canceled",
        }
        return status_map.get(stripe_status, "free")

    # Verify subscription status with Stripe if we have Stripe available
    if STRIPE_AVAILABLE:
        stripe_to_use = _get_stripe_module()
        if stripe_to_use:
            # Case 1: We have a subscription ID in MongoDB - verify it exists and check status
            if mongo_subscription_id:
                try:
                    logger.debug(
                        f"Verifying subscription {mongo_subscription_id} with Stripe for user {user_id}"
                    )
                    subscription = stripe_to_use.Subscription.retrieve(
                        mongo_subscription_id, expand=["items.data.price.product"]
                    )

                    # Subscription exists in Stripe - get its status
                    stripe_status = subscription.status
                    expected_status = map_stripe_status(stripe_status)
                    stripe_period_end = (
                        datetime.fromtimestamp(subscription.current_period_end)
                        if subscription.current_period_end
                        else None
                    )
                    # Get ended_at if subscription is canceled
                    stripe_ended_at = (
                        datetime.fromtimestamp(subscription.ended_at)
                        if hasattr(subscription, "ended_at") and subscription.ended_at
                        else None
                    )

                    # Get product_id and price_id from subscription (for frontend plan matching)
                    items_data = (
                        subscription.items.data if hasattr(subscription.items, "data") else []
                    )
                    if items_data and len(items_data) > 0:
                        price_obj = items_data[0].price
                        if not price_id and hasattr(price_obj, "id"):
                            price_id = price_obj.id if isinstance(price_obj.id, str) else str(price_obj)

                        if not product_id:
                            # Try to get product ID from expanded price object
                            if hasattr(price_obj, "product") and price_obj.product:
                                if isinstance(price_obj.product, str):
                                    product_id = price_obj.product
                                elif hasattr(price_obj.product, "id"):
                                    product_id = price_obj.product.id

                            # If not expanded, retrieve price separately
                            if not product_id and price_id:
                                try:
                                    price = stripe_to_use.Price.retrieve(
                                        price_id, expand=["product"]
                                    )
                                    if hasattr(price, "product"):
                                        if isinstance(price.product, str):
                                            product_id = price.product
                                        elif hasattr(price.product, "id"):
                                            product_id = price.product.id
                                except Exception as e:
                                    logger.debug(f"Could not retrieve price {price_id}: {e}")

                    # Check if MongoDB status matches Stripe status
                    if mongo_status != expected_status:
                        logger.warning(
                            f"Subscription status mismatch for user {user_id}: "
                            f"MongoDB={mongo_status}, Stripe={stripe_status} (expected={expected_status}). "
                            f"Updating MongoDB to match Stripe."
                        )

                        # Update MongoDB to match Stripe
                        update_user_subscription(
                            user_id=user_id,
                            subscription_id=mongo_subscription_id,
                            subscription_status=expected_status,
                            subscription_plan=mongo_plan,  # Keep existing plan name
                            subscription_product_id=product_id,
                            subscription_price_id=price_id,
                            current_period_end=stripe_period_end,
                            subscription_ended_at=stripe_ended_at,
                        )

                        # Update local variables to return correct data
                        mongo_status = expected_status
                        current_period_end = stripe_period_end
                        subscription_ended_at = stripe_ended_at

                    # Always use Stripe's current_period_end for response (BACKEND_SUBSCRIPTION_IDS_REQUIREMENT §4)
                    if stripe_period_end is not None:
                        current_period_end = stripe_period_end
                    if stripe_ended_at is not None:
                        subscription_ended_at = stripe_ended_at

                    # Persist product_id and price_id if we found them (for frontend plan matching)
                    updates = {}
                    if product_id and not user.get("subscriptionProductId"):
                        updates["subscriptionProductId"] = product_id
                    if price_id and not user.get("subscriptionPriceId"):
                        updates["subscriptionPriceId"] = price_id
                    if updates:
                        collection.update_one({"_id": user_id_obj}, {"$set": updates})

                except Exception as e:
                    # Check if subscription doesn't exist in Stripe
                    error_str = str(e).lower()
                    if (
                        "no such subscription" in error_str
                        or "resource_missing" in error_str
                        or "does not exist" in error_str
                    ):
                        logger.warning(
                            f"Subscription {mongo_subscription_id} does not exist in Stripe for user {user_id}. "
                            f"Updating MongoDB to reflect this."
                        )

                        # Subscription doesn't exist in Stripe - set to free
                        update_user_subscription(
                            user_id=user_id,
                            subscription_id=None,
                            subscription_status="free",
                            subscription_plan="free",
                        )

                        # Update local variables
                        mongo_subscription_id = None
                        mongo_status = "free"
                        mongo_plan = "free"
                        current_period_end = None
                    else:
                        # Some other error - log it but continue with MongoDB data
                        logger.error(
                            f"Error verifying subscription {mongo_subscription_id} with Stripe for user {user_id}: {e}",
                            exc_info=True,
                        )

            # Case 2: No subscription ID in MongoDB, but we have a Stripe customer ID
            # Check if there are any active subscriptions in Stripe
            elif stripe_customer_id and mongo_status == "free":
                try:
                    logger.debug(
                        f"Checking for active subscriptions in Stripe for customer {stripe_customer_id}"
                    )
                    subscriptions = stripe_to_use.Subscription.list(
                        customer=stripe_customer_id, status="all", limit=10
                    )

                    # Find active subscriptions
                    active_subscriptions = [
                        s
                        for s in subscriptions.data
                        if s.status in ["active", "trialing", "past_due"]
                    ]

                    if active_subscriptions:
                        # Found active subscription in Stripe but not in MongoDB
                        subscription = active_subscriptions[0]  # Use the first active one
                        logger.warning(
                            f"Found active subscription {subscription.id} in Stripe for user {user_id} "
                            f"but MongoDB shows 'free'. Updating MongoDB."
                        )

                        # Get product ID
                        items_data = (
                            subscription.items.data if hasattr(subscription.items, "data") else []
                        )
                        if items_data and len(items_data) > 0:
                            price_obj = items_data[0].price
                            if not price_id and hasattr(price_obj, "id"):
                                price_id = price_obj.id if isinstance(price_obj.id, str) else str(price_obj)
                            if hasattr(price_obj, "product") and price_obj.product:
                                if isinstance(price_obj.product, str):
                                    product_id = price_obj.product
                                elif hasattr(price_obj.product, "id"):
                                    product_id = price_obj.product.id

                        stripe_period_end = (
                            datetime.fromtimestamp(subscription.current_period_end)
                            if subscription.current_period_end
                            else None
                        )
                        stripe_ended_at = (
                            datetime.fromtimestamp(subscription.ended_at)
                            if hasattr(subscription, "ended_at") and subscription.ended_at
                            else None
                        )

                        # Update MongoDB with active subscription
                        update_user_subscription(
                            user_id=user_id,
                            subscription_id=subscription.id,
                            subscription_status=map_stripe_status(subscription.status),
                            subscription_plan=mongo_plan,  # Keep existing plan or could try to determine from product
                            subscription_product_id=product_id,
                            subscription_price_id=price_id,
                            current_period_end=stripe_period_end,
                            subscription_ended_at=stripe_ended_at,
                        )

                        # Update local variables
                        mongo_subscription_id = subscription.id
                        mongo_status = map_stripe_status(subscription.status)
                        current_period_end = stripe_period_end
                        subscription_ended_at = stripe_ended_at

                except Exception as e:
                    # Error checking Stripe - log but continue with MongoDB data
                    logger.debug(
                        f"Error checking Stripe subscriptions for customer {stripe_customer_id}: {e}"
                    )

    # Map stored plan (may be price_id) to frontend-friendly "monthly" | "annual" per BACKEND_STRIPE_REQUIREMENTS
    display_plan = mongo_plan
    if mongo_plan and mongo_plan not in ("free", "monthly", "annual"):
        if settings.STRIPE_PRICE_ID_MONTHLY and mongo_plan == settings.STRIPE_PRICE_ID_MONTHLY:
            display_plan = "monthly"
        elif settings.STRIPE_PRICE_ID_ANNUAL and mongo_plan == settings.STRIPE_PRICE_ID_ANNUAL:
            display_plan = "annual"
    if mongo_status == "free":
        display_plan = None  # Doc: free tier returns subscriptionPlan null

    # Credits: include for free and paid so frontend can show them (BACKEND_STRIPE_REQUIREMENTS)
    generation_credits = user.get("generation_credits")
    max_credits = user.get("max_credits")
    if generation_credits is None:
        generation_credits = 10
    if max_credits is None:
        max_credits = 10

    return SubscriptionResponse(
        subscriptionId=mongo_subscription_id,
        subscriptionStatus=mongo_status,
        subscriptionPlan=display_plan,
        productId=product_id,
        priceId=price_id,
        subscriptionCurrentPeriodEnd=current_period_end,
        subscriptionEndedAt=subscription_ended_at,
        lastPaymentDate=last_payment_date,
        stripeCustomerId=stripe_customer_id,
        generation_credits=generation_credits,
        max_credits=max_credits,
    )


def update_user_subscription(
    user_id: str,
    subscription_id: Optional[str] = None,
    subscription_status: str = "free",
    subscription_plan: str = "free",
    subscription_product_id: Optional[str] = None,
    subscription_price_id: Optional[str] = None,
    stripe_customer_id: Optional[str] = None,
    current_period_end: Optional[datetime] = None,
    subscription_ended_at: Optional[datetime] = None,
    last_payment_date: Optional[datetime] = None,
) -> None:
    """
    Update user's subscription information in database

    Args:
        user_id: User ID
        subscription_id: Stripe subscription ID
        subscription_status: Subscription status
        subscription_plan: Subscription plan name
        subscription_product_id: Stripe Product ID
        subscription_price_id: Stripe Price ID (for frontend plan matching)
        stripe_customer_id: Stripe customer ID
        current_period_end: Current period end date
        subscription_ended_at: When subscription actually ended (for canceled subscriptions)
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
        "subscriptionProductId": subscription_product_id,
        "subscriptionPriceId": subscription_price_id,
        "subscriptionCurrentPeriodEnd": current_period_end,
        "subscriptionEndedAt": subscription_ended_at,
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
    # Use _get_stripe_module() to ensure API key is properly configured
    stripe_to_use = _get_stripe_module()

    if stripe_to_use is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe library not available. Please ensure stripe>=7.0.0 is installed: pip install stripe>=7.0.0",
        )

    # Verify API key is set
    if not stripe_to_use.api_key:
        stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
        if not stripe_api_key:
            logger.error("Stripe API key not configured (STRIPE_API_KEY or STRIPE_TEST_API_KEY)")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe API key not configured. Please set STRIPE_API_KEY or STRIPE_TEST_API_KEY in environment variables.",
            )
        stripe_to_use.api_key = stripe_api_key
        logger.debug("Stripe API key set in create_stripe_customer")

    try:
        customer = stripe_to_use.Customer.create(
            email=email, name=name, metadata={"user_id": user_id}
        )
        logger.info(f"Created Stripe customer {customer.id} for user {user_id}")
        return customer.id
    except stripe_to_use.error.StripeError as e:
        logger.error(f"Stripe error creating customer: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create Stripe customer: {str(e)}",
        )


def get_payment_intent_status(payment_intent_id: str) -> dict:
    """
    Get the status of a PaymentIntent.
    Used by frontend to check payment status after confirmation.

    Args:
        payment_intent_id: Stripe PaymentIntent ID

    Returns:
        Dictionary with payment intent status and details
    """
    stripe_to_use = _get_stripe_module()

    if stripe_to_use is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe library not available. Please ensure stripe>=7.0.0 is installed: pip install stripe>=7.0.0",
        )

    if not stripe_to_use.api_key:
        stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
        if not stripe_api_key:
            logger.error("Stripe API key not configured (STRIPE_API_KEY or STRIPE_TEST_API_KEY)")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe API key not configured. Please set STRIPE_API_KEY or STRIPE_TEST_API_KEY in environment variables.",
            )
        stripe_to_use.api_key = stripe_api_key

    try:
        payment_intent = stripe_to_use.PaymentIntent.retrieve(payment_intent_id)

        status_messages = {
            "succeeded": "Payment completed successfully",
            "requires_action": "Payment requires additional authentication (3D Secure)",
            "processing": "Payment is being processed",
            "requires_payment_method": "Payment failed. Please try a different payment method",
            "canceled": "Payment was canceled",
        }

        result = {
            "payment_intent_id": payment_intent.id,
            "status": payment_intent.status,
            "client_secret": payment_intent.client_secret,
            "message": status_messages.get(
                payment_intent.status, f"Payment status: {payment_intent.status}"
            ),
        }

        # Add next_action if present (for 3DS)
        if hasattr(payment_intent, "next_action") and payment_intent.next_action:
            result["next_action"] = {
                "type": payment_intent.next_action.type,
                "redirect_to_url": getattr(payment_intent.next_action, "redirect_to_url", None),
            }

        # Add payment method info if available
        if payment_intent.payment_method:
            result["payment_method_id"] = (
                payment_intent.payment_method
                if isinstance(payment_intent.payment_method, str)
                else payment_intent.payment_method.id
            )

        return result

    except stripe_to_use.error.InvalidRequestError as e:
        logger.error(f"Invalid PaymentIntent ID: {e}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"PaymentIntent not found: {str(e)}",
        )
    except stripe_to_use.error.StripeError as e:
        logger.error(f"Stripe error retrieving PaymentIntent: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve PaymentIntent: {str(e)}",
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
    # Use _get_stripe_module() to ensure API key is properly configured
    stripe_to_use = _get_stripe_module()

    if stripe_to_use is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe module could not be loaded. Please ensure stripe>=7.0.0 is installed: pip install stripe>=7.0.0",
        )

    # Verify API key is set
    if not stripe_to_use.api_key:
        stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
        if not stripe_api_key:
            logger.error("Stripe API key not configured (STRIPE_API_KEY or STRIPE_TEST_API_KEY)")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe API key not configured. Please set STRIPE_API_KEY or STRIPE_TEST_API_KEY in environment variables.",
            )
        stripe_to_use.api_key = stripe_api_key
        logger.debug("Stripe API key set in create_payment_intent")

    # Use stripe_to_use throughout the function to avoid scope issues

    if not is_connected():
        logger.error("Database connection unavailable")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    # Get user info - check database first to avoid PyMongo collection bool() issue
    from app.db.mongodb import get_database

    db = get_database()
    if db is None:
        logger.error("MongoDB database not initialized")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    collection = get_collection(USERS_COLLECTION)

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
            # No customer ID in database - create new customer
            stripe_customer_id = create_stripe_customer(
                user_id=user_id, email=user.get("email", ""), name=user.get("name")
            )
            # Update user with customer ID
            update_user_subscription(user_id=user_id, stripe_customer_id=stripe_customer_id)
        else:
            # Customer ID exists in database - verify it exists in Stripe
            try:
                stripe_to_use.Customer.retrieve(stripe_customer_id)
                logger.debug(
                    f"Verified existing Stripe customer {stripe_customer_id} for user {user_id}"
                )
            except stripe_to_use.error.InvalidRequestError as e:
                # Customer doesn't exist in Stripe (maybe deleted or wrong account)
                if "No such customer" in str(e) or e.code == "resource_missing":
                    logger.warning(
                        f"Customer {stripe_customer_id} not found in Stripe for user {user_id}, creating new customer"
                    )
                    stripe_customer_id = create_stripe_customer(
                        user_id=user_id, email=user.get("email", ""), name=user.get("name")
                    )
                    # Update user with new customer ID
                    update_user_subscription(user_id=user_id, stripe_customer_id=stripe_customer_id)
                else:
                    # Some other error - re-raise it
                    raise

        # Get price details
        price = stripe_to_use.Price.retrieve(price_id)

        # Create PaymentIntent
        # setup_future_usage='off_session' forces the payment method to be saved
        # and allows it to be used for future subscription renewals
        # confirmation_method='automatic' allows PaymentSheet to confirm automatically
        payment_intent = stripe_to_use.PaymentIntent.create(
            amount=int(price.unit_amount),  # Amount in cents
            currency=price.currency,
            customer=stripe_customer_id,
            payment_method_types=["card"],
            setup_future_usage="off_session",  # Force save payment method for future use
            confirmation_method="automatic",  # Allow PaymentSheet to confirm automatically
            metadata={"user_id": user_id, "price_id": price_id, "subscription_type": "new"},
        )

        # Create ephemeral key for customer (allows PaymentSheet to access customer)
        ephemeral_key = stripe_to_use.EphemeralKey.create(
            customer=stripe_customer_id,
            stripe_version=STRIPE_API_VERSION,  # Use consistent Stripe API version
        )

        logger.info(f"Created PaymentIntent {payment_intent.id} for user {user_id}")

        response_data = {
            "client_secret": payment_intent.client_secret,
            "customer_id": stripe_customer_id,
            "customer_ephemeral_key_secret": ephemeral_key.secret,
        }

        # Validate all required fields are present
        if not response_data.get("client_secret"):
            logger.error("PaymentIntent missing client_secret!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="PaymentIntent created but missing client_secret",
            )
        if not response_data.get("customer_id"):
            logger.error("Response missing customer_id!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Customer ID missing from response",
            )
        if not response_data.get("customer_ephemeral_key_secret"):
            logger.error("Response missing customer_ephemeral_key_secret!")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Ephemeral key missing from response",
            )

        logger.info(f"Payment intent response validated - all fields present")
        return response_data

    except stripe_to_use.error.StripeError as e:
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
    # Use _get_stripe_module() to ensure API key is properly configured
    stripe_to_use = _get_stripe_module()

    if stripe_to_use is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe library not available. Please ensure stripe>=7.0.0 is installed: pip install stripe>=7.0.0",
        )

    # Verify API key is set
    if not stripe_to_use.api_key:
        stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
        if not stripe_api_key:
            logger.error("Stripe API key not configured (STRIPE_API_KEY or STRIPE_TEST_API_KEY)")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe API key not configured. Please set STRIPE_API_KEY or STRIPE_TEST_API_KEY in environment variables.",
            )
        stripe_to_use.api_key = stripe_api_key
        logger.debug("Stripe API key set in create_subscription")

    # Get user info to create customer if needed - check database first
    from app.db.mongodb import get_database

    db = get_database()
    if db is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )

    collection = get_collection(USERS_COLLECTION)

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID format"
        )

    user = collection.find_one({"_id": user_id_obj})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Get or create customer - ensure customer exists in Stripe
    if not customer_id:
        customer_id = user.get("stripeCustomerId")

    # Verify customer exists in Stripe, create if it doesn't
    if customer_id:
        try:
            stripe_to_use.Customer.retrieve(customer_id)
            logger.debug(f"Verified existing Stripe customer {customer_id} for user {user_id}")
        except stripe_to_use.error.InvalidRequestError as e:
            # Customer doesn't exist in Stripe (maybe deleted or wrong account)
            if "No such customer" in str(e) or e.code == "resource_missing":
                logger.warning(
                    f"Customer {customer_id} not found in Stripe for user {user_id}, creating new customer"
                )
                customer_id = create_stripe_customer(
                    user_id=user_id, email=user.get("email", ""), name=user.get("name")
                )
                # Update user with new customer ID
                update_user_subscription(user_id=user_id, stripe_customer_id=customer_id)
            else:
                # Some other error - re-raise it
                raise
    else:
        # No customer ID in database - create new customer
        logger.info(f"No Stripe customer found for user {user_id}, creating new customer")
        customer_id = create_stripe_customer(
            user_id=user_id, email=user.get("email", ""), name=user.get("name")
        )
        # Update user with customer ID
        update_user_subscription(user_id=user_id, stripe_customer_id=customer_id)

    if not customer_id:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create or retrieve Stripe customer",
        )

    # Handle PaymentIntent flow (PaymentSheet) - MUST be done BEFORE creating subscription
    payment_method_id = None
    if payment_intent_id:
        try:
            # Step 1: Retrieve PaymentIntent
            payment_intent = stripe_to_use.PaymentIntent.retrieve(payment_intent_id)
            logger.debug(
                f"Retrieved PaymentIntent {payment_intent_id}, status: {payment_intent.status}"
            )

            # Step 1.5: Confirm PaymentIntent if it's in requires_confirmation state
            if payment_intent.status == "requires_confirmation":
                logger.info(
                    f"PaymentIntent {payment_intent_id} requires confirmation. Confirming now..."
                )
                try:
                    # Get payment method from PaymentIntent if available
                    confirm_params = {}
                    if payment_intent.payment_method:
                        payment_method_id = (
                            payment_intent.payment_method
                            if isinstance(payment_intent.payment_method, str)
                            else payment_intent.payment_method.id
                        )
                        confirm_params["payment_method"] = payment_method_id
                        logger.debug(
                            f"Confirming PaymentIntent with payment method: {payment_method_id}"
                        )

                    # Confirm the PaymentIntent
                    payment_intent = stripe_to_use.PaymentIntent.confirm(
                        payment_intent_id, **confirm_params
                    )
                    logger.info(
                        f"✅ Successfully confirmed PaymentIntent {payment_intent_id}. New status: {payment_intent.status}"
                    )

                    # If still requires_confirmation after confirmation, there might be an issue
                    if payment_intent.status == "requires_confirmation":
                        logger.warning(
                            f"⚠️ PaymentIntent {payment_intent_id} still requires confirmation after confirm() call. "
                            f"This may indicate the payment method needs to be attached or there's an issue with the payment."
                        )
                        raise HTTPException(
                            status_code=status.HTTP_402_PAYMENT_REQUIRED,
                            detail={
                                "status": payment_intent.status,
                                "message": "Payment confirmation failed. Please try again or use a different payment method.",
                                "payment_intent_id": payment_intent_id,
                            },
                        )
                except HTTPException:
                    raise
                except stripe_to_use.error.StripeError as e:
                    logger.error(f"Failed to confirm PaymentIntent {payment_intent_id}: {e}")
                    raise HTTPException(
                        status_code=status.HTTP_402_PAYMENT_REQUIRED,
                        detail={
                            "status": "requires_confirmation",
                            "message": f"Failed to confirm payment: {str(e)}",
                            "payment_intent_id": payment_intent_id,
                        },
                    )

            # Handle different payment intent statuses
            if payment_intent.status == "succeeded":
                # Payment completed successfully - proceed
                logger.info(f"PaymentIntent {payment_intent_id} succeeded")
            elif payment_intent.status == "requires_action":
                # Payment requires 3DS authentication
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "status": "requires_action",
                        "message": "Payment requires additional authentication (3D Secure). Please complete authentication in the frontend.",
                        "payment_intent_id": payment_intent_id,
                        "client_secret": payment_intent.client_secret,
                        "next_action": (
                            {
                                "type": payment_intent.next_action.type,
                                "redirect_to_url": getattr(
                                    payment_intent.next_action, "redirect_to_url", None
                                ),
                            }
                            if hasattr(payment_intent, "next_action") and payment_intent.next_action
                            else None
                        ),
                    },
                )
            elif payment_intent.status == "processing":
                # Payment is being processed (async payment methods like ACH)
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "status": "processing",
                        "message": "Payment is being processed. Please wait for confirmation.",
                        "payment_intent_id": payment_intent_id,
                    },
                )
            elif payment_intent.status == "requires_payment_method":
                # Payment failed - need new payment method
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "status": "requires_payment_method",
                        "message": "Payment failed. Please try a different payment method.",
                        "payment_intent_id": payment_intent_id,
                    },
                )
            elif payment_intent.status == "canceled":
                # Payment was canceled
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "status": "canceled",
                        "message": "Payment was canceled. Please create a new payment intent.",
                        "payment_intent_id": payment_intent_id,
                    },
                )
            else:
                # Unknown status
                raise HTTPException(
                    status_code=status.HTTP_402_PAYMENT_REQUIRED,
                    detail={
                        "status": payment_intent.status,
                        "message": f"Payment not completed. PaymentIntent status: {payment_intent.status}",
                        "payment_intent_id": payment_intent_id,
                    },
                )

            # Step 2: Get payment method from PaymentIntent
            payment_method_id = payment_intent.payment_method

            if not payment_method_id:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Payment method not found in PaymentIntent",
                )

            logger.debug(f"Payment method ID from PaymentIntent: {payment_method_id}")

            # Step 3: Check if payment method is already attached, then attach if needed
            payment_method_attached = False
            try:
                # First, retrieve the payment method to check if it's already attached
                payment_method = stripe_to_use.PaymentMethod.retrieve(payment_method_id)

                if payment_method.customer == customer_id:
                    # Payment method is already attached to this customer
                    logger.info(
                        f"Payment method {payment_method_id} already attached to customer {customer_id}"
                    )
                    payment_method_attached = True
                elif payment_method.customer is None:
                    # Payment method is not attached to any customer - try to attach it
                    try:
                        stripe_to_use.PaymentMethod.attach(payment_method_id, customer=customer_id)
                        logger.info(
                            f"Attached payment method {payment_method_id} to customer {customer_id}"
                        )
                        payment_method_attached = True
                    except stripe_to_use.error.InvalidRequestError as attach_error:
                        # Check if it's the "previously used" error
                        error_msg = str(attach_error).lower()
                        if "previously used" in error_msg or "may not be used again" in error_msg:
                            logger.warning(
                                f"Payment method {payment_method_id} was previously used and cannot be attached. "
                                f"This may happen if PaymentIntent was confirmed without attaching the payment method. "
                                f"Will proceed with subscription creation - the payment method from the successful "
                                f"PaymentIntent will be used directly."
                            )
                            payment_method_attached = False
                        else:
                            raise
                else:
                    # Payment method is attached to a different customer
                    if payment_method.customer != customer_id:
                        logger.warning(
                            f"Payment method {payment_method_id} is attached to customer {payment_method.customer}, "
                            f"not {customer_id}. This should not happen in normal flow."
                        )
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Payment method belongs to a different customer",
                        )
                    else:
                        payment_method_attached = True
            except stripe_to_use.error.InvalidRequestError as e:
                # If we can't retrieve the payment method, log and continue
                error_msg = str(e).lower()
                if "no such payment_method" in error_msg:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Payment method {payment_method_id} not found",
                    )
                else:
                    logger.warning(f"Could not retrieve payment method {payment_method_id}: {e}")
                    # Continue - we'll use the payment method from PaymentIntent

            # Step 4: Set as default payment method BEFORE creating subscription (only if attached)
            if payment_method_attached:
                try:
                    stripe_to_use.Customer.modify(
                        customer_id, invoice_settings={"default_payment_method": payment_method_id}
                    )
                    logger.info(
                        f"Set payment method {payment_method_id} as default for customer {customer_id}"
                    )
                except stripe_to_use.error.StripeError as e:
                    logger.warning(f"Could not set payment method as default: {e}")
                    # Continue - subscription creation will still work
            else:
                logger.info(
                    f"Payment method {payment_method_id} not attached, so not setting as default. "
                    f"Subscription will use payment method from PaymentIntent."
                )

        except stripe_to_use.error.StripeError as e:
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

    # Step 5: THEN create the subscription (after payment method is attached and set as default)
    try:
        subscription_params = {
            "customer": customer_id,
            "items": [{"price": price_id}],
            "metadata": {"user_id": user_id},
            "expand": ["latest_invoice.payment_intent"],
        }

        # Only set default_payment_method if it was successfully attached to the customer
        # Stripe requires the payment method to be attached before it can be used in subscription
        if payment_method_id and payment_method_attached:
            subscription_params["default_payment_method"] = payment_method_id
            logger.info(f"Using attached payment method {payment_method_id} for subscription")
        elif payment_method_id and not payment_method_attached:
            # Payment method couldn't be attached (e.g., "previously used" error)
            # Don't set it as default_payment_method - Stripe will use the payment from PaymentIntent
            logger.warning(
                f"Payment method {payment_method_id} not attached, so not setting as default_payment_method. "
                f"Subscription will use payment from PaymentIntent."
            )

        # Payment is already completed via PaymentIntent, so subscription should be active
        # Use "default_incomplete" - we'll pay the invoice immediately after creation
        # This prevents Stripe from trying to charge immediately (which could fail)
        subscription_params["payment_behavior"] = "default_incomplete"

        subscription_params["payment_settings"] = {
            "payment_method_types": ["card"],
            "save_default_payment_method": "on_subscription",
        }

        if trial_days:
            subscription_params["trial_period_days"] = trial_days

        logger.info(f"Creating subscription for customer {customer_id} with price {price_id}")

        # Get product ID from price before creating subscription
        product_id = None
        try:
            price = stripe_to_use.Price.retrieve(price_id)
            product_id = price.product if isinstance(price.product, str) else price.product.id
            logger.debug(f"Retrieved product ID {product_id} from price {price_id}")
        except Exception as e:
            logger.warning(f"Could not retrieve product ID from price {price_id}: {e}")

        subscription = stripe_to_use.Subscription.create(**subscription_params)

        # Note: PaymentIntent is already confirmed by PaymentSheet before this point
        # The subscription creates an invoice with its own PaymentIntent (status: "incomplete")
        # We need to pay this invoice using the already-confirmed payment method

        # Retrieve the subscription with expanded invoice to get the PaymentIntent
        subscription = stripe_to_use.Subscription.retrieve(
            subscription.id, expand=["latest_invoice.payment_intent"]
        )

        # Pay the subscription's invoice using the confirmed payment method
        if hasattr(subscription, "latest_invoice") and subscription.latest_invoice:
            invoice = subscription.latest_invoice
            invoice_id = invoice.id if hasattr(invoice, "id") else invoice

            # Retrieve invoice with payment intent
            if isinstance(invoice, str):
                invoice = stripe_to_use.Invoice.retrieve(invoice_id, expand=["payment_intent"])

            # Check if invoice has a PaymentIntent that needs to be paid
            if hasattr(invoice, "payment_intent") and invoice.payment_intent:
                invoice_payment_intent = invoice.payment_intent
                invoice_pi_id = (
                    invoice_payment_intent.id
                    if hasattr(invoice_payment_intent, "id")
                    else invoice_payment_intent
                )

                # Retrieve the PaymentIntent
                if isinstance(invoice_payment_intent, str):
                    invoice_payment_intent = stripe_to_use.PaymentIntent.retrieve(invoice_pi_id)

                # If the invoice PaymentIntent needs confirmation or is incomplete, confirm it
                if invoice_payment_intent.status in [
                    "requires_confirmation",
                    "requires_payment_method",
                    "incomplete",
                ]:
                    # Use payment method from invoice PaymentIntent if available, otherwise use the one from original PaymentIntent
                    invoice_pm_id = None
                    if (
                        hasattr(invoice_payment_intent, "payment_method")
                        and invoice_payment_intent.payment_method
                    ):
                        invoice_pm_id = (
                            invoice_payment_intent.payment_method
                            if isinstance(invoice_payment_intent.payment_method, str)
                            else invoice_payment_intent.payment_method.id
                        )
                        logger.debug(f"Invoice PaymentIntent has payment method: {invoice_pm_id}")

                    # Use invoice payment method if available, otherwise fall back to original
                    pm_to_use = invoice_pm_id or payment_method_id

                    if pm_to_use:
                        try:
                            # Confirm the invoice PaymentIntent using the payment method
                            confirm_params = {"payment_method": pm_to_use}
                            logger.info(
                                f"Confirming invoice PaymentIntent {invoice_pi_id} with payment method {pm_to_use} (status: {invoice_payment_intent.status})"
                            )
                            confirmed_pi = stripe_to_use.PaymentIntent.confirm(
                                invoice_pi_id, **confirm_params
                            )
                            logger.info(
                                f"✅ Confirmed subscription invoice PaymentIntent {invoice_pi_id}. New status: {confirmed_pi.status}"
                            )

                            # If still requires confirmation, log warning but don't fail
                            if confirmed_pi.status == "requires_confirmation":
                                logger.warning(
                                    f"⚠️ Invoice PaymentIntent {invoice_pi_id} still requires confirmation after confirm() call. "
                                    f"This may require additional action or the payment may process asynchronously."
                                )
                        except stripe_to_use.error.StripeError as e:
                            logger.error(
                                f"❌ Failed to confirm invoice PaymentIntent {invoice_pi_id}: {e}"
                            )
                            logger.error(
                                f"   Error details: {str(e)}. This may result in an incomplete PaymentIntent in Stripe."
                            )
                            # Don't raise - let the subscription creation continue
                            # The payment might still process asynchronously
                    else:
                        logger.warning(
                            f"⚠️ Invoice PaymentIntent {invoice_pi_id} needs confirmation but no payment_method available. "
                            f"Status: {invoice_payment_intent.status}"
                        )
                elif invoice_payment_intent.status == "succeeded":
                    logger.info(f"✅ Invoice PaymentIntent {invoice_pi_id} already succeeded")
                else:
                    logger.info(
                        f"ℹ️ Invoice PaymentIntent {invoice_pi_id} status: {invoice_payment_intent.status}"
                    )

        # Update user subscription info (store "monthly"/"annual" for frontend per BACKEND_STRIPE_REQUIREMENTS)
        current_period_end = datetime.fromtimestamp(subscription.current_period_end)
        update_user_subscription(
            user_id=user_id,
            subscription_id=subscription.id,
            subscription_status=subscription.status,
            subscription_plan=_price_id_to_plan_name(price_id),
            subscription_product_id=product_id,  # Store product ID
            subscription_price_id=price_id,  # For frontend plan matching (BACKEND_SUBSCRIPTION_IDS_REQUIREMENT)
            stripe_customer_id=customer_id,
            current_period_end=current_period_end,
        )

        logger.info(f"Created subscription {subscription.id} for user {user_id}")
        return subscription
    except stripe_to_use.error.StripeError as e:
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
    # Use _get_stripe_module() to ensure API key is properly configured
    stripe_to_use = _get_stripe_module()

    if stripe_to_use is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe library not available. Please ensure stripe>=7.0.0 is installed: pip install stripe>=7.0.0",
        )

    # Verify API key is set
    if not stripe_to_use.api_key:
        stripe_api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
        if not stripe_api_key:
            logger.error("Stripe API key not configured (STRIPE_API_KEY or STRIPE_TEST_API_KEY)")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Stripe API key not configured. Please set STRIPE_API_KEY or STRIPE_TEST_API_KEY in environment variables.",
            )
        stripe_to_use.api_key = stripe_api_key
        logger.debug("Stripe API key set in upgrade_subscription")

    # Get current subscription
    subscription_info = get_user_subscription(user_id)
    if not subscription_info.subscriptionId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User does not have an active subscription",
        )

    try:
        # Retrieve current subscription
        subscription = stripe_to_use.Subscription.retrieve(subscription_info.subscriptionId)

        # Get product ID from new price before updating subscription
        product_id = None
        try:
            price = stripe_to_use.Price.retrieve(new_price_id)
            product_id = price.product if isinstance(price.product, str) else price.product.id
            logger.debug(f"Retrieved product ID {product_id} from price {new_price_id}")
        except Exception as e:
            logger.warning(f"Could not retrieve product ID from price {new_price_id}: {e}")

        # Update subscription with new price
        updated_subscription = stripe_to_use.Subscription.modify(
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

        # Update user subscription info (store "monthly"/"annual" for frontend per BACKEND_STRIPE_REQUIREMENTS)
        current_period_end = datetime.fromtimestamp(updated_subscription.current_period_end)
        update_user_subscription(
            user_id=user_id,
            subscription_id=updated_subscription.id,
            subscription_status=updated_subscription.status,
            subscription_plan=_price_id_to_plan_name(new_price_id),
            subscription_product_id=product_id,  # Store product ID
            subscription_price_id=new_price_id,  # For frontend plan matching (BACKEND_SUBSCRIPTION_IDS_REQUIREMENT)
            current_period_end=current_period_end,
        )

        logger.info(f"Upgraded subscription {updated_subscription.id} for user {user_id}")
        return updated_subscription
    except stripe_to_use.error.StripeError as e:
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

        # Get ended_at if subscription was canceled
        subscription_ended_at = None
        if hasattr(canceled_subscription, "ended_at") and canceled_subscription.ended_at:
            subscription_ended_at = datetime.fromtimestamp(canceled_subscription.ended_at)

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
            subscription_ended_at=subscription_ended_at,
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


def _fetch_stripe_products_and_prices(campaign_filter: Optional[str] = None) -> List[Dict]:
    """
    Fetch active products and their prices from Stripe.

    Args:
        campaign_filter: Optional metadata filter for products (e.g., "campaign:premium")
                         If provided, only products with matching metadata will be returned.

    Returns:
        List of plan dictionaries with product and price information
    """
    if not STRIPE_AVAILABLE:
        logger.warning("Stripe library not available - cannot fetch products dynamically")
        return []

    try:
        stripe_module = _get_stripe_module()
        if stripe_module is None:
            logger.error("Failed to get Stripe module")
            return []

        # Log campaign filter status
        if campaign_filter:
            logger.info(
                f"Campaign filter active: '{campaign_filter}' - will filter products by metadata"
            )
        else:
            logger.info("No campaign filter - fetching all active products")

        plans = []

        # Fetch active products
        try:
            # Build product list parameters
            product_params = {"active": True, "limit": 100}

            # If campaign filter is provided, we'll filter after fetching
            # (Stripe metadata filtering requires specific query format)
            logger.info(f"Attempting to fetch products from Stripe with params: {product_params}")
            logger.info(f"Stripe API key configured: {bool(stripe_module.api_key)}")
            logger.info(f"Stripe API version: {getattr(stripe_module, 'api_version', 'not_set')}")
            products = stripe_module.Product.list(**product_params)

            logger.info(f"Found {len(products.data)} active products in Stripe")

            if len(products.data) == 0:
                logger.warning(
                    "No active products found in Stripe. Check that products are marked as 'active' in Stripe Dashboard."
                )
                return []

            products_processed = 0
            products_filtered = 0
            products_without_recurring_prices = 0

            # Process each product
            for product in products.data:
                logger.debug(
                    f"Processing product: {product.id} - {product.name} (metadata: {product.metadata})"
                )

                # Apply campaign filter if provided
                if campaign_filter:
                    product_metadata = product.metadata or {}
                    # Check if campaign filter matches any metadata value
                    if campaign_filter not in product_metadata.values():
                        # Also check if it's a key
                        if campaign_filter not in product_metadata:
                            logger.debug(
                                f"Product {product.id} filtered out by campaign filter '{campaign_filter}' (metadata: {product_metadata})"
                            )
                            products_filtered += 1
                            continue

                products_processed += 1

                # Fetch prices for this product
                try:
                    prices = stripe_module.Price.list(product=product.id, active=True, limit=100)

                    logger.debug(f"Product {product.id} has {len(prices.data)} active prices")

                    recurring_prices_found = 0

                    # Process each price
                    for price in prices.data:
                        logger.debug(
                            f"  Price {price.id}: type={price.type}, active={price.active}"
                        )

                        # Only include recurring prices (subscriptions)
                        if price.type != "recurring":
                            logger.debug(
                                f"  Price {price.id} skipped: not a recurring price (type: {price.type})"
                            )
                            continue

                        if not price.active:
                            logger.debug(f"  Price {price.id} skipped: not active")
                            continue

                        recurring_prices_found += 1

                        # Extract interval information
                        interval = price.recurring.interval if price.recurring else "month"
                        interval_count = price.recurring.interval_count if price.recurring else 1

                        # Format interval for display
                        if interval_count > 1:
                            interval_display = f"{interval_count} {interval}s"
                        else:
                            interval_display = interval

                        # Get amount and currency
                        amount = price.unit_amount / 100 if price.unit_amount else 0
                        currency = price.currency.upper() if price.currency else "USD"

                        # Build plan ID from product and interval
                        plan_id = f"{product.id}_{interval}_{interval_count}".lower().replace(
                            "_", "-"
                        )

                        # Build plan name from product name and interval
                        plan_name = product.name or "Subscription"
                        if interval_count == 1:
                            if interval == "month":
                                plan_name = f"{plan_name} (Monthly)"
                            elif interval == "year":
                                plan_name = f"{plan_name} (Annual)"
                            else:
                                plan_name = f"{plan_name} ({interval_display.capitalize()})"
                        else:
                            plan_name = f"{plan_name} ({interval_display.capitalize()})"

                        # Build description from product description or default
                        description = product.description or f"{plan_name} subscription plan"

                        # Extract features from product
                        # First, try the native Stripe "marketing_features" field (Marketing feature list from Dashboard)
                        # This is an array of objects with a "name" property
                        features = []
                        if hasattr(product, "marketing_features") and product.marketing_features:
                            # Stripe's native marketing_features field (array of objects with "name" property)
                            marketing_features = product.marketing_features
                            if isinstance(marketing_features, (list, tuple)):
                                # Extract the "name" from each feature object
                                features = [
                                    feat.get("name") if isinstance(feat, dict) else str(feat)
                                    for feat in marketing_features
                                    if feat
                                    and (
                                        isinstance(feat, dict)
                                        and feat.get("name")
                                        or not isinstance(feat, dict)
                                    )
                                ]
                            else:
                                # Handle single feature object
                                if isinstance(marketing_features, dict):
                                    features = [marketing_features.get("name", "")]
                                else:
                                    features = [str(marketing_features)]
                            logger.debug(
                                f"Using native Stripe marketing_features field for product {product.id}: {len(features)} features"
                            )
                        elif hasattr(product, "features") and product.features:
                            # Fallback to "features" field (if it exists)
                            features_list = product.features
                            if isinstance(features_list, (list, tuple)):
                                features = [str(f) for f in features_list]
                            else:
                                features = [str(features_list)]
                            logger.debug(
                                f"Using Stripe features field for product {product.id}: {len(features)} features"
                            )
                        elif product.metadata:
                            # Fallback to metadata if native fields are not available
                            feature_list = product.metadata.get("features")
                            if feature_list:
                                # Features might be comma-separated or JSON
                                try:
                                    import json

                                    features = (
                                        json.loads(feature_list)
                                        if feature_list.startswith("[")
                                        else feature_list.split(",")
                                    )
                                    logger.debug(
                                        f"Using metadata features for product {product.id}: {len(features)} features"
                                    )
                                except:
                                    features = [f.strip() for f in feature_list.split(",")]
                                    logger.debug(
                                        f"Using metadata features (comma-separated) for product {product.id}: {len(features)} features"
                                    )

                        # Default features if none found
                        if not features:
                            features = [
                                "Unlimited cover letter generations",
                                "All AI models available",
                                "Priority support",
                                "Cancel anytime",
                            ]

                        # Determine if this is a popular/recommended plan
                        # Check metadata or default annual to popular
                        popular = False
                        if product.metadata:
                            popular_str = product.metadata.get("popular", "false").lower()
                            popular = popular_str in ("true", "1", "yes")
                        elif interval == "year":
                            popular = True  # Default annual to popular

                        plan_dict = {
                            "id": plan_id,
                            "name": plan_name,
                            "interval": interval,
                            "interval_count": interval_count,
                            "description": description,
                            "priceId": price.id,
                            "amount": amount,
                            "currency": currency,
                            "productId": product.id,
                            "features": features,
                            "popular": popular,
                        }

                        plans.append(plan_dict)
                        logger.info(
                            f"Added plan: {plan_name} (Price: {price.id}, Product: {product.id})"
                        )

                    if recurring_prices_found == 0:
                        total_prices = len(prices.data)
                        one_time_prices = sum(1 for p in prices.data if p.type == "one_time")
                        inactive_prices = sum(1 for p in prices.data if not p.active)
                        logger.warning(
                            f"Product {product.id} ({product.name}) has no active recurring prices. "
                            f"Total prices: {total_prices}, One-time: {one_time_prices}, Inactive: {inactive_prices}. "
                            f"This product will NOT appear in subscription plans."
                        )
                        products_without_recurring_prices += 1

                except Exception as e:
                    logger.error(
                        f"Error fetching prices for product {product.id} ({product.name}): {e}",
                        exc_info=True,
                    )
                    continue

            # Log summary
            total_products = len(products.data)
            logger.info(
                f"Product processing summary: {total_products} total products found, "
                f"{products_processed} processed, "
                f"{products_filtered} filtered by campaign, "
                f"{products_without_recurring_prices} without recurring prices, "
                f"{len(plans)} subscription plans created"
            )
            if total_products > len(plans):
                logger.warning(
                    f"⚠️  Only {len(plans)} plan(s) created from {total_products} product(s). "
                    f"Missing products likely have no active recurring prices (only one-time prices)."
                )

        except Exception as e:
            logger.error(f"Error fetching products from Stripe: {e}", exc_info=True)
            logger.error(f"Error type: {type(e).__name__}, Error details: {str(e)}")
            return []

        # Sort plans: popular first, then by interval (year before month), then by interval_count
        plans.sort(
            key=lambda x: (
                not x.get("popular", False),  # Popular plans first
                x.get("interval") != "year",  # Year before month
                x.get("interval_count", 1),  # Lower interval_count first
            )
        )

        if len(plans) == 0:
            logger.warning(
                "No subscription plans found. Possible reasons:\n"
                "  1. Products are not marked as 'active' in Stripe\n"
                "  2. Products don't have active recurring prices\n"
                "  3. Campaign filter is excluding all products\n"
                "  4. Stripe API key doesn't have access to products"
            )
        else:
            logger.info(f"Successfully fetched {len(plans)} subscription plans from Stripe")

        return plans

    except Exception as e:
        error_type = type(e).__name__
        error_details = str(e)
        logger.error(f"Unexpected error fetching Stripe products: {e}", exc_info=True)
        logger.error(f"Error type: {error_type}, Error details: {error_details}")

        # Check for specific Stripe error types
        if hasattr(e, "code"):
            logger.error(f"Stripe error code: {e.code}")
        if hasattr(e, "user_message"):
            logger.error(f"Stripe user message: {e.user_message}")
        if hasattr(e, "param"):
            logger.error(f"Stripe error parameter: {e.param}")

        # Log if it's a connection/network error
        if (
            "connection" in error_details.lower()
            or "network" in error_details.lower()
            or "timeout" in error_details.lower()
        ):
            logger.error(
                "⚠️ This appears to be a network/connection error. Check if Render can reach Stripe API."
            )
        elif "authentication" in error_details.lower() or "unauthorized" in error_details.lower():
            logger.error("⚠️ This appears to be an authentication error. Check your Stripe API key.")

        return []


def get_raw_stripe_products(force_refresh: bool = False) -> dict:
    """
    Get raw Stripe products with full structure including marketing_features.
    Returns products exactly as Stripe returns them.

    Args:
        force_refresh: If True, bypass cache and fetch fresh data from Stripe

    Returns:
        Dictionary with Stripe product list structure
    """
    if not STRIPE_AVAILABLE:
        logger.warning("Stripe library not available - cannot fetch products")
        return {"object": "list", "data": [], "has_more": False, "url": "/v1/products"}

    try:
        stripe_module = _get_stripe_module()
        if stripe_module is None:
            logger.error("Failed to get Stripe module")
            return {"object": "list", "data": [], "has_more": False, "url": "/v1/products"}

        # Fetch active products
        products = stripe_module.Product.list(active=True, limit=100)

        # Convert Stripe objects to dictionaries
        products_data = []
        for product in products.data:
            product_dict = {
                "id": product.id,
                "object": "product",
                "active": product.active,
                "attributes": getattr(product, "attributes", []),
                "created": product.created,
                "default_price": (
                    product.default_price if hasattr(product, "default_price") else None
                ),
                "description": product.description,
                "images": product.images if hasattr(product, "images") else [],
                "livemode": product.livemode,
                "marketing_features": None,
                "metadata": product.metadata or {},
                "name": product.name,
                "package_dimensions": getattr(product, "package_dimensions", None),
                "shippable": getattr(product, "shippable", None),
                "statement_descriptor": getattr(product, "statement_descriptor", None),
                "tax_code": getattr(product, "tax_code", None),
                "type": getattr(product, "type", "service"),
                "unit_label": getattr(product, "unit_label", None),
                "updated": getattr(product, "updated", product.created),
                "url": getattr(product, "url", None),
            }

            # Preserve marketing_features as objects with name property
            if hasattr(product, "marketing_features") and product.marketing_features:
                product_dict["marketing_features"] = [
                    {"name": feat.get("name") if isinstance(feat, dict) else str(feat)}
                    for feat in product.marketing_features
                    if feat
                ]

            products_data.append(product_dict)

        # Sort products by metadata "index" field (ascending order)
        # Products without an "index" field will be sorted to the end
        def get_index(product):
            metadata = product.get("metadata", {})
            index_str = metadata.get("index")
            if index_str is None:
                return float("inf")  # Put items without index at the end
            try:
                return int(index_str)
            except (ValueError, TypeError):
                # If index is not a valid integer, put it at the end
                return float("inf")

        products_data.sort(key=get_index)

        logger.info(f"Fetched {len(products_data)} raw Stripe products (sorted by metadata.index)")

        return {
            "object": "list",
            "data": products_data,
            "has_more": products.has_more if hasattr(products, "has_more") else False,
            "url": "/v1/products",
        }

    except Exception as e:
        logger.error(f"Error fetching raw Stripe products: {e}", exc_info=True)
        return {"object": "list", "data": [], "has_more": False, "url": "/v1/products"}


def get_subscription_plans(force_refresh: bool = False) -> dict:
    """
    Get available subscription plans with Stripe Price IDs.
    Dynamically fetches products and prices from Stripe, with caching.
    Falls back to environment variables if Stripe is unavailable or no products found.

    Args:
        force_refresh: If True, bypass cache and fetch fresh data from Stripe

    Returns:
        Dictionary with 'plans' list containing plan information
    """
    global _stripe_plans_cache, _stripe_plans_cache_time

    # Check cache first (unless force refresh)
    if (
        not force_refresh
        and _stripe_plans_cache is not None
        and _stripe_plans_cache_time is not None
    ):
        cache_age = datetime.now() - _stripe_plans_cache_time
        if cache_age < _stripe_plans_cache_ttl:
            logger.debug(f"Returning cached plans (age: {cache_age.total_seconds():.1f}s)")
            return _stripe_plans_cache

    # Try to fetch dynamically from Stripe
    plans = []
    stripe_fetch_successful = False

    if STRIPE_AVAILABLE:
        # Get campaign filter from environment if set
        campaign_filter = getattr(settings, "STRIPE_PRODUCT_CAMPAIGN", None)

        if campaign_filter:
            logger.warning(
                f"⚠️ Campaign filter is set to: '{campaign_filter}' - products without matching metadata will be excluded"
            )

        try:
            plans = _fetch_stripe_products_and_prices(campaign_filter=campaign_filter)
            stripe_fetch_successful = True
            if len(plans) > 0:
                logger.info(f"✅ Successfully fetched {len(plans)} plans from Stripe")
            else:
                logger.warning(
                    f"⚠️ Stripe fetch succeeded but returned 0 plans. Check logs above for details."
                )
        except Exception as e:
            logger.error(f"❌ Error fetching plans from Stripe: {e}", exc_info=True)
            plans = []
            stripe_fetch_successful = False

    # Fallback to env when Stripe returns no plans (per BACKEND_STRIPE_REQUIREMENTS)
    if not plans:
        if not stripe_fetch_successful:
            logger.warning(
                "No plans from Stripe (fetch failed), falling back to STRIPE_PRICE_ID_MONTHLY / STRIPE_PRICE_ID_ANNUAL"
            )
        monthly_price_id = settings.STRIPE_PRICE_ID_MONTHLY
        annual_price_id = settings.STRIPE_PRICE_ID_ANNUAL
        if monthly_price_id:
            plans.append(
                {
                    "id": "monthly",
                    "name": "Monthly",
                    "interval": "month",
                    "interval_count": 1,
                    "description": "Perfect for ongoing job applications. Unlimited cover letter generations.",
                    "priceId": monthly_price_id,
                    "features": [
                        "Unlimited cover letter generations",
                        "All AI models available",
                        "Priority support",
                        "Cancel anytime",
                    ],
                    "popular": False,
                }
            )
        if annual_price_id:
            plans.append(
                {
                    "id": "annual",
                    "name": "Annual",
                    "interval": "year",
                    "interval_count": 1,
                    "description": "Best value! Save with annual billing. Unlimited cover letter generations.",
                    "priceId": annual_price_id,
                    "features": [
                        "Unlimited cover letter generations",
                        "All AI models available",
                        "Priority support",
                        "Best value - save with annual billing",
                        "Cancel anytime",
                    ],
                    "popular": True,
                }
            )

    # Update cache
    result = {"plans": plans}
    _stripe_plans_cache = result
    _stripe_plans_cache_time = datetime.now()

    return result
