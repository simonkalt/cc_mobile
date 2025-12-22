"""
User service - business logic for user operations
"""
import logging
from datetime import datetime
from typing import Dict
from bson import ObjectId
from fastapi import HTTPException, status

from app.models.user import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
)
from app.db.mongodb import get_collection, is_connected
from app.utils.password import hash_password, verify_password
from app.utils.user_helpers import (
    user_doc_to_response,
    normalize_personality_profiles,
    USERS_COLLECTION,
)

logger = logging.getLogger(__name__)


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
    
    # Hash password
    hashed_password_str = hash_password(user_data.password)
    
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
        "preferences": user_data.preferences or {
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
                "personalityProfiles": [],
                "selectedModel": None,
                "lastResumeUsed": None,
                "last_personality_profile_used": None
            },
            # Form field defaults - ensure all form fields start empty for new users
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
    
    logger.debug(f"Querying MongoDB for user_id: {user_id} (ObjectId: {user_id_obj})")
    user = collection.find_one({"_id": user_id_obj})
    if not user:
        # Log collection info for debugging
        total_users = collection.count_documents({})
        logger.warning(f"User not found: {user_id}. Total users in collection: {total_users}")
        # Try to find any user to verify collection access
        sample_user = collection.find_one({})
        if sample_user:
            logger.debug(f"Sample user in collection: {sample_user.get('_id')}, email: {sample_user.get('email')}")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
    logger.debug(f"Found user: {user.get('email')} (ID: {user.get('_id')})")
    return user_doc_to_response(user)


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
                    if "personalityProfiles" in app_settings:
                        personality_profiles = app_settings["personalityProfiles"]
                        if isinstance(personality_profiles, list):
                            normalized_profiles = normalize_personality_profiles(personality_profiles)
                            if len(normalized_profiles) == 0:
                                # Get current user to check existing profiles
                                try:
                                    current_user = collection.find_one({"_id": user_id_obj})
                                    if current_user:
                                        existing_profiles = current_user.get("preferences", {}).get("appSettings", {}).get("personalityProfiles", [])
                                        if existing_profiles and len(existing_profiles) > 0:
                                            logger.warning(
                                                f"⚠️ WARNING: Updating personalityProfiles to empty array for user {user_id}. "
                                                f"This will DELETE {len(existing_profiles)} existing profile(s)"
                                            )
                                except Exception as e:
                                    logger.warning(f"Could not check existing profiles before update: {e}")
                            
                            if len(normalized_profiles) > 0:
                                update_doc["preferences.appSettings.personalityProfiles"] = normalized_profiles
                                logger.info(f"Updated personalityProfiles for user {user_id}: {len(normalized_profiles)} profile(s)")
                            else:
                                if len(personality_profiles) == 0:
                                    update_doc["preferences.appSettings.personalityProfiles"] = []
                                    logger.info(f"Cleared personalityProfiles for user {user_id}")
                    # Update selectedModel
                    if "selectedModel" in app_settings:
                        update_doc["preferences.appSettings.selectedModel"] = app_settings["selectedModel"]
                    # Update lastResumeUsed
                    if "lastResumeUsed" in app_settings:
                        update_doc["preferences.appSettings.lastResumeUsed"] = app_settings["lastResumeUsed"]
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
    return UserLoginResponse(
        success=True,
        user=user_doc_to_response(user),
        message="Login successful"
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

