# JWT Authentication API Documentation

This document describes how to implement JWT (JSON Web Token) authentication for the API using OAuth2-style Bearer tokens.

## Overview

The API uses JWT tokens for authentication. When a user logs in, they receive:
- **Access Token**: Short-lived token (default: 24 hours) for API requests
- **Refresh Token**: Long-lived token (default: 30 days) for obtaining new access tokens

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Authentication Flow

1. **User Login** → Receive access token and refresh token
2. **API Requests** → Include access token in Authorization header
3. **Token Expires** → Use refresh token to get new access token
4. **Refresh Token Expires** → User must login again

---

## Endpoints

### 1. Login

**POST** `/api/users/login`

Authenticate user and receive JWT tokens.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

**Response (200 OK):**
```json
{
  "success": true,
  "user": {
    "id": "507f1f77bcf86cd799439011",
    "name": "John Doe",
    "email": "user@example.com",
    "isActive": true,
    "isEmailVerified": false,
    "roles": ["user"],
    ...
  },
  "message": "Login successful",
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**
- `401 Unauthorized`: Invalid email or password
- `403 Forbidden`: User account is inactive
- `503 Service Unavailable`: Database connection unavailable

---

### 2. Refresh Access Token

**POST** `/api/users/refresh-token`

Get a new access token using a refresh token.

**Request Body:**
```json
{
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
}
```

**Response (200 OK):**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer"
}
```

**Error Responses:**
- `400 Bad Request`: Missing or invalid refresh_token field
- `401 Unauthorized`: Invalid or expired refresh token

---

### 3. Get Current User

**GET** `/api/users/me`

Get the current authenticated user's information.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response (200 OK):**
```json
{
  "id": "507f1f77bcf86cd799439011",
  "name": "John Doe",
  "email": "user@example.com",
  "isActive": true,
  ...
}
```

**Error Responses:**
- `401 Unauthorized`: Missing or invalid token
- `403 Forbidden`: User account is inactive

---

## Protected Endpoints

All endpoints that require authentication will return `401 Unauthorized` if:
- No `Authorization` header is provided
- The token is invalid or expired
- The token format is incorrect

To use protected endpoints, include the access token in the request header:

```
Authorization: Bearer <your_access_token>
```

---

## Token Structure

JWT tokens contain the following claims:
- `sub`: User ID (subject)
- `email`: User email address
- `exp`: Token expiration timestamp
- `iat`: Token issued at timestamp
- `type`: Token type ("access" or "refresh")

---

## Environment Variables

The following environment variables can be configured:

- `JWT_SECRET_KEY`: Secret key for signing tokens (default: "your-secret-key-change-in-production")
- `JWT_ALGORITHM`: Algorithm for token signing (default: "HS256")
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`: Access token expiration in minutes (default: 1440 = 24 hours)
- `JWT_REFRESH_TOKEN_EXPIRE_DAYS`: Refresh token expiration in days (default: 30)

**⚠️ Important:** Always set a strong `JWT_SECRET_KEY` in production!

---

## Security Best Practices

1. **Store tokens securely**: Never store tokens in localStorage if your app is vulnerable to XSS attacks. Consider using httpOnly cookies or secure storage.

2. **HTTPS only**: Always use HTTPS in production to protect tokens in transit.

3. **Token expiration**: Access tokens expire after 24 hours by default. Use refresh tokens to obtain new access tokens.

4. **Refresh token rotation**: Consider implementing refresh token rotation for enhanced security.

5. **Logout**: When logging out, invalidate tokens on the client side. For enhanced security, consider implementing token blacklisting on the server.

---

## Example Protected Endpoint Usage

```javascript
// Example: Making an authenticated request
const response = await fetch('http://localhost:8000/api/users/me', {
  method: 'GET',
  headers: {
    'Authorization': `Bearer ${accessToken}`,
    'Content-Type': 'application/json'
  }
});

if (response.status === 401) {
  // Token expired or invalid - try refreshing
  const newToken = await refreshAccessToken();
  // Retry request with new token
}
```

---

## Error Handling

### 401 Unauthorized
- Token is missing, invalid, or expired
- Solution: Login again or refresh the token

### 403 Forbidden
- User account is inactive
- Solution: Contact support to activate account

### 400 Bad Request
- Invalid request format
- Solution: Check request body format

---

## Next Steps

See the following documentation for implementation examples:
- [Frontend JWT Implementation Guide](./JWT_FRONTEND_IMPLEMENTATION.md)
- [Postman JWT Implementation Guide](./JWT_POSTMAN_IMPLEMENTATION.md)

