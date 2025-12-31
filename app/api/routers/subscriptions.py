"""
Subscription management API routes
"""
import logging
from fastapi import APIRouter, HTTPException, status

from app.models.subscription import (
    SubscriptionResponse,
    SubscribeRequest,
    UpgradeRequest,
    CancelRequest
)
from app.services.subscription_service import (
    get_user_subscription,
    create_subscription,
    upgrade_subscription,
    cancel_subscription
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
    try:
        return get_user_subscription(user_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving subscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving subscription: {str(e)}"
        )


@router.post("/subscriptions/subscribe")
def subscribe(request: SubscribeRequest):
    """
    Create a new subscription for a user
    
    Args:
        request: SubscribeRequest with user_id, price_id, and optional payment_method_id
        
    Returns:
        Subscription information
    """
    try:
        subscription = create_subscription(
            user_id=request.user_id,
            price_id=request.price_id,
            payment_method_id=request.payment_method_id,
            trial_days=request.trial_days
        )
        
        # Get updated subscription info
        subscription_info = get_user_subscription(request.user_id)
        
        return {
            "message": "Subscription created successfully",
            "subscription": subscription_info.dict(),
            "stripe_subscription_id": subscription.id
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating subscription: {e}")
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

