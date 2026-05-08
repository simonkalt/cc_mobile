# iOS / Apple subscription tier UX (rank-based)

Phase 1 uses MongoDB **`subscription_product_catalog`** (see [BILLING_MONGODB_SCHEMA.md](./BILLING_MONGODB_SCHEMA.md)) as the single source of SKU → **`planKey`** + **`rank`**. The API exposes:

- **`GET /api/subscriptions/{user_id}`** — when `billingProvider === "apple"`, **`applePlanKey`** and **`applePlanRank`** for the user’s current subscription SKU (from `appleProductId` / `subscriptionProductId`).
- **`GET /api/subscriptions/apple/catalog`** — ordered **`products`** for building StoreKit rows (`productId`, `planKey`, `rank`, `label`, …).

Do **not** hard-code `MONTHLY001` → tier in the app; use the API.

## Building the billing screen

1. Fetch **`GET /api/subscriptions/apple/catalog`** (optional cache, short TTL).
2. Fetch **`GET /api/subscriptions/{userId}`**.
3. Let **`currentRank`** = `applePlanRank`, **`currentSku`** = `appleProductId` or `productId` when on Apple.

### Row behavior (same ladder as product intent)

For each catalog **`product`** row:

| Condition | Primary action |
|-----------|----------------|
| User has **no** active Apple entitlement (`billingProvider` not apple or status not active) | **Subscribe with Apple** on rows where `enabled !== false` |
| **`product.productId` === `currentSku`** (active Apple sub) | **Manage** (management URL / App Store) |
| **`currentRank`** is set and **`product.rank` &lt; `currentRank`** | **Disable** row (user already on a higher tier in your ladder) |
| **`currentRank`** is set and **`product.rank` &gt; `currentRank`** | **Subscribe with Apple** (upgrade path within the subscription group; server still validates on verify) |

If **`applePlanRank`** is **null** (unknown SKU or empty catalog fallback), show **Manage** when entitled on Apple, but skip disable-by-rank until the snapshot and catalog both resolve.

## Headers

Send **`X-Billing-Correlation-Id`** and optionally **`X-Client-Platform: ios`** on subscription requests per [BILLING_OBSERVABILITY.md](./BILLING_OBSERVABILITY.md).

## Phase 2

Android / Stripe will use the **same collection** with `platform: "android"` / `billingProvider: "stripe"` — see rollout notes in the product plan.
