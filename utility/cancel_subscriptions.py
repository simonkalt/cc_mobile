import stripe
from dotenv import load_dotenv
import os

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")


def clear_customer_subscriptions(customer_id):
    subs = stripe.Subscription.list(
        customer=customer_id,
        status="all",
        limit=100,
    )

    for sub in subs.data:
        if sub.status not in ["canceled", "incomplete_expired"]:
            stripe.Subscription.delete(sub.id)
            print(f"Canceled subscription {sub.id}")


clear_customer_subscriptions("cus_Tk8mdxLgBDypHQ")
