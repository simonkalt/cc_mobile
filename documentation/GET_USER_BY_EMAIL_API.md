# Get User by Email API - Frontend Implementation Guide

## Endpoint

**GET** `/api/users/email/{email}`

This is a **public endpoint** that does not require authentication. It allows checking if a user exists by email address.

## Request

- **Method**: `GET`
- **Authentication**: None required (public endpoint)
- **Path Parameter**: `email` - The user's email address (must be URL encoded)

## Response

### Success (200 OK) - User Exists

When a user is found, the endpoint returns a 200 OK status with the full user object:

```json
{
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
  "lastLogin": "2024-04-27T12:00:00.000Z",
  "llm_counts": {...},
  "last_llm_used": "gpt-4.1",
  "subscriptionStatus": "free",
  "subscriptionPlan": "free",
  ...
}
```

### Not Found (404) - User Does Not Exist

When a user is not found, the endpoint returns a 404 Not Found status:

```json
{
  "detail": "User not found"
}
```

### Service Unavailable (503)

If the database is unavailable:

```json
{
  "detail": "Database connection unavailable"
}
```

## Frontend Implementation

### Basic Implementation

```javascript
async getUserByEmail(email) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/users/email/${encodeURIComponent(email)}`
    );
    
    if (response.ok) {
      // User exists - return user object
      const user = await response.json();
      return user;
    } else if (response.status === 404) {
      // User doesn't exist - return null
      return null;
    } else {
      // Other error - throw
      const error = await response.json();
      throw new Error(error.detail || 'Failed to check user');
    }
  } catch (error) {
    // Network error or other exception
    throw error;
  }
}
```

### Using with Axios

```javascript
async getUserByEmail(email) {
  try {
    const response = await axios.get(
      `/api/users/email/${encodeURIComponent(email)}`
    );
    // User exists - return user object
    return response.data;
  } catch (error) {
    if (error.response?.status === 404) {
      // User doesn't exist - return null
      return null;
    }
    // Other error - re-throw
    throw error;
  }
}
```

### Usage Example

```javascript
// Check if email exists when user types email
useEffect(() => {
  if (!email.trim()) {
    setEmailExists(false);
    return;
  }

  // Basic email validation
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!emailRegex.test(email.trim())) {
    setEmailExists(false);
    return;
  }

  // Debounce the check
  const timeoutId = setTimeout(async () => {
    try {
      const user = await api.getUserByEmail(email.trim());
      
      // Check if user exists by checking for id field
      const exists = user && user.id;
      setEmailExists(exists);

      // Show modal if email exists
      if (exists) {
        setShowEmailExistsModal(true);
      }
    } catch (err) {
      // Error checking email - assume doesn't exist
      setEmailExists(false);
      console.error("Error checking email:", err);
    }
  }, 500);

  return () => clearTimeout(timeoutId);
}, [email]);
```

## Important Notes

1. **URL Encoding**: Always URL encode the email address when including it in the URL path:
   ```javascript
   encodeURIComponent(email)  // "user@example.com" -> "user%40example.com"
   ```

2. **Checking if User Exists**: Always check for the presence of an `id` field, not just truthiness:
   ```javascript
   // ✅ Correct
   const exists = user && user.id;
   
   // ❌ Wrong - object is always truthy
   const exists = !!user;
   ```

3. **Status Code Handling**:
   - `200 OK` = User exists (has `id` field)
   - `404 Not Found` = User doesn't exist (return `null`)
   - `503 Service Unavailable` = Database error (handle as error)

4. **No Authentication Required**: This endpoint is public and does not require any authentication tokens or headers.

## Error Handling

```javascript
async getUserByEmail(email) {
  try {
    const response = await fetch(
      `${API_BASE_URL}/api/users/email/${encodeURIComponent(email)}`
    );
    
    if (response.ok) {
      return await response.json();
    } else if (response.status === 404) {
      return null;  // User doesn't exist
    } else if (response.status === 503) {
      throw new Error('Service temporarily unavailable');
    } else {
      const error = await response.json();
      throw new Error(error.detail || 'Unknown error');
    }
  } catch (error) {
    // Handle network errors
    if (error.message) {
      throw error;
    }
    throw new Error('Network error: Could not connect to server');
  }
}
```

## Testing

### Test User Exists
```bash
curl http://localhost:8000/api/users/email/user@example.com
```

### Test User Doesn't Exist
```bash
curl http://localhost:8000/api/users/email/nonexistent@example.com
# Returns: 404 Not Found
```

### Test with URL Encoded Email
```bash
curl "http://localhost:8000/api/users/email/user%40example.com"
```

