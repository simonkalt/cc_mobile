# Unified entitlement and purchase eligibility

## Goal

One **account** has a single premium answer combining Stripe + Apple inputs. Separate stores still handle charges and refunds; your API exposes one entitlement snapshot to mobile.

## Recompute triggers

- Stripe webhooks (`customer.subscription.*`, `invoice.paid`, etc.)
- `POST /api/subscriptions/apple/verify`
- App Store Server Notifications v2
- Optional periodic reconciliation job (App Store Server API)

## Outputs (expose on `GET /api/subscriptions/:userId`)

| Field | Type | Notes |
|-------|------|-------|
| `entitlement_active` | boolean | Premium access for this account (all platforms) |
| `subscription_status` | string | Keep existing values; should align with `entitlement_active` |
| `billing_provider` | `"stripe"` \| `"apple"` \| null | Where **management** (cancel/change plan) applies |
| `can_initiate_new_paid_subscription` | boolean | **`false`** when already entitled (either merchant) to avoid double billing |
| `cross_platform_billing` | boolean | **Management UX only:** `true` if client OS ≠ management OS (e.g. iOS user with Stripe sub) |
| `entitlement_source` | `"stripe"` \| `"apple"` \| null | Optional |

### `cross_platform_billing` matrix

- **iOS** + `billing_provider === "stripe"` → `true`
- **Android** + `billing_provider === "apple"` → `true`
- Else → `false`

Mobile may compute this locally if omitted, but server is preferred.

## Conflict: both Stripe and Apple active

Define one policy, e.g.:

- Prefer first active source by `updated_at`, or
- Prefer Stripe, or
- Block second purchase at verify/webhook time

Document the choice; support tooling may be needed to refund or detach one.

## Optional `GET /api/subscriptions/purchase-eligibility?platform=ios|android`

| Response field | Type |
|----------------|------|
| `can_initiate_new_paid_subscription` | boolean |
| `reason` | `already_entitled` \| `free` \| `lapsed` |
| `billing_provider` | string or null |

Mobile can rely on extended `GET :userId` instead if the same fields are present.

## Email (pre-login only)

Optional: normalized email lookup during sign-up to suggest “sign in” if an account already has `entitlement_active`. **Not** authoritative; Apple/Google relay emails differ. After login, use **only** `user_id` + subscription payload.
