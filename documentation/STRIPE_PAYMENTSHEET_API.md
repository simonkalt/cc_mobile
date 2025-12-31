# Stripe PaymentSheet API Documentation

This document describes the backend API endpoints required for PCI-compliant subscription payments using Stripe PaymentSheet.

## Overview

PaymentSheet is Stripe's fully PCI-compliant payment solution. Card data is collected and processed entirely on Stripe's secure servers - your backend never touches sensitive card information. This qualifies you for **SAQ A** (the simplest PCI compliance level).

## Required Backend Endpoints

### 1. Create PaymentIntent for Subscription

**Endpoint**: `POST /api/subscriptions/create-payment-intent`

**Purpose**: Creates a Stripe PaymentIntent that will be used by PaymentSheet to collect payment information securely.

**Request Body**:

```json
{
  "user_id": "string (MongoDB ObjectId)",
  "price_id": "string (Stripe Price ID, e.g., 'price_xxx')"
}
```

**Response** (200 OK):

```json
{
  "client_secret": "pi_xxx_secret_xxx",
  "customer_id": "cus_xxx (optional, if customer exists)",
  "customer_ephemeral_key_secret": "ek_test_xxx (optional, if customer exists)"
}
```

**Backend Implementation Example** (Python/FastAPI):

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import stripe

router = APIRouter()

class CreatePaymentIntentRequest(BaseModel):
    user_id: str
    price_id: str

@router.post("/api/subscriptions/create-payment-intent")
async def create_payment_intent(
    request: CreatePaymentIntentRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create a PaymentIntent for subscription payment via PaymentSheet.
    This is PCI compliant - card data never touches our servers.
    """
    try:
        # Verify user
        if request.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        # Get or create Stripe customer
        stripe_customer_id = current_user.stripe_customer_id
        if not stripe_customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.name,
                metadata={"user_id": str(current_user.id)}
            )
            stripe_customer_id = customer.id
            # Save stripe_customer_id to user record
            current_user.stripe_customer_id = stripe_customer_id
            await current_user.save()

        # Get price details
        price = stripe.Price.retrieve(request.price_id)

        # Create PaymentIntent
        payment_intent = stripe.PaymentIntent.create(
            amount=int(price.unit_amount),  # Amount in cents
            currency=price.currency,
            customer=stripe_customer_id,
            payment_method_types=["card"],
            metadata={
                "user_id": str(current_user.id),
                "price_id": request.price_id,
                "subscription_type": "new"
            },
            # For subscriptions, you might want to set up_future_usage
            # But for immediate payment, we don't need it
        )

        # Create ephemeral key for customer (allows PaymentSheet to access customer)
        ephemeral_key = stripe.EphemeralKey.create(
            customer=stripe_customer_id,
            stripe_version="2023-10-16"  # Use latest Stripe API version
        )

        return {
            "client_secret": payment_intent.client_secret,
            "customer_id": stripe_customer_id,
            "customer_ephemeral_key_secret": ephemeral_key.secret
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=402,
            detail={
                "message": str(e.user_message) if hasattr(e, 'user_message') else "Payment processing failed",
                "stripe_error": {
                    "type": e.__class__.__name__,
                    "code": getattr(e, 'code', None),
                    "message": str(e)
                }
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

### 2. Create Subscription (Updated)

**Endpoint**: `POST /api/subscriptions/subscribe`

**Purpose**: Creates a subscription after PaymentSheet successfully processes the payment.

**Request Body** (Updated):

```json
{
  "user_id": "string (MongoDB ObjectId)",
  "price_id": "string (Stripe Price ID)",
  "payment_intent_id": "string (Stripe PaymentIntent ID, e.g., 'pi_xxx')",
  "trial_days": "number (optional)"
}
```

**Note**: Changed from `payment_method_id` to `payment_intent_id` for PaymentSheet compatibility.

**Response** (200 OK):

```json
{
  "subscription_id": "sub_xxx",
  "subscriptionStatus": "active",
  "subscriptionPlan": "monthly" | "annual",
  "subscriptionCurrentPeriodEnd": "2024-12-31T23:59:59Z",
  "generation_credits": 10,
  "max_credits": 10
}
```

**Backend Implementation Example** (Updated):

```python
@router.post("/api/subscriptions/subscribe")
async def create_subscription(
    request: CreateSubscriptionRequest,
    current_user: User = Depends(get_current_user)
):
    """
    Create subscription after PaymentSheet confirms payment.
    """
    try:
        # Verify user
        if request.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="Unauthorized")

        # Retrieve PaymentIntent to get payment method
        payment_intent = stripe.PaymentIntent.retrieve(request.payment_intent_id)

        if payment_intent.status != "succeeded":
            raise HTTPException(
                status_code=402,
                detail="Payment not completed"
            )

        # Get payment method from PaymentIntent
        payment_method_id = payment_intent.payment_method

        # Get or create Stripe customer
        stripe_customer_id = current_user.stripe_customer_id
        if not stripe_customer_id:
            raise HTTPException(
                status_code=400,
                detail="Customer not found. Please create payment intent first."
            )

        # Attach payment method to customer
        stripe.PaymentMethod.attach(
            payment_method_id,
            customer=stripe_customer_id
        )

        # Set as default payment method
        stripe.Customer.modify(
            stripe_customer_id,
            invoice_settings={
                "default_payment_method": payment_method_id
            }
        )

        # Create subscription
        subscription_params = {
            "customer": stripe_customer_id,
            "items": [{"price": request.price_id}],
            "payment_behavior": "default_incomplete",
            "payment_settings": {
                "payment_method_types": ["card"],
                "save_default_payment_method": "on_subscription"
            },
            "expand": ["latest_invoice.payment_intent"]
        }

        if request.trial_days:
            subscription_params["trial_period_days"] = request.trial_days

        subscription = stripe.Subscription.create(**subscription_params)

        # Confirm the subscription payment
        if subscription.latest_invoice.payment_intent:
            stripe.PaymentIntent.confirm(subscription.latest_invoice.payment_intent.id)

        # Save subscription to database
        user_subscription = UserSubscription(
            user_id=current_user.id,
            stripe_subscription_id=subscription.id,
            stripe_customer_id=stripe_customer_id,
            price_id=request.price_id,
            status=subscription.status,
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            plan=request.price_id  # Map to "monthly" or "annual" based on price_id
        )
        await user_subscription.save()

        return {
            "subscription_id": subscription.id,
            "subscriptionStatus": subscription.status,
            "subscriptionPlan": get_plan_name(request.price_id),  # "monthly" or "annual"
            "subscriptionCurrentPeriodEnd": datetime.fromtimestamp(
                subscription.current_period_end
            ).isoformat(),
            "generation_credits": current_user.generation_credits,
            "max_credits": current_user.max_credits
        }

    except stripe.error.StripeError as e:
        raise HTTPException(
            status_code=402,
            detail={
                "message": str(e.user_message) if hasattr(e, 'user_message') else "Subscription creation failed",
                "stripe_error": {
                    "type": e.__class__.__name__,
                    "code": getattr(e, 'code', None),
                    "message": str(e)
                }
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Payment Flow

1. **User selects subscription plan** → Frontend calls `/api/subscriptions/create-payment-intent`
2. **Backend creates PaymentIntent** → Returns `client_secret`, `customer_id`, `ephemeral_key_secret`
3. **Frontend initializes PaymentSheet** → Uses Stripe SDK to show secure payment form
4. **User enters card details** → All handled by Stripe (PCI compliant)
5. **PaymentSheet confirms payment** → Returns `payment_intent_id` to frontend
6. **Frontend calls `/api/subscriptions/subscribe`** → Backend creates subscription using `payment_intent_id`
7. **Subscription created** → User has active subscription

## Security Benefits

✅ **PCI SAQ A Compliance**: Card data never touches your servers  
✅ **Secure by Default**: Stripe handles all sensitive data  
✅ **Apple Pay / Google Pay**: Automatically supported  
✅ **3D Secure**: Automatically handled by Stripe  
✅ **Reduced Liability**: You're not responsible for card data security

## Testing

Use Stripe test mode with test cards:

- Success: `4242 4242 4242 4242`
- Decline: `4000 0000 0000 0002`
- 3D Secure: `4000 0025 0000 3155`

## Error Handling

All Stripe errors should be caught and returned with user-friendly messages. The frontend `stripeErrorHandler.js` will format these appropriately.

## Notes

- PaymentSheet automatically handles Apple Pay and Google Pay if configured
- The ephemeral key allows PaymentSheet to access customer data securely
- PaymentIntent must be confirmed before creating the subscription
- Always use the latest Stripe API version for ephemeral keys
