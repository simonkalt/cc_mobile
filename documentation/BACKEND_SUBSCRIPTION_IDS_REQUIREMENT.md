# Backend: Subscription & Plan IDs Requirement for Billing UI

The mobile app’s Billing tab identifies the user’s **current subscription plan** only by **literal Stripe IDs**. There is no fallback matching by plan name, interval, or tier. For the correct plan to show as “current” (with **Cancel** instead of **Subscribe**), the backend must send the IDs below.

---

## 1. GET User Subscription — Required IDs

**Endpoint:** `GET /api/subscriptions/{user_id}`

When the user has an active (or trialing) subscription, the response **must** include at least one of the following so the app can match to a plan card:

| Field            | Type   | Required    | Description                                                                                                                                                                     |
| ---------------- | ------ | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **`product_id`** | string | Recommended | Stripe Product ID (e.g. `prod_xxxxxxxxxxxxx`). Must match the `productId` / `product_id` of one of the plans returned by `GET /api/subscriptions/plans` or by the products API. |
| **`price_id`**   | string | Recommended | Stripe Price ID (e.g. `price_xxxxxxxxxxxxx`). Must match the `priceId` / `price_id` of one of the plans the app displays.                                                       |

- The app matches **by product ID or by price ID** (either is enough).
- You may send both; the app accepts **snake_case** (`product_id`, `price_id`) or **camelCase** (`productId`, `priceId`).
- If you currently only send `subscription_plan` as a label (e.g. `"monthly"`, `"annual"`, `"2year"`), the app **cannot** match that to a plan. You must also (or instead) send the **Stripe `price_id`** and/or **Stripe `product_id`** for the subscribed price/product.

### Example response (200 OK) with IDs

```json
{
  "subscription_status": "active",
  "subscription_plan": "monthly",
  "subscription_current_period_end": "2025-12-31T23:59:59Z",
  "product_id": "prod_ABC123xyz",
  "price_id": "price_XYZ789abc",
  "subscription_id": "sub_xxxxx",
  "generation_credits": 10,
  "max_credits": 10
}
```

- **Alternative:** If your API already returns `subscription_plan` as the **Stripe Price ID** (e.g. `"price_XYZ789abc"`), the app will use that for matching. In that case, sending `product_id` as well is still recommended for consistency.

---

## 2. Plans / Products APIs — IDs Must Be Preserved

The app loads plans from:

- **`GET /api/subscriptions/plans`**, and/or
- **`GET /api/subscriptions/products`** (with plan data merged when available).

Each plan card the user sees must have:

- **`productId`** or **`product_id`**: Stripe Product ID.
- **`priceId`** or **`price_id`**: Stripe Price ID (used for subscribe/upgrade).

The app does **not** derive or guess IDs (e.g. from plan names or intervals). It only matches when:

`subscription.product_id` === `plan.productId` (or `plan.product_id`)  
**or**  
`subscription.price_id` === `plan.priceId` (or `plan.price_id`).

So:

- Every plan in the plans (and, if used, products) response must include the **exact** Stripe **product** and **price** IDs that you store and return in the subscription response.
- Use the same ID values in both the subscription endpoint and the plans/products endpoints so the app can match them literally.

---

## 3. Summary Checklist for Backend

- [ ] **GET /api/subscriptions/{user_id}** (or equivalent) returns **`product_id`** and/or **`price_id`** (Stripe IDs) when the user has an active subscription.
- [ ] Same IDs are returned whether you use **snake_case** (`product_id`, `price_id`) or **camelCase** (`productId`, `priceId`); the app normalizes both.
- [ ] **GET /api/subscriptions/plans** (and products, if used) returns **`productId`**/`product_id` and **`priceId`**/`price_id` for each plan, and these match the IDs you send in the subscription response.
- [ ] No reliance on plan names or intervals for “current plan” detection; matching is **by ID only**.

---

## 4. Subscription period end — must be current from Stripe

**Field:** `subscription_current_period_end` (or `subscriptionCurrentPeriodEnd`)

The app treats a subscription as **expired** when `subscription_current_period_end` is in the past (i.e. `periodEnd <= now`). If your backend returns an **outdated** value (e.g. from a previous period or from a cached record that wasn’t updated after renewal/upgrade), the app will show the subscription as expired even though Stripe shows it as active.

**Requirement:**

- Return the **current** period end from Stripe for this subscription.
- Use Stripe’s **`current_period_end`** on the subscription object (Unix timestamp or ISO 8601 string). Stripe updates this when the subscription renews or is changed.
- Do **not** return a stored/cached value that might be from an old billing period.
- Prefer reading from Stripe on each request (or from a cache that is updated whenever the subscription is updated in Stripe).

**Example:** If Stripe shows “Current period: Mar 13 – Apr 13, 2026”, the API must return a date/time equivalent to **Apr 13, 2026** (end of that period), not a previous period’s end (e.g. Feb 13, 2026).

**Format:** ISO 8601 is recommended (e.g. `2026-04-13T23:59:59Z`). The app parses the value with `new Date(...)`; avoid sending date-only strings without timezone if you need consistent behavior across user locales.

---

## 5. Why This Matters

If the subscription response does **not** include `product_id` or `price_id` (or `subscription_plan` as a Stripe price ID), the app cannot determine which plan card is the user’s current one. Every plan will show **Subscribe** instead of **Cancel** for the plan the user is already on. Sending the Stripe IDs from your subscription record fixes this. If `subscription_current_period_end` is not the **current** period end from Stripe (e.g. from a previous period or cached), the app will show the subscription as expired even though it is active in Stripe.
