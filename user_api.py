"""
User API endpoints for registration and CRUD operations
"""
import bcrypt
from fastapi import HTTPException, status
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson import ObjectId
from mongodb_client import get_collection, is_connected
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


def user_doc_to_response(user_doc: dict) -> UserResponse:
    """Convert MongoDB user document to UserResponse"""
    return UserResponse(
        id=str(user_doc["_id"]),
        name=user_doc.get("name", ""),
        email=user_doc.get("email", ""),
        isActive=user_doc.get("isActive", True),
        isEmailVerified=user_doc.get("isEmailVerified", False),
        roles=user_doc.get("roles", ["user"]),
        phone=user_doc.get("phone"),
        address=user_doc.get("address"),
        preferences=user_doc.get("preferences"),
        avatarUrl=user_doc.get("avatarUrl"),
        dateCreated=user_doc.get("dateCreated"),
        dateUpdated=user_doc.get("dateUpdated"),
        lastLogin=user_doc.get("lastLogin")
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
                    }
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
                            for prop_key in ["fontFamily", "fontSize", "lineHeight"]:
                                if prop_key in print_props:
                                    update_doc[f"preferences.appSettings.printProperties.{prop_key}"] = print_props[prop_key]
                            # Update pageSize
                            if "pageSize" in print_props:
                                for size_key, size_value in print_props["pageSize"].items():
                                    update_doc[f"preferences.appSettings.printProperties.pageSize.{size_key}"] = size_value
                    # Update personalityProfiles
                    if "personalityProfiles" in app_settings:
                        update_doc["preferences.appSettings.personalityProfiles"] = app_settings["personalityProfiles"]
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
        result = collection.update_one(
            {"_id": user_id_obj},
            {
                "$inc": {f"llm_counts.{llm_name}": 1},
                "$set": {"dateUpdated": datetime.utcnow()}
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

