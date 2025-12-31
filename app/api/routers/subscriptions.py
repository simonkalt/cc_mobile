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
    CreatePaymentIntentResponse
)
from app.services.subscription_service import (
    get_user_subscription,
    create_subscription,
    upgrade_subscription,
    cancel_subscription,
    create_payment_intent
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["subscriptions"])


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
        logger.info(f"Successfully retrieved subscription for user {user_id}: status={subscription.subscriptionStatus}")
        return subscription
    except HTTPException as e:
        logger.warning(f"HTTP error retrieving subscription for user {user_id}: {e.status_code} - {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Error retrieving subscription for user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving subscription: {str(e)}"
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
    try:
        result = create_payment_intent(
            user_id=request.user_id,
            price_id=request.price_id
        )
        return CreatePaymentIntentResponse(**result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating payment intent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating payment intent: {str(e)}"
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
            trial_days=request.trial_days
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
            "max_credits": max_credits
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error creating subscription: {str(e)}"
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
            user_id=request.user_id,
            new_price_id=request.new_price_id
        )
        
        # Get updated subscription info
        subscription_info = get_user_subscription(request.user_id)
        
        return {
            "message": "Subscription upgraded successfully",
            "subscription": subscription_info.dict(),
            "stripe_subscription_id": subscription.id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error upgrading subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error upgrading subscription: {str(e)}"
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
            user_id=request.user_id,
            cancel_immediately=request.cancel_immediately
        )
        
        # Get updated subscription info
        subscription_info = get_user_subscription(request.user_id)
        
        return {
            "message": "Subscription canceled successfully",
            "subscription": subscription_info.dict(),
            "stripe_subscription_id": subscription.id,
            "canceled_immediately": request.cancel_immediately
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error canceling subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error canceling subscription: {str(e)}"
        )

