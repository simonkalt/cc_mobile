"""
User API endpoints for registration and CRUD operations
"""
import bcrypt
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from app.db.mongodb import get_collection, is_connected
import logging

logger = logging.getLogger(__name__)

USERS_COLLECTION = "users"


# Nested Models for Preferences
class PrintMargins(BaseModel):
    top: Optional[float] = 1.0
    right: Optional[float] = 0.75
    bottom: Optional[float] = 0.25
    left: Optional[float] = 0.75


class PageSize(BaseModel):
    width: Optional[float] = 8.5
    height: Optional[float] = 11.0


class PrintProperties(BaseModel):
    margins: Optional[PrintMargins] = None
    fontFamily: Optional[str] = "Georgia"
    fontSize: Optional[float] = 11.0
    lineHeight: Optional[float] = 1.15
    pageSize: Optional[PageSize] = None
    useDefaultFonts: Optional[bool] = False


class PersonalityProfile(BaseModel):
    id: str
    name: str
    description: str


class AppSettings(BaseModel):
    printProperties: Optional[PrintProperties] = None
    personalityProfiles: Optional[List[PersonalityProfile]] = None
    selectedModel: Optional[str] = None
    lastResumeUsed: Optional[str] = None
    last_personality_profile_used: Optional[str] = None


class UserPreferences(BaseModel):
    newsletterOptIn: Optional[bool] = False
    theme: Optional[str] = "light"
    appSettings: Optional[AppSettings] = None


# Pydantic Models for Request/Response
class UserRegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone: Optional[str] = None
    address: Optional[dict] = None
    preferences: Optional[dict] = None


class UserUpdateRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    isActive: Optional[bool] = None
    isEmailVerified: Optional[bool] = None
    roles: Optional[List[str]] = None
    address: Optional[dict] = None
    preferences: Optional[dict] = None
    avatarUrl: Optional[str] = None
    last_llm_used: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    name: str
    email: str
    isActive: bool
    isEmailVerified: bool
    roles: List[str]
    phone: Optional[str] = None
    address: Optional[dict] = None
    preferences: Optional[dict] = None
    avatarUrl: Optional[str] = None
    dateCreated: datetime
    dateUpdated: datetime
    lastLogin: Optional[datetime] = None
    llm_counts: Optional[dict] = None
    last_llm_used: Optional[str] = None

    class Config:
        from_attributes = True


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserLoginResponse(BaseModel):
    success: bool
    user: Optional[UserResponse] = None
    message: str


# Helper Functions
def hash_password(password: str) -> str:
    """Hash a password using bcrypt"""
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    return hashed.decode('utf-8')


def verify_password(password: str, hashed_password: str) -> bool:
    """Verify a password against a hash"""
    return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))


def normalize_personality_profile(profile: dict) -> dict:
    """
    Normalize a personality profile to ensure it only contains id, name, description.
    Returns a dict with only these three fields.
    """
    if not isinstance(profile, dict):
        return None
    
    return {
        "id": profile.get("id", ""),
        "name": profile.get("name", ""),
        "description": profile.get("description", "")
    }


def normalize_personality_profiles(profiles: list) -> list:
    """
    Normalize a list of personality profiles to ensure each only contains id, name, description.
    Filters out invalid profiles.
    """
    if not isinstance(profiles, list):
        return []
    
    normalized = []
    for profile in profiles:
        normalized_profile = normalize_personality_profile(profile)
        if normalized_profile and normalized_profile.get("id") and normalized_profile.get("name"):
            normalized.append(normalized_profile)
    
    return normalized


def user_doc_to_response(user_doc: dict) -> UserResponse:
    """Convert MongoDB user document to UserResponse"""
    # Normalize preferences to ensure personalityProfiles have correct structure
    # Create a copy to avoid mutating the original document
    import copy
    import logging
    logger = logging.getLogger(__name__)
    
    preferences = user_doc.get("preferences")
    if preferences and isinstance(preferences, dict):
        # Deep copy preferences to avoid mutating original
        preferences = copy.deepcopy(preferences)
        
        # Ensure appSettings exists
        if "appSettings" not in preferences:
            preferences["appSettings"] = {}
        
        app_settings = preferences.get("appSettings", {})
        if isinstance(app_settings, dict):
            # Always ensure personalityProfiles exists and is normalized
            # Get existing profiles or default to empty list
            existing_profiles = app_settings.get("personalityProfiles", [])
            
            # Log for debugging (especially on Render)
            if not existing_profiles:
                logger.debug(
                    f"User {user_doc.get('_id')}: No personalityProfiles found in appSettings. "
                    f"appSettings keys: {list(app_settings.keys()) if isinstance(app_settings, dict) else 'N/A'}"
                )
            else:
                logger.debug(
                    f"User {user_doc.get('_id')}: Found {len(existing_profiles) if isinstance(existing_profiles, list) else 'N/A'} personality profile(s)"
                )
            
            # Normalize personalityProfiles to ensure structure is {"id", "name", "description"} only
            # This will return an empty list if profiles is None or invalid
            normalized_profiles = normalize_personality_profiles(
                existing_profiles if isinstance(existing_profiles, list) else []
            )
            
            # Always set personalityProfiles (even if empty) to ensure it's present in response
            app_settings["personalityProfiles"] = normalized_profiles
            
            logger.debug(
                f"User {user_doc.get('_id')}: Returning {len(normalized_profiles)} normalized personality profile(s)"
            )
        else:
            logger.warning(
                f"User {user_doc.get('_id')}: appSettings is not a dict (type: {type(app_settings)}). "
                f"Initializing appSettings with empty personalityProfiles."
            )
            preferences["appSettings"] = {"personalityProfiles": []}
    else:
        # If preferences is None or not a dict, initialize it with empty personalityProfiles
        logger.debug(
            f"User {user_doc.get('_id')}: preferences is {type(preferences)}. "
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
        last_llm_used=user_doc.get("last_llm_used")
    )


# API Functions
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
    hashed_password = hash_password(user_data.password)
    
    # Build user document
    user_doc = {
        "name": user_data.name,
        "email": user_data.email,
        "hashedPassword": hashed_password,
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
    
    user = collection.find_one({"_id": user_id_obj})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found"
        )
    
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
        # If preferences is a dict, we can merge it or replace it
        # For nested updates like appSettings, we'll use dot notation
        if isinstance(updates.preferences, dict):
            # Check if this is a partial update (has appSettings nested structure)
            if "appSettings" in updates.preferences:
                # Handle nested appSettings updates using dot notation
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
                    # Only update if explicitly provided and is a valid list
                    # IMPORTANT: Only update if personalityProfiles is explicitly in the request
                    # This prevents accidental deletion when updating other appSettings fields
                    if "personalityProfiles" in app_settings:
                        personality_profiles = app_settings["personalityProfiles"]
                        # Validate that it's a list
                        if isinstance(personality_profiles, list):
                            # Normalize and validate each profile to ensure correct structure: {"id", "name", "description"}
                            normalized_profiles = []
                            for idx, profile in enumerate(personality_profiles):
                                if isinstance(profile, dict):
                                    # Extract only id, name, description fields (ignore any extra fields)
                                    normalized_profile = {
                                        "id": profile.get("id", ""),
                                        "name": profile.get("name", ""),
                                        "description": profile.get("description", "")
                                    }
                                    # Validate required fields
                                    if not normalized_profile["id"]:
                                        logger.warning(f"Profile at index {idx} missing 'id' field, skipping")
                                        continue
                                    if not normalized_profile["name"]:
                                        logger.warning(f"Profile at index {idx} missing 'name' field, skipping")
                                        continue
                                    if not normalized_profile["description"]:
                                        logger.warning(f"Profile at index {idx} missing 'description' field, using empty string")
                                    normalized_profiles.append(normalized_profile)
                                else:
                                    logger.warning(f"Profile at index {idx} is not a dict, skipping: {type(profile)}")
                            
                            # Check if user has existing profiles before clearing
                            if len(normalized_profiles) == 0:
                                # Get current user to check existing profiles
                                try:
                                    current_user = collection.find_one({"_id": user_id_obj})
                                    if current_user:
                                        existing_profiles = current_user.get("preferences", {}).get("appSettings", {}).get("personalityProfiles", [])
                                        if existing_profiles and len(existing_profiles) > 0:
                                            logger.warning(
                                                f"⚠️ WARNING: Updating personalityProfiles to empty array for user {user_id}. "
                                                f"This will DELETE {len(existing_profiles)} existing profile(s): {[p.get('name', 'Unknown') for p in existing_profiles if isinstance(p, dict)]}"
                                            )
                                        else:
                                            logger.info(f"Setting personalityProfiles to empty array for user {user_id} (no existing profiles to delete)")
                                except Exception as e:
                                    logger.warning(f"Could not check existing profiles before update: {e}")
                            
                            # Save normalized profiles (only id, name, description)
                            if len(normalized_profiles) > 0:
                                update_doc["preferences.appSettings.personalityProfiles"] = normalized_profiles
                                logger.info(f"Updated personalityProfiles for user {user_id}: {len(normalized_profiles)} profile(s) saved with structure {{id, name, description}}")
                            else:
                                # If all profiles were invalid, only update if explicitly clearing
                                if len(personality_profiles) == 0:
                                    update_doc["preferences.appSettings.personalityProfiles"] = []
                                    logger.info(f"Cleared personalityProfiles for user {user_id}")
                                else:
                                    logger.warning(f"All personalityProfiles were invalid for user {user_id}. Not updating to preserve existing profiles.")
                        elif personality_profiles is None:
                            # If explicitly set to None, don't update (preserve existing)
                            logger.warning(f"personalityProfiles set to None in update request for user {user_id}. Ignoring to preserve existing profiles.")
                        else:
                            # Invalid type - log error but don't update
                            logger.error(f"Invalid personalityProfiles type for user {user_id}: {type(personality_profiles)}. Expected list. Ignoring update.")
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



def increment_llm_usage_count(user_id: str, llm_name: str) -> bool:
    """
    Increment the usage count for a specific LLM in the user's record.
    If the LLM doesn't exist in llm_counts, add it and set count to 1.
    Also updates the last_llm_used field to track the most recently used LLM.
    Returns True if successful, False otherwise.
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
        # If the field doesn't exist, MongoDB will create it with value 1
        # Also update last_llm_used field to track the most recently used LLM
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
            # Verify the increment worked (check if field was created or incremented)
            updated_user = collection.find_one({"_id": user_id_obj})
            if updated_user and "llm_counts" in updated_user:
                count = updated_user["llm_counts"].get(llm_name, 0)
                if count == 1:
                    logger.info(f"Initialized LLM count for {llm_name} to 1 for user {user_id}")
                else:
                    logger.debug(f"Incremented LLM count for {llm_name} to {count} for user {user_id}")
                # Log last_llm_used update
                if updated_user.get("last_llm_used") == llm_name:
                    logger.debug(f"Updated last_llm_used to {llm_name} for user {user_id}")
            return True
        else:
            logger.warning(f"User {user_id} not found. Cannot update LLM usage count.")
            return False
            
    except Exception as e:
        logger.error(f"Error incrementing LLM usage count: {e}")
        return False

def delete_user(user_id: str) -> dict:
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
    hashed_password = user.get("hashedPassword", "")
    if not verify_password(login_data.password, hashed_password):
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
    
    # Ensure user's S3 folder exists (create if it doesn't)
    user_id = str(user["_id"])
    try:
        # Import the S3 function from main module
        # We'll handle this in the endpoint to avoid circular imports
        pass
    except Exception as e:
        logger.warning(f"Could not ensure S3 folder during login: {e}")
    
    logger.info(f"User logged in: {login_data.email}")
    return UserLoginResponse(
        success=True,
        user=user_doc_to_response(user),
        message="Login successful"
    )

