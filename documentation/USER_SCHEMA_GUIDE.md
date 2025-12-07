# User Schema Guide

This guide explains the updated user schema that supports app settings, print properties, and custom personality profiles.

## Schema Structure

```json
{
  "_id": "ObjectId",
  "name": "string",
  "email": "string",
  "hashedPassword": "string",
  "isActive": true,
  "isEmailVerified": false,
  "roles": ["user"],
  "failedLoginAttempts": 0,
  "lastLogin": "datetime",
  "passwordChangedAt": "datetime or null",
  "avatarUrl": "string or null",
  "phone": "string or null",
  "address": {
    "street": "string or null",
    "city": "string or null",
    "state": "string or null",
    "zip": "string or null",
    "country": "string or null"
  },
  "dateCreated": "datetime",
  "dateUpdated": "datetime",
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
          "id": "1764984202588",
          "name": "Dumb",
          "description": "Get everything wrong. Seem confident in my confusion."
        }
      ],
      "selectedModel": "gemini-2.5-flash"
    }
  }
}
```

## API Usage Examples

### Register User with App Settings

```javascript
const registerUser = async () => {
  const response = await fetch('https://your-api.onrender.com/api/users/register', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      name: "Simon Kaltgrad",
      email: "simon@example.com",
      password: "securePassword123",
      preferences: {
        newsletterOptIn: false,
        theme: "light",
        appSettings: {
          printProperties: {
            margins: {
              top: 1.0,
              right: 0.75,
              bottom: 0.25,
              left: 0.75
            },
            fontFamily: "Georgia",
            fontSize: 11.0,
            lineHeight: 1.15,
            pageSize: {
              width: 8.5,
              height: 11.0
            }
          },
          personalityProfiles: [],
          selectedModel: "gemini-2.5-flash"
        }
      }
    })
  });
  return response.json();
};
```

### Update Print Properties

```javascript
const updatePrintProperties = async (userId) => {
  const response = await fetch(`https://your-api.onrender.com/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          printProperties: {
            margins: {
              top: 0.5,
              right: 0.5,
              bottom: 0.5,
              left: 0.5
            },
            fontFamily: "Arial",
            fontSize: 12.0,
            lineHeight: 1.2
          }
        }
      }
    })
  });
  return response.json();
};
```

### Add Custom Personality Profile

```javascript
const addPersonalityProfile = async (userId) => {
  const response = await fetch(`https://your-api.onrender.com/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          personalityProfiles: [
            {
              id: Date.now().toString(),
              name: "Professional",
              description: "Formal and business-like tone"
            },
            {
              id: Date.now().toString() + "1",
              name: "Casual",
              description: "Friendly and relaxed tone"
            }
          ]
        }
      }
    })
  });
  return response.json();
};
```

### Update Selected Model

```javascript
const updateSelectedModel = async (userId, modelName) => {
  const response = await fetch(`https://your-api.onrender.com/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      preferences: {
        appSettings: {
          selectedModel: modelName  // e.g., "gemini-2.5-flash", "gpt-4.1", etc.
        }
      }
    })
  });
  return response.json();
};
```

### Update Multiple Settings at Once

```javascript
const updateUserSettings = async (userId) => {
  const response = await fetch(`https://your-api.onrender.com/api/users/${userId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      preferences: {
        theme: "dark",
        appSettings: {
          printProperties: {
            fontSize: 10.5,
            fontFamily: "Times New Roman"
          },
          selectedModel: "gpt-4.1",
          personalityProfiles: [
            {
              id: "1",
              name: "Custom Profile",
              description: "My custom description"
            }
          ]
        }
      }
    })
  });
  return response.json();
};
```

## Field Descriptions

### Print Properties

- **margins**: Page margins in inches
  - `top`: Top margin (default: 1.0)
  - `right`: Right margin (default: 0.75)
  - `bottom`: Bottom margin (default: 0.25)
  - `left`: Left margin (default: 0.75)

- **fontFamily**: Font family name (default: "Georgia")
- **fontSize**: Font size in points (default: 11.0)
- **lineHeight**: Line spacing multiplier (default: 1.15)
- **pageSize**: Page dimensions in inches
  - `width`: Page width (default: 8.5)
  - `height`: Page height (default: 11.0)

### Personality Profiles

Array of custom personality profiles:
- **id**: Unique identifier (string, typically timestamp)
- **name**: Profile name (string)
- **description**: Profile description/instructions (string)

### Selected Model

The LLM model selected by the user:
- Examples: `"gemini-2.5-flash"`, `"gpt-4.1"`, `"claude-sonnet-4-20250514"`, etc.

## Default Values

When a user is registered without specifying preferences, defaults are:

```json
{
  "newsletterOptIn": false,
  "theme": "light",
  "appSettings": {
    "printProperties": {
      "margins": { "top": 1.0, "right": 0.75, "bottom": 0.25, "left": 0.75 },
      "fontFamily": "Georgia",
      "fontSize": 11.0,
      "lineHeight": 1.15,
      "pageSize": { "width": 8.5, "height": 11.0 }
    },
    "personalityProfiles": [],
    "selectedModel": null
  }
}
```

## Update Behavior

The API supports **nested updates** using dot notation:

- ✅ You can update just `preferences.appSettings.selectedModel` without affecting other settings
- ✅ You can update `preferences.appSettings.printProperties.fontSize` independently
- ✅ You can update `preferences.appSettings.personalityProfiles` array
- ✅ You can update top-level preferences like `preferences.theme`

**Note:** When updating nested fields, only include the fields you want to change. The API will merge your updates with existing preferences.

## Validation

The API validates:
- Email format (must be valid email)
- Required fields (name, email, password for registration)
- Data types (numbers for margins, fontSize, etc.)
- Array structure for personalityProfiles

## Error Handling

If validation fails, you'll receive a `422 Unprocessable Entity` response with details about what's wrong.

Example error response:
```json
{
  "detail": [
    {
      "loc": ["body", "preferences", "appSettings", "printProperties", "fontSize"],
      "msg": "value is not a valid float",
      "type": "type_error.float"
    }
  ]
}
```

