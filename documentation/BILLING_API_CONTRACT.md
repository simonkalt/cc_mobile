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

---

## GET `/api/subscriptions/{user_id}` — extended fields

In addition to existing fields (`subscription_status`, `subscription_plan`, `subscription_current_period_end`, `product_id`, `price_id`, `billing_provider`, etc.), the backend SHOULD return:

| Field | Type | Description |
|-------|------|-------------|
| `entitlement_active` | boolean | Unified premium flag (optional if `subscription_status` alone is sufficient) |
| `can_initiate_new_paid_subscription` | boolean | `false` when already entitled via Stripe **or** Apple |
| `cross_platform_billing` | boolean | Management on another surface (see unified entitlement doc) |
| `entitlement_source` | `"stripe"` \| `"apple"` \| null | Optional |

Apple-specific fields when `billing_provider === "apple"`: see [BILLING_MONGODB_SCHEMA.md](./BILLING_MONGODB_SCHEMA.md).

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
