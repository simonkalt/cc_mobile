# JWT Authentication - Frontend Implementation Guide

This guide provides step-by-step instructions for implementing JWT authentication in a React frontend application.

## Table of Contents

1. [Setup](#setup)
2. [Authentication Service](#authentication-service)
3. [Token Storage](#token-storage)
4. [API Client Configuration](#api-client-configuration)
5. [Protected Routes](#protected-routes)
6. [Login Component](#login-component)
7. [Token Refresh](#token-refresh)
8. [Logout](#logout)
9. [Complete Example](#complete-example)

---

## Setup

### Install Dependencies

No additional dependencies are required if you're using `fetch` or `axios`. The examples below use `axios`.

```bash
npm install axios
# or
yarn add axios
```

---

## Authentication Service

Create an authentication service to handle login, token management, and API calls.

### `src/services/authService.js`

```javascript
import axios from "axios";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// Token storage keys
const ACCESS_TOKEN_KEY = "access_token";
const REFRESH_TOKEN_KEY = "refresh_token";
const USER_KEY = "user";

/**
 * Store tokens and user data
 */
export const setAuthTokens = (accessToken, refreshToken, user) => {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
};

/**
 * Get stored access token
 */
export const getAccessToken = () => {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
};

/**
 * Get stored refresh token
 */
export const getRefreshToken = () => {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
};

/**
 * Get stored user data
 */
export const getUser = () => {
  const userStr = localStorage.getItem(USER_KEY);
  return userStr ? JSON.parse(userStr) : null;
};

/**
 * Clear all auth data
 */
export const clearAuth = () => {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
};

/**
 * Check if user is authenticated
 */
export const isAuthenticated = () => {
  return !!getAccessToken();
};

/**
 * Login user
 */
export const login = async (email, password) => {
  try {
    const response = await axios.post(`${API_BASE_URL}/api/users/login`, {
      email,
      password,
    });

    if (response.data.success && response.data.access_token) {
      setAuthTokens(
        response.data.access_token,
        response.data.refresh_token,
        response.data.user
      );
      return {
        success: true,
        user: response.data.user,
      };
    } else {
      throw new Error("Login failed");
    }
  } catch (error) {
    if (error.response) {
      const status = error.response.status;
      if (status === 401) {
        throw new Error("Invalid email or password");
      } else if (status === 403) {
        throw new Error("Account is inactive. Please contact support.");
      } else {
        throw new Error(error.response.data.detail || "Login failed");
      }
    }
    throw new Error("Network error: Could not connect to server");
  }
};

/**
 * Refresh access token
 */
export const refreshAccessToken = async () => {
  const refreshToken = getRefreshToken();

  if (!refreshToken) {
    throw new Error("No refresh token available");
  }

  try {
    const response = await axios.post(
      `${API_BASE_URL}/api/users/refresh-token`,
      {
        refresh_token: refreshToken,
      }
    );

    if (response.data.access_token) {
      localStorage.setItem(ACCESS_TOKEN_KEY, response.data.access_token);
      return response.data.access_token;
    } else {
      throw new Error("Failed to refresh token");
    }
  } catch (error) {
    // Refresh token expired or invalid - clear auth and redirect to login
    clearAuth();
    throw new Error("Session expired. Please login again.");
  }
};

/**
 * Logout user
 */
export const logout = () => {
  clearAuth();
  // Redirect to login page
  window.location.href = "/login";
};
```

---

## API Client Configuration

Configure your API client to automatically include the access token in requests and handle token refresh.

### `src/services/apiClient.js`

```javascript
import axios from "axios";
import { getAccessToken, refreshAccessToken, clearAuth } from "./authService";

const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// Create axios instance
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 30000,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor - Add access token to all requests
apiClient.interceptors.request.use(
  (config) => {
    const token = getAccessToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor - Handle token refresh on 401 errors
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  async (error) => {
    const originalRequest = error.config;

    // If error is 401 and we haven't already tried to refresh
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true;

      try {
        // Try to refresh the token
        const newAccessToken = await refreshAccessToken();

        // Update the authorization header with new token
        originalRequest.headers.Authorization = `Bearer ${newAccessToken}`;

        // Retry the original request
        return apiClient(originalRequest);
      } catch (refreshError) {
        // Refresh failed - clear auth and redirect to login
        clearAuth();
        window.location.href = "/login";
        return Promise.reject(refreshError);
      }
    }

    return Promise.reject(error);
  }
);

export default apiClient;
```

---

## Protected Routes

Create a component to protect routes that require authentication.

### `src/components/ProtectedRoute.jsx`

```javascript
import React from "react";
import { Navigate } from "react-router-dom";
import { isAuthenticated } from "../services/authService";

const ProtectedRoute = ({ children }) => {
  if (!isAuthenticated()) {
    // Redirect to login if not authenticated
    return <Navigate to="/login" replace />;
  }

  return children;
};

export default ProtectedRoute;
```

### Usage in Router

```javascript
import { BrowserRouter, Routes, Route } from "react-router-dom";
import ProtectedRoute from "./components/ProtectedRoute";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />
      </Routes>
    </BrowserRouter>
  );
}
```

---

## Login Component

Example login component using the authentication service.

### `src/pages/Login.jsx`

```javascript
import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { login } from "../services/authService";

const Login = () => {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);

    try {
      const result = await login(email, password);
      if (result.success) {
        // Redirect to dashboard or home page
        navigate("/dashboard");
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="login-container">
      <form onSubmit={handleSubmit}>
        <h2>Login</h2>

        {error && <div className="error-message">{error}</div>}

        <div>
          <label>Email:</label>
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </div>

        <div>
          <label>Password:</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </div>

        <button type="submit" disabled={loading}>
          {loading ? "Logging in..." : "Login"}
        </button>
      </form>
    </div>
  );
};

export default Login;
```

---

## Token Refresh

The API client automatically handles token refresh when a 401 error occurs. However, you can also proactively refresh tokens before they expire.

### Proactive Token Refresh

```javascript
import { getAccessToken, refreshAccessToken } from "./services/authService";
import jwt_decode from "jwt-decode"; // npm install jwt-decode

/**
 * Check if token is about to expire and refresh if needed
 */
export const checkAndRefreshToken = async () => {
  const token = getAccessToken();

  if (!token) {
    return null;
  }

  try {
    // Decode token to check expiration
    const decoded = jwt_decode(token);
    const currentTime = Date.now() / 1000;

    // If token expires in less than 5 minutes, refresh it
    if (decoded.exp - currentTime < 300) {
      console.log("Token expiring soon, refreshing...");
      return await refreshAccessToken();
    }

    return token;
  } catch (error) {
    console.error("Error checking token:", error);
    return null;
  }
};
```

---

## Logout

### Logout Component

```javascript
import React from "react";
import { useNavigate } from "react-router-dom";
import { logout } from "../services/authService";

const LogoutButton = () => {
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return <button onClick={handleLogout}>Logout</button>;
};

export default LogoutButton;
```

---

## Complete Example

### Making Authenticated API Calls

```javascript
import React, { useEffect, useState } from "react";
import apiClient from "../services/apiClient";
import { getUser } from "../services/authService";

const Dashboard = () => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUserData = async () => {
      try {
        // Option 1: Use the /me endpoint
        const response = await apiClient.get("/api/users/me");
        setUser(response.data);

        // Option 2: Use stored user data
        // const storedUser = getUser();
        // setUser(storedUser);
      } catch (error) {
        console.error("Error fetching user data:", error);
      } finally {
        setLoading(false);
      }
    };

    fetchUserData();
  }, []);

  if (loading) {
    return <div>Loading...</div>;
  }

  return (
    <div>
      <h1>Welcome, {user?.name}!</h1>
      <p>Email: {user?.email}</p>
      {/* Your dashboard content */}
    </div>
  );
};

export default Dashboard;
```

---

## Best Practices

1. **Secure Storage**: Consider using httpOnly cookies or secure storage mechanisms for production apps vulnerable to XSS.

2. **Token Expiration Handling**: The interceptor automatically handles token refresh, but you can also implement proactive refresh.

3. **Error Handling**: Always handle authentication errors gracefully and redirect to login when necessary.

4. **Loading States**: Show loading indicators during authentication operations.

5. **User Feedback**: Provide clear error messages for authentication failures.

---

## Environment Variables

Create a `.env` file in your React app root:

```env
REACT_APP_API_URL=http://localhost:8000
```

For production:

```env
REACT_APP_API_URL=https://your-api-domain.com
```

---

## Additional Resources

- [Axios Documentation](https://axios-http.com/docs/intro)
- [React Router Documentation](https://reactrouter.com/)
- [JWT.io](https://jwt.io/) - JWT token decoder and debugger
