# Backend request: Apple subscription fields on `GET /api/subscriptions/{user_id}`

## Context

The **iOS Billing** tab combines:

1. **`GET /api/subscriptions/{user_id}`** — entitlement snapshot used across the app  
2. **`GET /api/subscriptions/apple/catalog`** — SKU list with **`rank`** (higher = higher tier)  
3. **StoreKit** — active subscription SKU on the device  

When **`GET /subscriptions`** reports **free tier** (`subscriptionStatus: free`, null Apple identifiers and ranks) **while StoreKit shows an active Apple subscription**, the mobile UI was inconsistent (e.g. one row shows **Manage Subscription**, lower tiers still show **Subscribe with Apple** instead of disabled **Lower tier**).  

The client now **infers tier from StoreKit + catalog** as a fallback, but **the server remains authoritative** for credits, cross‑platform rules, analytics, and consistency after reinstall or new device.

This document lists what the backend should persist and return so **`GET /subscriptions` matches reality** after Apple purchases and restores.

---

## Required behavior after successful `POST /api/subscriptions/apple/verify`

Once verify persists the entitlement, **`GET /api/subscriptions/{user_id}`** must reflect an **Apple-managed paid subscription**, not free tier.

Align field names with **[BILLING_API_CONTRACT.md](./BILLING_API_CONTRACT.md)** and **[BILLING_MONGODB_SCHEMA.md](./BILLING_MONGODB_SCHEMA.md)**.

### Must populate (minimum)

| Field | Purpose |
|-------|--------|
| **`billing_provider`** | **`"apple"`** when entitlement is App Store–managed |
| **`subscription_status`** | Treat as active for subscribers (e.g. **`active`** or **`trialing`**) — **not** `free` while Apple sub is active |
| **`apple_product_id`** (alias **`appleProductId`**) | App Store subscription SKU string |
| **`apple_plan_rank`** (alias **`applePlanRank`**) | Integer **equal to `rank`** for that SKU in **`GET /api/subscriptions/apple/catalog`** |

Optional but recommended for parity with docs / UX:

| Field | Purpose |
|-------|--------|
| **`apple_plan_key`** / **`applePlanKey`** | Stable plan label from catalog |
| **`subscription_current_period_end`** / **`subscriptionCurrentPeriodEnd`** | ISO expiry / renewal anchor |
| **`product_id`** / **`productId`** | May mirror **`apple_product_id`** when `billing_provider === "apple"` |
| **`entitlement_active`** | **`true`** when access should be granted |

### Rank consistency rule

**`apple_plan_rank` must match the catalog:**

- Same integer as the **`rank`** returned for that **`product_id`** on **`GET /api/subscriptions/apple/catalog`**  
- **Higher rank = higher tier** (e.g. annual ≥ monthly ≥ weekly as configured)

If **`apple_plan_rank` is missing or wrong**, tier UX (disable lower tiers vs subscribe / manage) cannot match Stripe-style behavior using server data alone.

### Anti-pattern observed in production debugging

Returning a payload shaped like:

- `subscriptionStatus: "free"`  
- `billingProvider: null`  
- `appleProductId`, `apple_plan_rank`, `subscriptionId`: **null**  

while the user **does** have an active Apple subscription verified elsewhere causes:

- Incorrect **free-tier** flows in parts of the app that trust **`GET /subscriptions`**  
- Extra reliance on StoreKit-only inference on iOS  

**Fix:** After verify (and on subsequent GET), persist and return the Apple snapshot fields above.

---

## Optional: generic `planRank` / `planKey`

If the API uses **`planRank`** / **`planKey`** for non-Stripe plans, ensure either:

- They mirror **`apple_plan_rank`** / **`apple_plan_key`** for Apple users, **or**  
- Prefer emitting **`apple_plan_rank`** explicitly so clients do not depend on ambiguous naming  

The mobile client maps **`planRank` / `plan_rank`** into tier normalization when **`apple_plan_rank`** is absent, but **canonical Apple fields should still be implemented server-side.**

---

## Acceptance checklist

1. Purchase or restore Apple subscription → **`POST …/apple/verify`** succeeds.  
2. Immediate **`GET /api/subscriptions/{user}`**: **`billing_provider`** is **`apple`**, **`subscription_status`** is active (not **`free`**), **`apple_product_id`** set.  
3. **`apple_plan_rank`** equals catalog **`rank`** for that SKU.  
4. Changing tier (upgrade/downgrade via Apple) eventually updates **`apple_product_id`** and **`apple_plan_rank`** on GET after verify/webhooks process the transaction.

---

## References

- [BILLING_API_CONTRACT.md](./BILLING_API_CONTRACT.md) — GET snapshot + verify response shapes  
- [BILLING_MONGODB_SCHEMA.md](./BILLING_MONGODB_SCHEMA.md) — persistence fields  
- [IOS_APPLE_SUBSCRIPTION_TIER_UX.md](./IOS_APPLE_SUBSCRIPTION_TIER_UX.md) — how tier ranks drive Manage / Subscribe / disabled rows  
