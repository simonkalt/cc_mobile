"""
User service - business logic for user operations
"""
import logging
import time
import json
import re
import base64
import hmac
import hashlib
from datetime import datetime
from typing import Dict, Optional, Any
from bson import ObjectId
from fastapi import HTTPException, status

from app.models.user import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
)
from app.core.config import settings
from app.db.mongodb import get_collection, is_connected
from app.utils.password import hash_password, verify_password, validate_strong_password
from app.utils.user_helpers import (
    user_doc_to_response,
    normalize_personality_profiles,
    USERS_COLLECTION,
)

logger = logging.getLogger(__name__)


def _built_in_default_personality_profiles() -> list[dict]:
    """Fallback defaults used if JSON config is missing or invalid."""
    return [
        {
            "id": "professional-default",
            "name": "Professional",
            "description": (
                "I am trying to garner interest in my talents and experience so that I stand out "
                "and make easy for the recruiter to hire me. Be very professional."
            ),
        }
    ]


def _load_default_personality_profiles() -> list[dict]:
    """
    Load default profiles for new users from JSON file.
    Expected shape:
    {
      "profiles": [{"id": "...", "name": "...", "description": "..."}]
    }
    """
    path = settings.DEFAULT_PERSONALITY_PROFILES_PATH
    try:
        with path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        profiles = payload.get("profiles", []) if isinstance(payload, dict) else []
        normalized = normalize_personality_profiles(profiles if isinstance(profiles, list) else [])
        if normalized:
            return normalized
        logger.warning(
            "Default personality profiles file has no valid profiles: %s. Using fallback.",
            path,
        )
    except FileNotFoundError:
        logger.warning("Default personality profiles file not found: %s. Using fallback.", path)
    except Exception as e:
        logger.warning("Failed to load default personality profiles from %s: %s", path, e)
    return _built_in_default_personality_profiles()


def _normalize_sms_opt_value(registration_data: Optional[dict] = None) -> str:
    """
    Normalize registration SMS consent to backend enum ('IN'/'OUT').
    Defaults to 'IN' for new registrations.
    """
    if not isinstance(registration_data, dict):
        return "IN"

    direct_value = (
        registration_data.get("SMSOpt")
        or registration_data.get("smsOpt")
        or registration_data.get("sms_opt")
    )
    if isinstance(direct_value, str):
        candidate = direct_value.strip().upper()
        if candidate in {"IN", "OUT"}:
            return candidate

    bool_value = registration_data.get("sms_opt_in")
    if isinstance(bool_value, bool):
        return "IN" if bool_value else "OUT"

    return "IN"


def _b64url(data: bytes) -> str:
    """Base64 URL-safe encoding without padding."""
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _make_signed_token(payload: dict, secret: str) -> str:
    """
    Create a compact JWT-like HMAC token.
    This project currently does not verify bearer tokens server-side; this is for
    frontend contract compatibility (access_token/refresh_token fields).
    """
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = _b64url(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_b64}.{payload_b64}".encode("utf-8")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    signature_b64 = _b64url(signature)
    return f"{header_b64}.{payload_b64}.{signature_b64}"


def _apply_standard_jwt_claims(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Attach standard issuer/audience claims when configured."""
    enriched = payload.copy()
    if settings.JWT_ISSUER:
        enriched["iss"] = settings.JWT_ISSUER
    if settings.JWT_AUDIENCE:
        enriched["aud"] = settings.JWT_AUDIENCE
    return enriched


def register_user(user_data: UserRegisterRequest) -> UserResponse:
    """Register a new user"""
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    # Check if user already exists
    existing_user = collection.find_one({"email": user_data.email})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )

    if settings.ENFORCE_STRONG_PASSWORDS:
        validation_error = validate_strong_password(user_data.password)
        if validation_error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=validation_error,
            )
    
    # Hash password
    hashed_password_str = hash_password(user_data.password)
    
    # Extract preferences if provided
    preferences = user_data.preferences or {}
    app_settings = preferences.get("appSettings", {})
    personality_profiles = app_settings.get("personalityProfiles", [])
    
    # If no personality profiles provided or empty, create defaults from JSON.
    if not personality_profiles or len(personality_profiles) == 0:
        personality_profiles = _load_default_personality_profiles()
        logger.info(
            "Assigned %d default personality profile(s) to new user: %s",
            len(personality_profiles),
            user_data.email,
        )
    
    # Ensure appSettings exists in preferences
    if "appSettings" not in preferences:
        preferences["appSettings"] = {}
    
    # Set the personality profiles (either provided or default)
    preferences["appSettings"]["personalityProfiles"] = personality_profiles
    
    # Merge provided preferences with defaults to ensure all required fields exist
    default_preferences = {
        "newsletterOptIn": False,
        "theme": "light",
        "appSettings": {
            "printProperties": {
                "margins": {
                    "top": 1.0,
                    "right": 0.75,
                    "bottom": 0.25,
                    "left": 0.75
                },
                "fontFamily": "Georgia",
                "fontSize": 11.0,
                "lineHeight": 1.15,
                "pageSize": {
                    "width": 8.5,
                    "height": 11.0
                },
                "useDefaultFonts": False
            },
            "personalityProfiles": personality_profiles,
            "selectedModel": None,
            "lastResumeUsed": None,
            "last_personality_profile_used": None
        },
        "formDefaults": {
            "companyName": "",
            "hiringManager": "",
            "adSource": "",
            "jobDescription": "",
            "additionalInstructions": "",
            "tone": "Professional",
            "address": "",
            "phoneNumber": "",
            "resume": ""
        }
    }
    
    # Deep merge: start with defaults, then overlay provided preferences
    def deep_merge(default: dict, provided: dict) -> dict:
        """Recursively merge provided dict into default dict"""
        result = default.copy()
        for key, value in provided.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = deep_merge(result[key], value)
            else:
                result[key] = value
        return result
    
    final_preferences = deep_merge(default_preferences, preferences)
    # Ensure personalityProfiles is set (in case it was overwritten)
    final_preferences["appSettings"]["personalityProfiles"] = personality_profiles
    
    # Build user document
    user_doc = {
        "name": user_data.name,
        "email": user_data.email,
        "hashedPassword": hashed_password_str,
        "isActive": True,
        "isEmailVerified": False,
        "roles": ["user"],
        "failedLoginAttempts": 0,
        "lastLogin": None,
        "passwordChangedAt": None,
        "avatarUrl": None,
        "phone": user_data.phone,
        "address": user_data.address or {
            "street": None,
            "city": None,
            "state": None,
            "zip": None,
            "country": None
        },
        "dateCreated": datetime.utcnow(),
        "dateUpdated": datetime.utcnow(),
        "llm_counts": {},  # Initialize empty LLM usage counts object
        "last_llm_used": None,  # Initialize last LLM used field
        "preferences": final_preferences,
        "subscriptionId": None,
        "subscriptionStatus": "free",
        "subscriptionPlan": "free",
        "subscriptionCurrentPeriodEnd": None,
        "lastPaymentDate": None,
        "stripeCustomerId": None,
        "generation_credits": 10,
        "max_credits": 10,
        "SMSOpt": "IN",
        "SMSOptDate": datetime.utcnow(),
    }
    
    try:
        result = collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        logger.info(f"User registered: {user_data.email} (ID: {result.inserted_id})")
        return user_doc_to_response(user_doc)
    except Exception as e:
        logger.error(f"Error registering user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register user: {str(e)}"
        )


def get_user_by_id(user_id: str) -> UserResponse:
    """Get user by ID"""
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    logger.info(f"Querying MongoDB for user_id: {user_id} (ObjectId: {user_id_obj})")
    try:
        user = collection.find_one({"_id": user_id_obj})
        if not user:
            # Log collection info for debugging
            try:
                total_users = collection.estimated_document_count()
                logger.warning(f"User not found: {user_id}. Estimated total users in collection: {total_users}")
                # Try to find any user to verify collection access
                sample_user = collection.find_one({})
                if sample_user:
                    logger.info(f"Sample user in collection: {sample_user.get('_id')}, email: {sample_user.get('email')}")
                else:
                    logger.warning("Collection is empty - no users found")
            except Exception as count_error:
                logger.error(f"Could not count documents: {count_error}")
            
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found with ID: {user_id}"
            )
        
        logger.info(f"Found user: {user.get('email')} (ID: {user.get('_id')})")
        return user_doc_to_response(user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error querying user {user_id}: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {str(e)}"
        )


def get_user_by_email(email: str) -> UserResponse:
    """Get user by email"""
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    user = collection.find_one({"email": email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    return user_doc_to_response(user)


def get_user_by_email_ignore_case(email: str) -> UserResponse:
    """Get user by email, case-insensitive."""
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

    # Anchor regex to exact email with case-insensitive comparison.
    user = collection.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    return user_doc_to_response(user)


def create_user_from_registration_data(
    registration_data: dict, is_email_verified: bool = False
) -> UserResponse:
    """
    Create a user from pre-validated registration payload (e.g. Redis flow).
    Expects `registration_data["password"]` to already be hashed.
    """
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

    email = registration_data.get("email")
    name = registration_data.get("name")
    hashed_password = registration_data.get("password")
    if not email or not name or not hashed_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="registration_data must include name, email, and hashed password",
        )

    existing_user = collection.find_one({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists",
        )

    preferences = registration_data.get("preferences") or {}
    if not isinstance(preferences, dict):
        preferences = {}

    # Ensure minimal app settings shape exists
    app_settings: Dict[str, Any] = preferences.get("appSettings") or {}
    if not isinstance(app_settings, dict):
        app_settings = {}
    app_settings.setdefault("printProperties", {
        "margins": {"top": 1.0, "right": 0.75, "bottom": 0.25, "left": 0.75},
        "fontFamily": "Georgia",
        "fontSize": 11.0,
        "lineHeight": 1.15,
        "pageSize": {"width": 8.5, "height": 11.0},
        "useDefaultFonts": False,
    })
    if not app_settings.get("personalityProfiles"):
        app_settings["personalityProfiles"] = _load_default_personality_profiles()
    preferences["appSettings"] = app_settings

    sms_opt_value = _normalize_sms_opt_value(registration_data)

    user_doc = {
        "name": name,
        "email": email,
        "hashedPassword": hashed_password,
        "isActive": True,
        "isEmailVerified": is_email_verified,
        "roles": ["user"],
        "failedLoginAttempts": 0,
        "lastLogin": None,
        "passwordChangedAt": None,
        "avatarUrl": None,
        "phone": registration_data.get("phone"),
        "address": registration_data.get("address")
        or {"street": None, "city": None, "state": None, "zip": None, "country": None},
        "dateCreated": datetime.utcnow(),
        "dateUpdated": datetime.utcnow(),
        "llm_counts": {},
        "last_llm_used": None,
        "preferences": preferences,
        "subscriptionId": None,
        "subscriptionStatus": "free",
        "subscriptionPlan": "free",
        "subscriptionCurrentPeriodEnd": None,
        "lastPaymentDate": None,
        "stripeCustomerId": None,
        "generation_credits": 10,
        "max_credits": 10,
        "SMSOpt": sms_opt_value,
        "SMSOptDate": datetime.utcnow(),
    }

    try:
        result = collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        return user_doc_to_response(user_doc)
    except Exception as e:
        logger.error(f"Error creating user from registration data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}",
        )


def update_user(user_id: str, updates: UserUpdateRequest) -> UserResponse:
    """Update user"""
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    # Get current user to preserve existing personalityProfiles if not explicitly updated
    current_user = collection.find_one({"_id": user_id_obj})
    existing_profiles = []
    if current_user:
        existing_profiles = current_user.get("preferences", {}).get("appSettings", {}).get("personalityProfiles", [])
        logger.debug(f"Current user has {len(existing_profiles) if isinstance(existing_profiles, list) else 0} existing personality profile(s)")
    
    # Build update document (only include fields that are provided)
    update_doc = {"dateUpdated": datetime.utcnow()}
    
    if updates.name is not None:
        update_doc["name"] = updates.name
    if updates.email is not None:
        # Check if email is already taken by another user
        existing = collection.find_one({"email": updates.email, "_id": {"$ne": user_id_obj}})
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Email already in use by another user"
            )
        update_doc["email"] = updates.email
    if updates.phone is not None:
        update_doc["phone"] = updates.phone
    if updates.isActive is not None:
        update_doc["isActive"] = updates.isActive
    if updates.isEmailVerified is not None:
        update_doc["isEmailVerified"] = updates.isEmailVerified
    if updates.roles is not None:
        update_doc["roles"] = updates.roles
    if updates.address is not None:
        update_doc["address"] = updates.address
    if updates.preferences is not None:
        # Handle preferences update - support nested structure
        if isinstance(updates.preferences, dict):
            # Check if this is a partial update (has appSettings nested structure)
            if "appSettings" in updates.preferences:
                app_settings = updates.preferences.get("appSettings", {})
                if isinstance(app_settings, dict):
                    # Update printProperties if present
                    if "printProperties" in app_settings:
                        print_props = app_settings["printProperties"]
                        if isinstance(print_props, dict):
                            # Update margins
                            if "margins" in print_props:
                                for margin_key, margin_value in print_props["margins"].items():
                                    update_doc[f"preferences.appSettings.printProperties.margins.{margin_key}"] = margin_value
                            # Update other printProperties fields
                            for prop_key in ["fontFamily", "fontSize", "lineHeight", "useDefaultFonts"]:
                                if prop_key in print_props:
                                    update_doc[f"preferences.appSettings.printProperties.{prop_key}"] = print_props[prop_key]
                            # Update pageSize
                            if "pageSize" in print_props:
                                for size_key, size_value in print_props["pageSize"].items():
                                    update_doc[f"preferences.appSettings.printProperties.pageSize.{size_key}"] = size_value
                    # Update personalityProfiles
                    # IMPORTANT: Only update if explicitly provided in the request
                    # If not provided, preserve existing profiles
                    if "personalityProfiles" in app_settings:
                        personality_profiles = app_settings["personalityProfiles"]
                        logger.info(
                            "personalityProfiles provided in update request for user %s: type=%s, length=%s",
                            user_id,
                            type(personality_profiles),
                            len(personality_profiles) if isinstance(personality_profiles, list) else "N/A",
                        )
                        
                        if isinstance(personality_profiles, list):
                            # Only update if explicitly provided (even if empty array)
                            # If the array is empty, that means user wants to clear profiles
                            # If normalization filters out invalid profiles, preserve existing ones
                            normalized_profiles = normalize_personality_profiles(personality_profiles)
                            
                            # If frontend sent empty array, clear profiles (explicit intent)
                            if len(personality_profiles) == 0:
                                update_doc["preferences.appSettings.personalityProfiles"] = []
                                logger.warning(
                                    f"⚠️ Cleared personalityProfiles for user {user_id} (explicit empty array). "
                                    f"Had {len(existing_profiles) if isinstance(existing_profiles, list) else 0} existing profile(s)."
                                )
                            # If normalization filtered out all profiles but frontend sent some, warn and preserve existing
                            elif len(normalized_profiles) == 0 and len(personality_profiles) > 0:
                                logger.warning(
                                    f"⚠️ WARNING: All personalityProfiles were filtered out during normalization for user {user_id}. "
                                    f"Frontend sent {len(personality_profiles)} profile(s) but none were valid. Preserving {len(existing_profiles) if isinstance(existing_profiles, list) else 0} existing profile(s)."
                                )
                                # Don't update - preserve existing profiles
                            # If we have valid normalized profiles, update them
                            elif len(normalized_profiles) > 0:
                                update_doc["preferences.appSettings.personalityProfiles"] = normalized_profiles
                                logger.info(
                                    f"Updated personalityProfiles for user {user_id}: {len(normalized_profiles)} profile(s) "
                                    f"(replaced {len(existing_profiles) if isinstance(existing_profiles, list) else 0} existing)"
                                )
                        elif personality_profiles is None:
                            # Explicitly set to None - don't update, preserve existing
                            logger.info(f"personalityProfiles set to None in update request for user {user_id}. Preserving existing profiles.")
                        else:
                            logger.error(f"Invalid personalityProfiles type for user {user_id}: {type(personality_profiles)}. Expected list. Preserving existing profiles.")
                    else:
                        # personalityProfiles not in update request - preserve existing
                        logger.debug(f"personalityProfiles not in update request for user {user_id}. Preserving {len(existing_profiles) if isinstance(existing_profiles, list) else 0} existing profile(s).")
                    # Update selectedModel
                    if "selectedModel" in app_settings:
                        update_doc["preferences.appSettings.selectedModel"] = app_settings["selectedModel"]
                    # Update lastResumeUsed (accept camelCase and legacy snake_case keys)
                    last_resume_value_set = False
                    if "lastResumeUsed" in app_settings:
                        update_doc["preferences.appSettings.lastResumeUsed"] = app_settings["lastResumeUsed"]
                        last_resume_value_set = True
                    elif "last_resume_used" in app_settings:
                        update_doc["preferences.appSettings.lastResumeUsed"] = app_settings["last_resume_used"]
                        last_resume_value_set = True
                    elif "last_resume" in app_settings:
                        update_doc["preferences.appSettings.lastResumeUsed"] = app_settings["last_resume"]
                        last_resume_value_set = True
                    if last_resume_value_set:
                        logger.info(
                            "Updated lastResumeUsed for user %s",
                            user_id,
                        )
                    # Update last_personality_profile_used
                    if "last_personality_profile_used" in app_settings:
                        update_doc["preferences.appSettings.last_personality_profile_used"] = app_settings["last_personality_profile_used"]
            # Update top-level preferences fields
            if "newsletterOptIn" in updates.preferences:
                update_doc["preferences.newsletterOptIn"] = updates.preferences["newsletterOptIn"]
            if "theme" in updates.preferences:
                update_doc["preferences.theme"] = updates.preferences["theme"]
        else:
            # If it's not a dict, replace the whole preferences object
            update_doc["preferences"] = updates.preferences
    if updates.avatarUrl is not None:
        update_doc["avatarUrl"] = updates.avatarUrl
    if updates.last_llm_used is not None:
        update_doc["last_llm_used"] = updates.last_llm_used
    
    try:
        result = collection.update_one(
            {"_id": user_id_obj},
            {"$set": update_doc}
        )
        
        if result.matched_count == 0:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Return updated user
        updated_user = collection.find_one({"_id": user_id_obj})
        logger.info(f"User updated: {user_id}")
        return user_doc_to_response(updated_user)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update user: {str(e)}"
        )


def delete_user(user_id: str) -> Dict:
    """Delete user"""
    if not is_connected():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable"
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid user ID format"
        )
    
    result = collection.delete_one({"_id": user_id_obj})
    
    if result.deleted_count == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.info(f"User deleted: {user_id}")
    return {"success": True, "message": "User deleted successfully"}


def login_user(login_data: UserLoginRequest) -> UserLoginResponse:
    """Authenticate user login"""
    if not is_connected():
        logger.error("Database connection unavailable when attempting login")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database connection unavailable. Please try again in a moment."
        )
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        logger.error("Failed to get users collection")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Failed to access users collection"
        )
    
    # Find user by email
    user = collection.find_one({"email": login_data.email})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Check if user is active
    if not user.get("isActive", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )
    
    # Verify password
    hashed_password_str = user.get("hashedPassword", "")
    if not verify_password(login_data.password, hashed_password_str):
        # Increment failed login attempts
        collection.update_one(
            {"_id": user["_id"]},
            {"$inc": {"failedLoginAttempts": 1}}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Reset failed login attempts and update last login
    collection.update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "lastLogin": datetime.utcnow(),
                "failedLoginAttempts": 0
            }
        }
    )
    
    logger.info(f"User logged in: {login_data.email}")

    # Generate token fields expected by existing frontend contract.
    # NOTE: Tokens are currently not validated by backend routes in this repo.
    now = int(time.time())
    access_ttl_seconds = 24 * 60 * 60
    refresh_ttl_seconds = 30 * 24 * 60 * 60
    jwt_secret = settings.JWT_SECRET
    user_id = str(user["_id"])

    access_payload = _apply_standard_jwt_claims({
        "sub": user_id,
        "email": user.get("email"),
        "type": "access",
        "iat": now,
        "exp": now + access_ttl_seconds,
    })
    refresh_payload = _apply_standard_jwt_claims({
        "sub": user_id,
        "email": user.get("email"),
        "type": "refresh",
        "iat": now,
        "exp": now + refresh_ttl_seconds,
    })

    access_token = _make_signed_token(access_payload, jwt_secret)
    refresh_token = _make_signed_token(refresh_payload, jwt_secret)

    return UserLoginResponse(
        success=True,
        user=user_doc_to_response(user),
        message="Login successful",
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=access_ttl_seconds,
    )


def increment_llm_usage_count(user_id: str, llm_name: str) -> bool:
    """
    Increment the usage count for a specific LLM in the user's record.
    If the LLM doesn't exist in llm_counts, add it and set count to 1.
    Also updates the last_llm_used field to track the most recently used LLM.
    
    Args:
        user_id: User ID
        llm_name: Name of the LLM
        
    Returns:
        True if successful, False otherwise
    """
    if not is_connected():
        logger.warning("Database connection unavailable. Cannot update LLM usage count.")
        return False
    
    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        logger.warning("Failed to access users collection. Cannot update LLM usage count.")
        return False
    
    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        logger.warning(f"Invalid user ID format: {user_id}")
        return False
    
    try:
        # First, ensure llm_counts field exists
        user = collection.find_one({"_id": user_id_obj})
        if not user:
            logger.warning(f"User {user_id} not found. Cannot update LLM usage count.")
            return False
        
        # Initialize llm_counts if it doesn't exist
        if "llm_counts" not in user:
            collection.update_one(
                {"_id": user_id_obj},
                {"$set": {"llm_counts": {}}}
            )
        
        # Use MongoDB's $inc operator to increment the count
        result = collection.update_one(
            {"_id": user_id_obj},
            {
                "$inc": {f"llm_counts.{llm_name}": 1},
                "$set": {
                    "last_llm_used": llm_name,
                    "dateUpdated": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count > 0:
            updated_user = collection.find_one({"_id": user_id_obj})
            if updated_user and "llm_counts" in updated_user:
                count = updated_user["llm_counts"].get(llm_name, 0)
                if count == 1:
                    logger.info(f"Initialized LLM count for {llm_name} to 1 for user {user_id}")
                else:
                    logger.debug(f"Incremented LLM count for {llm_name} to {count} for user {user_id}")
            return True
        else:
            logger.warning(f"User {user_id} not found. Cannot update LLM usage count.")
            return False
            
    except Exception as e:
        logger.error(f"Error incrementing LLM usage count: {e}")
        return False


def decrement_generation_credits(user_id: str) -> bool:
    """
    Decrement generation credits for free users if the field exists.
    This is best-effort and intentionally non-fatal for generation flow.
    """
    if not is_connected():
        logger.warning("Database connection unavailable. Cannot decrement generation credits.")
        return False

    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        logger.warning("Failed to access users collection. Cannot decrement generation credits.")
        return False

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        logger.warning(f"Invalid user ID format: {user_id}")
        return False

    try:
        user = collection.find_one({"_id": user_id_obj})
        if not user:
            logger.warning(f"User {user_id} not found. Cannot decrement generation credits.")
            return False

        # Only apply to free users when generation_credits is tracked.
        if "generation_credits" not in user:
            logger.debug(f"User {user_id} has no generation_credits field; skipping decrement.")
            return True

        subscription_status = str(user.get("subscriptionStatus", "")).lower()
        if subscription_status == "active":
            logger.debug(f"User {user_id} has active subscription; skipping credit decrement.")
            return True

        current_credits = int(user.get("generation_credits", 0) or 0)
        if current_credits <= 0:
            logger.info(f"User {user_id} has no remaining generation credits.")
            return True

        result = collection.update_one(
            {"_id": user_id_obj, "generation_credits": {"$gt": 0}},
            {"$inc": {"generation_credits": -1}, "$set": {"dateUpdated": datetime.utcnow()}},
        )
        if result.matched_count == 0:
            logger.info(f"No generation credit decrement applied for user {user_id}.")
            return True

        logger.info(f"Decremented generation credits for user {user_id}: {current_credits} -> {current_credits - 1}")
        return True
    except Exception as e:
        logger.error(f"Error decrementing generation credits for user {user_id}: {e}")
        return False


def set_linkedin_token(user_id: str, token_data: Dict) -> bool:
    """
    Store LinkedIn OAuth token data under user preferences.
    """
    if not is_connected():
        logger.warning("MongoDB not connected; cannot set LinkedIn token")
        return False

    collection = get_collection(USERS_COLLECTION)
    if collection is None:
        return False

    try:
        user_id_obj = ObjectId(user_id)
    except Exception:
        logger.warning("Invalid user_id for set_linkedin_token: %s", user_id)
        return False

    user = collection.find_one({"_id": user_id_obj})
    if not user:
        logger.warning("User not found for set_linkedin_token: %s", user_id)
        return False

    preferences = user.get("preferences") or {}
    if not isinstance(preferences, dict):
        preferences = {}
    preferences["linkedin"] = token_data

    result = collection.update_one(
        {"_id": user_id_obj},
        {"$set": {"preferences": preferences, "dateUpdated": datetime.utcnow()}},
    )
    return result.matched_count > 0


def get_linkedin_token(user_id: str) -> Optional[Dict]:
    """
    Read LinkedIn OAuth token data from user preferences.
    """
    try:
        user = get_user_by_id(user_id)
        prefs = user.preferences or {}
        linkedin = prefs.get("linkedin")
        if isinstance(linkedin, dict) and linkedin.get("access_token"):
            return linkedin
    except Exception:
        pass
    return None

