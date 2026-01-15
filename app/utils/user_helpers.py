"""
User-related helper functions
"""

import copy
import logging
from typing import Optional, List, Dict

from app.models.user import UserResponse
from app.db.mongodb import get_collection
from app.core.config import settings

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"


def normalize_personality_profile(profile: dict) -> Optional[dict]:
    """
    Normalize a personality profile to ensure it only contains id, name, description.
    Returns a dict with only these three fields.

    Args:
        profile: Personality profile dictionary

    Returns:
        Normalized profile dict or None if invalid
    """
    if not isinstance(profile, dict):
        logger.warning(f"Profile is not a dict: {type(profile)}, value: {profile}")
        return None

    profile_id = profile.get("id", "")
    profile_name = profile.get("name", "")

    # Log if profile is missing required fields
    if not profile_id or not profile_name:
        logger.warning(
            f"Profile missing required fields - id: {bool(profile_id)}, name: {bool(profile_name)}, "
            f"profile keys: {list(profile.keys())}, full profile: {profile}"
        )
        return None

    normalized = {"id": profile_id, "name": profile_name, "description": profile.get("description", "")}
    logger.debug(f"Normalized profile: {normalized}")
    return normalized


def normalize_personality_profiles(profiles: list) -> List[dict]:
    """
    Normalize a list of personality profiles to ensure each only contains id, name, description.
    Filters out invalid profiles.

    Args:
        profiles: List of personality profile dictionaries

    Returns:
        List of normalized profile dictionaries
    """
    if not isinstance(profiles, list):
        logger.warning(f"Profiles is not a list: {type(profiles)}, value: {profiles}")
        return []

    logger.debug(f"Normalizing {len(profiles)} profile(s)")
    normalized = []
    filtered_count = 0
    for idx, profile in enumerate(profiles):
        logger.debug(f"Processing profile {idx}: {profile}")
        normalized_profile = normalize_personality_profile(profile)
        if normalized_profile and normalized_profile.get("id") and normalized_profile.get("name"):
            normalized.append(normalized_profile)
            logger.debug(f"Profile {idx} normalized successfully: {normalized_profile}")
        else:
            filtered_count += 1
            logger.warning(
                f"Filtered out profile at index {idx}: missing id or name. "
                f"Original profile: {profile}, normalized: {normalized_profile}"
            )

    if filtered_count > 0:
        logger.warning(
            f"Filtered out {filtered_count} invalid profile(s) out of {len(profiles)} total. "
            f"Returning {len(normalized)} valid profile(s)."
        )
    else:
        logger.info(f"Successfully normalized all {len(profiles)} profile(s)")

    return normalized


def user_doc_to_response(user_doc: dict) -> UserResponse:
    """
    Convert MongoDB user document to UserResponse

    Args:
        user_doc: MongoDB user document

    Returns:
        UserResponse object
    """
    user_id = str(user_doc.get("_id", "unknown"))
    
    # Normalize preferences to ensure personalityProfiles have correct structure
    # Create a copy to avoid mutating the original document
    preferences = user_doc.get("preferences")
    
    # Log raw preferences structure for debugging
    logger.info(
        f"User {user_id}: Processing preferences. Type: {type(preferences)}, "
        f"is None: {preferences is None}, keys: {list(preferences.keys()) if isinstance(preferences, dict) else 'N/A'}"
    )
    
    if preferences and isinstance(preferences, dict):
        # Deep copy preferences to avoid mutating original
        preferences = copy.deepcopy(preferences)
        
        # Ensure appSettings exists
        if "appSettings" not in preferences:
            logger.warning(f"User {user_id}: appSettings missing from preferences. Creating it.")
            preferences["appSettings"] = {}
        
        app_settings = preferences.get("appSettings", {})
        logger.info(
            f"User {user_id}: appSettings type: {type(app_settings)}, "
            f"is None: {app_settings is None}, keys: {list(app_settings.keys()) if isinstance(app_settings, dict) else 'N/A'}"
        )
        
        if isinstance(app_settings, dict):
            # Always ensure personalityProfiles exists and is normalized
            # Get existing profiles or default to empty list
            existing_profiles = app_settings.get("personalityProfiles")
            
            # Log detailed info about what we found
            logger.info(
                f"User {user_id}: personalityProfiles from DB - "
                f"type: {type(existing_profiles)}, "
                f"is None: {existing_profiles is None}, "
                f"value: {existing_profiles}"
            )
            
            if existing_profiles is None:
                logger.warning(
                    f"User {user_id}: personalityProfiles is None in database. "
                    f"appSettings keys: {list(app_settings.keys())}"
                )
                existing_profiles = []
            elif not isinstance(existing_profiles, list):
                logger.warning(
                    f"User {user_id}: personalityProfiles is not a list (type: {type(existing_profiles)}). "
                    f"Converting to list."
                )
                existing_profiles = []
            
            # Log each profile before normalization
            if existing_profiles:
                logger.info(
                    f"User {user_id}: Found {len(existing_profiles)} profile(s) before normalization. "
                    f"Sample profile structure: {existing_profiles[0] if existing_profiles else 'N/A'}"
                )
            
            # Normalize personalityProfiles to ensure structure is {"id", "name", "description"} only
            # This will return an empty list if profiles is None or invalid
            normalized_profiles = normalize_personality_profiles(existing_profiles)
            
            # Log after normalization
            logger.info(
                f"User {user_id}: After normalization - {len(normalized_profiles)} profile(s). "
                f"Normalized profiles: {normalized_profiles}"
            )
            
            # Always set personalityProfiles (even if empty) to ensure it's present in response
            app_settings["personalityProfiles"] = normalized_profiles
            
            # Verify it's set correctly
            logger.info(
                f"User {user_id}: Final appSettings['personalityProfiles'] = {app_settings.get('personalityProfiles')}"
            )
        else:
            logger.warning(
                f"User {user_id}: appSettings is not a dict (type: {type(app_settings)}). "
                f"Initializing appSettings with empty personalityProfiles."
            )
            preferences["appSettings"] = {"personalityProfiles": []}
    else:
        # If preferences is None or not a dict, initialize it with empty personalityProfiles
        logger.warning(
            f"User {user_id}: preferences is {type(preferences)}. "
            f"Initializing with empty personalityProfiles."
        )
        preferences = {
            "appSettings": {
                "personalityProfiles": []
            }
        }

    return UserResponse(
        id=str(user_doc["_id"]),
        name=user_doc.get("name", ""),
        email=user_doc.get("email", ""),
        isActive=user_doc.get("isActive", True),
        isEmailVerified=user_doc.get("isEmailVerified", False),
        roles=user_doc.get("roles", ["user"]),
        phone=user_doc.get("phone"),
        address=user_doc.get("address"),
        preferences=preferences,
        avatarUrl=user_doc.get("avatarUrl"),
        dateCreated=user_doc.get("dateCreated"),
        dateUpdated=user_doc.get("dateUpdated"),
        lastLogin=user_doc.get("lastLogin"),
        llm_counts=user_doc.get("llm_counts"),
        last_llm_used=user_doc.get("last_llm_used"),
        generation_credits=user_doc.get("generation_credits"),
        max_credits=user_doc.get("max_credits"),
        # Subscription fields
        subscriptionId=user_doc.get("subscriptionId"),
        subscriptionStatus=user_doc.get("subscriptionStatus", "free"),
        subscriptionPlan=user_doc.get("subscriptionPlan", "free"),
        subscriptionCurrentPeriodEnd=user_doc.get("subscriptionCurrentPeriodEnd"),
        lastPaymentDate=user_doc.get("lastPaymentDate"),
        stripeCustomerId=user_doc.get("stripeCustomerId"),
    )
