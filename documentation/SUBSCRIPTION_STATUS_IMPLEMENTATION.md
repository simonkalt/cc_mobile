# Subscription Status — Frontend Implementation Contract

This document defines how every Stripe subscription status maps to frontend behavior
in the Billing tab. Backend must return these exact `subscriptionStatus` strings.

---

## Stripe Subscription Statuses

| Status | Stripe Meaning | Frontend Treatment |
|---|---|---|
| `active` | Payment collected, subscription running | ✅ Current plan; shows "Cancel Subscription" |
| `trialing` | Free trial period, no payment yet | ✅ Current plan; shows "Cancel Subscription" |
| `incomplete` | Created but first payment not yet collected | ⏳ Pending — NOT treated as active; no cancel button; no "current plan" badge |
| `incomplete_expired` | First payment never completed; Stripe has abandoned it | ❌ Inactive — treated as no subscription |
| `past_due` | Renewal payment failed; Stripe retrying | ⚠️ Treat as inactive (user should update payment method) |
| `canceled` | Subscription explicitly canceled | ⚠️ Two sub-cases — see Grace Period section below |
| `unpaid` | All retry attempts exhausted; not canceled but unpaid | ❌ Inactive |
| `paused` | Subscription paused (Stripe feature, rarely used) | ⚠️ Treat as inactive unless explicitly required |

---

## The `subscriptionPlan` Field

The backend must return the **actual price ID** (e.g. `price_1Sk…`) or product ID slug
in `subscriptionPlan`, never the string `"free"`, when a real subscription exists.

`"free"` is only a valid value when there is no paid subscription at all
(`subscriptionId` is null/absent). Returning `subscriptionPlan: "free"` alongside a
real `subscriptionId` prevents the frontend from identifying which plan is current
(`matchesByPriceId` will always be false).

---

## Grace-Period Cancellation ("Cancels on Date X")

When a user cancels but their paid period has not yet ended, Stripe can report status as
either:

- `active` + `cancel_at_period_end: true` — most common form
- `canceled` + `current_period_end` still in the future — less common

In both cases the frontend needs to know it is a **scheduled cancellation** still within
the paid period. Backend must surface at least one of the following fields alongside the
subscription object so the frontend can detect this state:

| Field | Type | Notes |
|---|---|---|
| `cancelAtPeriodEnd` | `boolean` | `true` when Stripe's `cancel_at_period_end` is set |
| `canceledAt` | ISO-8601 string | Stripe's `canceled_at` unix timestamp as a date string |
| `subscriptionCurrentPeriodEnd` | ISO-8601 string | Period end date; required to show "Cancels on …" |

### Frontend behavior for grace-period cancellation

- Badge: **"Current Plan"** (still paid through period end).
- Button: **"Cancellation Scheduled"** (disabled — no further action needed).
- Renewal date line: Shows "Cancels on [date]" rather than "Renews on [date]".

---

## `isCurrentPlan` Decision Matrix

```
subscriptionStatus  | matchesByProductId | matchesByPriceId | cancelAtPeriodEnd | isCurrentPlan
--------------------|--------------------|--------------------|-------------------|-------------
active              | true               | any                | false             | YES
active              | true               | any                | true              | YES (grace)
trialing            | true               | any                | any               | YES
incomplete          | any                | any                | any               | NO
incomplete_expired  | any                | any                | any               | NO
past_due            | any                | any                | any               | NO
canceled            | true               | any                | true (in period)  | YES (grace)
canceled            | true               | any                | false             | NO
unpaid              | any                | any                | any               | NO
```

---

## "Cancel Subscription" Button Visibility Rules

| Condition | Show button? | Button state |
|---|---|---|
| `isCurrentPlan` = true AND `isGracePeriodCanceled` = false | ✅ Yes | Enabled |
| `isCurrentPlan` = true AND `isGracePeriodCanceled` = true  | ✅ Yes | Disabled, label = "Cancellation Scheduled" |
| `isCurrentPlan` = false | ❌ No | — |

---

## Backend Checklist

- [ ] Never return `subscriptionPlan: "free"` when a real `subscriptionId` is present.
- [ ] Return `priceId` and `productId` for the active subscription so the frontend can
      match plans by price and product.
- [ ] Return `cancelAtPeriodEnd: true` whenever Stripe's `cancel_at_period_end` is set.
- [ ] Return `canceledAt` as an ISO-8601 string whenever `canceled_at` is set in Stripe.
- [ ] Return `subscriptionCurrentPeriodEnd` as an ISO-8601 string for every active or
      grace-period subscription.
- [ ] When multiple subscriptions exist for a user, return only the **most relevant
      one** (precedence: `active` > `trialing` > `incomplete` > `past_due`). Do not
      return an `incomplete` subscription as the primary subscription if an `active` one
      also exists.
