# Personality Profiles Structure Documentation

This document describes the structure and validation rules for personality profiles stored in user preferences.

## Structure

Each personality profile in the `personalityProfiles` array must have exactly three fields:

```json
{
  "id": "string",
  "name": "string",
  "description": "string"
}
```

## Schema Location

Personality profiles are stored at:
```
preferences.appSettings.personalityProfiles
```

**Full Schema Path:**
```json
{
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        {
          "id": "1765054595705",
          "name": "Professional",
          "description": "Formal and business-like tone"
        },
        {
          "id": "1765054595706",
          "name": "Creative",
          "description": "Lean in my artistic senses as I am a pro level drummer and song writer"
        }
      ]
    }
  }
}
```

## Field Requirements

### `id` (required)
- **Type**: `string`
- **Description**: Unique identifier for the profile
- **Format**: Typically a timestamp string (e.g., `"1765054595705"`)
- **Validation**: Must be present and non-empty

### `name` (required)
- **Type**: `string`
- **Description**: Display name for the profile
- **Validation**: Must be present and non-empty

### `description` (required)
- **Type**: `string`
- **Description**: The personality profile instructions/description
- **Validation**: Should be present (empty string allowed but not recommended)

## API Behavior

### GET Operations

All GET operations automatically normalize personality profiles to ensure only `id`, `name`, and `description` fields are returned. Any extra fields in the database are filtered out.

**Example Response:**
```json
{
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        {
          "id": "1765054595705",
          "name": "Professional",
          "description": "Formal and business-like tone"
        }
      ]
    }
  }
}
```

### PUT Operations

When updating personality profiles:

1. **Validation**: Each profile must have `id` and `name` fields
2. **Normalization**: Only `id`, `name`, and `description` fields are saved
3. **Extra Fields**: Any additional fields in the request are ignored
4. **Invalid Profiles**: Profiles missing required fields are skipped with a warning

**Example Request:**
```json
{
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        {
          "id": "1765054595705",
          "name": "Professional",
          "description": "Formal and business-like tone"
        }
      ]
    }
  }
}
```

**Note**: Even if you send extra fields like `"createdAt"` or `"updatedAt"`, only `id`, `name`, and `description` will be saved.

## Normalization

The API automatically normalizes personality profiles in the following scenarios:

1. **When Retrieving User Data**: `GET /api/users/{user_id}` normalizes profiles before returning
2. **When Updating Profiles**: `PUT /api/users/{user_id}` normalizes profiles before saving
3. **When Getting Profiles**: `GET /api/personality-profiles` normalizes profiles before returning
4. **When Using Profiles**: Profile matching in `POST /api/job-info` normalizes profiles before use

## Migration from Old Structure

If you have existing profiles with extra fields, the API will automatically normalize them:

**Before (old structure with extra fields):**
```json
{
  "id": "1765054595705",
  "name": "Professional",
  "description": "Formal tone",
  "createdAt": "2024-01-01",
  "updatedAt": "2024-01-02",
  "isActive": true
}
```

**After (normalized structure):**
```json
{
  "id": "1765054595705",
  "name": "Professional",
  "description": "Formal tone"
}
```

## Client-Side Implementation

### Creating a Profile

```javascript
const createPersonalityProfile = async (userId, profileName, profileDescription) => {
  // Get existing profiles
  const userResponse = await fetch(`http://localhost:8000/api/users/${userId}`);
  const user = await userResponse.json();
  const existingProfiles = user.preferences?.appSettings?.personalityProfiles || [];
  
  // Create new profile with correct structure
  const newProfile = {
    id: Date.now().toString(),  // Generate unique ID
    name: profileName,
    description: profileDescription
  };
  
  // Add to existing profiles
  const updatedProfiles = [...existingProfiles, newProfile];
  
  // Update user
  const updateResponse = await fetch(`http://localhost:8000/api/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          personalityProfiles: updatedProfiles
        }
      }
    })
  });
  
  return updateResponse.json();
};
```

### Updating a Profile

```javascript
const updatePersonalityProfile = async (userId, profileId, updates) => {
  // Get existing profiles
  const userResponse = await fetch(`http://localhost:8000/api/users/${userId}`);
  const user = await userResponse.json();
  const existingProfiles = user.preferences?.appSettings?.personalityProfiles || [];
  
  // Find and update the profile
  const updatedProfiles = existingProfiles.map(profile => {
    if (profile.id === profileId) {
      // Only update id, name, description (ignore any extra fields)
      return {
        id: profile.id,  // Keep original ID
        name: updates.name || profile.name,
        description: updates.description || profile.description
      };
    }
    return profile;
  });
  
  // Update user
  const updateResponse = await fetch(`http://localhost:8000/api/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          personalityProfiles: updatedProfiles
        }
      }
    })
  });
  
  return updateResponse.json();
};
```

### Deleting a Profile

```javascript
const deletePersonalityProfile = async (userId, profileId) => {
  // Get existing profiles
  const userResponse = await fetch(`http://localhost:8000/api/users/${userId}`);
  const user = await userResponse.json();
  const existingProfiles = user.preferences?.appSettings?.personalityProfiles || [];
  
  // Filter out the profile to delete
  const updatedProfiles = existingProfiles.filter(profile => profile.id !== profileId);
  
  // Update user
  const updateResponse = await fetch(`http://localhost:8000/api/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          personalityProfiles: updatedProfiles
        }
      }
    })
  });
  
  return updateResponse.json();
};
```

## Validation Rules

1. **Required Fields**: `id` and `name` are required. Profiles without these fields are skipped.
2. **Type Validation**: Each field must be a string.
3. **Empty Values**: Empty strings for `id` or `name` are considered invalid.
4. **Extra Fields**: Extra fields are automatically removed during normalization.
5. **Array Structure**: `personalityProfiles` must be an array of objects.

## Error Handling

### Invalid Profile Structure

If a profile is missing required fields:
- The profile is skipped (not saved)
- A warning is logged
- Other valid profiles are still saved

**Example:**
```json
{
  "personalityProfiles": [
    {
      "id": "123",
      "name": "Valid Profile",
      "description": "This will be saved"
    },
    {
      "name": "Invalid Profile"
      // Missing 'id' - this profile will be skipped
    }
  ]
}
```

### Empty Array

Setting `personalityProfiles` to an empty array `[]` will delete all existing profiles. A warning is logged when this happens.

## Best Practices

1. **Always Include All Fields**: When creating or updating profiles, always include `id`, `name`, and `description`
2. **Use Unique IDs**: Generate unique IDs (e.g., using `Date.now().toString()`)
3. **Don't Rely on Extra Fields**: Don't add custom fields as they will be removed during normalization
4. **Validate Before Sending**: Validate profile structure on the client before sending to the API
5. **Handle Normalization**: Be aware that the API normalizes profiles, so don't expect extra fields to persist

## Related Endpoints

- **Get User**: `GET /api/users/{user_id}` - Returns normalized personality profiles
- **Update User**: `PUT /api/users/{user_id}` - Normalizes profiles before saving
- **Get Profiles**: `GET /api/personality-profiles` - Returns normalized profiles for UI
- **Job Info**: `POST /api/job-info` - Uses normalized profiles for matching

## Examples

### Complete Example: Full CRUD Operations

```javascript
const API_BASE_URL = "http://localhost:8000";

// 1. Create a new profile
async function createProfile(userId, name, description) {
  const user = await (await fetch(`${API_BASE_URL}/api/users/${userId}`)).json();
  const existing = user.preferences?.appSettings?.personalityProfiles || [];
  
  const newProfile = {
    id: Date.now().toString(),
    name: name,
    description: description
  };
  
  await fetch(`${API_BASE_URL}/api/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          personalityProfiles: [...existing, newProfile]
        }
      }
    })
  });
}

// 2. Update an existing profile
async function updateProfile(userId, profileId, name, description) {
  const user = await (await fetch(`${API_BASE_URL}/api/users/${userId}`)).json();
  const profiles = user.preferences?.appSettings?.personalityProfiles || [];
  
  const updated = profiles.map(p => 
    p.id === profileId 
      ? { id: p.id, name: name, description: description }
      : p
  );
  
  await fetch(`${API_BASE_URL}/api/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          personalityProfiles: updated
        }
      }
    })
  });
}

// 3. Delete a profile
async function deleteProfile(userId, profileId) {
  const user = await (await fetch(`${API_BASE_URL}/api/users/${userId}`)).json();
  const profiles = user.preferences?.appSettings?.personalityProfiles || [];
  
  const filtered = profiles.filter(p => p.id !== profileId);
  
  await fetch(`${API_BASE_URL}/api/users/${userId}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          personalityProfiles: filtered
        }
      }
    })
  });
}

// 4. Get all profiles
async function getProfiles(userId) {
  const response = await fetch(`${API_BASE_URL}/api/personality-profiles?user_id=${userId}`);
  const data = await response.json();
  return data.profiles;  // Already normalized to {id, name, description, label, value}
}
```

