# Billing: MongoDB schema (Apple IAP parity + Stripe)

This document specifies subscription fields for the API server (not stored in this mobile repo). Store one logical subscription/entitlement record per user (e.g. `users.subscription` embedded document or `subscriptions` collection keyed by `user_id`).

## Core

| Field | Type | Description |
|-------|------|-------------|
| `billing_provider` | `"stripe"` \| `"apple"` \| `null` | Merchant of record for the current paid subscription. `null` / absent = free tier. |

## Invariants

- When `billing_provider === "stripe"`, treat Apple IAP fields as `null` (ignore if stale).
- When `billing_provider === "apple"`, treat Stripe subscription IDs as `null` (ignore if stale).

## Stripe (typical existing fields)

- `stripe_customer_id`, `stripe_subscription_id`
- `stripe_price_id` / `stripe_product_id` (or equivalent)
- Status aligned with Stripe (`active`, `trialing`, `past_due`, `canceled`, …)
- `subscription_current_period_end` (ISO), `cancel_at_period_end`, etc.

## Apple IAP (add)

| Field | Type | Description |
|-------|------|-------------|
| `apple_original_transaction_id` | string | Stable subscription key; idempotency for verify + ASSN correlation |
| `apple_latest_transaction_id` | string | Latest renewal transaction |
| `apple_product_id` | string | App Store SKU |
| `apple_subscription_group_id` | string (optional) | Subscription group |
| `apple_environment` | `"sandbox"` \| `"production"` | |
| `apple_auto_renew_status` | boolean or enum | From decoded transaction / App Store Server API |
| `subscription_current_period_end` | ISO string | Same field name as Stripe path; set from Apple expiry when Apple is provider |
| `apple_last_verified_at` | ISO string | Last successful server validation |

Optional: `apple_offer_*` for offer codes.

## Indexes

- **Unique sparse** index on `apple_original_transaction_id` scoped by environment if sandbox and production share one database.

## Unified entitlement (projection)

Derive and store or compute on read:

- `entitlement_active` (boolean)
- `can_initiate_new_paid_subscription` (boolean) — `false` when user is already entitled via **either** merchant (prevents double billing)
- `cross_platform_billing` (boolean) — management UX: `true` when the **client OS** is not where cancel/upgrade is done (iOS + Stripe billing, or Android + Apple billing)

See [BILLING_UNIFIED_ENTITLEMENT_AND_ELIGIBILITY.md](./BILLING_UNIFIED_ENTITLEMENT_AND_ELIGIBILITY.md).

---

## Collection: `subscription_product_catalog` (remote config)

Configuration only — **not** per-user subscription state. Default collection name; override with env `MONGODB_SUBSCRIPTION_PRODUCT_CATALOG_COLLECTION`.

**Phase 1 (iOS / Apple):** one document per `(platform, billingProvider, environment)`, e.g. `_id: "apple_ios_production"`:

| Field | Type | Description |
|-------|------|-------------|
| `platform` | `"ios"` \| `"android"` | |
| `billingProvider` | `"apple"` \| `"stripe"` | |
| `environment` | `"production"` \| `"sandbox"` | Catalog doc matched using `APP_STORE_USE_SANDBOX` (sandbox vs production); falls back to production doc if sandbox doc missing |
| `products` | array | Embedded product rows |

Each element of `products` (Apple):

| Field | Type | Description |
|-------|------|-------------|
| `productId` | string | App Store SKU |
| `planKey` | string | Logical plan persisted as `subscriptionPlan` / used in API `applePlanKey` |
| `rank` | integer | Relative tier for UX (higher = higher tier); exposed as `applePlanRank` on `GET /api/subscriptions/{user_id}` |
| `enabled` | boolean | Optional; default treat as true |
| `label` | string | Optional display string for clients |

The API merges SKU → `planKey` from this catalog with `APP_STORE_PRODUCT_PLAN_MAP_JSON` (**Mongo wins** on duplicate SKUs). Client UX patterns: [IOS_APPLE_SUBSCRIPTION_TIER_UX.md](./IOS_APPLE_SUBSCRIPTION_TIER_UX.md).
