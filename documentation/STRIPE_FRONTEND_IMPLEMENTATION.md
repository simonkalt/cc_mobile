# Stripe Frontend Implementation Guide

Complete guide for implementing Stripe payment processing and subscription management in your frontend application.

## Table of Contents

1. [Overview](#overview)
2. [Setup & Installation](#setup--installation)
3. [Stripe Elements Integration](#stripe-elements-integration)
4. [Payment Method Collection](#payment-method-collection)
5. [Subscription Management](#subscription-management)
6. [Error Handling](#error-handling)
7. [Complete React Examples](#complete-react-examples)
8. [Best Practices](#best-practices)
9. [Testing](#testing)

---

## Overview

This guide covers integrating Stripe for subscription management in your frontend application. The backend provides subscription endpoints that work with Stripe to handle:

- **Subscription Creation**: Create new subscriptions with payment methods
- **Subscription Upgrades**: Upgrade to higher-tier plans
- **Subscription Cancellation**: Cancel subscriptions (immediate or at period end)
- **Subscription Status**: Check current subscription status and details

### Backend API Endpoints

- `GET /api/subscriptions/{user_id}` - Get user's subscription information
- `POST /api/subscriptions/subscribe` - Create a new subscription
- `PUT /api/subscriptions/upgrade` - Upgrade subscription to a new plan
- `POST /api/subscriptions/cancel` - Cancel subscription

### Stripe Integration Flow

1. **Frontend**: Collect payment method using Stripe Elements
2. **Frontend**: Send payment method ID to backend
3. **Backend**: Creates Stripe customer (if needed) and subscription
4. **Backend**: Returns subscription details
5. **Frontend**: Display subscription status and manage subscription

---

## Setup & Installation

### 1. Install Stripe.js

```bash
npm install @stripe/stripe-js @stripe/react-stripe-js
# or
yarn add @stripe/stripe-js @stripe/react-stripe-js
```

### 2. Get Stripe Publishable Key

You'll need your Stripe publishable key. This should be different for test and production:

- **Test Mode**: `pk_test_...`
- **Production Mode**: `pk_live_...`

**Important**: Never expose your secret key (`sk_...`) in frontend code. Only use publishable keys.

### 3. Environment Variables

Add to your `.env` file:

```env
REACT_APP_STRIPE_PUBLISHABLE_KEY=pk_test_your_test_key_here
REACT_APP_STRIPE_ENV=test  # or 'production'
```

For production:

```env
REACT_APP_STRIPE_PUBLISHABLE_KEY=pk_live_your_live_key_here
REACT_APP_STRIPE_ENV=production
```

### 4. Stripe Provider Setup

Wrap your app with Stripe Provider:

```javascript
// src/App.js
import { loadStripe } from '@stripe/stripe-js';
import { Elements } from '@stripe/react-stripe-js';
import App from './components/App';

const stripePromise = loadStripe(process.env.REACT_APP_STRIPE_PUBLISHABLE_KEY);

function App() {
  return (
    <Elements stripe={stripePromise}>
      <App />
    </Elements>
  );
}

export default App;
```

---

## Stripe Elements Integration

### Basic Payment Form Component

```javascript
// src/components/PaymentForm.js
import React, { useState } from 'react';
import {
  CardElement,
  useStripe,
  useElements
} from '@stripe/react-stripe-js';
import './PaymentForm.css';

const PaymentForm = ({ onPaymentMethodCreated, onError }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Get card element
      const cardElement = elements.getElement(CardElement);

      // Create payment method
      const { error: pmError, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: cardElement,
      });

      if (pmError) {
        setError(pmError.message);
        setLoading(false);
        if (onError) onError(pmError);
        return;
      }

      // Payment method created successfully
      if (onPaymentMethodCreated) {
        onPaymentMethodCreated(paymentMethod.id);
      }

      setLoading(false);
    } catch (err) {
      setError(err.message || 'An error occurred');
      setLoading(false);
      if (onError) onError(err);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="payment-form">
      <div className="card-element-container">
        <CardElement
          options={{
            style: {
              base: {
                fontSize: '16px',
                color: '#424770',
                '::placeholder': {
                  color: '#aab7c4',
                },
              },
              invalid: {
                color: '#9e2146',
              },
            },
          }}
        />
      </div>

      {error && <div className="error-message">{error}</div>}

      <button
        type="submit"
        disabled={!stripe || loading}
        className="submit-button"
      >
        {loading ? 'Processing...' : 'Add Payment Method'}
      </button>
    </form>
  );
};

export default PaymentForm;
```

### Payment Form Styles

```css
/* src/components/PaymentForm.css */
.payment-form {
  max-width: 500px;
  margin: 0 auto;
  padding: 20px;
}

.card-element-container {
  padding: 12px;
  border: 1px solid #e0e0e0;
  border-radius: 4px;
  margin-bottom: 20px;
  background: white;
}

.error-message {
  color: #dc3545;
  font-size: 14px;
  margin-bottom: 15px;
  padding: 10px;
  background-color: #f8d7da;
  border: 1px solid #f5c6cb;
  border-radius: 4px;
}

.submit-button {
  width: 100%;
  padding: 12px;
  background-color: #007bff;
  color: white;
  border: none;
  border-radius: 4px;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: background-color 0.2s;
}

.submit-button:hover:not(:disabled) {
  background-color: #0056b3;
}

.submit-button:disabled {
  background-color: #6c757d;
  cursor: not-allowed;
}
```

---

## Payment Method Collection

### Enhanced Payment Form with Billing Details

```javascript
// src/components/EnhancedPaymentForm.js
import React, { useState } from 'react';
import {
  CardElement,
  useStripe,
  useElements
} from '@stripe/react-stripe-js';

const EnhancedPaymentForm = ({ onPaymentMethodCreated, userEmail, userName }) => {
  const stripe = useStripe();
  const elements = useElements();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [billingDetails, setBillingDetails] = useState({
    name: userName || '',
    email: userEmail || '',
    address: {
      line1: '',
      city: '',
      state: '',
      postal_code: '',
      country: 'US',
    },
  });

  const handleSubmit = async (event) => {
    event.preventDefault();

    if (!stripe || !elements) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const cardElement = elements.getElement(CardElement);

      const { error: pmError, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: cardElement,
        billing_details: {
          name: billingDetails.name,
          email: billingDetails.email,
          address: {
            line1: billingDetails.address.line1,
            city: billingDetails.address.city,
            state: billingDetails.address.state,
            postal_code: billingDetails.address.postal_code,
            country: billingDetails.address.country,
          },
        },
      });

      if (pmError) {
        setError(pmError.message);
        setLoading(false);
        return;
      }

      if (onPaymentMethodCreated) {
        onPaymentMethodCreated(paymentMethod.id);
      }

      setLoading(false);
    } catch (err) {
      setError(err.message || 'An error occurred');
      setLoading(false);
    }
  };

  return (
    <form onSubmit={handleSubmit}>
      <div>
        <label>Cardholder Name</label>
        <input
          type="text"
          value={billingDetails.name}
          onChange={(e) => setBillingDetails({ ...billingDetails, name: e.target.value })}
          required
        />
      </div>

      <div>
        <label>Email</label>
        <input
          type="email"
          value={billingDetails.email}
          onChange={(e) => setBillingDetails({ ...billingDetails, email: e.target.value })}
          required
        />
      </div>

      <div>
        <label>Card Details</label>
        <CardElement
          options={{
            style: {
              base: {
                fontSize: '16px',
                color: '#424770',
                '::placeholder': {
                  color: '#aab7c4',
                },
              },
            },
          }}
        />
      </div>

      <div>
        <label>Address Line 1</label>
        <input
          type="text"
          value={billingDetails.address.line1}
          onChange={(e) => setBillingDetails({
            ...billingDetails,
            address: { ...billingDetails.address, line1: e.target.value }
          })}
        />
      </div>

      <div>
        <label>City</label>
        <input
          type="text"
          value={billingDetails.address.city}
          onChange={(e) => setBillingDetails({
            ...billingDetails,
            address: { ...billingDetails.address, city: e.target.value }
          })}
        />
      </div>

      <div>
        <label>State</label>
        <input
          type="text"
          value={billingDetails.address.state}
          onChange={(e) => setBillingDetails({
            ...billingDetails,
            address: { ...billingDetails.address, state: e.target.value }
          })}
        />
      </div>

      <div>
        <label>Postal Code</label>
        <input
          type="text"
          value={billingDetails.address.postal_code}
          onChange={(e) => setBillingDetails({
            ...billingDetails,
            address: { ...billingDetails.address, postal_code: e.target.value }
          })}
        />
      </div>

      {error && <div className="error">{error}</div>}

      <button type="submit" disabled={!stripe || loading}>
        {loading ? 'Processing...' : 'Add Payment Method'}
      </button>
    </form>
  );
};

export default EnhancedPaymentForm;
```

---

## Subscription Management

### Subscription Service

```javascript
// src/services/subscriptionService.js
import apiClient from './apiClient';
import { API_ENDPOINTS } from '../config/api';

/**
 * Get user's subscription information
 */
export const getUserSubscription = async (userId) => {
  try {
    const response = await apiClient.get(`/api/subscriptions/${userId}`);
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Failed to fetch subscription');
    }
    throw new Error('Network error: Could not fetch subscription');
  }
};

/**
 * Create a new subscription
 */
export const createSubscription = async (userId, priceId, paymentMethodId, trialDays = null) => {
  try {
    const response = await apiClient.post('/api/subscriptions/subscribe', {
      user_id: userId,
      price_id: priceId,
      payment_method_id: paymentMethodId,
      trial_days: trialDays,
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Failed to create subscription');
    }
    throw new Error('Network error: Could not create subscription');
  }
};

/**
 * Upgrade subscription to a new plan
 */
export const upgradeSubscription = async (userId, newPriceId) => {
  try {
    const response = await apiClient.put('/api/subscriptions/upgrade', {
      user_id: userId,
      new_price_id: newPriceId,
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Failed to upgrade subscription');
    }
    throw new Error('Network error: Could not upgrade subscription');
  }
};

/**
 * Cancel subscription
 */
export const cancelSubscription = async (userId, cancelImmediately = false) => {
  try {
    const response = await apiClient.post('/api/subscriptions/cancel', {
      user_id: userId,
      cancel_immediately: cancelImmediately,
    });
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(error.response.data.detail || 'Failed to cancel subscription');
    }
    throw new Error('Network error: Could not cancel subscription');
  }
};
```

---

## Error Handling

### Stripe Error Handler

```javascript
// src/utils/stripeErrorHandler.js
export const handleStripeError = (error) => {
  // Stripe-specific error codes
  if (error.code) {
    switch (error.code) {
      case 'card_declined':
        return {
          type: 'card_declined',
          message: 'Your card was declined. Please try a different payment method.',
          userMessage: 'Your card was declined. Please check your card details or try a different card.',
        };
      case 'expired_card':
        return {
          type: 'expired_card',
          message: 'Your card has expired.',
          userMessage: 'Your card has expired. Please use a different card.',
        };
      case 'incorrect_cvc':
        return {
          type: 'incorrect_cvc',
          message: 'Your card\'s security code is incorrect.',
          userMessage: 'The security code on your card is incorrect. Please check and try again.',
        };
      case 'insufficient_funds':
        return {
          type: 'insufficient_funds',
          message: 'Your card has insufficient funds.',
          userMessage: 'Your card has insufficient funds. Please try a different payment method.',
        };
      case 'invalid_expiry_month':
        return {
          type: 'invalid_expiry_month',
          message: 'Your card\'s expiration month is invalid.',
          userMessage: 'The expiration month on your card is invalid. Please check and try again.',
        };
      case 'invalid_expiry_year':
        return {
          type: 'invalid_expiry_year',
          message: 'Your card\'s expiration year is invalid.',
          userMessage: 'The expiration year on your card is invalid. Please check and try again.',
        };
      case 'invalid_number':
        return {
          type: 'invalid_number',
          message: 'Your card number is invalid.',
          userMessage: 'Your card number is invalid. Please check and try again.',
        };
      case 'processing_error':
        return {
          type: 'processing_error',
          message: 'An error occurred while processing your card. Please try again.',
          userMessage: 'An error occurred while processing your payment. Please try again.',
        };
      default:
        return {
          type: 'unknown',
          message: error.message || 'An error occurred',
          userMessage: 'An error occurred processing your payment. Please try again.',
        };
    }
  }

  // Generic error
  return {
    type: 'unknown',
    message: error.message || 'An error occurred',
    userMessage: 'An error occurred. Please try again.',
  };
};
```

---

## Complete React Examples

### Subscription Plan Selection Component

```javascript
// src/components/SubscriptionPlans.js
import React, { useState, useEffect } from 'react';
import { useStripe, useElements, CardElement } from '@stripe/react-stripe-js';
import { createSubscription, getUserSubscription } from '../services/subscriptionService';
import { useUser } from '../context/UserContext';
import { handleStripeError } from '../utils/stripeErrorHandler';

// Define your subscription plans with Stripe Price IDs
const SUBSCRIPTION_PLANS = [
  {
    id: 'basic',
    name: 'Basic',
    price: '$9.99',
    priceId: 'price_basic_monthly', // Replace with your actual Stripe Price ID
    features: [
      '10 cover letters per month',
      'Basic templates',
      'Email support',
    ],
  },
  {
    id: 'premium',
    name: 'Premium',
    price: '$19.99',
    priceId: 'price_premium_monthly', // Replace with your actual Stripe Price ID
    features: [
      'Unlimited cover letters',
      'All templates',
      'Priority support',
      'PDF export',
    ],
    popular: true,
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: '$49.99',
    priceId: 'price_enterprise_monthly', // Replace with your actual Stripe Price ID
    features: [
      'Everything in Premium',
      'Custom templates',
      'Dedicated support',
      'API access',
    ],
  },
];

const SubscriptionPlans = () => {
  const { user } = useUser();
  const stripe = useStripe();
  const elements = useElements();
  const [selectedPlan, setSelectedPlan] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [subscription, setSubscription] = useState(null);
  const [showPaymentForm, setShowPaymentForm] = useState(false);

  useEffect(() => {
    if (user?.id) {
      loadSubscription();
    }
  }, [user]);

  const loadSubscription = async () => {
    try {
      const sub = await getUserSubscription(user.id);
      setSubscription(sub);
    } catch (err) {
      console.error('Failed to load subscription:', err);
    }
  };

  const handlePlanSelect = (plan) => {
    setSelectedPlan(plan);
    setShowPaymentForm(true);
    setError(null);
  };

  const handleSubscribe = async (event) => {
    event.preventDefault();

    if (!stripe || !elements || !selectedPlan) {
      return;
    }

    setLoading(true);
    setError(null);

    try {
      // Get card element
      const cardElement = elements.getElement(CardElement);

      // Create payment method
      const { error: pmError, paymentMethod } = await stripe.createPaymentMethod({
        type: 'card',
        card: cardElement,
      });

      if (pmError) {
        const errorInfo = handleStripeError(pmError);
        setError(errorInfo.userMessage);
        setLoading(false);
        return;
      }

      // Create subscription via backend
      const result = await createSubscription(
        user.id,
        selectedPlan.priceId,
        paymentMethod.id,
        selectedPlan.trialDays || null
      );

      // Reload subscription info
      await loadSubscription();

      // Reset form
      setShowPaymentForm(false);
      setSelectedPlan(null);
      elements.getElement(CardElement).clear();

      alert('Subscription created successfully!');
    } catch (err) {
      const errorInfo = handleStripeError(err);
      setError(errorInfo.userMessage || err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="subscription-plans">
      <h2>Choose Your Plan</h2>

      {subscription && subscription.subscriptionStatus !== 'free' && (
        <div className="current-subscription">
          <h3>Current Subscription</h3>
          <p>Plan: {subscription.subscriptionPlan}</p>
          <p>Status: {subscription.subscriptionStatus}</p>
          {subscription.subscriptionCurrentPeriodEnd && (
            <p>
              Renews: {new Date(subscription.subscriptionCurrentPeriodEnd).toLocaleDateString()}
            </p>
          )}
        </div>
      )}

      <div className="plans-grid">
        {SUBSCRIPTION_PLANS.map((plan) => (
          <div
            key={plan.id}
            className={`plan-card ${plan.popular ? 'popular' : ''} ${
              subscription?.subscriptionPlan === plan.id ? 'active' : ''
            }`}
          >
            {plan.popular && <div className="popular-badge">Most Popular</div>}
            <h3>{plan.name}</h3>
            <div className="price">{plan.price}/month</div>
            <ul className="features">
              {plan.features.map((feature, index) => (
                <li key={index}>{feature}</li>
              ))}
            </ul>
            {subscription?.subscriptionPlan === plan.id ? (
              <button disabled className="current-plan-button">
                Current Plan
              </button>
            ) : (
              <button
                onClick={() => handlePlanSelect(plan)}
                className="select-plan-button"
              >
                {subscription?.subscriptionStatus !== 'free' ? 'Switch Plan' : 'Subscribe'}
              </button>
            )}
          </div>
        ))}
      </div>

      {showPaymentForm && selectedPlan && (
        <div className="payment-modal">
          <div className="payment-modal-content">
            <h3>Subscribe to {selectedPlan.name}</h3>
            <p>Price: {selectedPlan.price}/month</p>

            <form onSubmit={handleSubscribe}>
              <div className="card-element-container">
                <CardElement
                  options={{
                    style: {
                      base: {
                        fontSize: '16px',
                        color: '#424770',
                        '::placeholder': {
                          color: '#aab7c4',
                        },
                      },
                    },
                  }}
                />
              </div>

              {error && <div className="error-message">{error}</div>}

              <div className="modal-actions">
                <button
                  type="button"
                  onClick={() => {
                    setShowPaymentForm(false);
                    setSelectedPlan(null);
                    setError(null);
                  }}
                  className="cancel-button"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={!stripe || loading}
                  className="submit-button"
                >
                  {loading ? 'Processing...' : 'Subscribe'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default SubscriptionPlans;
```

### Subscription Management Component

```javascript
// src/components/SubscriptionManagement.js
import React, { useState, useEffect } from 'react';
import {
  getUserSubscription,
  upgradeSubscription,
  cancelSubscription,
} from '../services/subscriptionService';
import { useUser } from '../context/UserContext';
import { handleApiError } from '../utils/errorHandler';

const SubscriptionManagement = () => {
  const { user } = useUser();
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [showCancelConfirm, setShowCancelConfirm] = useState(false);

  useEffect(() => {
    if (user?.id) {
      loadSubscription();
    }
  }, [user]);

  const loadSubscription = async () => {
    try {
      setLoading(true);
      const sub = await getUserSubscription(user.id);
      setSubscription(sub);
      setError(null);
    } catch (err) {
      const errorInfo = handleApiError(err);
      setError(errorInfo.message);
    } finally {
      setLoading(false);
    }
  };

  const handleUpgrade = async (newPriceId) => {
    try {
      setActionLoading(true);
      await upgradeSubscription(user.id, newPriceId);
      await loadSubscription();
      alert('Subscription upgraded successfully!');
    } catch (err) {
      const errorInfo = handleApiError(err);
      alert(`Failed to upgrade: ${errorInfo.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  const handleCancel = async (cancelImmediately = false) => {
    try {
      setActionLoading(true);
      await cancelSubscription(user.id, cancelImmediately);
      await loadSubscription();
      setShowCancelConfirm(false);
      alert(
        cancelImmediately
          ? 'Subscription canceled immediately.'
          : 'Subscription will be canceled at the end of the current period.'
      );
    } catch (err) {
      const errorInfo = handleApiError(err);
      alert(`Failed to cancel: ${errorInfo.message}`);
    } finally {
      setActionLoading(false);
    }
  };

  if (loading) {
    return <div>Loading subscription information...</div>;
  }

  if (error) {
    return <div className="error">Error: {error}</div>;
  }

  if (!subscription || subscription.subscriptionStatus === 'free') {
    return (
      <div>
        <h2>Subscription Management</h2>
        <p>You don't have an active subscription.</p>
        <p>Visit the pricing page to subscribe to a plan.</p>
      </div>
    );
  }

  return (
    <div className="subscription-management">
      <h2>Subscription Management</h2>

      <div className="subscription-details">
        <h3>Current Subscription</h3>
        <div className="detail-row">
          <span className="label">Plan:</span>
          <span className="value">{subscription.subscriptionPlan}</span>
        </div>
        <div className="detail-row">
          <span className="label">Status:</span>
          <span className="value">{subscription.subscriptionStatus}</span>
        </div>
        {subscription.subscriptionCurrentPeriodEnd && (
          <div className="detail-row">
            <span className="label">Current Period Ends:</span>
            <span className="value">
              {new Date(subscription.subscriptionCurrentPeriodEnd).toLocaleDateString()}
            </span>
          </div>
        )}
        {subscription.lastPaymentDate && (
          <div className="detail-row">
            <span className="label">Last Payment:</span>
            <span className="value">
              {new Date(subscription.lastPaymentDate).toLocaleDateString()}
            </span>
          </div>
        )}
      </div>

      <div className="subscription-actions">
        <h3>Actions</h3>

        {/* Upgrade Options */}
        {subscription.subscriptionPlan !== 'enterprise' && (
          <div className="action-section">
            <h4>Upgrade Plan</h4>
            <button
              onClick={() => handleUpgrade('price_premium_monthly')}
              disabled={actionLoading}
            >
              Upgrade to Premium
            </button>
            {subscription.subscriptionPlan === 'basic' && (
              <button
                onClick={() => handleUpgrade('price_enterprise_monthly')}
                disabled={actionLoading}
              >
                Upgrade to Enterprise
              </button>
            )}
          </div>
        )}

        {/* Cancel Subscription */}
        <div className="action-section">
          <h4>Cancel Subscription</h4>
          {!showCancelConfirm ? (
            <button
              onClick={() => setShowCancelConfirm(true)}
              className="cancel-button"
            >
              Cancel Subscription
            </button>
          ) : (
            <div className="cancel-confirmation">
              <p>How would you like to cancel?</p>
              <button
                onClick={() => handleCancel(false)}
                disabled={actionLoading}
                className="cancel-at-period-end"
              >
                Cancel at Period End (Recommended)
              </button>
              <button
                onClick={() => handleCancel(true)}
                disabled={actionLoading}
                className="cancel-immediately"
              >
                Cancel Immediately
              </button>
              <button
                onClick={() => setShowCancelConfirm(false)}
                className="cancel-cancel"
              >
                Keep Subscription
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SubscriptionManagement;
```

### Subscription Status Hook

```javascript
// src/hooks/useSubscription.js
import { useState, useEffect } from 'react';
import { getUserSubscription } from '../services/subscriptionService';

export const useSubscription = (userId) => {
  const [subscription, setSubscription] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }

    const loadSubscription = async () => {
      try {
        setLoading(true);
        const sub = await getUserSubscription(userId);
        setSubscription(sub);
        setError(null);
      } catch (err) {
        setError(err.message);
        console.error('Failed to load subscription:', err);
      } finally {
        setLoading(false);
      }
    };

    loadSubscription();

    // Refresh subscription every 5 minutes
    const interval = setInterval(loadSubscription, 5 * 60 * 1000);

    return () => clearInterval(interval);
  }, [userId]);

  const isActive = subscription?.subscriptionStatus === 'active';
  const isTrialing = subscription?.subscriptionStatus === 'trialing';
  const isCanceled = subscription?.subscriptionStatus === 'canceled';
  const isPastDue = subscription?.subscriptionStatus === 'past_due';
  const isFree = subscription?.subscriptionStatus === 'free' || !subscription;

  return {
    subscription,
    loading,
    error,
    isActive,
    isTrialing,
    isCanceled,
    isPastDue,
    isFree,
    hasActiveSubscription: isActive || isTrialing,
    refresh: async () => {
      if (userId) {
        try {
          const sub = await getUserSubscription(userId);
          setSubscription(sub);
        } catch (err) {
          setError(err.message);
        }
      }
    },
  };
};
```

---

## Best Practices

### 1. Security

- **Never expose secret keys**: Only use publishable keys in frontend code
- **Validate on backend**: Always validate payment data on the backend
- **Use HTTPS**: Always use HTTPS in production
- **Handle errors gracefully**: Don't expose sensitive error details to users

### 2. User Experience

- **Show loading states**: Always show loading indicators during payment processing
- **Clear error messages**: Provide user-friendly error messages
- **Confirm actions**: Ask for confirmation before canceling subscriptions
- **Show subscription status**: Display current subscription status clearly

### 3. Error Handling

```javascript
// Example: Comprehensive error handling
const handlePaymentError = (error) => {
  if (error.type === 'card_error') {
    // Card was declined
    showError('Your card was declined. Please try a different payment method.');
  } else if (error.type === 'rate_limit_error') {
    // Too many requests
    showError('Too many requests. Please try again later.');
  } else if (error.type === 'invalid_request_error') {
    // Invalid request
    showError('Invalid request. Please check your information.');
  } else if (error.type === 'api_error') {
    // Stripe API error
    showError('An error occurred with our payment processor. Please try again.');
  } else {
    // Unknown error
    showError('An unexpected error occurred. Please try again.');
  }
};
```

### 4. Testing

Use Stripe test cards for testing:

- **Success**: `4242 4242 4242 4242`
- **Decline**: `4000 0000 0000 0002`
- **Insufficient funds**: `4000 0000 0000 9995`
- **Expired card**: `4000 0000 0000 0069`

Use any future expiry date (e.g., 12/34) and any 3-digit CVC.

---

## Testing

### Test Mode Setup

1. **Get test publishable key** from Stripe Dashboard
2. **Use test cards** for testing payment flows
3. **Monitor test events** in Stripe Dashboard
4. **Test error scenarios** using specific test card numbers

### Test Subscription Flow

```javascript
// Test subscription creation
const testSubscription = async () => {
  const testPriceId = 'price_test_basic'; // Your test price ID
  const testPaymentMethodId = 'pm_test_123'; // From Stripe test
  
  try {
    const result = await createSubscription(
      'test_user_id',
      testPriceId,
      testPaymentMethodId
    );
    console.log('Test subscription created:', result);
  } catch (error) {
    console.error('Test subscription failed:', error);
  }
};
```

---

## Additional Resources

- [Stripe.js Documentation](https://stripe.com/docs/stripe-js)
- [Stripe Elements Documentation](https://stripe.com/docs/stripe-js/react)
- [Stripe Testing Guide](https://stripe.com/docs/testing)
- [Stripe API Reference](https://stripe.com/docs/api)

---

## Support

For issues or questions:
1. Check Stripe Dashboard for payment events
2. Review error messages in browser console
3. Verify API keys are correct for your environment
4. Check backend logs for subscription creation errors

---

**Last Updated**: 2024-12-31

