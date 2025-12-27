# Default Personality Profile for New Users

## Overview

When a new user registers, the server should automatically create a default personality profile if no personality profiles are provided in the registration request. This ensures all users have at least one personality profile to use immediately after registration.

## Implementation Requirements

### When to Create Default Profile

The server should create the default profile when:
1. A new user is registered via `POST /api/users/register`
2. The request does NOT include `personalityProfiles` in `preferences.appSettings`, OR
3. The `personalityProfiles` array is empty or null

### Default Profile Structure

The server should create a single default personality profile with the following structure:

```json
{
  "id": "<timestamp_as_string>",
  "name": "Professional",
  "description": "I am trying to garner interest in my talents and experience so that I stand out and make easy for the recruiter to hire me. Be very professional."
}
```

### ID Generation

- The `id` field should be a unique string identifier
- Recommended format: timestamp as string (e.g., `"1735267200000"` or `Date.now().toString()`)
- Must be unique per user (can use timestamp + random suffix if needed)

### Implementation Location

This should be implemented in the user registration endpoint handler, after validating the registration data but before saving the user to the database.

## Example Implementation (Python/FastAPI)

```python
from datetime import datetime
import time

def register_user(user_data: dict):
    # ... existing registration validation ...
    
    # Extract preferences if provided
    preferences = user_data.get("preferences", {})
    app_settings = preferences.get("appSettings", {})
    personality_profiles = app_settings.get("personalityProfiles", [])
    
    # If no personality profiles provided or empty, create default
    if not personality_profiles or len(personality_profiles) == 0:
        default_profile = {
            "id": str(int(time.time() * 1000)),  # Current timestamp in milliseconds
            "name": "Professional",
            "description": "I am trying to garner interest in my talents and experience so that I stand out and make easy for the recruiter to hire me. Be very professional."
        }
        personality_profiles = [default_profile]
    
    # Ensure appSettings exists
    if "appSettings" not in preferences:
        preferences["appSettings"] = {}
    
    # Set the personality profiles (either provided or default)
    preferences["appSettings"]["personalityProfiles"] = personality_profiles
    
    # Continue with user creation...
    user_data["preferences"] = preferences
    # ... save user to database ...
```

## Example Implementation (Node.js/Express)

```javascript
async function registerUser(userData) {
  // ... existing registration validation ...
  
  // Extract preferences if provided
  const preferences = userData.preferences || {};
  const appSettings = preferences.appSettings || {};
  let personalityProfiles = appSettings.personalityProfiles || [];
  
  // If no personality profiles provided or empty, create default
  if (!personalityProfiles || personalityProfiles.length === 0) {
    const defaultProfile = {
      id: Date.now().toString(), // Current timestamp in milliseconds
      name: "Professional",
      description: "I am trying to garner interest in my talents and experience so that I stand out and make easy for the recruiter to hire me. Be very professional."
    };
    personalityProfiles = [defaultProfile];
  }
  
  // Ensure appSettings exists
  if (!preferences.appSettings) {
    preferences.appSettings = {};
  }
  
  // Set the personality profiles (either provided or default)
  preferences.appSettings.personalityProfiles = personalityProfiles;
  
  // Continue with user creation...
  userData.preferences = preferences;
  // ... save user to database ...
}
```

## Behavior Rules

1. **Only create default if missing**: Only create the default profile if the user doesn't provide any personality profiles
2. **Don't override provided profiles**: If the client sends personality profiles, use those instead
3. **Single default profile**: Only create ONE default profile ("Professional")
4. **Exact description**: Use the exact description text provided above

## Testing

### Test Case 1: New User with No Profiles
**Request:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "password123",
  "preferences": {
    "appSettings": {}
  }
}
```

**Expected Result:**
User should be created with:
```json
{
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        {
          "id": "1735267200000",
          "name": "Professional",
          "description": "I am trying to garner interest in my talents and experience so that I stand out and make easy for the recruiter to hire me. Be very professional."
        }
      ]
    }
  }
}
```

### Test Case 2: New User with Existing Profiles
**Request:**
```json
{
  "name": "Jane Doe",
  "email": "jane@example.com",
  "password": "password123",
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        {
          "id": "custom123",
          "name": "Creative",
          "description": "Be creative and artistic"
        }
      ]
    }
  }
}
```

**Expected Result:**
User should be created with the provided profile (no default added):
```json
{
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        {
          "id": "custom123",
          "name": "Creative",
          "description": "Be creative and artistic"
        }
      ]
    }
  }
}
```

### Test Case 3: New User with Empty Profiles Array
**Request:**
```json
{
  "name": "Bob Smith",
  "email": "bob@example.com",
  "password": "password123",
  "preferences": {
    "appSettings": {
      "personalityProfiles": []
    }
  }
}
```

**Expected Result:**
User should be created with the default profile (empty array should trigger default creation).

## Related Documentation

- [Personality Profiles Structure](./PERSONALITY_PROFILES_STRUCTURE.md) - Structure and validation rules
- [User Schema Guide](./USER_SCHEMA_GUIDE.md) - Complete user schema documentation

## Notes

- The client will no longer send default profiles, so the server must handle this
- This ensures consistency across all new users
- The default profile should be created at registration time, not on first login or first use

