"""
OAuth login and account linking (Google / LinkedIn, Authorization Code + PKCE).
See documentation/OAUTH_LOGIN_API.md.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Optional

from bson import ObjectId
from fastapi import HTTPException, status

from app.constants.http_details import HTTP_DETAIL_PENDING_ACCOUNT_DELETION
from app.constants.oauth_errors import oauth_error_detail
from app.models.oauth import (
    AppleOAuthLinkRequest,
    AppleOAuthLoginRequest,
    OAuthLinkResponse,
    OAuthLoginResponse,
    OAuthTokenExchangeRequest,
)
from app.models.user import UserResponse
from app.services.oauth_providers import (
    OAuthIdentity,
    OAuthProviderError,
    resolve_oauth_identity,
    verify_apple_identity_token,
)
from app.services.user_service import (
    USERS_COLLECTION,
    build_login_response_from_user_doc,
    create_oauth_user_document,
    normalize_email_for_lookup,
)
from app.db.mongodb import get_collection, is_connected
from app.utils.user_helpers import user_doc_to_response

logger = logging.getLogger(__name__)

OAUTH_PROVIDERS = frozenset({"google", "linkedin", "apple"})


def _require_db_collection():
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
    return collection


def _oauth_http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail=oauth_error_detail(code, message))


def _find_user_by_provider_sub(collection, provider: str, subject: str) -> Optional[dict]:
    return collection.find_one(
        {"authProviders": {"$elemMatch": {"provider": provider, "subject": subject}}}
    )


def _find_user_by_email_insensitive(collection, email: str) -> Optional[dict]:
    import re

    normalized = normalize_email_for_lookup(email)
    if not normalized:
        return None
    pattern = f"^{re.escape(normalized)}$"
    return collection.find_one({"email": {"$regex": pattern, "$options": "i"}})


def _user_has_provider(user_doc: dict, provider: str) -> bool:
    providers = user_doc.get("authProviders") or []
    return any(
        isinstance(p, dict) and p.get("provider") == provider for p in providers
    )


def _provider_sub_linked_to_other_user(
    collection,
    provider: str,
    subject: str,
    exclude_user_id: ObjectId,
) -> bool:
    other = collection.find_one(
        {
            "_id": {"$ne": exclude_user_id},
            "authProviders": {"$elemMatch": {"provider": provider, "subject": subject}},
        }
    )
    return other is not None


def _assert_user_can_authenticate(user_doc: dict) -> None:
    if user_doc.get("account_deletion_pending"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=HTTP_DETAIL_PENDING_ACCOUNT_DELETION,
        )
    if not user_doc.get("account_deletion_pending") and not user_doc.get("isActive", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=oauth_error_detail(
                "inactive_account",
                "User account is inactive",
            ),
        )


def _replace_auth_provider(
    collection,
    user_id: ObjectId,
    identity: OAuthIdentity,
) -> dict:
    now = datetime.now(UTC)
    collection.update_one(
        {"_id": user_id, "authProviders.provider": identity.provider},
        {
            "$set": {
                "authProviders.$.subject": identity.sub,
                "authProviders.$.linkedAt": now,
                "authProviders.$.emailFromProvider": identity.email,
                "dateUpdated": now,
            }
        },
    )
    updated = collection.find_one({"_id": user_id})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user after replacing provider",
        )
    return updated


def _append_auth_provider(
    collection,
    user_id: ObjectId,
    identity: OAuthIdentity,
) -> dict:
    now = datetime.now(UTC)
    provider_entry = {
        "provider": identity.provider,
        "subject": identity.sub,
        "linkedAt": now,
        "emailFromProvider": identity.email,
    }
    collection.update_one(
        {"_id": user_id},
        {
            "$push": {"authProviders": provider_entry},
            "$set": {"dateUpdated": now},
        },
    )
    updated = collection.find_one({"_id": user_id})
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to load user after linking provider",
        )
    return updated


def _touch_last_login(collection, user_id: ObjectId) -> None:
    collection.update_one(
        {"_id": user_id},
        {"$set": {"lastLogin": datetime.now(UTC), "failedLoginAttempts": 0}},
    )


def _resolve_identity(provider: str, body: OAuthTokenExchangeRequest) -> OAuthIdentity:
    if provider == "linkedin":
        logger.info(
            "OAuth LinkedIn exchange redirect_uri=%s code_len=%s verifier_len=%s",
            body.redirect_uri.strip(),
            len(body.code.strip()),
            len(body.code_verifier.strip()),
        )
    try:
        return resolve_oauth_identity(
            provider,
            body.code.strip(),
            body.redirect_uri.strip(),
            body.code_verifier.strip(),
        )
    except OAuthProviderError as exc:
        raise _oauth_http_error(
            status.HTTP_401_UNAUTHORIZED,
            exc.error_code or "invalid_code",
            exc.message or "Authorization code is invalid or expired",
        ) from exc


def _maybe_set_avatar(collection, user_id: ObjectId, picture: Optional[str]) -> None:
    if not picture:
        return
    collection.update_one(
        {"_id": user_id, "$or": [{"avatarUrl": None}, {"avatarUrl": ""}]},
        {"$set": {"avatarUrl": picture}},
    )


def _login_existing_user(
    collection,
    user_doc: dict,
    identity: OAuthIdentity,
    *,
    linked_provider: Optional[str] = None,
    replaced_provider: Optional[str] = None,
) -> OAuthLoginResponse:
    _assert_user_can_authenticate(user_doc)
    _touch_last_login(collection, user_doc["_id"])
    _maybe_set_avatar(collection, user_doc["_id"], identity.picture)
    refreshed = collection.find_one({"_id": user_doc["_id"]}) or user_doc
    base = build_login_response_from_user_doc(refreshed)
    return OAuthLoginResponse(
        success=base.success,
        user=base.user,
        message=base.message,
        access_token=base.access_token,
        refresh_token=base.refresh_token,
        token_type=base.token_type,
        expires_in=base.expires_in,
        files=base.files,
        linkedProvider=linked_provider,
        replacedProvider=replaced_provider,
    )


def _oauth_replace_provider_for_user(
    collection,
    user_doc: dict,
    identity: OAuthIdentity,
) -> dict:
    user_oid = user_doc["_id"]
    provider = identity.provider

    if not _user_has_provider(user_doc, provider):
        raise _oauth_http_error(
            status.HTTP_409_CONFLICT,
            "provider_not_linked",
            f"This account does not have {provider} linked yet.",
        )

    if _provider_sub_linked_to_other_user(collection, provider, identity.sub, user_oid):
        raise _oauth_http_error(
            status.HTTP_409_CONFLICT,
            "provider_sub_conflict",
            "This sign-in is already linked to another account.",
        )

    existing_by_sub = _find_user_by_provider_sub(collection, provider, identity.sub)
    if existing_by_sub and existing_by_sub["_id"] == user_oid:
        return user_doc

    if existing_by_sub and existing_by_sub["_id"] != user_oid:
        raise _oauth_http_error(
            status.HTTP_409_CONFLICT,
            "provider_sub_conflict",
            "This sign-in is already linked to another account.",
        )

    return _replace_auth_provider(collection, user_oid, identity)


def _resolve_apple_identity(
    identity_token: str,
    full_name,
) -> OAuthIdentity:
    full_name_dict = full_name.model_dump() if full_name is not None else None
    try:
        return verify_apple_identity_token(identity_token, full_name=full_name_dict)
    except OAuthProviderError as exc:
        raise _oauth_http_error(
            status.HTTP_401_UNAUTHORIZED,
            exc.error_code or "invalid_code",
            exc.message or "Sign in with Apple is invalid or expired",
        ) from exc


def oauth_login(provider: str, body: OAuthTokenExchangeRequest) -> OAuthLoginResponse:
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown OAuth provider: {provider}",
        )

    identity = _resolve_identity(provider, body)
    collection = _require_db_collection()
    intent = (body.intent or "login").strip().lower()
    return _complete_oauth_login(
        collection,
        identity,
        intent=intent,
        replace_existing=bool(body.replace_existing_provider),
        data_use_accepted=body.data_use_sharing_notice_accepted,
    )


def apple_oauth_login(body: AppleOAuthLoginRequest) -> OAuthLoginResponse:
    """Sign in with Apple: verify the native identity token, then login/link/create."""
    identity = _resolve_apple_identity(body.identity_token, body.full_name)
    collection = _require_db_collection()
    intent = (body.intent or "login").strip().lower()
    return _complete_oauth_login(
        collection,
        identity,
        intent=intent,
        replace_existing=False,
        data_use_accepted=body.data_use_sharing_notice_accepted,
    )


def _complete_oauth_login(
    collection,
    identity: OAuthIdentity,
    *,
    intent: str,
    replace_existing: bool,
    data_use_accepted: Optional[bool],
) -> OAuthLoginResponse:
    provider = identity.provider

    by_sub = _find_user_by_provider_sub(collection, provider, identity.sub)
    if by_sub:
        if intent == "register":
            if by_sub.get("oauthRegistrationPending"):
                return _login_existing_user(collection, by_sub, identity)
            raise _oauth_http_error(
                status.HTTP_409_CONFLICT,
                "oauth_account_exists",
                "An account with this sign-in already exists. "
                "Sign in on the login screen, or choose another account.",
            )
        return _login_existing_user(collection, by_sub, identity)

    replace_provider = intent == "replace_provider" or bool(replace_existing)
    email = (identity.email or "").strip()
    linked_provider: Optional[str] = None

    if email:
        by_email = _find_user_by_email_insensitive(collection, email)
        if by_email:
            if identity.email_verified:
                if replace_provider and _user_has_provider(by_email, provider):
                    updated = _oauth_replace_provider_for_user(
                        collection, by_email, identity
                    )
                    return _login_existing_user(
                        collection,
                        updated,
                        identity,
                        replaced_provider=provider,
                    )
                if _user_has_provider(by_email, provider):
                    if intent == "register":
                        if by_email.get("oauthRegistrationPending"):
                            return _login_existing_user(
                                collection, by_email, identity
                            )
                        raise _oauth_http_error(
                            status.HTTP_409_CONFLICT,
                            "oauth_account_exists",
                            "An account with this email already uses this sign-in method. "
                            "Sign in on the login screen, or choose another account.",
                        )
                    return _login_existing_user(collection, by_email, identity)
                updated = _append_auth_provider(collection, by_email["_id"], identity)
                linked_provider = provider
                return _login_existing_user(
                    collection,
                    updated,
                    identity,
                    linked_provider=linked_provider,
                )
            raise _oauth_http_error(
                status.HTTP_409_CONFLICT,
                "link_not_allowed",
                "An account with this email already exists. Sign in with your password or link from Settings.",
            )

    if intent == "login":
        raise _oauth_http_error(
            status.HTTP_401_UNAUTHORIZED,
            "user_not_found",
            "No account found for this sign-in. Register first or use a different method.",
        )

    if not data_use_accepted:
        raise _oauth_http_error(
            status.HTTP_400_BAD_REQUEST,
            "data_use_notice_required",
            "You must accept the Data Use & Sharing Notice to create an account.",
        )

    if not email:
        raise _oauth_http_error(
            status.HTTP_400_BAD_REQUEST,
            "invalid_code",
            "Email is required from the identity provider to create an account.",
        )

    user_doc = create_oauth_user_document(
        email=email,
        name=identity.name or "",
        avatar_url=identity.picture,
        provider=provider,
        subject=identity.sub,
        email_from_provider=identity.email,
    )
    return _login_existing_user(collection, user_doc, identity)


def oauth_link_provider(
    current_user: UserResponse,
    provider: str,
    body: OAuthTokenExchangeRequest,
) -> OAuthLinkResponse:
    if provider not in OAUTH_PROVIDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown OAuth provider: {provider}",
        )

    identity = _resolve_identity(provider, body)
    return _complete_oauth_link(
        current_user,
        identity,
        replace_existing=bool(body.replace_existing_provider),
    )


def apple_oauth_link_provider(
    current_user: UserResponse,
    body: AppleOAuthLinkRequest,
) -> OAuthLinkResponse:
    """Link Sign in with Apple to the authenticated user."""
    identity = _resolve_apple_identity(body.identity_token, body.full_name)
    return _complete_oauth_link(
        current_user,
        identity,
        replace_existing=bool(body.replace_existing_provider),
    )


def _complete_oauth_link(
    current_user: UserResponse,
    identity: OAuthIdentity,
    *,
    replace_existing: bool,
) -> OAuthLinkResponse:
    provider = identity.provider
    collection = _require_db_collection()

    try:
        user_oid = ObjectId(current_user.id)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID",
        ) from exc

    user_doc = collection.find_one({"_id": user_oid})
    if not user_doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    if _user_has_provider(user_doc, provider):
        if not replace_existing:
            raise _oauth_http_error(
                status.HTTP_409_CONFLICT,
                "provider_already_linked",
                f"This account already has {provider} linked.",
            )
        updated = _oauth_replace_provider_for_user(collection, user_doc, identity)
        logger.info("Replaced %s for user_id=%s", provider, current_user.id)
        return OAuthLinkResponse(
            success=True,
            user=user_doc_to_response(updated),
            replacedProvider=provider,
        )

    if _provider_sub_linked_to_other_user(collection, provider, identity.sub, user_oid):
        raise _oauth_http_error(
            status.HTTP_409_CONFLICT,
            "provider_sub_conflict",
            "This sign-in is already linked to another account.",
        )

    existing_by_sub = _find_user_by_provider_sub(collection, provider, identity.sub)
    if existing_by_sub and existing_by_sub["_id"] != user_oid:
        raise _oauth_http_error(
            status.HTTP_409_CONFLICT,
            "provider_sub_conflict",
            "This sign-in is already linked to another account.",
        )

    account_email = normalize_email_for_lookup(user_doc.get("email", ""))
    idp_email = normalize_email_for_lookup(identity.email or "")
    if idp_email and account_email and idp_email != account_email:
        if not identity.email_verified:
            raise _oauth_http_error(
                status.HTTP_409_CONFLICT,
                "link_not_allowed",
                "Provider email could not be verified for linking.",
            )
        raise _oauth_http_error(
            status.HTTP_409_CONFLICT,
            "link_not_allowed",
            "Provider email does not match your account email.",
        )

    if identity.email and not identity.email_verified:
        raise _oauth_http_error(
            status.HTTP_409_CONFLICT,
            "link_not_allowed",
            "Provider email must be verified before linking.",
        )

    updated = _append_auth_provider(collection, user_oid, identity)
    logger.info("Linked %s for user_id=%s", provider, current_user.id)
    return OAuthLinkResponse(
        success=True,
        user=user_doc_to_response(updated),
        linkedProvider=provider,
    )
