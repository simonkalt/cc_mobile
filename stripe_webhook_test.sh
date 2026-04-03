# Login (one-time)
stripe login
# Forward events to your local server
stripe listen --forward-to localhost:8675/api/stripe/webhook
# The CLI will print a temporary webhook signing secret (whsec_...). Use that in your .env instead of the dashboard one while testing locally.

# Then trigger test events:


# must be run separately in a separate terminal
# Simulate a subscription update
stripe trigger customer.subscription.updated
# Simulate a customer deletion
stripe trigger customer.deleted