#!/usr/bin/env python3
"""
Sync subscription status from Stripe into MongoDB for all users.

Fetches the most relevant Stripe subscription for each user that has a
stripeCustomerId, then updates the local DB fields to match Stripe's
authoritative state.

Usage:
    python scripts/sync_subscription_status.py              # dry-run (default)
    python scripts/sync_subscription_status.py --apply      # write changes
    python scripts/sync_subscription_status.py --user EMAIL # single user
"""

import argparse
import importlib
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure project root is on sys.path so app.* imports work
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv

load_dotenv(os.path.join(PROJECT_ROOT, ".env"))
load_dotenv(os.path.join(PROJECT_ROOT, ".secrets"), override=True)

from bson import ObjectId

from app.core.config import settings
from app.db.mongodb import connect_to_mongodb, get_database

USERS_COLLECTION = "users"

STATUS_PRECEDENCE = {
    "active": 0,
    "trialing": 1,
    "incomplete": 2,
    "past_due": 3,
    "unpaid": 4,
    "canceled": 5,
    "incomplete_expired": 6,
}


def get_stripe():
    try:
        import stripe
    except ImportError:
        print("ERROR: stripe package not installed. pip install stripe>=7.0.0")
        sys.exit(1)

    api_key = settings.STRIPE_API_KEY or settings.STRIPE_TEST_API_KEY
    if not api_key:
        print("ERROR: No STRIPE_API_KEY or STRIPE_TEST_API_KEY configured.")
        sys.exit(1)
    stripe.api_key = api_key
    return stripe


def best_subscription(stripe_mod, customer_id):
    """Return the most relevant subscription object for a Stripe customer."""
    subs = stripe_mod.Subscription.list(
        customer=customer_id,
        status="all",
        limit=100,
    )
    items = subs.data if hasattr(subs, "data") else []
    if not items:
        return None

    def rank(sub):
        st = str(getattr(sub, "status", "") or "")
        prec = STATUS_PRECEDENCE.get(st, 99)
        cpe = int(getattr(sub, "current_period_end", 0) or 0)
        created = int(getattr(sub, "created", 0) or 0)
        return (prec, -cpe, -created)

    best = sorted(items, key=rank)[0]

    # Re-fetch with price.product expansion (single subscription is fine)
    try:
        best = stripe_mod.Subscription.retrieve(
            best.id, expand=["items.data.price.product"]
        )
    except Exception:
        pass  # proceed with what we have

    return best


def extract_fields(sub):
    """Pull the fields we persist from a Stripe subscription object."""
    result = {
        "subscriptionId": sub.id,
        "subscriptionStatus": str(getattr(sub, "status", "free")),
    }

    if getattr(sub, "current_period_end", None):
        result["subscriptionCurrentPeriodEnd"] = datetime.fromtimestamp(
            sub.current_period_end, tz=timezone.utc
        )

    result["cancelAtPeriodEnd"] = bool(getattr(sub, "cancel_at_period_end", False))

    if getattr(sub, "canceled_at", None):
        result["canceledAt"] = datetime.fromtimestamp(sub.canceled_at, tz=timezone.utc)
    else:
        result["canceledAt"] = None

    items_data = sub.items.data if hasattr(sub.items, "data") else []
    if items_data:
        price_obj = items_data[0].price
        if hasattr(price_obj, "id") and price_obj.id:
            result["priceId"] = price_obj.id
            result["subscriptionPlan"] = price_obj.id
        if hasattr(price_obj, "product") and price_obj.product:
            if isinstance(price_obj.product, str):
                result["subscriptionProductId"] = price_obj.product
            elif hasattr(price_obj.product, "id"):
                result["subscriptionProductId"] = price_obj.product.id

    return result


def diff_fields(user_doc, stripe_fields):
    """Return only the fields that differ between DB and Stripe."""
    changes = {}
    for key, new_val in stripe_fields.items():
        old_val = user_doc.get(key)
        if key == "cancelAtPeriodEnd":
            old_val = bool(old_val) if old_val is not None else False
        if old_val != new_val:
            changes[key] = {"old": old_val, "new": new_val}
    return changes


def main():
    parser = argparse.ArgumentParser(description="Sync subscription status from Stripe to MongoDB")
    parser.add_argument("--apply", action="store_true", help="Actually write changes (default is dry-run)")
    parser.add_argument("--user", type=str, help="Sync only this user (by email)")
    args = parser.parse_args()

    stripe_mod = get_stripe()

    if not connect_to_mongodb():
        print("ERROR: Could not connect to MongoDB. Check MONGODB_URI in .env / .secrets.")
        sys.exit(1)

    db = get_database()

    collection = db[USERS_COLLECTION]

    query = {"stripeCustomerId": {"$exists": True, "$nin": [None, ""]}}
    if args.user:
        query["email"] = args.user

    users = list(collection.find(query))
    print(f"Found {len(users)} user(s) with a stripeCustomerId" + (f" (filter: {args.user})" if args.user else ""))
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}\n")

    synced = 0
    skipped = 0
    errors = 0

    for user_doc in users:
        uid = str(user_doc["_id"])
        email = user_doc.get("email", "?")
        cust_id = user_doc.get("stripeCustomerId")

        try:
            sub = best_subscription(stripe_mod, cust_id)
        except Exception as e:
            print(f"  ERROR  {email} (customer {cust_id}): {e}")
            errors += 1
            continue

        if sub is None:
            db_status = user_doc.get("subscriptionStatus", "free")
            if db_status and db_status not in ("free", "none", None):
                print(f"  RESET  {email}: no Stripe subscriptions; DB has '{db_status}' -> 'free'")
                if args.apply:
                    collection.update_one(
                        {"_id": user_doc["_id"]},
                        {"$set": {
                            "subscriptionStatus": "free",
                            "subscriptionId": None,
                            "cancelAtPeriodEnd": False,
                            "canceledAt": None,
                            "dateUpdated": datetime.utcnow(),
                        }},
                    )
                    synced += 1
                else:
                    skipped += 1
            else:
                print(f"  OK     {email}: no Stripe subscriptions, DB already '{db_status}'")
                skipped += 1
            continue

        stripe_fields = extract_fields(sub)
        changes = diff_fields(user_doc, stripe_fields)

        if not changes:
            print(f"  OK     {email}: status='{stripe_fields['subscriptionStatus']}' (in sync)")
            skipped += 1
            continue

        change_summary = ", ".join(f"{k}: '{c['old']}' -> '{c['new']}'" for k, c in changes.items())
        print(f"  UPDATE {email}: {change_summary}")

        if args.apply:
            update_doc = {k: v["new"] for k, v in changes.items()}
            update_doc["dateUpdated"] = datetime.utcnow()
            collection.update_one({"_id": user_doc["_id"]}, {"$set": update_doc})
            synced += 1
        else:
            skipped += 1

    print(f"\nDone. Synced: {synced}, Skipped/Up-to-date: {skipped}, Errors: {errors}")
    if not args.apply and synced == 0 and skipped > 0:
        print("(dry-run mode — re-run with --apply to write changes)")


if __name__ == "__main__":
    main()
