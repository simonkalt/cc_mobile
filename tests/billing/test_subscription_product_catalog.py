"""
Mongo-backed subscription_product_catalog: merged Apple plan map, GET snapshot fields, catalog route.
"""

from __future__ import annotations

from unittest.mock import patch

import mongomock
import pytest

from tests.billing.conftest import FAKE_USER_ID, FAKE_USER_OBJ_ID


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
    return col


def _collection_router(users_col, catalog_col):
    def _route(name: str):
        if name == "subscription_product_catalog":
            return catalog_col
        return users_col

    return _route


@pytest.fixture(autouse=True)
def clear_catalog_cache():
    from app.services.subscription_product_catalog_service import invalidate_ios_apple_catalog_cache

    invalidate_ios_apple_catalog_cache()
    yield
    invalidate_ios_apple_catalog_cache()


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
