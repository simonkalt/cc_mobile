#!/usr/bin/env bash
# Stripe CLI webhook forwarding (local). Requires .env + .secrets — see scripts/env-files.sh
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=scripts/env-files.sh
source "${ROOT}/scripts/env-files.sh"
require_env_files "$ROOT" || exit 1

# Login (one-time)
stripe login
# Forward events to your local server
stripe listen --forward-to localhost:8675/api/stripe/webhook
# The CLI will print a temporary webhook signing secret (whsec_...). Put it in .secrets as
# STRIPE_WEBHOOK_SECRET while testing locally (overrides the dashboard secret from .env).

# Then trigger test events:


# must be run separately in a separate terminal
# Simulate a subscription update
stripe trigger customer.subscription.updated
# Simulate a customer deletion
stripe trigger customer.deleted