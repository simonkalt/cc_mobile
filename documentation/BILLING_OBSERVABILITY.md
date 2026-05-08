# Billing observability (backend + mobile)

## Correlation ID

- **Mobile** sends header `X-Billing-Correlation-Id` on all `/api/subscriptions/*` requests (generated when Billing tab opens; see `src/utils/billingCorrelation.js`).
- **Backend** echoes the header on responses and includes it in structured logs for that request and downstream webhook handlers when correlatable.

## Backend structured logging

- **Apple:** `apple_verify_*`, `apple_assn_received` — include `product_id`, `transaction_id`, `original_transaction_id`, environment; **never** log full `signed_transaction`.
- **Stripe:** `stripe_webhook_*` — event `type`, subscription/customer ids; redact card data.
- **Internal:** `entitlement_recompute_*` — resulting `entitlement_active`, `billing_provider`.

## Mobile

Prefix `[BILLING]` / `[SUBSCRIPTION]` with correlation id when logging (see `subscriptionService` and `IosBillingPlanPicker`).

## Debugging “IAP selected plan but not entitled”

1. Client: StoreKit completed? `transactionId` / token present?
2. Client: `POST /api/subscriptions/apple/verify` called? HTTP status? error `code`?
3. Server: `apple_verify_fail` reason?
4. DB: user updated?
5. `GET /api/subscriptions/:userId`: `billing_provider`, `entitlement_active`?
