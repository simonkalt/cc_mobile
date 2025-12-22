"""
Personality profiles API routes
"""
import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, status

from app.services.user_service import get_user_by_id, get_user_by_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["personality"])


@router.get("/personality-profiles")
def get_personality_profiles(
    user_id: Optional[str] = None, user_email: Optional[str] = None
):
    """JSON API endpoint to get available personality profiles for the UI from user's preferences"""
    if not user_id and not user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id or user_email is required",
        )

    try:
        user = None
        if user_id:
            user = get_user_by_id(user_id)
        elif user_email:
            user = get_user_by_email(user_email)

        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )

        # Get user's custom personality profiles
        # Note: user_doc_to_response already normalizes personalityProfiles to {"id", "name", "description"} structure
        user_prefs = user.preferences if user.preferences else {}
        logger.debug(f"User preferences type: {type(user_prefs)}, keys: {list(user_prefs.keys()) if isinstance(user_prefs, dict) else 'N/A'}")
        
        if isinstance(user_prefs, dict):
            app_settings = user_prefs.get("appSettings", {})
            logger.debug(f"App settings type: {type(app_settings)}, keys: {list(app_settings.keys()) if isinstance(app_settings, dict) else 'N/A'}")
            
            if isinstance(app_settings, dict):
                custom_profiles = app_settings.get("personalityProfiles", [])
                logger.info(f"Found {len(custom_profiles) if isinstance(custom_profiles, list) else 0} personality profile(s) in database")
                
                # Ensure profiles are normalized (should already be normalized, but verify)
                if custom_profiles:
                    if not isinstance(custom_profiles, list):
                        logger.warning(f"personalityProfiles is not a list: {type(custom_profiles)}")
                        custom_profiles = []
                    else:
                        normalized_profiles = []
                        for idx, profile in enumerate(custom_profiles):
                            if (
                                isinstance(profile, dict)
                                and profile.get("id")
                                and profile.get("name")
                            ):
                                # Extract only id, name, description
                                normalized_profiles.append(
                                    {
                                        "id": profile.get("id", ""),
                                        "name": profile.get("name", ""),
                                        "description": profile.get("description", ""),
                                    }
                                )
                            else:
                                logger.debug(f"Profile at index {idx} is invalid: {profile}")
                        custom_profiles = normalized_profiles
                        logger.info(f"After normalization: {len(custom_profiles)} valid profile(s)")
            else:
                logger.warning(f"appSettings is not a dict: {type(app_settings)}")
                custom_profiles = []
        else:
            logger.warning(f"preferences is not a dict: {type(user_prefs)}")
            custom_profiles = []

        # Format profiles for the UI
        # Structure is already normalized to {"id", "name", "description"}
        profiles = []
        for profile in custom_profiles:
            if isinstance(profile, dict) and profile.get("id") and profile.get("name"):
                # Format for UI (add label and value for compatibility)
                profiles.append(
                    {
                        "id": profile.get("id", ""),
                        "name": profile.get("name", "Unknown"),
                        "description": profile.get("description", ""),
                        "label": profile.get("name", "Unknown"),  # For UI compatibility
                        "value": profile.get("name", "Unknown"),  # For UI compatibility
                    }
                )

        return {"profiles": profiles}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving personality profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving personality profiles: {str(e)}",
        )

