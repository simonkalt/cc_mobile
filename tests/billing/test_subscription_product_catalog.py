"""
Mongo-backed subscription_product_catalog: merged Apple plan map, Stripe plan map,
GET snapshot fields, catalog route.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import mongomock
import pytest

from tests.billing.conftest import FAKE_USER_ID, FAKE_USER_OBJ_ID


STRIPE_CATALOG_DOC = {
    "_id": "stripe_all_production",
    "platform": "all",
    "billingProvider": "stripe",
    "environment": "production",
    "products": [
        {
            "productId": "price_monthly",
            "planKey": "monthly",
            "rank": 1,
            "enabled": True,
            "label": "Monthly Pro",
        },
        {
            "productId": "price_annual",
            "planKey": "annual",
            "rank": 3,
            "enabled": True,
            "label": "Annual Pro",
        },
    ],
}


@pytest.fixture
def catalog_doc_apple_ios_production():
    return {
        "_id": "apple_ios_production",
        "platform": "ios",
        "billingProvider": "apple",
        "environment": "production",
        "products": [
            {
                "productId": "MONTHLY001",
                "planKey": "monthly",
                "rank": 1,
                "enabled": True,
                "label": "Monthly Pro",
            },
            {
                "productId": "ANNUAL001",
                "planKey": "annual",
                "rank": 3,
                "enabled": True,
                "label": "Annual Pro",
            },
        ],
    }


@pytest.fixture
def catalog_collection(catalog_doc_apple_ios_production):
    col = mongomock.MongoClient()["test"]["subscription_product_catalog"]
    col.insert_one(catalog_doc_apple_ios_production)
    col.insert_one(dict(STRIPE_CATALOG_DOC))
    return col


def _collection_router(users_col, catalog_col):
    def _route(name: str):
        if name == "subscription_product_catalog":
            return catalog_col
        return users_col

    return _route


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    from app.services.subscription_product_catalog_service import invalidate_all_catalog_caches

    invalidate_all_catalog_caches()
    yield
    invalidate_all_catalog_caches()


@pytest.fixture
def client_with_catalog(fake_user, mongomock_users, catalog_collection):
    """TestClient with Mongo routing users vs subscription_product_catalog (does not patch db.mongodb)."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import get_current_user

    async def _override_auth():
        return fake_user

    app.dependency_overrides[get_current_user] = _override_auth

    router = _collection_router(mongomock_users, catalog_collection)
    patches = [
        patch("app.db.mongodb.is_connected", return_value=True),
        patch("app.db.mongodb.get_collection", side_effect=router),
        patch("app.services.subscription_service.is_connected", return_value=True),
        patch("app.services.subscription_service.get_collection", side_effect=router),
        patch("app.services.subscription_product_catalog_service.is_connected", return_value=True),
        patch(
            "app.services.subscription_product_catalog_service.get_collection",
            side_effect=router,
        ),
        patch("app.services.apple_subscription_service.is_connected", return_value=True),
        patch(
            "app.services.apple_subscription_service.get_collection",
            side_effect=router,
        ),
        patch("app.services.subscription_service.STRIPE_AVAILABLE", False),
    ]
    for p in patches:
        p.start()
    try:
        with TestClient(app) as tc:
            yield tc
    finally:
        for p in patches:
            p.stop()
        app.dependency_overrides.clear()


class TestMergedApplePlanMap:
    def test_mongo_overrides_env_for_same_sku(
        self, mongomock_users, catalog_collection, monkeypatch
    ):
        from app.core.config import settings
        from app.services.subscription_product_catalog_service import (
            invalidate_ios_apple_catalog_cache,
            merged_apple_product_plan_map,
        )

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)
        monkeypatch.setattr(
            settings,
            "APP_STORE_PRODUCT_PLAN_MAP_JSON",
            '{"MONTHLY001": "legacy_plan"}',
        )
        invalidate_ios_apple_catalog_cache()

        router = _collection_router(mongomock_users, catalog_collection)
        with patch(
            "app.services.subscription_product_catalog_service.get_collection",
            side_effect=router,
        ), patch(
            "app.services.subscription_product_catalog_service.is_connected",
            return_value=True,
        ):
            m = merged_apple_product_plan_map()
        assert m.get("MONTHLY001") == "monthly"


class TestAppleCatalogEndpoint:
    def test_catalog_returns_products_sorted(
        self, client_with_catalog, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)

        resp = client_with_catalog.get("/api/subscriptions/apple/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert data["environment"] == "production"
        assert len(data["products"]) == 2
        assert data["products"][0]["productId"] == "MONTHLY001"
        assert data["products"][1]["productId"] == "ANNUAL001"

    def test_catalog_hides_test_products_for_non_super_user(
        self, client_with_catalog, catalog_collection, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)
        catalog_collection.update_one(
            {"_id": "apple_ios_production"},
            {
                "$push": {
                    "products": {
                        "productId": "TEST_MONTHLY001",
                        "planKey": "test_monthly",
                        "rank": 0,
                        "enabled": True,
                        "label": "Test Monthly",
                    }
                }
            },
        )

        resp = client_with_catalog.get("/api/subscriptions/apple/catalog")
        assert resp.status_code == 200
        product_ids = [p["productId"] for p in resp.json()["products"]]
        assert "TEST_MONTHLY001" not in product_ids
        assert "MONTHLY001" in product_ids

    def test_catalog_shows_test_products_for_super_user(
        self, fake_user, mongomock_users, catalog_collection, monkeypatch
    ):
        from datetime import datetime, timezone

        from app.core.config import settings
        from app.main import app
        from app.core.auth import get_current_user
        from app.models.user import UserResponse
        from fastapi.testclient import TestClient

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)
        catalog_collection.update_one(
            {"_id": "apple_ios_production"},
            {
                "$push": {
                    "products": {
                        "productId": "TEST_MONTHLY001",
                        "planKey": "test_monthly",
                        "rank": 0,
                        "enabled": True,
                        "label": "Test Monthly",
                    }
                }
            },
        )

        now = datetime.now(timezone.utc)
        super_user = UserResponse(
            id=fake_user.id,
            name=fake_user.name,
            email=fake_user.email,
            isActive=True,
            isEmailVerified=True,
            roles=["user"],
            super_user=True,
            dateCreated=now,
            dateUpdated=now,
        )

        async def _override_auth():
            return super_user

        app.dependency_overrides[get_current_user] = _override_auth
        router = _collection_router(mongomock_users, catalog_collection)
        patches = [
            patch("app.db.mongodb.is_connected", return_value=True),
            patch("app.db.mongodb.get_collection", side_effect=router),
            patch(
                "app.services.subscription_product_catalog_service.is_connected",
                return_value=True,
            ),
            patch(
                "app.services.subscription_product_catalog_service.get_collection",
                side_effect=router,
            ),
        ]
        for p in patches:
            p.start()
        try:
            with TestClient(app) as tc:
                resp = tc.get("/api/subscriptions/apple/catalog")
        finally:
            for p in patches:
                p.stop()
            app.dependency_overrides.clear()

        assert resp.status_code == 200
        product_ids = [p["productId"] for p in resp.json()["products"]]
        assert "TEST_MONTHLY001" in product_ids
        assert "MONTHLY001" in product_ids


class TestSubscriptionApplePlanFields:
    def test_apple_plan_key_and_rank_on_get_subscription(
        self, client_with_catalog, mongomock_users, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)

        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "apple",
                    "subscriptionStatus": "active",
                    "subscriptionPlan": "monthly",
                    "subscriptionProductId": "MONTHLY001",
                    "appleProductId": "MONTHLY001",
                    "subscriptionId": "ORIG-TX",
                }
            },
        )

        resp = client_with_catalog.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("billingProvider") == "apple"
        assert body.get("applePlanKey") == "monthly"
        assert body.get("applePlanRank") == 1

    def test_apple_legacy_null_billing_provider_heals_tier(
        self, client_with_catalog, mongomock_users, monkeypatch
    ):
        """Rows with Apple IDs but missing billingProvider still infer apple + catalog rank."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)

        future = datetime.now(timezone.utc) + timedelta(days=30)
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": None,
                    "subscriptionStatus": "free",
                    "subscriptionPlan": "free",
                    "subscriptionProductId": "MONTHLY001",
                    "appleProductId": "MONTHLY001",
                    "appleOriginalTransactionId": "ORIG-LEGACY",
                    "subscriptionId": "ORIG-LEGACY",
                    "subscriptionCurrentPeriodEnd": future,
                }
            },
        )

        resp = client_with_catalog.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("billingProvider") == "apple"
        assert body.get("billing_provider") == "apple"
        assert body.get("subscriptionStatus") == "active"
        assert body.get("applePlanRank") == 1
        assert body.get("apple_plan_rank") == 1
        assert body.get("productId") == "MONTHLY001"
        assert body.get("product_id") == "MONTHLY001"
        healed = mongomock_users.find_one({"_id": FAKE_USER_OBJ_ID})
        assert healed.get("billingProvider") == "apple"


# ---------------------------------------------------------------------------
# Stripe catalog
# ---------------------------------------------------------------------------


class TestMergedStripePlanMap:
    def test_mongo_overrides_env_for_same_price(
        self, mongomock_users, catalog_collection, monkeypatch
    ):
        from app.core.config import settings
        from app.services.subscription_product_catalog_service import (
            invalidate_stripe_catalog_cache,
            merged_stripe_price_plan_map,
        )

        monkeypatch.setattr(
            settings,
            "STRIPE_PRICE_PLAN_MAP_JSON",
            '{"price_monthly": "legacy_monthly"}',
        )
        invalidate_stripe_catalog_cache()

        router = _collection_router(mongomock_users, catalog_collection)
        with patch(
            "app.services.subscription_product_catalog_service.get_collection",
            side_effect=router,
        ), patch(
            "app.services.subscription_product_catalog_service.is_connected",
            return_value=True,
        ):
            m = merged_stripe_price_plan_map()
        assert m.get("price_monthly") == "monthly"

    def test_env_fallback_when_no_mongo_doc(self, monkeypatch):
        from app.core.config import settings
        from app.services.subscription_product_catalog_service import (
            invalidate_stripe_catalog_cache,
            resolve_stripe_product,
        )

        monkeypatch.setattr(
            settings,
            "STRIPE_PRICE_PLAN_MAP_JSON",
            '{"price_env_only": "semiannual"}',
        )
        invalidate_stripe_catalog_cache()

        with patch(
            "app.services.subscription_product_catalog_service.is_connected",
            return_value=False,
        ):
            pk, rk = resolve_stripe_product("price_env_only")
        assert pk == "semiannual"
        assert rk is None


class TestResolveStripeProduct:
    def test_known_price_returns_plan_key_and_rank(
        self, mongomock_users, catalog_collection
    ):
        from app.services.subscription_product_catalog_service import resolve_stripe_product

        router = _collection_router(mongomock_users, catalog_collection)
        with patch(
            "app.services.subscription_product_catalog_service.get_collection",
            side_effect=router,
        ), patch(
            "app.services.subscription_product_catalog_service.is_connected",
            return_value=True,
        ):
            pk, rk = resolve_stripe_product("price_annual")
        assert pk == "annual"
        assert rk == 3

    def test_unknown_price_returns_none(
        self, mongomock_users, catalog_collection
    ):
        from app.services.subscription_product_catalog_service import resolve_stripe_product

        router = _collection_router(mongomock_users, catalog_collection)
        with patch(
            "app.services.subscription_product_catalog_service.get_collection",
            side_effect=router,
        ), patch(
            "app.services.subscription_product_catalog_service.is_connected",
            return_value=True,
        ):
            pk, rk = resolve_stripe_product("price_unknown")
        assert pk is None
        assert rk is None


# ---------------------------------------------------------------------------
# Unified planKey / planRank on GET /api/subscriptions/{user_id}
# ---------------------------------------------------------------------------


class TestUnifiedPlanKeyFields:
    def test_apple_user_gets_unified_plan_key(
        self, client_with_catalog, mongomock_users, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)

        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "apple",
                    "subscriptionStatus": "active",
                    "subscriptionPlan": "monthly",
                    "subscriptionProductId": "MONTHLY001",
                    "appleProductId": "MONTHLY001",
                    "subscriptionId": "ORIG-TX",
                }
            },
        )

        resp = client_with_catalog.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["planKey"] == "monthly"
        assert body["planRank"] == 1
        assert body["applePlanKey"] == "monthly"

    def test_stripe_user_gets_unified_plan_key(
        self, client_with_catalog, mongomock_users, monkeypatch
    ):
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)

        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "stripe",
                    "subscriptionStatus": "active",
                    "subscriptionPlan": "price_annual",
                    "priceId": "price_annual",
                    "subscriptionId": "sub_test_123",
                }
            },
        )

        with patch("app.services.subscription_service._get_stripe_module", return_value=None):
            resp = client_with_catalog.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["planKey"] == "annual"
        assert body["planRank"] == 3
        assert body["applePlanKey"] is None

    def test_free_user_has_null_plan_key(self, client_with_catalog, mongomock_users):
        resp = client_with_catalog.get(f"/api/subscriptions/{FAKE_USER_ID}")
        assert resp.status_code == 200
        body = resp.json()
        assert body["planKey"] is None
        assert body["planRank"] is None

    def test_same_plan_key_across_providers(
        self, client_with_catalog, mongomock_users, monkeypatch
    ):
        """Monthly on Apple and monthly on Stripe both resolve to planKey='monthly'."""
        from app.core.config import settings

        monkeypatch.setattr(settings, "APP_STORE_USE_SANDBOX", False)

        # Apple monthly
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "apple",
                    "subscriptionStatus": "active",
                    "appleProductId": "MONTHLY001",
                    "subscriptionId": "ORIG-TX",
                }
            },
        )
        resp = client_with_catalog.get(f"/api/subscriptions/{FAKE_USER_ID}")
        apple_plan_key = resp.json()["planKey"]

        # Switch to Stripe monthly
        mongomock_users.update_one(
            {"_id": FAKE_USER_OBJ_ID},
            {
                "$set": {
                    "billingProvider": "stripe",
                    "subscriptionStatus": "active",
                    "priceId": "price_monthly",
                    "subscriptionId": "sub_stripe",
                    "appleProductId": None,
                }
            },
        )
        with patch("app.services.subscription_service._get_stripe_module", return_value=None):
            resp = client_with_catalog.get(f"/api/subscriptions/{FAKE_USER_ID}")
        stripe_plan_key = resp.json()["planKey"]

        assert apple_plan_key == "monthly"
        assert stripe_plan_key == "monthly"
        assert apple_plan_key == stripe_plan_key
