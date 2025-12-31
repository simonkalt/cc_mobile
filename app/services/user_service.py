"""
User service - business logic for user operations
"""
import logging
import time
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
    
    # Extract preferences if provided
    preferences = user_data.preferences or {}
    app_settings = preferences.get("appSettings", {})
    personality_profiles = app_settings.get("personalityProfiles", [])
    
    # If no personality profiles provided or empty, create default profile
    if not personality_profiles or len(personality_profiles) == 0:
        default_profile = {
            "id": str(int(time.time() * 1000)),  # Current timestamp in milliseconds
            "name": "Professional",
            "description": "I am trying to garner interest in my talents and experience so that I stand out and make easy for the recruiter to hire me. Be very professional."
        }
        personality_profiles = [default_profile]
        logger.info(f"Created default personality profile for new user: {user_data.email}")
    
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
        # Initialize free subscription for new users
        "subscriptionId": None,
        "subscriptionStatus": "free",
        "subscriptionPlan": "free",
        "subscriptionCurrentPeriodEnd": None,
        "lastPaymentDate": None,
        "stripeCustomerId": None,
        "generation_credits": 10,  # Default to 10 free generation credits for new users
        "max_credits": 10,  # Fixed maximum credits for free tier
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


def create_user_from_registration_data(registration_data: dict, is_email_verified: bool = False) -> UserResponse:
    """
    Create a user from registration data (used when completing registration from Redis)
    
    Args:
        registration_data: Dictionary containing user registration data
            - name: User's name
            - email: User's email
            - phone: User's phone (optional)
            - password: Already hashed password
            - preferences: User preferences (optional)
        is_email_verified: Whether email is already verified (default: False)
        
    Returns:
        UserResponse object
        
    Raises:
        HTTPException: If user creation fails
    """
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
    existing_user = collection.find_one({"email": registration_data["email"]})
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="User with this email already exists"
        )
    
    # Extract preferences if provided
    preferences = registration_data.get("preferences", {})
    app_settings = preferences.get("appSettings", {})
    personality_profiles = app_settings.get("personalityProfiles", [])
    
    # If no personality profiles provided or empty, create default profile
    if not personality_profiles or len(personality_profiles) == 0:
        default_profile = {
            "id": str(int(time.time() * 1000)),
            "name": "Professional",
            "description": "I am trying to garner interest in my talents and experience so that I stand out and make easy for the recruiter to hire me. Be very professional."
        }
        personality_profiles = [default_profile]
        logger.info(f"Created default personality profile for new user: {registration_data['email']}")
    
    # Ensure appSettings exists in preferences
    if "appSettings" not in preferences:
        preferences["appSettings"] = {}
    
    # Set the personality profiles (either provided or default)
    preferences["appSettings"]["personalityProfiles"] = personality_profiles
    
    # Merge provided preferences with defaults
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
    # Ensure personalityProfiles is set
    final_preferences["appSettings"]["personalityProfiles"] = personality_profiles
    
    # Build user document
    user_doc = {
        "name": registration_data["name"],
        "email": registration_data["email"],
        "hashedPassword": registration_data["password"],  # Already hashed
        "isActive": True,
        "isEmailVerified": is_email_verified,
        "roles": ["user"],
        "failedLoginAttempts": 0,
        "lastLogin": None,
        "passwordChangedAt": None,
        "avatarUrl": None,
        "phone": registration_data.get("phone"),
        "address": registration_data.get("address") or {
            "street": None,
            "city": None,
            "state": None,
            "zip": None,
            "country": None
        },
        "dateCreated": datetime.utcnow(),
        "dateUpdated": datetime.utcnow(),
        "llm_counts": {},
        "last_llm_used": None,
        "preferences": final_preferences,
        # Initialize free subscription for new users
        "subscriptionId": None,
        "subscriptionStatus": "free",
        "subscriptionPlan": "free",
        "subscriptionCurrentPeriodEnd": None,
        "lastPaymentDate": None,
        "stripeCustomerId": None,
        "generation_credits": 10,  # Default to 10 free generation credits for new users
        "max_credits": 10,  # Fixed maximum credits for free tier
    }
    
    try:
        result = collection.insert_one(user_doc)
        user_doc["_id"] = result.inserted_id
        logger.info(f"User created from registration data: {registration_data['email']} (ID: {result.inserted_id})")
        return user_doc_to_response(user_doc)
    except Exception as e:
        logger.error(f"Error creating user from registration data: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create user: {str(e)}"
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
                        logger.info(f"personalityProfiles provided in update request for user {user_id}: type={type(personality_profiles)}, value={personality_profiles}")
                        
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


def decrement_generation_credits(user_id: str) -> bool:
    """
    Decrement generation_credits for a user if they have no active subscription.
    Only decrements if credits > 0.
    
    Args:
        user_id: User ID
        
    Returns:
        True if credits were decremented, False otherwise (including if user has subscription)
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
        
        # Check subscription status - only decrement if user has no subscription (status is "free")
        subscription_status = user.get("subscriptionStatus", "free")
        if subscription_status != "free":
            logger.debug(f"User {user_id} has subscription status '{subscription_status}'. Skipping credit decrement.")
            return False
        
        # Get current credits (default to 0 if not set)
        current_credits = user.get("generation_credits", 0)
        
        # Only decrement if credits > 0
        if current_credits <= 0:
            logger.debug(f"User {user_id} has no generation credits ({current_credits}). Cannot decrement.")
            return False
        
        # Decrement credits
        result = collection.update_one(
            {"_id": user_id_obj},
            {
                "$inc": {"generation_credits": -1},
                "$set": {
                    "dateUpdated": datetime.utcnow()
                }
            }
        )
        
        if result.matched_count > 0:
            updated_user = collection.find_one({"_id": user_id_obj})
            if updated_user:
                new_credits = updated_user.get("generation_credits", 0)
                logger.info(f"Decremented generation credits for user {user_id}: {current_credits} -> {new_credits}")
            return True
        else:
            logger.warning(f"User {user_id} not found. Cannot decrement generation credits.")
            return False
            
    except Exception as e:
        logger.error(f"Error decrementing generation credits: {e}")
        return False
