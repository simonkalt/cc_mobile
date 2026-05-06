# Billing API contract (mobile ↔ backend)

Mobile callers live in [`src/services/subscriptionService.js`](../src/services/subscriptionService.js). All routes below are under the configured `BACKEND_URL`.

**Auth:** Bearer token for user-specific and mutating routes. Validate that JWT user matches `user_id` in path/body.

**Header:** Clients SHOULD send `X-Billing-Correlation-Id` on every subscription request; servers SHOULD echo it. See [BILLING_OBSERVABILITY.md](./BILLING_OBSERVABILITY.md).

---

## Endpoints (existing)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/subscriptions/products` | Stripe products; `?force_refresh=true` optional |
| GET | `/api/subscriptions/plans` | Stripe plans; `?force_refresh=true` optional |
| GET | `/api/subscriptions/{user_id}` | **Canonical** subscription + entitlement snapshot |
| POST | `/api/subscriptions/create-payment-intent` | Stripe PaymentSheet |
| GET | `/api/subscriptions/payment-intent/{payment_intent_id}` | Poll PaymentIntent |
| POST | `/api/subscriptions/subscribe` | Create Stripe subscription after payment |
| PUT | `/api/subscriptions/upgrade` | Change Stripe plan |
| POST | `/api/subscriptions/cancel` | Body: `user_id`, `cancel_immediately` |
| POST | `/api/subscriptions/apple/verify` | Verify StoreKit JWS; persist Apple entitlement |
| GET | `/api/subscriptions/apple/catalog` | iOS/Apple tier config from Mongo (`planKey`, `rank`, labels); authenticated |

---

## GET `/api/subscriptions/{user_id}` — extended fields

In addition to existing fields (`subscription_status`, `subscription_plan`, `subscription_current_period_end`, `product_id`, `price_id`, `billing_provider`, etc.), the backend SHOULD return:

| Field | Type | Description |
|-------|------|-------------|
| `entitlement_active` | boolean | Unified premium flag (optional if `subscription_status` alone is sufficient) |
| `can_initiate_new_paid_subscription` | boolean | `false` when already entitled via Stripe **or** Apple |
| `cross_platform_billing` | boolean | Management on another surface (see unified entitlement doc) |
| `entitlement_source` | `"stripe"` \| `"apple"` \| null | Optional |
| `applePlanKey` | string \| null | When `billingProvider === "apple"` and SKU maps in `subscription_product_catalog`: logical plan (`monthly`, `semiannual`, `annual`, …) |
| `applePlanRank` | integer \| null | Same condition: integer rank for upgrade/disable UX (higher = higher tier in catalog) |

Apple-specific fields when `billing_provider === "apple"`: see [BILLING_MONGODB_SCHEMA.md](./BILLING_MONGODB_SCHEMA.md). Catalog document layout: **subscription_product_catalog** collection.

---

## GET `/api/subscriptions/apple/catalog`

**Auth:** Bearer JWT (same as other subscription reads).

**Response (JSON):** `environment` (`sandbox` \| `production`, aligned with `APP_STORE_USE_SANDBOX`) and `products[]` with `productId`, `planKey`, `rank`, `enabled`, optional `label` — sorted by `rank` then `productId`. Used to render StoreKit offering rows without hard-coding SKUs; combine with `applePlanKey` / `applePlanRank` on `GET /api/subscriptions/{user_id}` for Manage vs Subscribe vs disabled states.

See also [IOS_APPLE_SUBSCRIPTION_TIER_UX.md](./IOS_APPLE_SUBSCRIPTION_TIER_UX.md) for client-side rank rules.

---

## POST `/api/subscriptions/apple/verify`

**Request body:**

```json
{
  "user_id": "<mongo id>",
  "signed_transaction": "<StoreKit JWS>",
  "product_id": "MONTHLY001",
  "transaction_id": "...",
  "original_transaction_id": "..."
}
```

**Success:** Body equals updated subscription object, or `{ "data": { ... } }` or `{ "subscription": { ... } }` (mobile unwraps in `useSubscription`).

**Errors:** JSON with `detail` and preferably `code`: `apple_validation_failed`, `user_mismatch`, `transaction_already_consumed`, etc.

### Server checklist (needed for Settings → Billing UI after Apple purchase)

The iOS client **must** persist entitlement on your side; Apple’s “purchase successful” sheet does not update MongoDB.

1. **Implement `POST /api/subscriptions/apple/verify`** (or proxy to another service): decode and validate `signed_transaction` (**StoreKit 2-style JWS**) with **App Store Server API** — including **sandbox**, **StoreKit Xcode local testing**, and **production**. If validation only accepts production keys, Xcode Test / Simulator purchases will succeed on-device but **`verify` returns 4xx**, the mobile user sees **“Could not confirm subscription with our servers”**, **`GET /api/subscriptions/{user}` stays on free tier**, and no user document fields appear.

2. **After successful verify**, update the subscription / user record with at least ([`BILLING_MONGODB_SCHEMA.md`](./BILLING_MONGODB_SCHEMA.md)):
   - `billing_provider`: `"apple"`
   - Apple identifiers (`apple_product_id`, `apple_original_transaction_id`, etc.)
   - `subscription_current_period_end` (ISO string from decoded renewal / expiry)
   - `subscription_status`: use a value the client treats as active (see below)

3. **`GET /api/subscriptions/{user_id}` must reflect the new state immediately** (same read model the app already calls via `getUserSubscription`). The mobile app deduces “active Apple subscription” and switches from **Subscribe with Apple** to **App Store subscription / Manage subscription** using:

   - `subscription_status` / `subscriptionStatus`: **`active`** or **`trialing`** (preferred), **or**
   - `entitlement_active` / `entitlementActive`: **`true`**, **or**
   - a future `subscription_current_period_end` later than “now” together with a stable subscription id / plan.

4. **Expose Apple SKU on the snapshot** — at least one of:
   - `apple_product_id` / `appleProductId`: e.g. `MONTHLY001`, `SIXMONTH001`, `ANNUAL001` (aligned with [`src/utils/constants.js`](../src/utils/constants.js)), **or**
   - `product_id` / `productId` set to that **App Store SKU** when `billing_provider === "apple"`.

If `billing_provider` is missing, all Apple SKUs missing, and status stays `free`, the UX will **never leave the storefront** despite a finished StoreKit transaction.

See also [STOREKIT_LOCAL_TESTING.md](./STOREKIT_LOCAL_TESTING.md) (local `.storekit` JWS ≠ production receipts).

---

## GET `/api/subscriptions/purchase-eligibility` (optional)

Query: `?platform=ios` or `?platform=android`

**Response:**

```json
{
  "can_initiate_new_paid_subscription": true,
  "reason": "free | already_entitled | lapsed",
  "billing_provider": "stripe | apple | null"
}
```

Mobile may use this **or** only the extended `GET /api/subscriptions/{user_id}` — keep rules consistent.

---

## Related specs

- [BILLING_MONGODB_SCHEMA.md](./BILLING_MONGODB_SCHEMA.md)
- [BILLING_APPLE_VERIFY_AND_ASSN.md](./BILLING_APPLE_VERIFY_AND_ASSN.md)
- [BILLING_UNIFIED_ENTITLEMENT_AND_ELIGIBILITY.md](./BILLING_UNIFIED_ENTITLEMENT_AND_ELIGIBILITY.md)
- [STOREKIT_LOCAL_TESTING.md](./STOREKIT_LOCAL_TESTING.md)
