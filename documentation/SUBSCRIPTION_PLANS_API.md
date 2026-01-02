# Subscription Plans API - Frontend Integration Guide

This document describes how to consume the dynamic subscription plans endpoint that automatically fetches products and prices from Stripe.

## Endpoint

**GET** `/api/subscriptions/plans`

### Description

Retrieves all available subscription plans dynamically from your Stripe account. The endpoint automatically discovers active products and their recurring prices, eliminating the need to hardcode plan information.

**Authentication:** Not required (public endpoint)

### Query Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `force_refresh` | boolean | No | `false` | If `true`, bypasses the 5-minute cache and fetches fresh data from Stripe |

### Request Example

```javascript
// Basic request
const response = await fetch('http://localhost:8000/api/subscriptions/plans');

// Force refresh (bypass cache)
const response = await fetch('http://localhost:8000/api/subscriptions/plans?force_refresh=true');
```

### Response Format

**Status Code:** `200 OK`

```typescript
interface SubscriptionPlansResponse {
  plans: SubscriptionPlan[];
}

interface SubscriptionPlan {
  id: string;                    // Unique plan identifier (e.g., "prod_xxx_month_1")
  name: string;                   // Display name (e.g., "Premium Plan (Monthly)")
  interval: string;               // Billing interval: "month" or "year"
  interval_count: number;         // Number of intervals (default: 1)
  description: string;            // Plan description
  priceId: string;                // Stripe Price ID (required for payment)
  amount: number | null;          // Price amount in currency units (e.g., 9.99)
  currency: string | null;        // Currency code (e.g., "USD")
  productId: string | null;       // Stripe Product ID
  features: string[];             // Array of feature descriptions
  popular: boolean;               // Whether this plan is marked as recommended
}
```

### Response Example

```json
{
  "plans": [
    {
      "id": "prod_abc123_month_1",
      "name": "Premium Plan (Monthly)",
      "interval": "month",
      "interval_count": 1,
      "description": "Perfect for ongoing job applications. Unlimited cover letter generations.",
      "priceId": "price_1ABC123xyz...",
      "amount": 9.99,
      "currency": "USD",
      "productId": "prod_abc123",
      "features": [
        "Unlimited cover letter generations",
        "All AI models available",
        "Priority support",
        "Cancel anytime"
      ],
      "popular": false
    },
    {
      "id": "prod_abc123_year_1",
      "name": "Premium Plan (Annual)",
      "interval": "year",
      "interval_count": 1,
      "description": "Best value! Save with annual billing. Unlimited cover letter generations.",
      "priceId": "price_1XYZ789abc...",
      "amount": 99.99,
      "currency": "USD",
      "productId": "prod_abc123",
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

## Frontend Implementation

### TypeScript/React Example

```typescript
// types.ts
export interface SubscriptionPlan {
  id: string;
  name: string;
  interval: string;
  interval_count: number;
  description: string;
  priceId: string;
  amount: number | null;
  currency: string | null;
  productId: string | null;
  features: string[];
  popular: boolean;
}

export interface SubscriptionPlansResponse {
  plans: SubscriptionPlan[];
}

// api.ts
const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:8000';

export async function fetchSubscriptionPlans(
  forceRefresh: boolean = false
): Promise<SubscriptionPlansResponse> {
  const url = new URL(`${API_BASE_URL}/api/subscriptions/plans`);
  if (forceRefresh) {
    url.searchParams.set('force_refresh', 'true');
  }

  const response = await fetch(url.toString());
  
  if (!response.ok) {
    throw new Error(`Failed to fetch subscription plans: ${response.statusText}`);
  }

  return response.json();
}

// Component example
import React, { useEffect, useState } from 'react';
import { fetchSubscriptionPlans, SubscriptionPlan } from './api';

export function SubscriptionPlans() {
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function loadPlans() {
      try {
        setLoading(true);
        const data = await fetchSubscriptionPlans();
        setPlans(data.plans);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to load plans');
      } finally {
        setLoading(false);
      }
    }

    loadPlans();
  }, []);

  if (loading) return <div>Loading plans...</div>;
  if (error) return <div>Error: {error}</div>;
  if (plans.length === 0) return <div>No subscription plans available</div>;

  return (
    <div className="subscription-plans">
      {plans.map((plan) => (
        <div key={plan.id} className={`plan-card ${plan.popular ? 'popular' : ''}`}>
          {plan.popular && <div className="badge">Recommended</div>}
          <h3>{plan.name}</h3>
          <p>{plan.description}</p>
          
          {plan.amount !== null && plan.currency && (
            <div className="price">
              ${plan.amount.toFixed(2)} / {plan.interval}
            </div>
          )}
          
          <ul className="features">
            {plan.features.map((feature, index) => (
              <li key={index}>{feature}</li>
            ))}
          </ul>
          
          <button onClick={() => handleSubscribe(plan.priceId)}>
            Subscribe
          </button>
        </div>
      ))}
    </div>
  );
}

function handleSubscribe(priceId: string) {
  // Use priceId with your payment flow
  console.log('Subscribing to plan with price ID:', priceId);
  // ... implement your payment flow here
}
```

### JavaScript/Vanilla Example

```javascript
// Fetch subscription plans
async function getSubscriptionPlans(forceRefresh = false) {
  const url = new URL('http://localhost:8000/api/subscriptions/plans');
  if (forceRefresh) {
    url.searchParams.set('force_refresh', 'true');
  }

  try {
    const response = await fetch(url.toString());
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    const data = await response.json();
    return data.plans;
  } catch (error) {
    console.error('Error fetching subscription plans:', error);
    throw error;
  }
}

// Usage
getSubscriptionPlans()
  .then(plans => {
    console.log('Available plans:', plans);
    plans.forEach(plan => {
      console.log(`${plan.name}: $${plan.amount}/${plan.interval}`);
    });
  })
  .catch(error => {
    console.error('Failed to load plans:', error);
  });
```

## Using Plan Data

### Displaying Plans

The plans array is automatically sorted by:
1. Popular plans first
2. Annual plans before monthly
3. Lower interval counts first

You can display plans directly without additional sorting:

```typescript
// Plans are already sorted optimally
plans.forEach(plan => {
  // Display plan
});
```

### Formatting Prices

```typescript
function formatPrice(plan: SubscriptionPlan): string {
  if (plan.amount === null || !plan.currency) {
    return 'Price not available';
  }

  const formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: plan.currency,
  });

  const intervalText = plan.interval_count === 1 
    ? plan.interval 
    : `every ${plan.interval_count} ${plan.interval}s`;

  return `${formatter.format(plan.amount)} / ${intervalText}`;
}

// Usage
const priceText = formatPrice(plan);
// Output: "$9.99 / month" or "$99.99 / year"
```

### Highlighting Popular Plans

```typescript
{plans.map(plan => (
  <div className={plan.popular ? 'plan-card popular' : 'plan-card'}>
    {plan.popular && (
      <div className="popular-badge">Most Popular</div>
    )}
    {/* Plan content */}
  </div>
))}
```

### Using Price ID for Payment

The `priceId` field is required when creating a payment intent or subscription:

```typescript
// When user selects a plan
const selectedPlan = plans.find(p => p.id === selectedPlanId);

// Use priceId for payment
const paymentIntent = await createPaymentIntent({
  user_id: currentUserId,
  price_id: selectedPlan.priceId,  // Use this
});
```

## Error Handling

### HTTP Status Codes

| Status Code | Description | Action |
|-------------|-------------|--------|
| `200 OK` | Success | Use the returned plans |
| `500 Internal Server Error` | Server error | Show error message, retry after delay |

### Error Response Format

```json
{
  "detail": "Failed to fetch subscription plans: [error message]"
}
```

### Error Handling Example

```typescript
try {
  const data = await fetchSubscriptionPlans();
  setPlans(data.plans);
} catch (error) {
  if (error instanceof Error) {
    console.error('Error:', error.message);
    // Show user-friendly error message
    setError('Unable to load subscription plans. Please try again later.');
  }
}
```

## Caching Behavior

- Plans are cached for **5 minutes** by default
- Use `force_refresh=true` to bypass cache when needed
- Cache is automatically refreshed after expiration
- Recommended: Only use `force_refresh` when user explicitly requests refresh

```typescript
// Normal request (uses cache if available)
const plans = await fetchSubscriptionPlans();

// Force refresh (bypass cache)
const freshPlans = await fetchSubscriptionPlans(true);
```

## Best Practices

### 1. Handle Empty Plans Array

```typescript
if (plans.length === 0) {
  return <div>No subscription plans available at this time.</div>;
}
```

### 2. Validate Required Fields

```typescript
function isValidPlan(plan: SubscriptionPlan): boolean {
  return !!(
    plan.id &&
    plan.name &&
    plan.priceId &&  // Required for payment
    plan.interval
  );
}

const validPlans = plans.filter(isValidPlan);
```

### 3. Display Fallback for Missing Price

```typescript
{plan.amount !== null ? (
  <div>${plan.amount.toFixed(2)} / {plan.interval}</div>
) : (
  <div>Contact us for pricing</div>
)}
```

### 4. Group Plans by Product

```typescript
// Group plans by productId if you have multiple products
const plansByProduct = plans.reduce((acc, plan) => {
  const productId = plan.productId || 'unknown';
  if (!acc[productId]) {
    acc[productId] = [];
  }
  acc[productId].push(plan);
  return acc;
}, {} as Record<string, SubscriptionPlan[]>);
```

### 5. Filter by Interval

```typescript
// Get only monthly plans
const monthlyPlans = plans.filter(p => p.interval === 'month');

// Get only annual plans
const annualPlans = plans.filter(p => p.interval === 'year');
```

## Integration with Payment Flow

After fetching plans, use the `priceId` to create a payment intent:

```typescript
// 1. Fetch plans
const plans = await fetchSubscriptionPlans();

// 2. User selects a plan
const selectedPlan = plans[0]; // User's selection

// 3. Create payment intent with priceId
const paymentIntent = await fetch('/api/subscriptions/create-payment-intent', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    user_id: currentUserId,
    price_id: selectedPlan.priceId,  // From the plan
  }),
});

// 4. Continue with PaymentSheet flow
```

## Notes

- **Dynamic Discovery**: Plans are automatically discovered from Stripe, so you don't need to update code when adding/removing plans
- **Product Metadata**: Features can be configured in Stripe product metadata (comma-separated or JSON array)
- **Popular Flag**: Set `popular: true` in product metadata to mark a plan as recommended
- **Campaign Filtering**: Backend can filter products by metadata if `STRIPE_PRODUCT_CAMPAIGN` is configured
- **Fallback**: If Stripe is unavailable, the endpoint falls back to environment variables (`STRIPE_PRICE_ID_MONTHLY`, `STRIPE_PRICE_ID_ANNUAL`)

## Troubleshooting

### Empty Plans Array

1. **Check Stripe Dashboard**: Ensure products are marked as "Active"
2. **Verify Prices**: Each product must have at least one active recurring price
3. **Check Logs**: Backend logs will indicate why plans aren't being returned
4. **Force Refresh**: Try `?force_refresh=true` to bypass cache

### Missing Price Information

- `amount` and `currency` may be `null` if price data isn't available
- Always check for `null` before displaying prices
- Use `priceId` for payment operations regardless of `amount` value

### Cache Issues

- Plans are cached for 5 minutes
- Use `force_refresh=true` if you need immediate updates
- Cache is shared across all requests

## Example: Complete Subscription Selection Flow

```typescript
import React, { useState, useEffect } from 'react';
import { fetchSubscriptionPlans, SubscriptionPlan } from './api';

export function SubscriptionSelector() {
  const [plans, setPlans] = useState<SubscriptionPlan[]>([]);
  const [selectedPlan, setSelectedPlan] = useState<SubscriptionPlan | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSubscriptionPlans()
      .then(data => {
        setPlans(data.plans);
        // Auto-select popular plan if available
        const popularPlan = data.plans.find(p => p.popular);
        if (popularPlan) {
          setSelectedPlan(popularPlan);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  }, []);

  const handleSubscribe = async () => {
    if (!selectedPlan) return;

    try {
      // Create payment intent with selected plan's priceId
      const response = await fetch('/api/subscriptions/create-payment-intent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          user_id: getCurrentUserId(),
          price_id: selectedPlan.priceId,
        }),
      });

      const { client_secret, customer_id, customer_ephemeral_key_secret } = 
        await response.json();

      // Initialize Stripe PaymentSheet with client_secret
      // ... your PaymentSheet implementation
    } catch (error) {
      console.error('Subscription error:', error);
    }
  };

  if (loading) return <div>Loading...</div>;

  return (
    <div>
      <h2>Choose Your Plan</h2>
      <div className="plans-grid">
        {plans.map(plan => (
          <div
            key={plan.id}
            className={`plan ${selectedPlan?.id === plan.id ? 'selected' : ''} ${
              plan.popular ? 'popular' : ''
            }`}
            onClick={() => setSelectedPlan(plan)}
          >
            {plan.popular && <span className="badge">Recommended</span>}
            <h3>{plan.name}</h3>
            {plan.amount && (
              <div className="price">
                ${plan.amount.toFixed(2)}/{plan.interval}
              </div>
            )}
            <p>{plan.description}</p>
            <ul>
              {plan.features.map((feature, i) => (
                <li key={i}>{feature}</li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      <button 
        onClick={handleSubscribe} 
        disabled={!selectedPlan}
      >
        Subscribe to {selectedPlan?.name || 'Selected Plan'}
      </button>
    </div>
  );
}
```

