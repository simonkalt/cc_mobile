# User API Documentation

RESTful API endpoints for user registration and CRUD operations.

## Base URL
```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## User response shape (`UserResponse`)

Successful **register** (`201`), **get user** (by id, email, or GET `/api/users/me`), and **put user** (`200`) return a **single JSON user object** matching the `UserResponse` model below. **Login** returns the same object nested under `user` (see [Login User](#2-login-user)), plus access and refresh tokens.

Omitted optional fields are often `null` in JSON responses.

| Field | Type | Notes |
| --- | --- | --- |
| `id` | string | MongoDB ObjectId as string |
| `name` | string | |
| `email` | string | |
| `isActive` | boolean | |
| `isEmailVerified` | boolean | |
| `roles` | string[] | e.g. `["user"]` |
| `phone` | string or null | |
| `address` | object or null | Opaque key/value map (e.g. street, city, state, zip, country) |
| `preferences` | object or null | See [Preferences (including personality / tone)](#preferences-including-personality--tone) |
| `avatarUrl` | string or null | |
| `dateCreated` | string (ISO 8601) | |
| `dateUpdated` | string (ISO 8601) | |
| `lastLogin` | string (ISO 8601) or null | |
| `llm_counts` | object or null | Map of LLM name → integer usage count; see [LLM Usage Tracking](#llm-usage-tracking) |
| `last_llm_used` | string or null | |
| `generation_credits` | integer | Non-negative; default `10` for new free-tier users |
| `max_credits` | integer | Non-negative; default `10` for new free-tier users |
| `SMSOpt` | string or null | e.g. `"IN"` or `"OUT"` when set |
| `SMSOptDate` | string (ISO 8601) or null | |
| `subscriptionStatus` | string or null | e.g. `"free"` when set on new users |
| `subscriptionPlan` | string or null | |
| `subscriptionCurrentPeriodEnd` | string (ISO 8601) or null | |
| `super_user` | boolean | Default `false` |
| `archived` | boolean | Default `false` |
| `archived_at` | string (ISO 8601) or null | |
| `account_deletion_pending` | boolean | Default `false` |
| `account_deletion_requested_at` | string (ISO 8601) or null | |

### Preferences (including personality / tone)

`preferences` is a flexible object. The backend merges **registration defaults** (see `register_user` in the codebase) and normalizes on read. Known structure:

- **`newsletterOptIn`** (boolean, optional): Default `false` for new users.
- **`theme`** (string, optional): e.g. `"light"`; default for new users is `"light"`.
- **`appSettings`** (object, optional):
  - **`printProperties`**: print layout (margins, `fontFamily`, `fontSize`, `lineHeight`, `pageSize`, `useDefaultFonts`, etc.).
  - **`personalityProfiles`** (array): Each profile is returned with **only** `id`, `name`, and `description` (other keys are dropped when serializing). These are the user’s custom personality / tone definitions.
  - **`last_personality_profile_used`** (string or null): Id of the profile most recently used (e.g. from LLM flows); aligns with a profile in `personalityProfiles`.
  - **`selectedModel`** (string or null), **`lastResumeUsed`** (string or null), **`letterTemplateAutoPick`** (boolean), **`letterTemplateSelection`** (object with `name` and `index` for the chosen template, or null).
  - **`docxServiceBaseUrl`** (string): **Injected on every read** from server configuration (not stored from the client). Clients should use the value the API returns.
- **`formDefaults`** (object, optional): Default field values for the cover-letter form, including:
  - **`tone`** (string): Human-readable “tone” / personality label (often matches a `personalityProfiles[].name`). The **last used profile id** is `appSettings.last_personality_profile_used`, not the `tone` string.
  - Other fields such as `companyName`, `hiringManager`, `jobDescription`, `additionalInstructions`, `address`, `phoneNumber`, `resume`, `adSource`, etc. (all optional depending on what is stored).

**Canonical spec for `formDefaults`:** Letter `address` / `phoneNumber`, `tone` persistence paths, which `preferences` keys actually persist on `PUT`, and how generation uses `address` / `phone_number` are defined in [`FORM_DEFAULTS_ADDRESS_PHONE_BACKEND.md`](./FORM_DEFAULTS_ADDRESS_PHONE_BACKEND.md). That document is the **source of truth**; this section is an overview only.

**Personality (tone) summary:** The API returns custom profiles under `preferences.appSettings.personalityProfiles` (`id` + `name` + `description`), the last selected profile id under `preferences.appSettings.last_personality_profile_used`, and the form’s tone label under `preferences.formDefaults.tone` (and the same `tone` key is what the app uses for display defaults).

## Endpoints

### 1. Register User
**POST** `/api/users/register`

Register a new user account.

**Request Body:** `name`, `email`, `password`, and **`dataUseSharingNoticeAccepted`** (boolean, must be `true`) are required. Other fields are optional. If `preferences.appSettings.personalityProfiles` is missing or empty, the server assigns default profiles from `default_personality_profiles.json` (or a built-in fallback).

```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securePassword123",
  "dataUseSharingNoticeAccepted": true,
  "phone": "555-1234",
  "address": {
    "street": "123 Main St",
    "city": "Anytown",
    "state": "CA",
    "zip": "12345",
    "country": "USA"
  },
  "preferences": {
    "newsletterOptIn": true,
    "theme": "dark"
  }
}
```

**Response (201 Created):** A full [`UserResponse`](#user-response-shape-userresponse) object. Example (abbreviated `preferences`):

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "isActive": true,
  "isEmailVerified": false,
  "roles": ["user"],
  "phone": "555-1234",
  "address": {
    "street": "123 Main St",
    "city": "Anytown",
    "state": "CA",
    "zip": "12345",
    "country": "USA"
  },
  "preferences": {
    "newsletterOptIn": true,
    "theme": "dark",
    "appSettings": {
      "printProperties": { "margins": { "top": 1, "right": 0.75, "bottom": 0.25, "left": 0.75 }, "fontFamily": "Georgia", "fontSize": 11, "lineHeight": 1.15, "pageSize": { "width": 8.5, "height": 11 }, "useDefaultFonts": false },
      "personalityProfiles": [
        { "id": "professional-default", "name": "Professional", "description": "…" }
      ],
      "selectedModel": "claude-haiku-4-5",
      "lastResumeUsed": null,
      "last_personality_profile_used": null,
      "letterTemplateAutoPick": true,
      "letterTemplateSelection": null,
      "docxServiceBaseUrl": "https://api.saimonsoft.com"
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
  },
  "avatarUrl": null,
  "dateCreated": "2024-04-27T00:00:00.000Z",
  "dateUpdated": "2024-04-27T00:00:00.000Z",
  "lastLogin": null,
  "llm_counts": {},
  "last_llm_used": null,
  "generation_credits": 10,
  "max_credits": 10,
  "SMSOpt": "IN",
  "SMSOptDate": "2024-04-27T00:00:00.000Z",
  "subscriptionStatus": "free",
  "subscriptionPlan": "free",
  "subscriptionCurrentPeriodEnd": null,
  "super_user": false,
  "archived": false,
  "archived_at": null,
  "account_deletion_pending": false,
  "account_deletion_requested_at": null
}
```

Exact values for `selectedModel`, `docxServiceBaseUrl`, and default personality `id` / `name` / `description` depend on environment and on `default_personality_profiles.json`.

**Error Responses:**
- `400 Bad Request`: Data Use & Sharing Notice not accepted, weak password (when `ENFORCE_STRONG_PASSWORDS` is on), or validation error
- `409 Conflict`: Email already exists
- `503 Service Unavailable`: Database connection unavailable

---

### 2. Login User
**POST** `/api/users/login`

Authenticate user and return the same user payload as [`UserResponse`](#user-response-shape-userresponse) (including `preferences` with personality profiles, `last_personality_profile_used`, and `formDefaults.tone`), plus JWT-shaped **access** and **refresh** token strings for the client contract. Token verification behavior is implementation-dependent; see server code and auth middleware.

**Request Body:**
```json
{
  "email": "john@example.com",
  "password": "securePassword123"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "message": "Login successful",
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "name": "John Doe",
    "email": "john@example.com",
    "isActive": true,
    "isEmailVerified": false,
    "roles": ["user"],
    "phone": "555-1234",
    "address": { "street": "123 Main St", "city": "Anytown", "state": "CA", "zip": "12345", "country": "USA" },
    "preferences": {
      "newsletterOptIn": true,
      "theme": "dark",
      "appSettings": {
        "personalityProfiles": [
          { "id": "professional-default", "name": "Professional", "description": "…" }
        ],
        "last_personality_profile_used": "professional-default",
        "docxServiceBaseUrl": "https://api.saimonsoft.com"
      },
      "formDefaults": {
        "tone": "Professional"
      }
    },
    "avatarUrl": null,
    "dateCreated": "2024-04-27T00:00:00.000Z",
    "dateUpdated": "2024-04-27T00:00:00.000Z",
    "lastLogin": "2024-04-27T12:00:00.000Z",
    "llm_counts": { "claude-haiku-4-5": 3 },
    "last_llm_used": "claude-haiku-4-5",
    "generation_credits": 10,
    "max_credits": 10,
    "SMSOpt": "IN",
    "SMSOptDate": "2024-04-27T00:00:00.000Z",
    "subscriptionStatus": "free",
    "subscriptionPlan": "free",
    "subscriptionCurrentPeriodEnd": null,
    "super_user": false,
    "archived": false,
    "archived_at": null,
    "account_deletion_pending": false,
    "account_deletion_requested_at": null
  },
  "access_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI1MDdmMWY3N2JjZjg2Y2Q3OTk0MzkwMTEi...",
  "refresh_token": "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiI1MDdmMWY3N2JjZjg2Y2Q3OTk0MzkwMTEi...",
  "token_type": "bearer",
  "expires_in": 86400
}
```

The `user.preferences` object is the same normalized shape as for other user endpoints, including all `appSettings` and `formDefaults` keys that exist in the database (the sample above is abbreviated for readability; full registration defaults apply for new users—see the register example and [Preferences](#preferences-including-personality--tone)).

**Error Responses:**
- `401 Unauthorized`: Invalid email or password
- `403 Forbidden`: User account is inactive, or account deletion is already pending
- `503 Service Unavailable`: Database connection unavailable

---

### 3. Get User by ID
**GET** `/api/users/{user_id}`

Retrieve user information by MongoDB ObjectId.

**Path Parameters:**
- `user_id` (string): MongoDB ObjectId

**Response (200 OK):** Full [`UserResponse`](#user-response-shape-userresponse), including `preferences` with personality / tone fields as documented. Example fragment for LLM tracking:

```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "llm_counts": {
    "gpt-5.2": 15,
    "claude-sonnet-4-20250514": 8
  },
  "last_llm_used": "gpt-5.2"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid user ID format
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

---

### 4. Get User by Email
**GET** `/api/users/email/{email}`

Retrieve user information by email address.

**Path Parameters:**
- `email` (string): User's email address

**Response (200 OK):** Same as [Get User by ID](#3-get-user-by-id): full [`UserResponse`](#user-response-shape-userresponse) with the same `preferences` normalization (including `appSettings.personalityProfiles`, `last_personality_profile_used`, and `formDefaults.tone` when present).

**Error Responses:**
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

---

### 5. Update User
**PUT** `/api/users/{user_id}`

Update user information. Only provided fields will be updated.

**Path Parameters:**
- `user_id` (string): MongoDB ObjectId

**Request Body (all fields optional):**
```json
{
  "name": "John Smith",
  "email": "john.smith@example.com",
  "phone": "555-9999",
  "isActive": true,
  "isEmailVerified": true,
  "roles": ["user", "premium"],
  "address": {
    "street": "456 Oak Ave",
    "city": "Springfield",
    "state": "IL",
    "zip": "62701",
    "country": "USA"
  },
  "preferences": {
    "newsletterOptIn": false,
    "theme": "light",
    "appSettings": {
      "personalityProfiles": [
        { "id": "custom-1", "name": "Concise", "description": "Short, direct copy." }
      ],
      "last_personality_profile_used": "custom-1"
    },
    "formDefaults": {
      "tone": "Concise"
    }
  },
  "avatarUrl": "https://example.com/avatar.jpg",
  "last_llm_used": "gpt-5.2"
}
```

**Note**: The `llm_counts` field cannot be manually updated through the API. It is automatically managed by the system when LLMs are called. You can manually set `last_llm_used` if needed, but it is also automatically updated when LLMs are used. On every read, `user_doc_to_response` still injects `preferences.appSettings.docxServiceBaseUrl` from the server; clients should not assume they can persist that key.

**`preferences.formDefaults` on `PUT`:** Keys you send under `preferences.formDefaults` are merged with dotted `$set` paths (sibling keys preserved). Rules, limits, and types are in [`FORM_DEFAULTS_ADDRESS_PHONE_BACKEND.md`](./FORM_DEFAULTS_ADDRESS_PHONE_BACKEND.md).

**Response (200 OK):** Full updated [`UserResponse`](#user-response-shape-userresponse) (including normalized `personalityProfiles` on read: only `id`, `name`, `description` on each item).
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Smith",
  "email": "john.smith@example.com",
  "preferences": {
    "appSettings": {
      "personalityProfiles": [
        { "id": "custom-1", "name": "Concise", "description": "Short, direct copy." }
      ],
      "last_personality_profile_used": "custom-1",
      "docxServiceBaseUrl": "https://api.saimonsoft.com"
    },
    "formDefaults": { "tone": "Concise" }
  }
}
```

**Error Responses:**
- `400 Bad Request`: Invalid user ID format
- `404 Not Found`: User not found
- `409 Conflict`: Email already in use by another user
- `503 Service Unavailable`: Database connection unavailable

---

### 6. Delete User
**DELETE** `/api/users/{user_id}`

Delete a user account.

**Path Parameters:**
- `user_id` (string): MongoDB ObjectId

**Response (200 OK):**
```json
{
  "success": true,
  "message": "User deleted successfully"
}
```

**Error Responses:**
- `400 Bad Request`: Invalid user ID format
- `404 Not Found`: User not found
- `503 Service Unavailable`: Database connection unavailable

---

## React Integration Examples

### Register User
```javascript
const registerUser = async (userData) => {
  try {
    const response = await fetch('http://localhost:8000/api/users/register', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        name: userData.name,
        email: userData.email,
        password: userData.password,
        dataUseSharingNoticeAccepted: true,
        phone: userData.phone,
        address: userData.address,
        preferences: userData.preferences
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Registration failed');
    }
    
    const user = await response.json();
    return user;
  } catch (error) {
    console.error('Registration error:', error);
    throw error;
  }
};
```

### Login User
```javascript
const loginUser = async (email, password) => {
  try {
    const response = await fetch('http://localhost:8000/api/users/login', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ email, password })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }
    
    const result = await response.json();
    // result: { success, message, user, access_token, refresh_token, token_type, expires_in }
    return result;
  } catch (error) {
    console.error('Login error:', error);
    throw error;
  }
};
```

### Get User by ID
```javascript
const getUser = async (userId) => {
  try {
    const response = await fetch(`http://localhost:8000/api/users/${userId}`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    if (!response.ok) {
      throw new Error('Failed to fetch user');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Get user error:', error);
    throw error;
  }
};
```

### Update User
```javascript
const updateUser = async (userId, updates) => {
  try {
    const response = await fetch(`http://localhost:8000/api/users/${userId}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(updates)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Update failed');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Update user error:', error);
    throw error;
  }
};
```

### Delete User
```javascript
const deleteUser = async (userId) => {
  try {
    const response = await fetch(`http://localhost:8000/api/users/${userId}`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Delete failed');
    }
    
    return await response.json();
  } catch (error) {
    console.error('Delete user error:', error);
    throw error;
  }
};
```

## LLM Usage Tracking

The system automatically tracks LLM (Large Language Model) usage for each user:

### Automatic Tracking

When an LLM is successfully called through the API (e.g., `POST /api/job-info` or `POST /chat`), the system automatically:
- Increments the usage count for that LLM in `llm_counts`
- Updates `last_llm_used` to the name of the LLM that was just used

**Example**: After a successful call to `gpt-5.2`:
```json
{
  "llm_counts": {
    "gpt-5.2": 16  // Incremented from 15
  },
  "last_llm_used": "gpt-5.2"  // Updated
}
```

### Fields

- **llm_counts** (object): Dictionary of LLM names to usage counts
  - Automatically managed by the system
  - Cannot be manually updated through the API
  - Initialized as empty object `{}` for new users
  
- **last_llm_used** (string or null): Name of the most recently used LLM
  - Automatically updated when LLMs are called
  - Can be manually updated via PUT request if needed
  - Initialized as `null` for new users

### Retrieving Usage Data

Get user data including LLM usage statistics:
```bash
GET /api/users/{user_id}
```

Response includes:
```json
{
  "id": "...",
  "llm_counts": {
    "gpt-5.2": 15,
    "claude-sonnet-4-20250514": 8
  },
  "last_llm_used": "gpt-5.2"
}
```

### Manual Update

You can manually set `last_llm_used` (but not `llm_counts`):
```bash
PUT /api/users/{user_id}
Content-Type: application/json

{
  "last_llm_used": "gemini-2.5-flash"
}
```

**Note**: Manual updates to `last_llm_used` do not increment usage counts. Only actual LLM calls increment the counts.

For detailed documentation, see [LLM_USAGE_TRACKING_API.md](./LLM_USAGE_TRACKING_API.md).

## Security Notes

1. **Password Hashing**: Passwords are hashed using bcrypt before storage
2. **Email Validation**: Email addresses are validated using Pydantic's EmailStr
3. **No Password in Responses**: Passwords are never returned in API responses
4. **Failed Login Tracking**: Failed login attempts are tracked in the database
5. **Account Status**: Inactive accounts cannot log in
6. **Pending Deletion**: Users with a pending self-service account deletion may receive `403` on login; see the API error `detail` text

## Error Handling

All endpoints return appropriate HTTP status codes:
- `200 OK`: Successful operation
- `201 Created`: Resource created successfully
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Authentication failed
- `403 Forbidden`: Access denied
- `404 Not Found`: Resource not found
- `409 Conflict`: Resource conflict (e.g., email already exists)
- `422 Unprocessable Entity`: Validation error
- `503 Service Unavailable`: Database unavailable

Error responses follow this format:
```json
{
  "detail": "Error message description"
}
```

## Testing

You can test the API using:
- Postman
- curl
- Your React application
- The test script: `python test_user_crud.py`

Example curl commands:
```bash
# Register (dataUseSharingNoticeAccepted is required)
curl -X POST http://localhost:8000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"test123","dataUseSharingNoticeAccepted":true}'

# Login
curl -X POST http://localhost:8000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Get User
curl http://localhost:8000/api/users/{user_id}
```

