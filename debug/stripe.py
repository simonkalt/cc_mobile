import stripe
import os
import logging

logger = logging.getLogger("stripe-check")
logging.basicConfig(level=logging.INFO)

stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")


def stripe_connectivity_check():
    if not stripe.api_key:
        logger.error("❌ STRIPE_SECRET_KEY is NOT set")
        return

    try:
        acct = stripe.Account.retrieve()
        logger.info("✅ Stripe connectivity OK")
        logger.info(f"Stripe account ID: {acct.id}")
        logger.info(f"Stripe key prefix: {stripe.api_key[:8]}***")
    except stripe.error.AuthenticationError as e:
        logger.error("❌ Stripe AUTHENTICATION ERROR")
        logger.error(str(e))
    except stripe.error.APIConnectionError as e:
        logger.error("❌ Stripe NETWORK / CONNECTION ERROR")
        logger.error(str(e))
    except Exception as e:
        logger.error("❌ Stripe UNKNOWN ERROR")
        logger.error(f"{type(e).__name__}: {e}")
