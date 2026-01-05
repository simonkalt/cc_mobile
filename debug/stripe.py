from fastapi import APIRouter
import stripe
import os

router = APIRouter()

stripe.api_key = os.environ["STRIPE_SECRET_KEY"]


@router.get("/debug/stripe")
def stripe_debug():
    try:
        acct = stripe.Account.retrieve()
        return {
            "ok": True,
            "stripe_account_id": acct.id,
        }
    except Exception as e:
        return {
            "ok": False,
            "error": str(e),
            "type": e.__class__.__name__,
        }
