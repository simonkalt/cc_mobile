# Backend Stripe Integration Requirements

This document outlines all backend API endpoints required for the Stripe PaymentSheet subscription implementation.

## Overview

The frontend uses Stripe PaymentSheet for PCI-compliant payment processing. All card data is handled by Stripe - your backend never touches sensitive payment information. This qualifies you for **PCI SAQ A** compliance.

## Required Endpoints

### 1. Get Subscription Plans

**Endpoint**: `GET /api/subscriptions/plans`

**Purpose**: Returns available subscription plans with real Stripe Price IDs.

**Authentication**: Optional (may be public endpoint)

**Request**: No body required

**Response** (200 OK):

```json
{
  "plans": [
    {
      "id": "monthly",
      "name": "Monthly",
      "interval": "month",
      "description": "Perfect for ongoing job applications. Unlimited cover letter generations.",
      "priceId": "price_1ABC123xyz...",
      "features": [
        "Unlimited cover letter generations",
        "All AI models available",
        "Priority support",
        "Cancel anytime"
      ]
    },
    {
      "id": "annual",
      "name": "Annual",
      "interval": "year",
      "description": "Best value! Save with annual billing. Unlimited cover letter generations.",
      "priceId": "price_1XYZ789abc...",
      "features": [
        "Unlimited cover letter generations",
        "All AI models available",
        "Priority support",
        "Best value - save with annual billing",
        "Cancel anytime"
      ],
      "popular": true
    }
  ]
}
```

**Backend Implementation Example** (Python/FastAPI):

```python
from fastapi import APIRouter, Depends
import stripe
import os

router = APIRouter()

@router.get("/api/subscriptions/plans")
async def get_subscription_plans():
    """
    Get available subscription plans with Stripe Price IDs.
    This endpoint can be public (no auth required).
    """
    try:
        # Get Price IDs from environment variables or database
        monthly_price_id = os.getenv("STRIPE_PRICE_ID_MONTHLY")
        annual_price_id = os.getenv("STRIPE_PRICE_ID_ANNUAL")

        # Optionally verify prices exist in Stripe
        # monthly_price = stripe.Price.retrieve(monthly_price_id)
        # annual_price = stripe.Price.retrieve(annual_price_id)

        plans = [
            {
                "id": "monthly",
                "name": "Monthly",
                "interval": "month",
                "description": "Perfect for ongoing job applications. Unlimited cover letter generations.",
                "priceId": monthly_price_id,
                "features": [
                    "Unlimited cover letter generations",
                    "All AI models available",
                    "Priority support",
                    "Cancel anytime"
                ]
            },
            {
                "id": "annual",
                "name": "Annual",
                "interval": "year",
                "description": "Best value! Save with annual billing. Unlimited cover letter generations.",
                "priceId": annual_price_id,
                "features": [
                    "Unlimited cover letter generations",
                    "All AI models available",
                    "Priority support",
                    "Best value - save with annual billing",
                    "Cancel anytime"
                ],
                "popular": True
            }
        ]

        return {"plans": plans}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch subscription plans: {str(e)}")
```

**Notes**:

- Price IDs should be real Stripe Price IDs (e.g., `price_1ABC123xyz...`)
- Store Price IDs in environment variables or database
- The `popular` field marks the recommended plan
- Features array is displayed in the UI

---

### 2. Create PaymentIntent for Subscription

**Endpoint**: `POST /api/subscriptions/create-payment-intent`

**Purpose**: Creates a Stripe PaymentIntent that will be used by PaymentSheet to collect payment information securely.

**Authentication**: Required (Bearer token)

**Request Body**:

```json
{
  "user_id": "string (MongoDB ObjectId)",
  "price_id": "string (Stripe Price ID, e.g., 'price_1ABC123xyz...')"
}
```

**Response** (200 OK):

```json
{
  "client_secret": "pi_xxx_secret_xxx",
  "customer_id": "cus_xxx",
  "customer_ephemeral_key_secret": "ek_test_xxx"
}
```

**Backend Implementation Example** (Python/FastAPI):

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import stripe
from datetime import datetime

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
        if request.user_id != str(current_user.id):
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

        # Get price details from Stripe
        try:
            price = stripe.Price.retrieve(request.price_id)
        except stripe.error.InvalidRequestError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid price ID: {request.price_id}"
            )

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
            # For subscriptions, we'll confirm payment immediately
            # PaymentSheet will handle the payment confirmation
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Notes**:

- Always use the latest Stripe API version for ephemeral keys
- Store `stripe_customer_id` in your user model for future reference
- The `client_secret` is used by PaymentSheet to initialize the payment form
- Ephemeral keys are short-lived and allow PaymentSheet to access customer data securely

---

### 3. Create Subscription (Updated)

**Endpoint**: `POST /api/subscriptions/subscribe`

**Purpose**: Creates a subscription after PaymentSheet successfully processes the payment.

**Authentication**: Required (Bearer token)

**Request Body**:

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
  "subscriptionPlan": "monthly",
  "subscriptionCurrentPeriodEnd": "2024-12-31T23:59:59Z",
  "generation_credits": 10,
  "max_credits": 10
}
```

**Backend Implementation Example** (Updated):

```python
class CreateSubscriptionRequest(BaseModel):
    user_id: str
    price_id: str
    payment_intent_id: str  # Changed from payment_method_id
    trial_days: int = None

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
        if request.user_id != str(current_user.id):
            raise HTTPException(status_code=403, detail="Unauthorized")

        # Retrieve PaymentIntent to verify payment and get payment method
        try:
            payment_intent = stripe.PaymentIntent.retrieve(request.payment_intent_id)
        except stripe.error.InvalidRequestError:
            raise HTTPException(
                status_code=400,
                detail="Invalid payment intent ID"
            )

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

        # Determine plan name from price_id
        plan_name = "monthly" if "monthly" in request.price_id.lower() else "annual"

        # Save subscription to database
        user_subscription = UserSubscription(
            user_id=current_user.id,
            stripe_subscription_id=subscription.id,
            stripe_customer_id=stripe_customer_id,
            price_id=request.price_id,
            status=subscription.status,
            current_period_end=datetime.fromtimestamp(subscription.current_period_end),
            plan=plan_name
        )
        await user_subscription.save()

        return {
            "subscription_id": subscription.id,
            "subscriptionStatus": subscription.status,
            "subscriptionPlan": plan_name,
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
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

**Notes**:

- The `payment_intent_id` is extracted from the `client_secret` by the frontend (format: `pi_xxx_secret_xxx` → `pi_xxx`)
- Verify the PaymentIntent status is "succeeded" before creating subscription
- Attach the payment method to the customer for future billing
- Set it as the default payment method for the subscription

---

### 4. Get User Subscription (Existing - No Changes)

**Endpoint**: `GET /api/subscriptions/{user_id}`

**Purpose**: Get user's current subscription status.

**Authentication**: Required (Bearer token)

**Response** (200 OK):

```json
{
  "subscriptionStatus": "active",
  "subscriptionPlan": "monthly",
  "subscriptionCurrentPeriodEnd": "2024-12-31T23:59:59Z",
  "generation_credits": 10,
  "max_credits": 10
}
```

**Response** (404 Not Found - Free Tier):

```json
{
  "subscriptionStatus": "free",
  "subscriptionPlan": null,
  "subscriptionCurrentPeriodEnd": null,
  "generation_credits": 10,
  "max_credits": 10
}
```

**Note**: This endpoint should return `generation_credits` and `max_credits` for free tier users.

---

### 5. Upgrade Subscription (Existing - No Changes)

**Endpoint**: `PUT /api/subscriptions/upgrade`

**Purpose**: Upgrade subscription from Monthly to Annual.

**Authentication**: Required (Bearer token)

**Request Body**:

```json
{
  "user_id": "string (MongoDB ObjectId)",
  "new_price_id": "string (Stripe Price ID for Annual plan)"
}
```

**Response**: Same as Get User Subscription

---

### 6. Cancel Subscription (Existing - No Changes)

**Endpoint**: `POST /api/subscriptions/cancel`

**Purpose**: Cancel subscription (at period end or immediately).

**Authentication**: Required (Bearer token)

**Request Body**:

```json
{
  "user_id": "string (MongoDB ObjectId)",
  "cancel_immediately": "boolean (false = cancel at period end)"
}
```

**Response**: Same as Get User Subscription

---

## Database Schema Requirements

### User Model

Add the following fields to your User model:

```python
class User(BaseModel):
    # ... existing fields ...
    stripe_customer_id: Optional[str] = None  # Stripe Customer ID
    generation_credits: int = 10  # Remaining free credits
    max_credits: int = 10  # Total free credits limit
```

### Subscription Model

Create a subscription model to track subscriptions:

```python
class UserSubscription(BaseModel):
    user_id: str  # MongoDB ObjectId reference
    stripe_subscription_id: str  # Stripe Subscription ID
    stripe_customer_id: str  # Stripe Customer ID
    price_id: str  # Stripe Price ID
    status: str  # active, canceled, past_due, etc.
    current_period_end: datetime  # Subscription period end date
    plan: str  # "monthly" or "annual"
    created_at: datetime
    updated_at: datetime
```

---

## Environment Variables

Set these environment variables on your backend:

```bash
# Stripe API Keys
STRIPE_SECRET_KEY=sk_test_...  # or sk_live_... for production
STRIPE_PUBLISHABLE_KEY=pk_test_...  # or pk_live_... for production

# Stripe Price IDs (from Stripe Dashboard)
STRIPE_PRICE_ID_MONTHLY=price_1ABC123xyz...
STRIPE_PRICE_ID_ANNUAL=price_1XYZ789abc...

# Stripe API Version (for ephemeral keys)
STRIPE_API_VERSION=2023-10-16  # Use latest version
```

---

## Payment Flow

1. **Frontend**: User selects plan → Calls `GET /api/subscriptions/plans`
2. **Backend**: Returns plans with real Price IDs
3. **Frontend**: User clicks "Subscribe" → Calls `POST /api/subscriptions/create-payment-intent`
4. **Backend**: Creates PaymentIntent, returns `client_secret`, `customer_id`, `ephemeral_key`
5. **Frontend**: Initializes PaymentSheet with Stripe SDK
6. **User**: Enters card details in PaymentSheet (PCI compliant - handled by Stripe)
7. **PaymentSheet**: Confirms payment, returns `payment_intent_id` to frontend
8. **Frontend**: Calls `POST /api/subscriptions/subscribe` with `payment_intent_id`
9. **Backend**: Verifies payment, creates Stripe subscription, saves to database
10. **Frontend**: Displays success, refreshes subscription status

---

## Error Handling

All endpoints should return errors in this format:

```json
{
  "detail": "User-friendly error message",
  "stripe_error": {
    "type": "CardError",
    "code": "card_declined",
    "message": "Your card was declined."
  }
}
```

The frontend `stripeErrorHandler.js` will format these errors for display.

---

## Testing

### Test Mode Setup

1. Use Stripe test mode keys (`sk_test_...`, `pk_test_...`)
2. Create test Price IDs in Stripe Dashboard (test mode)
3. Use Stripe test cards for testing

### Test Cards

- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Insufficient Funds**: `4000 0000 0000 9995`
- **Expired Card**: `4000 0000 0000 0069`
- **3D Secure**: `4000 0025 0000 3155`

---

## Security Considerations

1. **Never expose secret keys**: Only use publishable keys in frontend
2. **Validate on backend**: Always validate payment data on the backend
3. **Use HTTPS**: Always use HTTPS in production
4. **Handle errors gracefully**: Don't expose sensitive error details to users
5. **PCI Compliance**: PaymentSheet handles all card data - you're SAQ A compliant

---

## Webhook Events (Optional but Recommended)

Set up Stripe webhooks to handle subscription events:

- `customer.subscription.created` - Subscription created
- `customer.subscription.updated` - Subscription updated
- `customer.subscription.deleted` - Subscription canceled
- `invoice.payment_succeeded` - Payment successful
- `invoice.payment_failed` - Payment failed

Webhook endpoint: `POST /api/webhooks/stripe`

---

## Summary Checklist

- [ ] Implement `GET /api/subscriptions/plans` - Return plans with real Price IDs
- [ ] Implement `POST /api/subscriptions/create-payment-intent` - Create PaymentIntent
- [ ] Update `POST /api/subscriptions/subscribe` - Accept `payment_intent_id` instead of `payment_method_id`
- [ ] Add `stripe_customer_id` field to User model
- [ ] Create UserSubscription model to track subscriptions
- [ ] Set environment variables for Stripe keys and Price IDs
- [ ] Test with Stripe test mode
- [ ] Set up webhooks (optional but recommended)

---

## Additional Resources

- [Stripe PaymentSheet Documentation](https://stripe.com/docs/payments/payment-sheet)
- [Stripe API Reference](https://stripe.com/docs/api)
- [Stripe Testing Guide](https://stripe.com/docs/testing)
- [PCI Compliance Guide](https://stripe.com/guides/pci-compliance)
