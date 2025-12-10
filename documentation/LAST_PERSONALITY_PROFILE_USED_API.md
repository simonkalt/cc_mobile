# Last Personality Profile Used API Documentation

This document describes how to use the `last_personality_profile_used` field in user settings to track and retrieve the default personality profile for a user.

## Overview

The `last_personality_profile_used` field is stored in the user's preferences under `preferences.appSettings.last_personality_profile_used`. This field stores the ID of the personality profile that should be used by default when the user generates a cover letter.

## Schema Structure

The field is located at:
```
preferences.appSettings.last_personality_profile_used
```

**Full Schema Path:**
```json
{
  "preferences": {
    "appSettings": {
      "printProperties": { ... },
      "personalityProfiles": [
        {
          "id": "1765054595705",
          "name": "Professional",
          "description": "Formal and business-like tone"
        },
        {
          "id": "1765054595706",
          "name": "Creative",
          "description": "Lean in my artistic senses..."
        }
      ],
      "selectedModel": "gemini-2.5-flash",
      "lastResumeUsed": "507f1f77bcf86cd799439011/resume_2024.pdf",
      "last_personality_profile_used": "1765054595705"
    }
  }
}
```

## Field Details

- **Type**: `string` (optional)
- **Default**: `null`
- **Format**: Personality profile ID (string)
- **Example**: `"1765054595705"`

## API Endpoints

### 1. Get User Settings (Retrieve last_personality_profile_used)

**GET** `/api/users/{user_id}`

Retrieves the user's settings including `last_personality_profile_used`.

**Request:**
```bash
GET /api/users/507f1f77bcf86cd799439011
```

**Response:**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "preferences": {
    "appSettings": {
      "printProperties": { ... },
      "personalityProfiles": [
        {
          "id": "1765054595705",
          "name": "Professional",
          "description": "Formal and business-like tone"
        }
      ],
      "selectedModel": "gemini-2.5-flash",
      "lastResumeUsed": "507f1f77bcf86cd799439011/my_resume.pdf",
      "last_personality_profile_used": "1765054595705"
    }
  }
}
```

### 2. Update last_personality_profile_used

**PUT** `/api/users/{user_id}`

Updates the `last_personality_profile_used` field in the user's app settings.

**Request:**
```bash
PUT /api/users/507f1f77bcf86cd799439011
Content-Type: application/json
```

**Request Body:**
```json
{
  "preferences": {
    "appSettings": {
      "last_personality_profile_used": "1765054595705"
    }
  }
}
```

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "preferences": {
    "appSettings": {
      "last_personality_profile_used": "1765054595705"
    }
  }
}
```

## Client-Side Usage Examples

### React/JavaScript - Setting last_personality_profile_used

```javascript
// Function to set the last personality profile used
async function setLastPersonalityProfileUsed(userId, profileId) {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        preferences: {
          appSettings: {
            last_personality_profile_used: profileId  // e.g., "1765054595705"
          }
        }
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const updatedUser = await response.json();
    console.log('Last personality profile used updated:', updatedUser.preferences.appSettings.last_personality_profile_used);
    return updatedUser;
  } catch (error) {
    console.error('Error setting last personality profile used:', error);
    throw error;
  }
}

// Usage: Set last personality profile when user selects one
const handlePersonalityProfileSelect = async (userId, profileId) => {
  await setLastPersonalityProfileUsed(userId, profileId);
  console.log(`Personality profile ${profileId} set as default for user ${userId}`);
};
```

### React/JavaScript - Retrieving last_personality_profile_used on Login

```javascript
// Function to get user settings and retrieve last_personality_profile_used
async function getUserSettings(userId) {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/users/${userId}`);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const user = await response.json();
    const lastPersonalityProfileUsed = user.preferences?.appSettings?.last_personality_profile_used;
    
    if (lastPersonalityProfileUsed) {
      console.log('Default personality profile found:', lastPersonalityProfileUsed);
      return lastPersonalityProfileUsed;
    } else {
      console.log('No default personality profile set');
      return null;
    }
  } catch (error) {
    console.error('Error getting user settings:', error);
    throw error;
  }
}

// Usage: Get default personality profile on app load
const loadDefaultPersonalityProfile = async (userId) => {
  const profileId = await getUserSettings(userId);
  if (profileId) {
    // Find the profile in the user's personalityProfiles array
    const user = await getUserSettings(userId);
    const profiles = user.preferences?.appSettings?.personalityProfiles || [];
    const defaultProfile = profiles.find(p => p.id === profileId);
    
    if (defaultProfile) {
      console.log('Default profile:', defaultProfile.name);
      // Set this as the selected profile in your UI
      setSelectedPersonalityProfile(defaultProfile);
    } else {
      console.warn('Default personality profile not found in user profiles');
    }
  }
};
```

### React/JavaScript - Complete Example: Load and Apply Default Personality Profile

```javascript
// Complete example: Load user settings and apply default personality profile
const initializeUserSettings = async (userId) => {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    // 1. Get user settings
    const userResponse = await fetch(`${API_BASE_URL}/api/users/${userId}`);
    const user = await userResponse.json();
    
    // 2. Check for last_personality_profile_used
    const lastPersonalityProfileUsed = user.preferences?.appSettings?.last_personality_profile_used;
    
    if (lastPersonalityProfileUsed) {
      // 3. Get all personality profiles
      const profilesResponse = await fetch(
        `${API_BASE_URL}/api/personality-profiles?user_id=${userId}`
      );
      const profilesData = await profilesResponse.json();
      
      // 4. Find the matching profile
      const defaultProfile = profilesData.profiles.find(
        profile => profile.id === lastPersonalityProfileUsed
      );
      
      if (defaultProfile) {
        // 5. Set this as the selected profile in your UI
        setSelectedPersonalityProfile(defaultProfile);
        console.log(`Default personality profile loaded: ${defaultProfile.name}`);
      } else {
        console.warn('Default personality profile not found in available profiles');
      }
    } else {
      console.log('No default personality profile set');
    }
  } catch (error) {
    console.error('Error initializing user settings:', error);
  }
};
```

### React/JavaScript - Update last_personality_profile_used After Selection

```javascript
// Update last_personality_profile_used after user selects a personality profile
const handlePersonalityProfileChange = async (userId, selectedProfile) => {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    // 1. Update the selected profile in your UI state
    setSelectedPersonalityProfile(selectedProfile);
    
    // 2. Update last_personality_profile_used in the database
    const response = await fetch(`${API_BASE_URL}/api/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        preferences: {
          appSettings: {
            last_personality_profile_used: selectedProfile.id
          }
        }
      })
    });
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const updatedUser = await response.json();
    console.log('Default personality profile updated:', selectedProfile.name);
  } catch (error) {
    console.error('Error updating default personality profile:', error);
  }
};
```

## React Component Example

```javascript
import React, { useState, useEffect } from 'react';

function PersonalityProfileSelector({ userId }) {
  const [profiles, setProfiles] = useState([]);
  const [selectedProfile, setSelectedProfile] = useState(null);
  const [defaultProfileId, setDefaultProfileId] = useState(null);
  const API_BASE_URL = 'http://localhost:8000';

  useEffect(() => {
    // Load personality profiles and default selection
    const loadProfiles = async () => {
      try {
        // Get user settings to find default profile
        const userResponse = await fetch(`${API_BASE_URL}/api/users/${userId}`);
        const user = await userResponse.json();
        const lastPersonalityProfileUsed = user.preferences?.appSettings?.last_personality_profile_used;
        
        // Get all available profiles
        const profilesResponse = await fetch(
          `${API_BASE_URL}/api/personality-profiles?user_id=${userId}`
        );
        const profilesData = await profilesResponse.json();
        setProfiles(profilesData.profiles);
        
        // Set default profile if one exists
        if (lastPersonalityProfileUsed) {
          const defaultProfile = profilesData.profiles.find(
            p => p.id === lastPersonalityProfileUsed
          );
          if (defaultProfile) {
            setSelectedProfile(defaultProfile);
            setDefaultProfileId(lastPersonalityProfileUsed);
          }
        }
      } catch (error) {
        console.error('Error loading personality profiles:', error);
      }
    };

    if (userId) {
      loadProfiles();
    }
  }, [userId]);

  const handleProfileChange = async (profile) => {
    setSelectedProfile(profile);
    
    // Update last_personality_profile_used
    try {
      await fetch(`${API_BASE_URL}/api/users/${userId}`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          preferences: {
            appSettings: {
              last_personality_profile_used: profile.id
            }
          }
        })
      });
    } catch (error) {
      console.error('Error updating default personality profile:', error);
    }
  };

  return (
    <div>
      <label>Personality Profile:</label>
      <select
        value={selectedProfile?.id || ''}
        onChange={(e) => {
          const profile = profiles.find(p => p.id === e.target.value);
          if (profile) handleProfileChange(profile);
        }}
      >
        <option value="">Select a profile...</option>
        {profiles.map(profile => (
          <option key={profile.id} value={profile.id}>
            {profile.label}
          </option>
        ))}
      </select>
      {selectedProfile && (
        <p>Description: {selectedProfile.description}</p>
      )}
    </div>
  );
}

export default PersonalityProfileSelector;
```

## cURL Examples

### Get last_personality_profile_used
```bash
curl -X GET "http://localhost:8000/api/users/507f1f77bcf86cd799439011"
```

### Set last_personality_profile_used
```bash
curl -X PUT "http://localhost:8000/api/users/507f1f77bcf86cd799439011" \
  -H "Content-Type: application/json" \
  -d '{
    "preferences": {
      "appSettings": {
        "last_personality_profile_used": "1765054595705"
      }
    }
  }'
```

## Best Practices

1. **Profile ID Format**: The `last_personality_profile_used` field should contain the personality profile ID (string), which matches the `id` field in the `personalityProfiles` array.

2. **Profile Validation**: Before using `last_personality_profile_used`, verify that the profile still exists in the user's `personalityProfiles` array. If the profile was deleted, handle this gracefully (e.g., clear the field or prompt the user to select a new profile).

3. **Default Behavior**: If `last_personality_profile_used` is `null` or the profile doesn't exist, the application should handle this gracefully (e.g., show no selection or prompt the user to select a profile).

4. **Updating on Selection**: Consider updating `last_personality_profile_used` whenever the user:
   - Selects a personality profile from a dropdown
   - Creates a new personality profile and selects it
   - Uses a personality profile to generate a cover letter

5. **Migration**: For existing users, `last_personality_profile_used` will be `null` until they select a personality profile.

## Error Handling

```javascript
async function getLastPersonalityProfileUsed(userId) {
  try {
    const user = await getUserSettings(userId);
    const lastPersonalityProfileUsed = user.preferences?.appSettings?.last_personality_profile_used;
    
    if (!lastPersonalityProfileUsed) {
      return null; // No default profile set
    }
    
    // Verify the profile exists in the user's personalityProfiles array
    const profiles = user.preferences?.appSettings?.personalityProfiles || [];
    const profileExists = profiles.some(
      profile => profile.id === lastPersonalityProfileUsed
    );
    
    if (!profileExists) {
      console.warn('Default personality profile not found, clearing last_personality_profile_used');
      // Optionally clear the invalid reference
      await setLastPersonalityProfileUsed(userId, null);
      return null;
    }
    
    return lastPersonalityProfileUsed;
  } catch (error) {
    console.error('Error getting last personality profile used:', error);
    return null;
  }
}
```

## Notes

- The field name uses snake_case (`last_personality_profile_used`) to match Python naming conventions in the backend.
- The profile ID is a string that uniquely identifies each personality profile within a user's profile list.
- When a personality profile is deleted, you may want to check if it was the default and clear `last_personality_profile_used` if needed.
- This field works in conjunction with the `/api/personality-profiles` endpoint to retrieve the full profile details.

