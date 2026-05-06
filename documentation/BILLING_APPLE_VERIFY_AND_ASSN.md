# Apple IAP: verify endpoint + App Store Server Notifications

## `POST /api/subscriptions/apple/verify`

Mobile sends (snake_case):

- `user_id`
- `signed_transaction` — StoreKit 2 JWS (`purchaseToken` from `expo-iap`; **never log full string**)
- `product_id`
- `transaction_id`
- `original_transaction_id` (optional but recommended)

### Server responsibilities

1. Validate JWS with **App Store Server API** (or equivalent) for the correct bundle ID and environment (**production**, **App Store sandbox**, and **Xcode StoreKit local testing** each require the matching validation path / keys).
2. Confirm `original_transaction_id` / `product_id` match decoded payload.
3. **Idempotent update:** same `original_transaction_id` + user should not create duplicate billing records.
4. Persist Apple fields from [BILLING_MONGODB_SCHEMA.md](./BILLING_MONGODB_SCHEMA.md); set `billing_provider` to `"apple"`.
5. **Recompute unified entitlement** (Stripe + Apple → `entitlement_active`, `can_initiate_new_paid_subscription`, etc.).
6. Return updated subscription JSON (same shape as `GET /api/subscriptions/:userId`) or `{ data: {...} }` / `{ subscription: {...} }`.

Implementation details required for Settings → Billing to update after Xcode StoreKit Testing or Sandbox are summarized in **[BILLING_API_CONTRACT.md](./BILLING_API_CONTRACT.md)** under `POST /api/subscriptions/apple/verify` (server checklist).

### Error codes (suggested)

Return stable `detail` / `code` for client logging:

| Code / detail | Meaning |
|---------------|---------|
| `apple_validation_failed` | JWS invalid or wrong environment |
| `user_mismatch` | Transaction not eligible for this `user_id` |
| `transaction_already_consumed` | Already applied to another account (policy-dependent) |

## App Store Server Notifications (ASSN) v2

- Register production and sandbox URLs with App Store Connect.
- On `SUBSCRIBED`, `DID_RENEW`, `DID_FAIL_TO_RENEW`, `EXPIRED`, `REFUND`, `REVOKE`, etc., update the user linked by `original_transaction_id` (and your `user_id` mapping).
- Recompute entitlement after each relevant notification.

## Observability

Log structured events: `apple_verify_start`, `apple_verify_ok`, `apple_verify_fail`, `apple_assn_received` with `user_id`, `X-Billing-Correlation-Id`, `product_id`, `transaction_id`, `original_transaction_id`, **not** full JWS.

See [BILLING_OBSERVABILITY.md](./BILLING_OBSERVABILITY.md).
