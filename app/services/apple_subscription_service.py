"""
Apple App Store Server API integration (StoreKit 2 transaction verification).

Server flow:
 1. Read transactionId from the client JWS (unsigned decode) to call Apple's API.
 2. Fetch authoritative signedTransactionInfo via GET /inApps/v1/transactions/{id}.
 3. Verify that JWS with SignedDataVerifier (Apple root certificates).

App Store Server Notifications V2: configure the same URL in App Store Connect; the handler
verifies `signedPayload` and updates Mongo user subscription fields for renewals, expirations,
refunds, and auto-renew status changes.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from fastapi import HTTPException, status
from pymongo.errors import DuplicateKeyError

from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.utils.user_helpers import USERS_COLLECTION

logger = logging.getLogger(__name__)


class AppleBillingError(Exception):
    """Raised by the Apple subscription service for billing-specific errors that need a stable
    machine-readable ``code`` in the HTTP response body (e.g. ``apple_validation_failed``)."""

    def __init__(self, code: str, detail: str, status_code: int = 400) -> None:
        self.code = code
        self.detail = detail
        self.status_code = status_code
        super().__init__(detail)


try:
    from appstoreserverlibrary.api_client import APIException, AppStoreServerAPIClient
    from appstoreserverlibrary.models.AutoRenewStatus import AutoRenewStatus
    from appstoreserverlibrary.models.Environment import Environment
    from appstoreserverlibrary.models.NotificationTypeV2 import NotificationTypeV2
    from appstoreserverlibrary.models.Subtype import Subtype
    from appstoreserverlibrary.models.Type import Type
    from appstoreserverlibrary.signed_data_verifier import (
        SignedDataVerifier,
        VerificationException,
        VerificationStatus,
    )

    APPLE_STOREKIT_LIB_AVAILABLE = True
except ImportError:
    APIException = Exception  # type: ignore[misc, assignment]
    AppStoreServerAPIClient = None  # type: ignore[misc, assignment]
    AutoRenewStatus = None  # type: ignore[misc, assignment]
    Environment = None  # type: ignore[misc, assignment]
    NotificationTypeV2 = None  # type: ignore[misc, assignment]
    Subtype = None  # type: ignore[misc, assignment]
    Type = None  # type: ignore[misc, assignment]
    SignedDataVerifier = None  # type: ignore[misc, assignment]
    VerificationException = Exception  # type: ignore[misc, assignment]
    VerificationStatus = None  # type: ignore[misc, assignment]
    APPLE_STOREKIT_LIB_AVAILABLE = False


def _ensure_apple_indexes() -> None:
    """Create the unique-sparse index on ``appleOriginalTransactionId`` in the users collection.

    Called once at application startup (after MongoDB connects).  Safe to call multiple times —
    PyMongo ``create_index`` is idempotent when the index specification is unchanged.
    """
    from app.db.mongodb import get_collection, is_connected

    if not is_connected():
        logger.warning("_ensure_apple_indexes: MongoDB not connected — skipping index creation")
        return
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        logger.warning("_ensure_apple_indexes: could not access users collection")
        return
    try:
        from pymongo import ASCENDING

        collection.create_index(
            [("appleOriginalTransactionId", ASCENDING)],
            unique=True,
            sparse=True,
            name="apple_original_transaction_id_unique",
        )
        logger.info("Apple unique index on appleOriginalTransactionId ensured")
    except Exception as exc:
        logger.warning("_ensure_apple_indexes: index creation failed: %s", exc)


def apple_subscription_configured() -> bool:
    if not APPLE_STOREKIT_LIB_AVAILABLE:
        return False
    if not settings.APP_STORE_ISSUER_ID or not settings.APP_STORE_KEY_ID:
        return False
    if not settings.APP_STORE_BUNDLE_ID:
        return False
    if not settings.APP_STORE_PRIVATE_KEY_PATH and not (
        settings.APP_STORE_PRIVATE_KEY and settings.APP_STORE_PRIVATE_KEY.strip()
    ):
        return False
    if not settings.APP_STORE_ROOT_CERTIFICATES_DIR:
        return False
    return True


def _decode_jws_payload_unverified(jws: str) -> Dict[str, Any]:
    parts = jws.strip().split(".")
    if len(parts) < 2:
        raise ValueError("Not a JWS")
    payload_b64 = parts[1]
    pad = "=" * ((4 - len(payload_b64) % 4) % 4)
    raw = base64.urlsafe_b64decode(payload_b64 + pad)
    return json.loads(raw.decode("utf-8"))


def _load_signing_key_bytes() -> bytes:
    if settings.APP_STORE_PRIVATE_KEY_PATH:
        path = Path(settings.APP_STORE_PRIVATE_KEY_PATH).expanduser()
        if not path.is_file():
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="App Store private key file not found (APP_STORE_PRIVATE_KEY_PATH)",
            )
        return path.read_bytes()
    pem = settings.APP_STORE_PRIVATE_KEY or ""
    if not pem.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="App Store API private key not configured",
        )
    if "\\n" in pem:
        pem = pem.replace("\\n", "\n")
    return pem.encode("utf-8")


def _load_root_certificates() -> List[bytes]:
    dir_raw = settings.APP_STORE_ROOT_CERTIFICATES_DIR or ""
    if not dir_raw.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APP_STORE_ROOT_CERTIFICATES_DIR is not configured",
        )
    path = Path(dir_raw).expanduser()
    if not path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APP_STORE_ROOT_CERTIFICATES_DIR is not a directory",
        )
    certs: List[bytes] = []
    for f in sorted(path.iterdir()):
        if f.is_file() and f.suffix.lower() in (".cer", ".crt", ".pem", ".der"):
            certs.append(f.read_bytes())
    if not certs:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No root certificate files (.cer/.crt/.pem/.der) in APP_STORE_ROOT_CERTIFICATES_DIR",
        )
    return certs


def _product_plan_map() -> Dict[str, str]:
    raw = settings.APP_STORE_PRODUCT_PLAN_MAP_JSON
    if not raw or not str(raw).strip():
        return {}
    try:
        data = json.loads(raw)
        if isinstance(data, dict):
            return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError as e:
        logger.warning("APP_STORE_PRODUCT_PLAN_MAP_JSON is not valid JSON: %s", e)
    return {}


def _allowed_product_ids() -> Optional[set]:
    raw = settings.APP_STORE_ALLOWED_PRODUCT_IDS
    if not raw or not str(raw).strip():
        return None
    return {x.strip() for x in str(raw).split(",") if x.strip()}


def _environment_order() -> List[Any]:
    primary = Environment.SANDBOX if settings.APP_STORE_USE_SANDBOX else Environment.PRODUCTION
    secondary = Environment.PRODUCTION if primary == Environment.SANDBOX else Environment.SANDBOX
    order = [primary]
    if settings.APP_STORE_RETRY_ALTERNATE_ENVIRONMENT:
        order.append(secondary)
    return order


def _api_client_for(env: Any) -> Any:
    key = _load_signing_key_bytes()
    return AppStoreServerAPIClient(
        signing_key=key,
        key_id=settings.APP_STORE_KEY_ID or "",
        issuer_id=settings.APP_STORE_ISSUER_ID or "",
        bundle_id=settings.APP_STORE_BUNDLE_ID or "",
        environment=env,
    )


def _verifier_for(env: Any) -> Any:
    certs = _load_root_certificates()
    app_apple_id = settings.APP_APPLE_ID if env == Environment.PRODUCTION else None
    if env == Environment.PRODUCTION and app_apple_id is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="APP_APPLE_ID is required for production Apple JWS verification",
        )
    return SignedDataVerifier(
        root_certificates=certs,
        enable_online_checks=True,
        environment=env,
        bundle_id=settings.APP_STORE_BUNDLE_ID or "",
        app_apple_id=app_apple_id,
    )


def _verify_and_decode_notification_multi_env(signed_payload: str) -> Tuple[Any, Any]:
    """Return (Environment, ResponseBodyV2DecodedPayload)."""
    last_exc: Optional[BaseException] = None
    for env in _environment_order():
        verifier = _verifier_for(env)
        try:
            decoded = verifier.verify_and_decode_notification(signed_payload)
            return env, decoded
        except VerificationException as e:
            last_exc = e
            st = getattr(e, "status", None)
            if VerificationStatus is not None and st == VerificationStatus.INVALID_ENVIRONMENT:
                continue
            raise
    if last_exc is not None:
        raise last_exc
    raise RuntimeError("Apple notification verification failed (no environment matched)")


def _free_tier_apple_clear_set() -> Dict[str, Any]:
    return {
        "billingProvider": None,
        "appleProductId": None,
        "appleOriginalTransactionId": None,
        "appleLatestTransactionId": None,
        "appleSubscriptionGroupId": None,
        "appleEnvironment": None,
        "appleAutoRenewStatus": None,
        "appleLastVerifiedAt": None,
        "appleAppAccountToken": None,
        "subscriptionId": None,
        "subscriptionStatus": "free",
        "subscriptionPlan": "free",
        "subscriptionProductId": None,
        "priceId": None,
        "subscriptionCurrentPeriodEnd": None,
        "cancelAtPeriodEnd": False,
        "canceledAt": None,
        "dateUpdated": datetime.utcnow(),
    }


def _subscription_fields_from_verified_apple_tx(
    decoded_tx: Any,
    renewal: Optional[Any] = None,
    *,
    env: Any = None,
    subscription_status_override: Optional[str] = None,
    cancel_at_period_end: Optional[bool] = None,
    canceled_at: Optional[datetime] = None,
) -> Dict[str, Any]:
    if Type is not None and getattr(decoded_tx, "type", None) != Type.AUTO_RENEWABLE_SUBSCRIPTION:
        raise ValueError("Transaction type is not Auto-Renewable Subscription")

    original_tx_id = getattr(decoded_tx, "originalTransactionId", None)
    if not original_tx_id:
        raise ValueError("Missing originalTransactionId")

    product_id = getattr(decoded_tx, "productId", None)
    if renewal:
        product_id = (
            getattr(renewal, "autoRenewProductId", None)
            or getattr(renewal, "productId", None)
            or product_id
        )
    if not product_id:
        raise ValueError("Missing productId")

    expires_ms = getattr(decoded_tx, "expiresDate", None)
    period_end: Optional[datetime] = None
    if expires_ms is not None:
        period_end = datetime.fromtimestamp(int(expires_ms) / 1000.0, tz=timezone.utc)

    now = datetime.now(timezone.utc)
    rev = getattr(decoded_tx, "revocationDate", None)

    if rev:
        subscription_status = "revoked"
    elif subscription_status_override:
        subscription_status = subscription_status_override
    elif period_end is None:
        subscription_status = "expired"
    elif period_end > now:
        in_retry = bool(renewal and getattr(renewal, "isInBillingRetryPeriod", False))
        subscription_status = "past_due" if in_retry else "active"
    else:
        subscription_status = "expired"

    plan_map = _product_plan_map()
    subscription_plan = plan_map.get(str(product_id), str(product_id))

    cap = cancel_at_period_end
    if cap is None and renewal is not None:
        ars = getattr(renewal, "autoRenewStatus", None)
        if ars is not None and AutoRenewStatus is not None:
            if ars == AutoRenewStatus.OFF:
                cap = True
            elif ars == AutoRenewStatus.ON:
                cap = False
    if cap is None:
        cap = False

    # --- extended schema fields ---
    latest_tx_id = getattr(decoded_tx, "transactionId", None)
    subscription_group_id = getattr(decoded_tx, "subscriptionGroupIdentifier", None)

    env_str: Optional[str] = None
    if env is not None and Environment is not None:
        try:
            if env == Environment.SANDBOX:
                env_str = "sandbox"
            elif env == Environment.PRODUCTION:
                env_str = "production"
            else:
                env_str = str(env).lower()
        except Exception:
            env_str = str(env).lower()

    auto_renew_status: Optional[bool] = None
    if renewal is not None and AutoRenewStatus is not None:
        ars_val = getattr(renewal, "autoRenewStatus", None)
        if ars_val == AutoRenewStatus.ON:
            auto_renew_status = True
        elif ars_val == AutoRenewStatus.OFF:
            auto_renew_status = False
    if auto_renew_status is None:
        auto_renew_status = not cap  # infer from cancelAtPeriodEnd when renewal info absent

    return {
        "billingProvider": "apple",
        "appleProductId": product_id,
        "appleOriginalTransactionId": str(original_tx_id),
        "appleLatestTransactionId": str(latest_tx_id) if latest_tx_id else None,
        "appleSubscriptionGroupId": str(subscription_group_id) if subscription_group_id else None,
        "appleEnvironment": env_str,
        "appleAutoRenewStatus": auto_renew_status,
        "appleLastVerifiedAt": datetime.utcnow(),
        "subscriptionId": str(original_tx_id),
        "subscriptionStatus": subscription_status,
        "subscriptionPlan": subscription_plan,
        "subscriptionProductId": product_id,
        "priceId": product_id,
        "subscriptionCurrentPeriodEnd": period_end,
        "cancelAtPeriodEnd": cap,
        "canceledAt": canceled_at,
        "dateUpdated": datetime.utcnow(),
    }


def _find_user_for_apple_subscription(
    collection: Any,
    original_tx_id: str,
    app_account_token: Optional[str],
) -> Optional[Dict[str, Any]]:
    u = collection.find_one({"appleOriginalTransactionId": str(original_tx_id)})
    if u:
        return u
    if app_account_token:
        return collection.find_one(
            {"appleAppAccountToken": str(app_account_token).strip().lower()}
        )
    return None


def _fetch_transaction_with_fallback(transaction_id: str) -> Tuple[Any, Any]:
    """Returns (environment, verified JWSTransactionDecodedPayload-like object from SignedDataVerifier)."""
    last_exc: Optional[Exception] = None
    for env in _environment_order():
        client = _api_client_for(env)
        try:
            info = client.get_transaction_info(transaction_id)
        except APIException as e:
            last_exc = e
            if getattr(e, "http_status_code", None) == 404:
                logger.info(
                    "App Store transaction %s not in %s; will retry if alternate env enabled",
                    transaction_id,
                    env,
                )
                continue
            logger.warning(
                "App Store get_transaction_info failed: status=%s raw=%s msg=%s",
                getattr(e, "http_status_code", None),
                getattr(e, "raw_api_error", None),
                getattr(e, "error_message", None),
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="App Store Server API error while fetching transaction",
            ) from e
        except Exception as e:
            last_exc = e
            logger.exception("Unexpected error calling App Store get_transaction_info")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Unexpected error calling App Store Server API",
            ) from e

        signed_jws = getattr(info, "signedTransactionInfo", None) if info else None
        if not signed_jws:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="App Store API returned no signedTransactionInfo",
            )

        verifier = _verifier_for(env)
        try:
            decoded = verifier.verify_and_decode_signed_transaction(signed_jws)
        except VerificationException as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Apple signed transaction failed verification: {e}",
            ) from e

        if getattr(decoded, "bundleId", None) != settings.APP_STORE_BUNDLE_ID:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Transaction bundleId does not match configured app",
            )

        return env, decoded

    if last_exc is not None and isinstance(last_exc, APIException):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found in App Store for this app",
        ) from last_exc
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Transaction not found in App Store for this app",
    )


def process_apple_server_notification_v2(signed_payload: str) -> Dict[str, Any]:
    """
    Verify ASN v2 outer JWS and apply subscription updates to MongoDB.
    Uses notificationUUID deduplication (collection MONGODB_APPLE_NOTIFICATIONS_COLLECTION).
    """
    if not APPLE_STOREKIT_LIB_AVAILABLE:
        return {"handled": False, "error": "app-store-server-library not installed"}
    if not apple_subscription_configured():
        return {"handled": False, "error": "Apple subscription not configured"}
    if not is_connected():
        return {"handled": False, "error": "database unavailable"}

    try:
        env, outer = _verify_and_decode_notification_multi_env(signed_payload)
    except VerificationException as e:
        logger.warning("Apple ASN v2 outer JWS verification failed: %s", e)
        return {"handled": False, "error": "invalid_signed_payload"}

    n_uuid = getattr(outer, "notificationUUID", None)
    n_type = getattr(outer, "notificationType", None)
    raw_ntype = getattr(outer, "rawNotificationType", None)
    subtype = getattr(outer, "subtype", None)
    raw_subtype = getattr(outer, "rawSubtype", None)

    if not n_uuid:
        logger.warning("Apple ASN v2 missing notificationUUID (type=%s)", raw_ntype)
        return {"handled": True, "missing_notification_uuid": True}

    dedupe = get_collection(settings.MONGODB_APPLE_NOTIFICATIONS_COLLECTION)
    if dedupe is not None:
        try:
            dedupe.insert_one(
                {
                    "_id": n_uuid,
                    "receivedAt": datetime.utcnow(),
                    "notificationType": raw_ntype,
                    "subtype": raw_subtype,
                }
            )
        except DuplicateKeyError:
            logger.info("Duplicate Apple notification uuid=%s — skipping", n_uuid)
            return {"handled": True, "duplicate": True}

    if NotificationTypeV2 and n_type == NotificationTypeV2.TEST:
        logger.info("Apple ASN v2 TEST notification uuid=%s", n_uuid)
        return {"handled": True, "test": True}

    data = getattr(outer, "data", None)
    if not data:
        logger.info("Apple notification uuid=%s has no data (type=%s)", n_uuid, raw_ntype)
        return {"handled": True, "no_data": True}

    verifier = _verifier_for(env)
    signed_tx = getattr(data, "signedTransactionInfo", None)
    signed_rn = getattr(data, "signedRenewalInfo", None)

    tx = None
    renewal = None
    if signed_tx:
        try:
            tx = verifier.verify_and_decode_signed_transaction(signed_tx)
        except VerificationException as e:
            logger.error("Apple notification %s: transaction JWS failed: %s", n_uuid, e)
            return {"handled": False, "error": "transaction_jws_verify_failed"}
    if signed_rn:
        try:
            renewal = verifier.verify_and_decode_renewal_info(signed_rn)
        except VerificationException as e:
            logger.error("Apple notification %s: renewal JWS failed: %s", n_uuid, e)
            return {"handled": False, "error": "renewal_jws_verify_failed"}

    if not tx and not renewal:
        logger.info("Apple notification uuid=%s: no signed tx or renewal", n_uuid)
        return {"handled": True, "empty": True}

    original_id: Optional[str] = None
    app_acct: Optional[str] = None
    if tx:
        original_id = getattr(tx, "originalTransactionId", None)
        tok = getattr(tx, "appAccountToken", None)
        if tok:
            app_acct = str(tok).strip().lower()
    if not original_id and renewal:
        original_id = getattr(renewal, "originalTransactionId", None)

    if not original_id:
        logger.warning("Apple notification uuid=%s: no originalTransactionId", n_uuid)
        return {"handled": True, "no_original_id": True}

    users = get_collection(USERS_COLLECTION)
    if users is None:
        return {"handled": False, "error": "users_collection_unavailable"}

    user_doc = _find_user_for_apple_subscription(users, str(original_id), app_acct)
    if not user_doc:
        logger.info(
            "Apple notification uuid=%s: no user for original_tx=%s type=%s",
            n_uuid,
            original_id,
            raw_ntype,
        )
        return {"handled": True, "no_user": True}

    from app.services.entitlement_service import recompute_and_persist

    if NotificationTypeV2 and n_type in (NotificationTypeV2.REFUND, NotificationTypeV2.REVOKE):
        users.update_one({"_id": user_doc["_id"]}, {"$set": _free_tier_apple_clear_set()})
        logger.info(
            "apple_assn_received uuid=%s user=%s type=%s action=cleared",
            n_uuid,
            user_doc["_id"],
            raw_ntype,
        )
        recompute_and_persist(str(user_doc["_id"]))
        return {"handled": True, "updated": "free", "user_id": str(user_doc["_id"])}

    if not tx and renewal:
        partial: Dict[str, Any] = {"dateUpdated": datetime.utcnow()}
        ars = getattr(renewal, "autoRenewStatus", None)
        if ars is not None and AutoRenewStatus is not None:
            partial["cancelAtPeriodEnd"] = ars == AutoRenewStatus.OFF
        users.update_one({"_id": user_doc["_id"]}, {"$set": partial})
        recompute_and_persist(str(user_doc["_id"]))
        return {"handled": True, "partial_renewal_only": True, "user_id": str(user_doc["_id"])}

    if Type is not None and getattr(tx, "type", None) != Type.AUTO_RENEWABLE_SUBSCRIPTION:
        logger.info("Apple notification uuid=%s: skipping non-auto-renewable transaction", n_uuid)
        return {"handled": True, "skipped_type": True}

    pid_for_allow = getattr(tx, "productId", None)
    if not pid_for_allow and renewal:
        pid_for_allow = getattr(renewal, "productId", None) or getattr(
            renewal, "autoRenewProductId", None
        )
    allowed = _allowed_product_ids()
    if allowed is not None and pid_for_allow and str(pid_for_allow) not in allowed:
        logger.warning(
            "Apple notification uuid=%s: product %s not allowlisted",
            n_uuid,
            pid_for_allow,
        )
        return {"handled": True, "disallowed_product": True}

    status_override: Optional[str] = None
    cap_override: Optional[bool] = None
    cat_override: Optional[datetime] = None

    if NotificationTypeV2 and n_type == NotificationTypeV2.DID_CHANGE_RENEWAL_STATUS:
        if Subtype and subtype == Subtype.AUTO_RENEW_DISABLED:
            cap_override = True
        elif Subtype and subtype == Subtype.AUTO_RENEW_ENABLED:
            cap_override = False

    if NotificationTypeV2 and n_type == NotificationTypeV2.EXPIRED:
        status_override = "expired"
        if Subtype and subtype == Subtype.VOLUNTARY and tx and getattr(tx, "expiresDate", None):
            cat_override = datetime.fromtimestamp(
                int(tx.expiresDate) / 1000.0, tz=timezone.utc
            )

    if NotificationTypeV2 and n_type == NotificationTypeV2.DID_FAIL_TO_RENEW:
        status_override = "past_due"

    if NotificationTypeV2 and n_type == NotificationTypeV2.GRACE_PERIOD_EXPIRED:
        status_override = "expired"

    skip_payload_types = (
        NotificationTypeV2.CONSUMPTION_REQUEST,
        NotificationTypeV2.PRICE_INCREASE,
        NotificationTypeV2.EXTERNAL_PURCHASE_TOKEN,
        NotificationTypeV2.RESCIND_CONSENT,
        NotificationTypeV2.ONE_TIME_CHARGE,
    )
    if NotificationTypeV2 and n_type in skip_payload_types:
        return {"handled": True, "skipped_notification_type": raw_ntype}

    try:
        set_doc = _subscription_fields_from_verified_apple_tx(
            tx,
            renewal,
            env=env,
            subscription_status_override=status_override,
            cancel_at_period_end=cap_override,
            canceled_at=cat_override,
        )
    except ValueError as e:
        logger.warning("Apple notification uuid=%s: %s", n_uuid, e)
        return {"handled": True, "skip": str(e)}

    users.update_one({"_id": user_doc["_id"]}, {"$set": set_doc})
    logger.info(
        "apple_assn_received uuid=%s user=%s type=%s status=%s",
        n_uuid,
        user_doc["_id"],
        raw_ntype,
        set_doc.get("subscriptionStatus"),
    )
    recompute_and_persist(str(user_doc["_id"]))
    return {"handled": True, "updated": True, "user_id": str(user_doc["_id"])}


def verify_apple_transaction_and_grant_entitlement(user_id: str, signed_transaction: str) -> None:
    """
    Validate signed_transaction with App Store Server API + SignedDataVerifier, then $set user entitlement.
    Idempotent for the same originalTransactionId on the same user. Conflict if another user holds the sub.
    """
    if not APPLE_STOREKIT_LIB_AVAILABLE:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="app-store-server-library is not installed",
        )
    if not apple_subscription_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Apple subscription verification is not configured on this server",
        )

    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable",
        )
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection",
        )
    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format",
        )

    user = collection.find_one({"_id": user_id_obj})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    try:
        unsafe = _decode_jws_payload_unverified(signed_transaction)
    except Exception as e:
        raise AppleBillingError(
            code="apple_validation_failed",
            detail="Invalid signed_transaction JWS",
            status_code=400,
        ) from e

    transaction_id = unsafe.get("transactionId")
    if not transaction_id:
        raise AppleBillingError(
            code="apple_validation_failed",
            detail="JWS payload missing transactionId",
            status_code=400,
        )

    _env, decoded = _fetch_transaction_with_fallback(str(transaction_id))

    if str(unsafe.get("transactionId") or "") != str(getattr(decoded, "transactionId", None) or ""):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Client JWS transactionId does not match App Store signed transaction",
        )

    if Type is not None and getattr(decoded, "type", None) != Type.AUTO_RENEWABLE_SUBSCRIPTION:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transaction is not an auto-renewable subscription",
        )

    product_id = getattr(decoded, "productId", None)
    if not product_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verified transaction missing productId",
        )

    allowed = _allowed_product_ids()
    if allowed is not None and product_id not in allowed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Subscription product is not allowed for this server",
        )

    original_tx_id = getattr(decoded, "originalTransactionId", None)
    if not original_tx_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verified transaction missing originalTransactionId",
        )

    if getattr(decoded, "revocationDate", None):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This transaction has been revoked",
        )

    expires_ms = getattr(decoded, "expiresDate", None)
    if expires_ms is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Verified subscription transaction missing expiresDate",
        )

    token = getattr(decoded, "appAccountToken", None)
    if token:
        token_norm = str(token).strip().lower()
        existing_token = user.get("appleAppAccountToken")
        if existing_token:
            if str(existing_token).strip().lower() != token_norm:
                raise AppleBillingError(
                    code="user_mismatch",
                    detail="App account token does not match this user",
                    status_code=403,
                )

    conflict = collection.find_one(
        {
            "appleOriginalTransactionId": original_tx_id,
            "_id": {"$ne": user_id_obj},
        }
    )
    if conflict:
        raise AppleBillingError(
            code="transaction_already_consumed",
            detail="This Apple subscription is already linked to another account",
            status_code=409,
        )

    try:
        set_doc = _subscription_fields_from_verified_apple_tx(decoded, None, env=_env)
    except ValueError as e:
        raise AppleBillingError(
            code="apple_validation_failed",
            detail=str(e),
            status_code=400,
        ) from e

    set_doc["cancelAtPeriodEnd"] = False
    set_doc["canceledAt"] = None

    if token and not user.get("appleAppAccountToken"):
        set_doc["appleAppAccountToken"] = str(token).strip().lower()

    collection.update_one({"_id": user_id_obj}, {"$set": set_doc})
    period_end = set_doc.get("subscriptionCurrentPeriodEnd")
    logger.info(
        "apple_verify_ok user_id=%s original_tx=%s product=%s status=%s expires=%s",
        user_id,
        original_tx_id,
        product_id,
        set_doc.get("subscriptionStatus"),
        period_end.isoformat() if isinstance(period_end, datetime) else period_end,
    )

    # Recompute and persist unified entitlement fields (Step 3).
    from app.services.entitlement_service import recompute_and_persist
    recompute_and_persist(user_id)
