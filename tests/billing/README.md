# Billing test suite

## Hermetic pytest tests (no live server or DB required)

```bash
# This project uses a local .venv — always invoke pip and pytest through it.
# (Bare `pip` hits the system Python and will be rejected on Debian/Ubuntu.)

# Install deps once
.venv/bin/python -m pip install mongomock pytest-mock httpx

# Run all billing tests
.venv/bin/python -m pytest tests/billing -v

# Run a single file
.venv/bin/python -m pytest tests/billing/test_entitlement_compute.py -v
```

Files:
| File | What it tests |
|------|---------------|
| `test_apple_verify_persist.py` | Step 1 — new Apple schema fields written, error codes, idempotency |
| `test_apple_verify_endpoint.py` | Step 1 — POST /apple/verify HTTP shape; `code` in error JSON |
| `test_entitlement_compute.py` | Step 2 — `compute_entitlement` and `compute_eligibility` matrix |
| `test_subscription_get_extended.py` | Step 2 — GET /subscriptions/{id} with X-Client-Platform |
| `test_entitlement_recompute.py` | Step 3 — `recompute_and_persist` writes persisted fields |
| `test_stripe_webhook_recompute.py` | Step 3 — Stripe webhook triggers entitlement update |
| `test_purchase_eligibility.py` | Step 4 — purchase-eligibility unit + endpoint |
| `test_correlation_middleware.py` | Step 5 — X-Billing-Correlation-Id echo |

---

## Live smoke scripts (require running server + real MongoDB)

```bash
export BILLING_TEST_USER_ID=<mongo_object_id>
export BILLING_TEST_SANDBOX_JWS=<StoreKit_2_signedTransaction>

# Step 1 — Apple verify + DB fields
.venv/bin/python tests/test_billing_apple_verify_smoke.py

# Step 2 — Extended GET subscription
.venv/bin/python tests/test_billing_get_subscription_smoke.py ios
.venv/bin/python tests/test_billing_get_subscription_smoke.py android

# Step 3 — Recompute via update_user_subscription
.venv/bin/python tests/test_billing_recompute_smoke.py

# Step 4 — Purchase eligibility
.venv/bin/python tests/test_billing_eligibility_smoke.py ios

# Step 5 — Correlation header echo
.venv/bin/python tests/test_billing_correlation_smoke.py
```

All smoke scripts print labelled JSON output and `[PASS]` / `[FAIL]` markers.
