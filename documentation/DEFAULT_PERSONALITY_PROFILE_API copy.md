# Default Personality Profiles for New Users

## Overview

When a new user registers, the server should automatically create **two** default personality profiles if no personality profiles are provided in the registration request. This ensures all users have profiles to use immediately after registration. **All default profile logic lives on the server;** the front-end does not define or send default profiles.

## Primary specification

**See [BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md](./BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md)** for the full backend specification, including:

- **When** to create defaults (registration, empty/missing `personalityProfiles`)
- **Two default profiles:**
  1. **Professional** – standard professional tone (same description as below)
  2. **Professional (Creative Layout)** – same professional intent, with instructions to use multiple fonts, font sizes, and colors in the generated letters
- Exact description text, ID generation rules, and testing checklist

The rest of this document is kept for backward reference and example code; implement according to the spec above.

## When to Create Defaults

The server should create the two default profiles when:

1. A new user is registered (e.g. `POST /api/users/register`)
2. The request does NOT include `personalityProfiles` in `preferences.appSettings`, OR the array is empty or null

## Default Profile Structures (reference)

**Profile 1 – Professional:**

```json
{
  "id": "<unique_string_per_user>",
  "name": "Professional",
  "description": "I am trying to garner interest in my talents and experience so that I stand out and make it easy for the recruiter to hire me. Be very professional."
}
```

**Profile 2 – Professional (Creative Layout):**  
See [BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md](./BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md) for the exact `name` and `description` (must require multiple fonts, font sizes, and colors).

### ID Generation

- Each profile `id` must be a unique string per user (e.g. timestamp as string or UUID)
- Must be unique per user (can use timestamp + random suffix if needed)

### Implementation Location

Implement in the user registration endpoint handler, after validating the registration data but before saving the user to the database.

## Example Implementation (Python/FastAPI)

**Note:** The spec requires **two** default profiles (Professional and Professional (Creative Layout)). See [BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md](./BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md) for the exact second profile. Example with two defaults:

```python
import time

def register_user(user_data: dict):
    # ... existing registration validation ...

    preferences = user_data.get("preferences", {})
    app_settings = preferences.get("appSettings", {})
    personality_profiles = app_settings.get("personalityProfiles", [])

    if not personality_profiles or len(personality_profiles) == 0:
        t = int(time.time() * 1000)
        personality_profiles = [
            {
                "id": str(t),
                "name": "Professional",
                "description": "I am trying to garner interest in my talents and experience so that I stand out and make it easy for the recruiter to hire me. Be very professional."
            },
            {
                "id": str(t + 1),
                "name": "Professional (Creative Layout)",
                "description": "Same professional tone and content as the standard Professional profile, but format the cover letter with varied typography and color: use multiple fonts, font sizes, and colors to create a visually distinctive, creative layout. Apply bold, italics, and subtle color for headings, key phrases, or section emphasis while keeping the content professional and recruiter-friendly."
            }
        ]

    if "appSettings" not in preferences:
        preferences["appSettings"] = {}
    preferences["appSettings"]["personalityProfiles"] = personality_profiles
    user_data["preferences"] = preferences
    # ... save user to database ...
```

## Example Implementation (Node.js/Express)

See [BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md](./BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md) for the full two-profile spec. Example:

```javascript
async function registerUser(userData) {
  const preferences = userData.preferences || {};
  const appSettings = preferences.appSettings || {};
  let personalityProfiles = appSettings.personalityProfiles || [];

  if (!personalityProfiles || personalityProfiles.length === 0) {
    const t = Date.now();
    personalityProfiles = [
      {
        id: String(t),
        name: "Professional",
        description:
          "I am trying to garner interest in my talents and experience so that I stand out and make it easy for the recruiter to hire me. Be very professional.",
      },
      {
        id: String(t + 1),
        name: "Professional (Creative Layout)",
        description:
          "Same professional tone and content as the standard Professional profile, but format the cover letter with varied typography and color: use multiple fonts, font sizes, and colors to create a visually distinctive, creative layout. Apply bold, italics, and subtle color for headings, key phrases, or section emphasis while keeping the content professional and recruiter-friendly.",
      },
    ];
  }

  if (!preferences.appSettings) preferences.appSettings = {};
  preferences.appSettings.personalityProfiles = personalityProfiles;
  userData.preferences = preferences;
  // ... save user to database ...
}
```

## Behavior Rules

1. **Only create defaults if missing**: Create the two default profiles only when the user doesn't provide any personality profiles (empty or omitted).
2. **Don't override provided profiles**: If the client sends personality profiles, use those exactly.
3. **Two default profiles**: Create exactly two: "Professional" and "Professional (Creative Layout)" per the spec.
4. **Exact descriptions**: Use the description text from [BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md](./BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md).

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
User should be created with two default profiles (see [BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md](./BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md)):

```json
{
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        {
          "id": "1735267200000",
          "name": "Professional",
          "description": "I am trying to garner interest in my talents and experience so that I stand out and make it easy for the recruiter to hire me. Be very professional."
        },
        {
          "id": "1735267200001",
          "name": "Professional (Creative Layout)",
          "description": "... (multiple fonts, font sizes, colors - see spec)"
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
User should be created with the two default profiles (empty array triggers default creation).

## Related Documentation

- **[BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md](./BACKEND_DEFAULT_PERSONALITY_PROFILES_SPEC.md)** – Full backend spec (two defaults, Creative Layout description, logic, testing)
- [Personality Profiles Structure](./PERSONALITY_PROFILES_STRUCTURE.md) – Structure and validation rules
- [User Schema Guide](./USER_SCHEMA_GUIDE.md) – Complete user schema documentation

## Notes

- The client does not send or define default profiles; the server is the single source of truth.
- Defaults are created at registration time when `personalityProfiles` is missing or empty.
- Two defaults: **Professional** and **Professional (Creative Layout)** (creative one uses multiple fonts, font sizes, and colors).
