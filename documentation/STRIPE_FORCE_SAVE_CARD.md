# Stripe PaymentSheet - Force Save Card Configuration

## Overview

This document outlines the backend requirements to force saving payment methods (credit cards) and hide the "save card" option in Stripe PaymentSheet when users subscribe.

## Requirement

When creating a PaymentIntent for subscription payments, the payment method (credit card) should be automatically saved to the customer and the "save card" option should be hidden or pre-checked in the PaymentSheet UI.

## Backend Implementation

### Endpoint to Modify

**Endpoint**: `POST /api/subscriptions/create-payment-intent`

### Required Change

Add `setup_future_usage: 'off_session'` parameter when creating the PaymentIntent.

### Current Implementation (Example)

```python
payment_intent = stripe.PaymentIntent.create(
    amount=int(price.unit_amount),
    currency=price.currency,
    customer=stripe_customer_id,
    payment_method_types=["card"],
    metadata={
        "user_id": str(current_user.id),
        "price_id": request.price_id,
        "subscription_type": "new"
    },
)
```

### Updated Implementation (Required)

```python
payment_intent = stripe.PaymentIntent.create(
    amount=int(price.unit_amount),
    currency=price.currency,
    customer=stripe_customer_id,
    payment_method_types=["card"],
    setup_future_usage='off_session',  # <-- ADD THIS LINE
    metadata={
        "user_id": str(current_user.id),
        "price_id": request.price_id,
        "subscription_type": "new"
    },
)
```

## Parameter Details

### `setup_future_usage`

- **Type**: String
- **Value**: `'off_session'`
- **Purpose**:
  - Forces the payment method to be saved to the customer
  - Allows the payment method to be used for future off-session payments (subscriptions, recurring charges)
  - PaymentSheet UI will automatically save the card and may hide/pre-check the "save card" option

### Alternative Values

- `'on_session'`: Payment method can only be used for on-session payments (not suitable for subscriptions)
- `None` or omitted: Payment method is not saved (current behavior - user must opt-in to save)

## Expected Behavior

After implementing this change:

1. **PaymentSheet UI**: The "save card" option will be automatically enabled/hidden (behavior varies by platform)
2. **Payment Method**: The card will be automatically saved to the Stripe customer
3. **Future Use**: The saved payment method can be used for:
   - Subscription renewals
   - Upgrade/downgrade operations
   - Future payments without re-entering card details

## Testing

After implementation, verify:

1. Create a new subscription payment
2. Complete payment in PaymentSheet
3. Check Stripe Dashboard → Customers → [Customer] → Payment Methods
4. Verify the payment method is saved to the customer
5. Verify the "save card" option is not visible or is pre-checked in PaymentSheet

## Additional Notes

- This change only affects **new** PaymentIntents created after the update
- Existing customers with saved payment methods are not affected
- The frontend PaymentSheet configuration does not need to change
- This is a backend-only change - no frontend modifications required

## Related Documentation

- [Stripe PaymentIntent API - setup_future_usage](https://stripe.com/docs/api/payment_intents/create#create_payment_intent-setup_future_usage)
- [Stripe PaymentSheet - Saving Payment Methods](https://stripe.com/docs/payments/save-during-payment)

## Implementation Checklist

- [ ] Update `POST /api/subscriptions/create-payment-intent` endpoint
- [ ] Add `setup_future_usage='off_session'` to PaymentIntent.create()
- [ ] Test with a new subscription payment
- [ ] Verify payment method is saved in Stripe Dashboard
- [ ] Verify PaymentSheet UI behavior (save card option hidden/pre-checked)
- [ ] Deploy to staging environment
- [ ] Test in staging
- [ ] Deploy to production
