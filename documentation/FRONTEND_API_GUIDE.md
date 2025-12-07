# Frontend API Guide - User Settings Retrieval

## Overview
This guide shows how to retrieve user settings and preferences from the backend API when a user loads the application.

## API Endpoint

### Get User by ID
Retrieves all user data including preferences, app settings, and personality profiles.

**Endpoint:** `GET /api/users/{user_id}`

**URL Example:**
```
http://localhost:8000/api/users/693326c07fcdaab8e81cdd2f
```

**Response Structure:**
```json
{
  "id": "693326c07fcdaab8e81cdd2f",
  "name": "John Doe",
  "email": "johndoe@email.com",
  "isActive": true,
  "isEmailVerified": false,
  "roles": ["user"],
  "phone": null,
  "address": {
    "street": null,
    "city": null,
    "state": null,
    "zip": null,
    "country": null
  },
  "preferences": {
    "newsletterOptIn": false,
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
      "personalityProfiles": [
        {
          "id": "1765054595705",
          "name": "Retarded",
          "description": "State everything incorrectly and in a dumb (retarded) way."
        },
        {
          "id": "1765054595706",
          "name": "Simon",
          "description": "My name is Simon Kaltgrad..."
        }
      ],
      "selectedModel": "ChatGPT"
    }
  },
  "avatarUrl": null,
  "dateCreated": "2024-04-27T00:00:00.000Z",
  "dateUpdated": "2024-04-27T00:00:00.000Z",
  "lastLogin": null
}
```

## React/JavaScript Implementation

### Using Fetch API

```javascript
// Function to fetch user settings on app load
async function fetchUserSettings(userId) {
  try {
    const response = await fetch(`http://localhost:8000/api/users/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      },
      credentials: 'include', // Include cookies if using session-based auth
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const userData = await response.json();
    
    // Extract preferences and settings
    const preferences = userData.preferences || {};
    const appSettings = preferences.appSettings || {};
    const personalityProfiles = appSettings.personalityProfiles || [];
    const selectedModel = appSettings.selectedModel;
    const printProperties = appSettings.printProperties || {};
    const theme = preferences.theme || 'light';
    
    return {
      user: userData,
      preferences,
      appSettings,
      personalityProfiles,
      selectedModel,
      printProperties,
      theme,
    };
  } catch (error) {
    console.error('Error fetching user settings:', error);
    throw error;
  }
}

// Usage in React component
useEffect(() => {
  const userId = localStorage.getItem('userId'); // or from your auth context
  if (userId) {
    fetchUserSettings(userId)
      .then((settings) => {
        // Update your state/context with settings
        setPersonalityProfiles(settings.personalityProfiles);
        setSelectedModel(settings.selectedModel);
        setTheme(settings.theme);
        setPrintProperties(settings.printProperties);
      })
      .catch((error) => {
        console.error('Failed to load user settings:', error);
      });
  }
}, []);
```

### Using Axios

```javascript
import axios from 'axios';

const API_BASE_URL = 'http://localhost:8000';

// Function to fetch user settings
async function fetchUserSettings(userId) {
  try {
    const response = await axios.get(`${API_BASE_URL}/api/users/${userId}`);
    const userData = response.data;
    
    // Extract and return structured settings
    return {
      user: userData,
      preferences: userData.preferences || {},
      appSettings: userData.preferences?.appSettings || {},
      personalityProfiles: userData.preferences?.appSettings?.personalityProfiles || [],
      selectedModel: userData.preferences?.appSettings?.selectedModel,
      printProperties: userData.preferences?.appSettings?.printProperties || {},
      theme: userData.preferences?.theme || 'light',
    };
  } catch (error) {
    console.error('Error fetching user settings:', error);
    if (error.response) {
      // Server responded with error status
      throw new Error(`Failed to fetch user: ${error.response.data.detail || error.message}`);
    } else {
      // Network error
      throw new Error('Network error: Could not connect to server');
    }
  }
}
```

### Complete React Hook Example

```javascript
import { useState, useEffect } from 'react';

function useUserSettings(userId) {
  const [settings, setSettings] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!userId) {
      setLoading(false);
      return;
    }

    async function loadSettings() {
      try {
        setLoading(true);
        const response = await fetch(`http://localhost:8000/api/users/${userId}`);
        
        if (!response.ok) {
          throw new Error(`Failed to fetch user: ${response.statusText}`);
        }
        
        const userData = await response.json();
        
        setSettings({
          user: userData,
          personalityProfiles: userData.preferences?.appSettings?.personalityProfiles || [],
          selectedModel: userData.preferences?.appSettings?.selectedModel,
          printProperties: userData.preferences?.appSettings?.printProperties || {},
          theme: userData.preferences?.theme || 'light',
        });
        setError(null);
      } catch (err) {
        setError(err.message);
        console.error('Error loading user settings:', err);
      } finally {
        setLoading(false);
      }
    }

    loadSettings();
  }, [userId]);

  return { settings, loading, error };
}

// Usage in component
function MyComponent() {
  const userId = localStorage.getItem('userId');
  const { settings, loading, error } = useUserSettings(userId);

  if (loading) return <div>Loading settings...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!settings) return <div>No settings available</div>;

  return (
    <div>
      <h1>Welcome, {settings.user.name}</h1>
      <p>Selected Model: {settings.selectedModel || 'None'}</p>
      <p>Theme: {settings.theme}</p>
      <p>Personality Profiles: {settings.personalityProfiles.length}</p>
    </div>
  );
}
```

## Alternative: Get User by Email

If you prefer to use email instead of user ID:

**Endpoint:** `GET /api/users/email/{email}`

**Example:**
```javascript
const response = await fetch(`http://localhost:8000/api/users/email/${userEmail}`);
const userData = await response.json();
```

## Error Handling

The API returns standard HTTP status codes:

- **200 OK**: User found and returned successfully
- **400 Bad Request**: Invalid user ID format
- **404 Not Found**: User not found
- **503 Service Unavailable**: Database connection unavailable

**Error Response Format:**
```json
{
  "detail": "User not found"
}
```

## Important Notes

1. **User ID Format**: The user ID is a MongoDB ObjectId string (24 hex characters). Make sure to store it correctly after login.

2. **After Login**: When a user logs in via `/api/users/login`, the response includes the full user object. You should store the `user.id` in localStorage or your state management solution.

3. **CORS**: Make sure your frontend URL is included in the `CORS_ORIGINS` environment variable on the backend, or it's in the default allowed origins (localhost:3000, localhost:3001, etc.).

4. **Base URL**: For production, replace `http://localhost:8000` with your actual backend URL (e.g., `https://your-app.onrender.com`).

## Example: Complete Load Flow

```javascript
// 1. On app initialization
const userId = localStorage.getItem('userId');

// 2. Fetch user settings
if (userId) {
  const settings = await fetchUserSettings(userId);
  
  // 3. Populate your app state
  setPersonalityProfiles(settings.personalityProfiles);
  setSelectedModel(settings.selectedModel);
  setTheme(settings.theme);
  setPrintProperties(settings.printProperties);
  
  // 4. Use settings throughout your app
  // e.g., populate dropdowns, set default values, etc.
}
```

## Related Endpoints

- **Login**: `POST /api/users/login` - Returns user object on successful login
- **Update User**: `PUT /api/users/{user_id}` - Update user preferences
- **Register**: `POST /api/users/register` - Create new user account

