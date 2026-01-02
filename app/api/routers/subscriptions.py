"""
Subscription management API routes
"""

import logging
from fastapi import APIRouter, HTTPException, status

from app.models.subscription import (
    SubscriptionResponse,
    SubscribeRequest,
    UpgradeRequest,
    CancelRequest,
    CreatePaymentIntentRequest,
    CreatePaymentIntentResponse,
    SubscriptionPlansResponse,
    StripeProductsResponse,
    StripeProductResponse,
    MarketingFeature,
)
from app.services.subscription_service import (
    get_user_subscription,
    create_subscription,
    upgrade_subscription,
    cancel_subscription,
    create_payment_intent,
    get_subscription_plans,
    get_raw_stripe_products,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["subscriptions"])


@router.get("/subscriptions/debug/stripe")
def debug_stripe():
    """
    Debug endpoint to check Stripe availability and configuration
    """
    import sys

    debug_info = {
        "python_executable": sys.executable,
        "python_version": sys.version,
        "python_path": sys.path[:5],
    }

    # Check module-level availability
    from app.services.subscription_service import STRIPE_AVAILABLE

    debug_info["module_level_stripe_available"] = STRIPE_AVAILABLE

    # Try runtime import
    try:
        import stripe

        debug_info["runtime_stripe_available"] = True
        debug_info["stripe_location"] = (
            stripe.__file__ if hasattr(stripe, "__file__") else "unknown"
        )
        try:
            debug_info["stripe_version"] = stripe.__version__
        except:
            debug_info["stripe_version"] = "unknown (no __version__ attribute)"
    except ImportError as e:
        debug_info["runtime_stripe_available"] = False
        debug_info["import_error"] = str(e)

    # Check API key
    from app.core.config import settings

    debug_info["stripe_test_key_present"] = bool(settings.STRIPE_TEST_API_KEY)
    debug_info["stripe_prod_key_present"] = bool(settings.STRIPE_API_KEY)
    debug_info["stripe_key_configured"] = bool(
        settings.STRIPE_TEST_API_KEY or settings.STRIPE_API_KEY
    )

    return debug_info


@router.get("/subscriptions/plans", response_model=SubscriptionPlansResponse)
def get_plans(force_refresh: bool = False):
    """
    Get available subscription plans with Stripe Price IDs.
    Dynamically fetches products and prices from Stripe.
    This endpoint is public (no auth required).
    
    Args:
        force_refresh: If True, bypass cache and fetch fresh data from Stripe (default: False)
    
    Returns:
        SubscriptionPlansResponse with available plans
    """
    try:
        plans_data = get_subscription_plans(force_refresh=force_refresh)
        plans_count = len(plans_data.get('plans', []))
        logger.info(f"Returning {plans_count} subscription plan(s) to client")
        
        # Log the full JSON response
        import json
        response_obj = SubscriptionPlansResponse(**plans_data)
        response_json = json.dumps(response_obj.dict(), indent=2)
        logger.info(f"Plans endpoint JSON response ({plans_count} plan(s)):\n{response_json}")
        
        return response_obj
    except Exception as e:
        logger.error(f"Error fetching subscription plans: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch subscription plans: {str(e)}",
        )


@router.get("/subscriptions/products", response_model=StripeProductsResponse)
def get_raw_products(force_refresh: bool = False):
    """
    Get raw Stripe products with full structure including marketing_features.
    Returns products exactly as Stripe returns them, with marketing_features as objects.
    This endpoint is public (no auth required).
    
    Args:
        force_refresh: If True, bypass cache and fetch fresh data from Stripe (default: False)
    
    Returns:
        StripeProductsResponse with raw Stripe product data
    """
    try:
        products_data = get_raw_stripe_products(force_refresh=force_refresh)
        products_count = len(products_data.get("data", []))
        logger.info(f"Returning {products_count} raw Stripe product(s) to client")
        
        return StripeProductsResponse(**products_data)
    except Exception as e:
        logger.error(f"Error fetching raw Stripe products: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch Stripe products: {str(e)}",
        )


@router.get("/subscriptions/{user_id}", response_model=SubscriptionResponse)
def list_subscription(user_id: str):
    """
    Get user's subscription information

    Args:
        user_id: User ID

    Returns:
        SubscriptionResponse with subscription details
    """
    logger.info(f"Subscription request received for user_id: {user_id}")
    try:
        subscription = get_user_subscription(user_id)
        logger.info(
            f"Successfully retrieved subscription for user {user_id}: status={subscription.subscriptionStatus}"
        )
        return subscription
    except HTTPException as e:
        logger.warning(
            f"HTTP error retrieving subscription for user {user_id}: {e.status_code} - {e.detail}"
        )
        raise
    except Exception as e:
        logger.error(f"Error retrieving subscription for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving subscription: {str(e)}",
        )


@router.post("/subscriptions/create-payment-intent", response_model=CreatePaymentIntentResponse)
def create_payment_intent_endpoint(request: CreatePaymentIntentRequest):
    """
    Create a PaymentIntent for subscription payment via PaymentSheet.
    This is PCI compliant - card data never touches our servers.

    Args:
        request: CreatePaymentIntentRequest with user_id and price_id

    Returns:
        CreatePaymentIntentResponse with client_secret, customer_id, and ephemeral_key_secret
    """
    logger.info(f"Creating payment intent for user {request.user_id} with price {request.price_id}")
    try:
        result = create_payment_intent(user_id=request.user_id, price_id=request.price_id)
        logger.info(f"Successfully created payment intent for user {request.user_id}")
        return CreatePaymentIntentResponse(**result)
    except HTTPException as e:
        logger.error(f"HTTP error creating payment intent: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating payment intent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment intent: {str(e)}",
        )


@router.post("/subscriptions/subscribe")
def subscribe(request: SubscribeRequest):
    """
    Create a new subscription for a user.
    Supports both PaymentSheet (payment_intent_id) and legacy (payment_method_id) flows.

    Args:
        request: SubscribeRequest with user_id, price_id, and optional payment_intent_id or payment_method_id

    Returns:
        Subscription information
    """
    try:
        subscription = create_subscription(
            user_id=request.user_id,
            price_id=request.price_id,
            payment_intent_id=request.payment_intent_id,
            payment_method_id=request.payment_method_id,
            trial_days=request.trial_days,
        )

        # Get updated subscription info
        subscription_info = get_user_subscription(request.user_id)

        # Get user to include generation_credits and max_credits
        from app.services.user_service import get_user_by_id

        try:
            user = get_user_by_id(request.user_id)
            generation_credits = user.generation_credits
            max_credits = user.max_credits
        except Exception:
            generation_credits = None
            max_credits = None

        return {
            "subscription_id": subscription.id,
            "subscriptionStatus": subscription_info.subscriptionStatus,
            "subscriptionPlan": subscription_info.subscriptionPlan,
            "subscriptionCurrentPeriodEnd": subscription_info.subscriptionCurrentPeriodEnd,
            "generation_credits": generation_credits,
            "max_credits": max_credits,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating subscription: {str(e)}",
        )


@router.put("/subscriptions/upgrade")
def upgrade(request: UpgradeRequest):
    """
    Upgrade user's subscription to a new plan

    Args:
        request: UpgradeRequest with user_id and new_price_id

    Returns:
        Updated subscription information
    """
    try:
        subscription = upgrade_subscription(
            user_id=request.user_id, new_price_id=request.new_price_id
        )

        # Get updated subscription info
        subscription_info = get_user_subscription(request.user_id)

        return {
            "message": "Subscription upgraded successfully",
            "subscription": subscription_info.dict(),
            "stripe_subscription_id": subscription.id,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upgrading subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error upgrading subscription: {str(e)}",
        )


@router.post("/subscriptions/cancel")
def cancel(request: CancelRequest):
    """
    Cancel user's subscription

    Args:
        request: CancelRequest with user_id and cancel_immediately flag

    Returns:
        Cancellation confirmation
    """
    try:
        subscription = cancel_subscription(
            user_id=request.user_id, cancel_immediately=request.cancel_immediately
        )

        # Get updated subscription info
        subscription_info = get_user_subscription(request.user_id)

        return {
            "message": "Subscription canceled successfully",
            "subscription": subscription_info.dict(),
            "stripe_subscription_id": subscription.id,
            "canceled_immediately": request.cancel_immediately,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error canceling subscription: {str(e)}",
        )
