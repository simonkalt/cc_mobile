# JWT Authentication - Postman Implementation Guide

This guide provides step-by-step instructions for testing JWT authentication in Postman.

## Table of Contents

1. [Setup](#setup)
2. [Login Request](#login-request)
3. [Storing Tokens](#storing-tokens)
4. [Using Tokens in Requests](#using-tokens-in-requests)
5. [Automatic Token Management](#automatic-token-management)
6. [Testing Protected Endpoints](#testing-protected-endpoints)
7. [Refresh Token Flow](#refresh-token-flow)
8. [Environment Variables](#environment-variables)
9. [Collection Setup](#collection-setup)

---

## Setup

### 1. Create a Postman Environment

1. Click the **Environments** icon in the left sidebar (or press `Ctrl+E`)
2. Click **+** to create a new environment
3. Name it "JWT Auth" (or your preferred name)
4. Add the following variables:

| Variable | Initial Value | Current Value |
|----------|---------------|---------------|
| `base_url` | `http://localhost:8000` | `http://localhost:8000` |
| `access_token` | (leave empty) | (leave empty) |
| `refresh_token` | (leave empty) | (leave empty) |
| `user_id` | (leave empty) | (leave empty) |

5. Click **Save**

6. Select your new environment from the environment dropdown (top right)

---

## Login Request

### 1. Create Login Request

1. Create a new request named "Login"
2. Set method to **POST**
3. Set URL to: `{{base_url}}/api/users/login`
4. Go to **Body** tab
5. Select **raw** and **JSON**
6. Enter the request body:

```json
{
  "email": "user@example.com",
  "password": "your_password"
}
```

### 2. Extract Tokens from Response

After creating the login request, we'll automatically save the tokens:

1. Go to the **Tests** tab in the Login request
2. Add the following script:

```javascript
// Check if login was successful
if (pm.response.code === 200) {
    const response = pm.response.json();
    
    // Save access token
    if (response.access_token) {
        pm.environment.set("access_token", response.access_token);
        console.log("Access token saved");
    }
    
    // Save refresh token
    if (response.refresh_token) {
        pm.environment.set("refresh_token", response.refresh_token);
        console.log("Refresh token saved");
    }
    
    // Save user ID (optional)
    if (response.user && response.user.id) {
        pm.environment.set("user_id", response.user.id);
        console.log("User ID saved");
    }
    
    // Test assertions
    pm.test("Login successful", function () {
        pm.response.to.have.status(200);
    });
    
    pm.test("Access token received", function () {
        pm.expect(response.access_token).to.exist;
    });
    
    pm.test("Refresh token received", function () {
        pm.expect(response.refresh_token).to.exist;
    });
} else {
    pm.test("Login failed", function () {
        pm.response.to.have.status(200);
    });
}
```

3. Click **Send**
4. Check the **Test Results** tab - you should see "Access token saved" and "Refresh token saved"
5. Verify tokens are saved: Go to your environment and check that `access_token` and `refresh_token` have values

---

## Using Tokens in Requests

### Method 1: Manual Authorization Header

1. Create a new request (e.g., "Get Current User")
2. Set method to **GET**
3. Set URL to: `{{base_url}}/api/users/me`
4. Go to **Authorization** tab
5. Select **Bearer Token** from Type dropdown
6. In the Token field, enter: `{{access_token}}`
7. Click **Send**

### Method 2: Using Authorization Tab (Recommended)

1. Create a new request
2. Go to **Authorization** tab
3. Select **Bearer Token** from Type dropdown
4. In the Token field, enter: `{{access_token}}`
5. Postman will automatically add the `Authorization: Bearer <token>` header

---

## Automatic Token Management

### Collection-Level Authorization

Set up automatic token injection for all requests in a collection:

1. Right-click your collection → **Edit**
2. Go to **Authorization** tab
3. Select **Bearer Token** from Type dropdown
4. In the Token field, enter: `{{access_token}}`
5. Click **Update**

Now all requests in this collection will automatically use the access token!

**Note**: You can override collection-level auth for specific requests if needed.

---

## Testing Protected Endpoints

### Example: Get Current User

1. Create a new request named "Get Current User"
2. Set method to **GET**
3. Set URL to: `{{base_url}}/api/users/me`
4. Authorization should be inherited from collection (or set manually as Bearer Token with `{{access_token}}`)
5. Add test script in **Tests** tab:

```javascript
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

pm.test("Response has user data", function () {
    const response = pm.response.json();
    pm.expect(response).to.have.property('id');
    pm.expect(response).to.have.property('email');
    pm.expect(response).to.have.property('name');
});

// Save user data if needed
if (pm.response.code === 200) {
    const user = pm.response.json();
    pm.environment.set("user_id", user.id);
}
```

6. Click **Send**

### Example: Update User

1. Create a new request named "Update User"
2. Set method to **PUT**
3. Set URL to: `{{base_url}}/api/users/{{user_id}}`
4. Go to **Body** tab → **raw** → **JSON**
5. Enter request body:

```json
{
  "name": "Updated Name",
  "phone": "555-1234"
}
```

6. Authorization should be set automatically (Bearer Token with `{{access_token}}`)
7. Click **Send**

---

## Refresh Token Flow

### Create Refresh Token Request

1. Create a new request named "Refresh Token"
2. Set method to **POST**
3. Set URL to: `{{base_url}}/api/users/refresh-token`
4. Go to **Body** tab → **raw** → **JSON**
5. Enter request body:

```json
{
  "refresh_token": "{{refresh_token}}"
}
```

6. Go to **Tests** tab and add:

```javascript
if (pm.response.code === 200) {
    const response = pm.response.json();
    
    // Save new access token
    if (response.access_token) {
        pm.environment.set("access_token", response.access_token);
        console.log("New access token saved");
    }
    
    pm.test("Token refreshed successfully", function () {
        pm.response.to.have.status(200);
        pm.expect(response.access_token).to.exist;
    });
} else {
    pm.test("Token refresh failed", function () {
        pm.response.to.have.status(200);
    });
}
```

7. Click **Send**

### Automatic Token Refresh on 401

You can create a Pre-request Script at the collection level to automatically refresh tokens:

1. Right-click your collection → **Edit**
2. Go to **Pre-request Script** tab
3. Add this script (optional - for advanced use):

```javascript
// This is a simple example - you may want to check token expiration first
// For production, consider checking token expiration before making requests

// Note: Postman doesn't automatically retry on 401, so this is just for reference
// You'll need to manually call the refresh token endpoint when you get a 401
```

**Better Approach**: Use the **Tests** tab in requests to handle 401 errors:

```javascript
if (pm.response.code === 401) {
    // Token expired - refresh it
    pm.sendRequest({
        url: pm.environment.get("base_url") + "/api/users/refresh-token",
        method: 'POST',
        header: {
            'Content-Type': 'application/json'
        },
        body: {
            mode: 'raw',
            raw: JSON.stringify({
                refresh_token: pm.environment.get("refresh_token")
            })
        }
    }, function (err, res) {
        if (res.code === 200) {
            const response = res.json();
            pm.environment.set("access_token", response.access_token);
            console.log("Token refreshed automatically");
            // Retry the original request
            // Note: You'll need to manually send the request again
        }
    });
}
```

---

## Environment Variables

### Recommended Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `base_url` | API base URL | `http://localhost:8000` |
| `access_token` | JWT access token | (auto-populated) |
| `refresh_token` | JWT refresh token | (auto-populated) |
| `user_id` | Current user ID | (auto-populated) |
| `user_email` | Current user email | (optional) |

### Setting Variables Programmatically

You can set variables in **Tests** scripts:

```javascript
pm.environment.set("variable_name", "value");
pm.collectionVariables.set("variable_name", "value"); // Collection-level
pm.globals.set("variable_name", "value"); // Global
```

---

## Collection Setup

### Complete Collection Structure

Create a collection with the following structure:

```
📁 JWT Auth Collection
  📁 Authentication
    📄 Login
    📄 Refresh Token
    📄 Get Current User
  📁 Users
    📄 Get User by ID
    📄 Update User
    📄 Delete User
  📁 Subscriptions
    📄 Create Payment Intent
    📄 Create Subscription
    ...
```

### Collection-Level Settings

1. **Authorization**: Bearer Token with `{{access_token}}`
2. **Pre-request Script**: (optional - for logging)
3. **Tests**: (optional - for common assertions)

---

## Testing Scenarios

### Scenario 1: Valid Token

1. Run "Login" request
2. Verify tokens are saved
3. Run "Get Current User" request
4. Should return 200 with user data

### Scenario 2: Expired Token

1. Wait for token to expire (or manually clear `access_token`)
2. Run any protected endpoint
3. Should return 401 Unauthorized
4. Run "Refresh Token" request
5. Verify new access token is saved
6. Retry the protected endpoint
7. Should now return 200

### Scenario 3: Invalid Token

1. Manually set `access_token` to an invalid value
2. Run a protected endpoint
3. Should return 401 Unauthorized

### Scenario 4: Missing Token

1. Clear `access_token` from environment
2. Run a protected endpoint
3. Should return 401 Unauthorized

---

## Tips and Best Practices

1. **Use Environment Variables**: Always use `{{variable_name}}` syntax for dynamic values

2. **Save Tokens Automatically**: Use Tests scripts to automatically save tokens from login/refresh responses

3. **Collection-Level Auth**: Set authorization at collection level to avoid repeating it in each request

4. **Test Scripts**: Add test scripts to verify responses and handle errors

5. **Organize Requests**: Group related requests in folders

6. **Documentation**: Add descriptions to requests explaining their purpose

7. **Variables**: Use different environments for development, staging, and production

---

## Example: Complete Request with Tests

### Request: Get Current User

**Method**: GET  
**URL**: `{{base_url}}/api/users/me`  
**Authorization**: Bearer Token `{{access_token}}`

**Tests Tab**:
```javascript
// Status code check
pm.test("Status code is 200", function () {
    pm.response.to.have.status(200);
});

// Response time check
pm.test("Response time is less than 500ms", function () {
    pm.expect(pm.response.responseTime).to.be.below(500);
});

// Response structure validation
pm.test("Response has required fields", function () {
    const response = pm.response.json();
    pm.expect(response).to.have.property('id');
    pm.expect(response).to.have.property('email');
    pm.expect(response).to.have.property('name');
    pm.expect(response).to.have.property('isActive');
});

// Save user ID
if (pm.response.code === 200) {
    const user = pm.response.json();
    pm.environment.set("user_id", user.id);
    console.log("User ID saved:", user.id);
}
```

---

## Troubleshooting

### Token Not Being Sent

- Check that Authorization is set to "Bearer Token"
- Verify `{{access_token}}` variable has a value
- Check collection-level authorization settings

### 401 Unauthorized Errors

- Verify token is valid and not expired
- Check token format in environment variable
- Try refreshing the token
- Verify the Authorization header format: `Bearer <token>`

### Variables Not Updating

- Check that you're using the correct environment
- Verify variable names match exactly (case-sensitive)
- Check Tests script syntax for saving variables

---

## Additional Resources

- [Postman Documentation](https://learning.postman.com/docs/)
- [Postman Scripting](https://learning.postman.com/docs/writing-scripts/intro-to-scripts/)
- [JWT.io](https://jwt.io/) - Decode and verify JWT tokens

