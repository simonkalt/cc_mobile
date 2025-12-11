# Use Default Fonts API Documentation

This document describes the `useDefaultFonts` setting that allows users to control whether their print settings (font family, font size, line height) are applied to HTML responses, or if the LLM's original HTML formatting should be preserved.

## Overview

The `useDefaultFonts` field is stored in the user's preferences under `preferences.appSettings.printProperties.useDefaultFonts`. When set to `true`, the API will not apply font styling to HTML responses, allowing the LLM's original HTML formatting to be displayed as-is.

## Schema Structure

The field is located at:

```
preferences.appSettings.printProperties.useDefaultFonts
```

**Full Schema Path:**

```json
{
  "preferences": {
    "appSettings": {
      "printProperties": {
        "margins": {
          "top": 1.0,
          "right": 0.75,
          "bottom": 0.25,
          "left": 0.75
        },
        "fontFamily": "Comic Sans Serif",
        "fontSize": 11.0,
        "lineHeight": 1.15,
        "pageSize": {
          "width": 8.5,
          "height": 11.0
        },
        "useDefaultFonts": false
      },
      "personalityProfiles": [ ... ],
      "selectedModel": "gemini-2.5-flash"
    }
  }
}
```

## Field Details

- **Type**: `boolean` (optional)
- **Default**: `false`
- **Description**: When `true`, the API will not apply font family, font size, or line height styling to HTML responses. The LLM's original HTML formatting will be preserved.
- **When `false`**: The API will apply the user's selected font family, font size, and line height to HTML responses.

## Behavior

### When `useDefaultFonts` is `false` (default):

- The API wraps the HTML response with inline CSS styling
- Font family, font size, and line height from print settings are applied
- Example: `<div style="font-family: 'Comic Sans Serif', serif; font-size: 11pt; line-height: 1.15;">...</div>`

### When `useDefaultFonts` is `true`:

- The API returns the raw HTML from the LLM without font styling
- The LLM's original HTML formatting is preserved
- No font family, font size, or line height styling is applied

## API Endpoints

### 1. Get User Settings (Retrieve useDefaultFonts)

**GET** `/api/users/{user_id}`

Retrieves the user's settings including `useDefaultFonts`.

**Request:**

```bash
GET /api/users/693326c07fcdaab8e81cdd2f
```

**Response:**

```json
{
  "id": "693326c07fcdaab8e81cdd2f",
  "name": "John Doe",
  "email": "john@example.com",
  "preferences": {
    "appSettings": {
      "printProperties": {
        "fontFamily": "Comic Sans Serif",
        "fontSize": 11.0,
        "lineHeight": 1.15,
        "useDefaultFonts": false
      }
    }
  }
}
```

### 2. Update useDefaultFonts

**PUT** `/api/users/{user_id}`

Updates the `useDefaultFonts` field in the user's print properties.

**Request:**

```bash
PUT /api/users/693326c07fcdaab8e81cdd2f
Content-Type: application/json
```

**Request Body:**

```json
{
  "preferences": {
    "appSettings": {
      "printProperties": {
        "useDefaultFonts": true
      }
    }
  }
}
```

**Response (200 OK):**

```json
{
  "id": "693326c07fcdaab8e81cdd2f",
  "name": "John Doe",
  "email": "john@example.com",
  "preferences": {
    "appSettings": {
      "printProperties": {
        "fontFamily": "Comic Sans Serif",
        "fontSize": 11.0,
        "lineHeight": 1.15,
        "useDefaultFonts": true
      }
    }
  }
}
```

### 3. Update Multiple Print Properties

You can update `useDefaultFonts` along with other print properties in a single request:

**Request Body:**

```json
{
  "preferences": {
    "appSettings": {
      "printProperties": {
        "fontFamily": "Arial",
        "fontSize": 12.0,
        "lineHeight": 1.5,
        "useDefaultFonts": false
      }
    }
  }
}
```

## Client-Side Implementation Examples

### JavaScript/React Example

```javascript
// Function to set useDefaultFonts
async function setUseDefaultFonts(userId, useDefaultFonts) {
  const API_BASE_URL = "http://localhost:8000";

  try {
    const response = await fetch(`${API_BASE_URL}/api/users/${userId}`, {
      method: "PUT",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        preferences: {
          appSettings: {
            printProperties: {
              useDefaultFonts: useDefaultFonts, // true or false
            },
          },
        },
      }),
    });

    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }

    const userData = await response.json();
    return userData;
  } catch (error) {
    console.error("Error updating useDefaultFonts:", error);
    throw error;
  }
}

// Usage: Enable default fonts (don't apply print settings)
await setUseDefaultFonts("693326c07fcdaab8e81cdd2f", true);

// Usage: Disable default fonts (apply print settings)
await setUseDefaultFonts("693326c07fcdaab8e81cdd2f", false);
```

### React Component Example

```javascript
import React, { useState, useEffect } from "react";

function FontSettingsToggle({ userId }) {
  const [useDefaultFonts, setUseDefaultFonts] = useState(false);
  const [loading, setLoading] = useState(false);

  // Load current setting
  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/api/users/${userId}`
        );
        const user = await response.json();
        const currentSetting =
          user.preferences?.appSettings?.printProperties?.useDefaultFonts ||
          false;
        setUseDefaultFonts(currentSetting);
      } catch (error) {
        console.error("Error loading font settings:", error);
      }
    };

    if (userId) {
      loadSettings();
    }
  }, [userId]);

  // Update setting
  const handleToggle = async (newValue) => {
    setLoading(true);
    try {
      await setUseDefaultFonts(userId, newValue);
      setUseDefaultFonts(newValue);
      alert(
        `Font settings ${newValue ? "disabled" : "enabled"}. HTML will ${
          newValue
            ? "use LLM's default formatting"
            : "apply your print settings"
        }.`
      );
    } catch (error) {
      console.error("Error updating font settings:", error);
      alert("Failed to update font settings");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <label>
        <input
          type="checkbox"
          checked={useDefaultFonts}
          onChange={(e) => handleToggle(e.target.checked)}
          disabled={loading}
        />
        Use LLM's Default Fonts
      </label>
      <p style={{ fontSize: "0.9em", color: "#666" }}>
        {useDefaultFonts
          ? "HTML responses will use the LLM's original font formatting"
          : "HTML responses will use your selected font family, size, and line height"}
      </p>
    </div>
  );
}

export default FontSettingsToggle;
```

### React Native Example

```javascript
import React, { useState, useEffect } from "react";
import { View, Text, Switch, ActivityIndicator } from "react-native";

function FontSettingsToggle({ userId }) {
  const [useDefaultFonts, setUseDefaultFonts] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const response = await fetch(
          `http://localhost:8000/api/users/${userId}`
        );
        const user = await response.json();
        const currentSetting =
          user.preferences?.appSettings?.printProperties?.useDefaultFonts ||
          false;
        setUseDefaultFonts(currentSetting);
      } catch (error) {
        console.error("Error loading font settings:", error);
      }
    };

    if (userId) {
      loadSettings();
    }
  }, [userId]);

  const handleToggle = async (value) => {
    setLoading(true);
    try {
      await fetch(`http://localhost:8000/api/users/${userId}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          preferences: {
            appSettings: {
              printProperties: {
                useDefaultFonts: value,
              },
            },
          },
        }),
      });
      setUseDefaultFonts(value);
    } catch (error) {
      console.error("Error updating font settings:", error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <View style={{ padding: 20 }}>
      <View style={{ flexDirection: "row", alignItems: "center" }}>
        <Switch
          value={useDefaultFonts}
          onValueChange={handleToggle}
          disabled={loading}
        />
        <Text style={{ marginLeft: 10 }}>Use LLM's Default Fonts</Text>
        {loading && <ActivityIndicator style={{ marginLeft: 10 }} />}
      </View>
      <Text style={{ marginTop: 5, fontSize: 12, color: "#666" }}>
        {useDefaultFonts
          ? "HTML will use LLM's original formatting"
          : "HTML will use your print settings"}
      </Text>
    </View>
  );
}

export default FontSettingsToggle;
```

## Impact on HTML Responses

### When `useDefaultFonts` is `false` (default):

The API response will include styled HTML:

```json
{
  "markdown": "...",
  "html": "<div style=\"font-family: 'Comic Sans Serif', serif; font-size: 11pt; line-height: 1.15; color: #000;\"><p>Cover letter content...</p></div>"
}
```

### When `useDefaultFonts` is `true`:

The API response will return raw HTML from the LLM:

```json
{
  "markdown": "...",
  "html": "<p>Cover letter content...</p>"
}
```

## Use Cases

### When to set `useDefaultFonts` to `true`:

- You want to preserve the LLM's original HTML formatting
- The LLM includes custom styling in its HTML output
- You prefer the LLM's default font choices
- You want maximum flexibility in HTML rendering

### When to set `useDefaultFonts` to `false` (default):

- You want consistent font styling across all responses
- You have specific font preferences (e.g., Comic Sans Serif)
- You want to match your print settings in the HTML preview
- You need consistent typography for your brand

## Notes

1. **PDF Generation**: The `useDefaultFonts` setting only affects HTML responses. PDF generation always uses the print settings (fontFamily, fontSize, lineHeight) regardless of this flag.

2. **Default Behavior**: If `useDefaultFonts` is not set or is `false`, the API will apply print settings to HTML responses.

3. **Backward Compatibility**: Existing users without this field will default to `false`, maintaining current behavior.

4. **Font Settings Still Stored**: Even when `useDefaultFonts` is `true`, the fontFamily, fontSize, and lineHeight values are still stored and used for PDF generation.

## Error Handling

If the update fails, the API will return an appropriate HTTP status code:

- `400 Bad Request`: Invalid user ID format or request body
- `404 Not Found`: User not found
- `500 Internal Server Error`: Server error during update

## Related Endpoints

- **Get User**: `GET /api/users/{user_id}` - Retrieve all user settings
- **Update User**: `PUT /api/users/{user_id}` - Update user settings
- **Job Info**: `POST /api/job-info` - Generate cover letter (affected by this setting)
- **Chat**: `POST /chat` - Chat endpoint (not affected by this setting)

## Testing

You can test the setting using curl:

```bash
# Get current settings
curl -X GET http://localhost:8000/api/users/693326c07fcdaab8e81cdd2f

# Enable useDefaultFonts
curl -X PUT http://localhost:8000/api/users/693326c07fcdaab8e81cdd2f \
  -H "Content-Type: application/json" \
  -d '{
    "preferences": {
      "appSettings": {
        "printProperties": {
          "useDefaultFonts": true
        }
      }
    }
  }'

# Disable useDefaultFonts
curl -X PUT http://localhost:8000/api/users/693326c07fcdaab8e81cdd2f \
  -H "Content-Type: application/json" \
  -d '{
    "preferences": {
      "appSettings": {
        "printProperties": {
          "useDefaultFonts": false
        }
      }
    }
  }'
```
