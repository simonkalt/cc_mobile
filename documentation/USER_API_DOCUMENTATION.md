# User API Documentation

RESTful API endpoints for user registration and CRUD operations.

## Base URL
```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoints

### 1. Register User
**POST** `/api/users/register`

Register a new user account.

**Request Body:**
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securePassword123",
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

**Response (201 Created):**
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
    "theme": "dark"
  },
  "avatarUrl": null,
  "dateCreated": "2024-04-27T00:00:00.000Z",
  "dateUpdated": "2024-04-27T00:00:00.000Z",
  "lastLogin": null,
  "llm_counts": {},
  "last_llm_used": null
}
```

**Error Responses:**
- `409 Conflict`: Email already exists
- `503 Service Unavailable`: Database connection unavailable

---

### 2. Login User
**POST** `/api/users/login`

Authenticate user and return user information.

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
    "address": {...},
    "preferences": {...},
    "avatarUrl": null,
    "dateCreated": "2024-04-27T00:00:00.000Z",
    "dateUpdated": "2024-04-27T00:00:00.000Z",
    "lastLogin": "2024-04-27T12:00:00.000Z"
  }
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid email or password
- `403 Forbidden`: User account is inactive
- `503 Service Unavailable`: Database connection unavailable

---

### 3. Get User by ID
**GET** `/api/users/{user_id}`

Retrieve user information by MongoDB ObjectId.

**Path Parameters:**
- `user_id` (string): MongoDB ObjectId

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "llm_counts": {
    "gpt-4.1": 15,
    "claude-sonnet-4-20250514": 8
  },
  "last_llm_used": "gpt-4.1",
  ...
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

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "john@example.com",
  "llm_counts": {
    "gpt-4.1": 15,
    "claude-sonnet-4-20250514": 8
  },
  "last_llm_used": "gpt-4.1",
  ...
}
```

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
    "theme": "light"
  },
  "avatarUrl": "https://example.com/avatar.jpg",
  "last_llm_used": "gpt-4.1"
}
```

**Note**: The `llm_counts` field cannot be manually updated through the API. It is automatically managed by the system when LLMs are called. You can manually set `last_llm_used` if needed, but it is also automatically updated when LLMs are used.

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Smith",
  "email": "john.smith@example.com",
  ...
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
    return result.user;
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

**Example**: After a successful call to `gpt-4.1`:
```json
{
  "llm_counts": {
    "gpt-4.1": 16  // Incremented from 15
  },
  "last_llm_used": "gpt-4.1"  // Updated
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
    "gpt-4.1": 15,
    "claude-sonnet-4-20250514": 8
  },
  "last_llm_used": "gpt-4.1"
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
# Register
curl -X POST http://localhost:8000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"test123"}'

# Login
curl -X POST http://localhost:8000/api/users/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123"}'

# Get User
curl http://localhost:8000/api/users/{user_id}
```

