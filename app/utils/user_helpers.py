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
ACCOUNT_DELETION_REQUESTS_COLLECTION = "account_deletion_requests"

DEFAULT_MAX_CREDITS = 10


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
        logger.debug(f"Profile is not a dict: {type(profile)}")
        return None
    
    profile_id = profile.get("id", "")
    profile_name = profile.get("name", "")
    
    # Log if profile is missing required fields
    if not profile_id or not profile_name:
        logger.debug(f"Profile missing required fields - id: {bool(profile_id)}, name: {bool(profile_name)}, profile keys: {list(profile.keys())}")
    
    return {
        "id": profile_id,
        "name": profile_name,
        "description": profile.get("description", "")
    }


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
        logger.debug(f"Profiles is not a list: {type(profiles)}")
        return []
    
    normalized = []
    filtered_count = 0
    for idx, profile in enumerate(profiles):
        normalized_profile = normalize_personality_profile(profile)
        if normalized_profile and normalized_profile.get("id") and normalized_profile.get("name"):
            normalized.append(normalized_profile)
        else:
            filtered_count += 1
            logger.debug(f"Filtered out profile at index {idx}: missing id or name")
    
    if filtered_count > 0:
        logger.info(f"Filtered out {filtered_count} invalid profile(s) out of {len(profiles)} total")
    
    return normalized


def user_doc_to_response(user_doc: dict) -> UserResponse:
    """
    Convert MongoDB user document to UserResponse
    
    Args:
        user_doc: MongoDB user document
        
    Returns:
        UserResponse object
    """
    # Normalize preferences to ensure personalityProfiles have correct structure
    # Create a copy to avoid mutating the original document
    preferences = user_doc.get("preferences")
    if preferences and isinstance(preferences, dict):
        # Deep copy preferences to avoid mutating original
        preferences = copy.deepcopy(preferences)
        app_settings = preferences.get("appSettings", {})
        if isinstance(app_settings, dict) and "personalityProfiles" in app_settings:
            # Normalize personalityProfiles to ensure structure is {"id", "name", "description"} only
            app_settings["personalityProfiles"] = normalize_personality_profiles(
                app_settings.get("personalityProfiles", [])
            )
        # Backward compatibility: normalize legacy snake_case last resume key for clients.
        if isinstance(app_settings, dict):
            if "lastResumeUsed" not in app_settings and "last_resume_used" in app_settings:
                app_settings["lastResumeUsed"] = app_settings.get("last_resume_used")
    
    subscription_status = str(user_doc.get("subscriptionStatus", "free") or "free").lower()
    max_credits_raw = user_doc.get("max_credits", DEFAULT_MAX_CREDITS)
    try:
        max_credits = max(0, int(max_credits_raw))
    except (TypeError, ValueError):
        max_credits = DEFAULT_MAX_CREDITS

    generation_credits_raw = user_doc.get("generation_credits")
    if generation_credits_raw is None:
        # Free-tier users must always receive explicit credit values.
        generation_credits = max_credits if subscription_status == "free" else 0
    else:
        try:
            generation_credits = max(0, int(generation_credits_raw))
        except (TypeError, ValueError):
            generation_credits = max_credits if subscription_status == "free" else 0

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
        generation_credits=generation_credits,
        max_credits=max_credits,
        SMSOpt=user_doc.get("SMSOpt"),
        SMSOptDate=user_doc.get("SMSOptDate"),
        subscriptionStatus=user_doc.get("subscriptionStatus"),
        subscriptionPlan=user_doc.get("subscriptionPlan"),
        subscriptionCurrentPeriodEnd=user_doc.get("subscriptionCurrentPeriodEnd"),
        super_user=user_doc.get("super_user", False),
        archived=user_doc.get("archived", False),
        account_deletion_pending=user_doc.get("account_deletion_pending", False),
    )

