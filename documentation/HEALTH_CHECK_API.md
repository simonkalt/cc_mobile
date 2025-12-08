# Health Check API Documentation

API endpoint for checking if the server is ready to load user preferences. This endpoint verifies that all required services (MongoDB connection and users collection) are accessible.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoint

### Health Check

**GET** `/api/health`

Checks if the server is ready by verifying:
- MongoDB module is available
- MongoDB connection is active
- Users collection is accessible

This endpoint is designed to be called at intervals by the client to confirm the server is operational.

**Request:**

No parameters required. Simple GET request.

**Response (200 OK - Server Ready):**

```json
{
  "ready": true,
  "mongodb": {
    "available": true,
    "connected": true,
    "collection_accessible": true
  },
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

**Response (503 Service Unavailable - Server Not Ready):**

```json
{
  "ready": false,
  "mongodb": {
    "available": false,
    "connected": false,
    "collection_accessible": false
  },
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

**Response Fields:**

- `ready`: Boolean indicating if the server is ready to load user preferences
- `mongodb`: Object containing MongoDB status details
  - `available`: Boolean - MongoDB module is available
  - `connected`: Boolean - MongoDB connection is active
  - `collection_accessible`: Boolean - Users collection can be accessed
- `timestamp`: ISO 8601 timestamp of when the health check was performed
- `error`: (optional) Error message if an unexpected error occurred

**HTTP Status Codes:**

- `200 OK`: Server is ready - all services are operational
- `503 Service Unavailable`: Server is not ready - one or more services are unavailable

---

## Client-Side Implementation Examples

### JavaScript/React Example

```javascript
// Function to check if server is ready
async function checkServerHealth() {
  const API_BASE_URL = "http://localhost:8000"; // or your production URL

  try {
    const response = await fetch(`${API_BASE_URL}/api/health`, {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    });

    const healthStatus = await response.json();

    if (response.ok && healthStatus.ready) {
      console.log("Server is ready");
      return true;
    } else {
      console.warn("Server is not ready:", healthStatus);
      return false;
    }
  } catch (error) {
    console.error("Error checking server health:", error);
    return false;
  }
}

// Usage - check server health
checkServerHealth().then((isReady) => {
  if (isReady) {
    console.log("Server is ready to load user preferences");
  } else {
    console.log("Server is not ready, retrying...");
  }
});
```

### React Component Example with Polling

```jsx
import React, { useState, useEffect } from "react";

function ServerHealthChecker({ onReady, onNotReady, interval = 5000 }) {
  const [healthStatus, setHealthStatus] = useState(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/health");
        const status = await response.json();

        setHealthStatus(status);
        setIsReady(status.ready);

        if (status.ready && onReady) {
          onReady();
        } else if (!status.ready && onNotReady) {
          onNotReady(status);
        }
      } catch (error) {
        console.error("Health check failed:", error);
        setIsReady(false);
        if (onNotReady) {
          onNotReady({ error: error.message });
        }
      }
    };

    // Check immediately
    checkHealth();

    // Then check at intervals
    const intervalId = setInterval(checkHealth, interval);

    return () => clearInterval(intervalId);
  }, [interval, onReady, onNotReady]);

  return (
    <div>
      {healthStatus && (
        <div>
          <p>
            Server Status:{" "}
            <span style={{ color: isReady ? "green" : "red" }}>
              {isReady ? "Ready" : "Not Ready"}
            </span>
          </p>
          {healthStatus.mongodb && (
            <details>
              <summary>MongoDB Status</summary>
              <ul>
                <li>Available: {healthStatus.mongodb.available ? "✓" : "✗"}</li>
                <li>Connected: {healthStatus.mongodb.connected ? "✓" : "✗"}</li>
                <li>
                  Collection Accessible:{" "}
                  {healthStatus.mongodb.collection_accessible ? "✓" : "✗"}
                </li>
              </ul>
            </details>
          )}
        </div>
      )}
    </div>
  );
}

// Usage
function App() {
  const handleServerReady = () => {
    console.log("Server is ready, loading user preferences...");
    // Load user preferences here
  };

  const handleServerNotReady = (status) => {
    console.warn("Server not ready:", status);
    // Show error message or retry
  };

  return (
    <div>
      <ServerHealthChecker
        onReady={handleServerReady}
        onNotReady={handleServerNotReady}
        interval={5000} // Check every 5 seconds
      />
      {/* Rest of your app */}
    </div>
  );
}

export default App;
```

### React Native Example

```javascript
import { useEffect, useState } from "react";
import { View, Text, ActivityIndicator } from "react-native";

function useServerHealth(interval = 5000) {
  const [isReady, setIsReady] = useState(false);
  const [healthStatus, setHealthStatus] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch("http://localhost:8000/api/health");
        const status = await response.json();

        setHealthStatus(status);
        setIsReady(status.ready);
        setLoading(false);
      } catch (error) {
        console.error("Health check failed:", error);
        setIsReady(false);
        setLoading(false);
      }
    };

    // Check immediately
    checkHealth();

    // Then check at intervals
    const intervalId = setInterval(checkHealth, interval);

    return () => clearInterval(intervalId);
  }, [interval]);

  return { isReady, healthStatus, loading };
}

// Usage in component
function App() {
  const { isReady, healthStatus, loading } = useServerHealth(5000);

  if (loading) {
    return (
      <View>
        <ActivityIndicator />
        <Text>Checking server status...</Text>
      </View>
    );
  }

  if (!isReady) {
    return (
      <View>
        <Text style={{ color: "red" }}>Server is not ready</Text>
        <Text>MongoDB Available: {healthStatus?.mongodb?.available ? "Yes" : "No"}</Text>
        <Text>MongoDB Connected: {healthStatus?.mongodb?.connected ? "Yes" : "No"}</Text>
      </View>
    );
  }

  return (
    <View>
      <Text style={{ color: "green" }}>Server is ready!</Text>
      {/* Load user preferences and render app */}
    </View>
  );
}
```

### Simple Polling Example

```javascript
// Simple function to poll server health until ready
async function waitForServerReady(maxAttempts = 10, interval = 2000) {
  const API_BASE_URL = "http://localhost:8000";

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      const response = await fetch(`${API_BASE_URL}/api/health`);
      const healthStatus = await response.json();

      if (healthStatus.ready) {
        console.log(`Server is ready after ${attempt} attempt(s)`);
        return true;
      }

      console.log(`Attempt ${attempt}/${maxAttempts}: Server not ready yet...`);
      
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, interval));
      }
    } catch (error) {
      console.error(`Attempt ${attempt} failed:`, error);
      if (attempt < maxAttempts) {
        await new Promise((resolve) => setTimeout(resolve, interval));
      }
    }
  }

  console.error("Server did not become ready after maximum attempts");
  return false;
}

// Usage
waitForServerReady(10, 2000).then((ready) => {
  if (ready) {
    // Load user preferences
    loadUserPreferences();
  } else {
    // Show error to user
    showError("Server is not available. Please try again later.");
  }
});
```

---

## Integration with User Preferences Loading

Here's how to integrate the health check with loading user preferences:

```javascript
async function loadUserPreferencesWithHealthCheck(userId) {
  const API_BASE_URL = "http://localhost:8000";

  // First, check if server is ready
  try {
    const healthResponse = await fetch(`${API_BASE_URL}/api/health`);
    const healthStatus = await healthResponse.json();

    if (!healthStatus.ready) {
      throw new Error("Server is not ready to load user preferences");
    }

    // Server is ready, now load user preferences
    const userResponse = await fetch(`${API_BASE_URL}/api/users/${userId}`);
    
    if (!userResponse.ok) {
      throw new Error("Failed to load user preferences");
    }

    const userData = await userResponse.json();
    return userData.preferences;
  } catch (error) {
    console.error("Error loading user preferences:", error);
    throw error;
  }
}
```

---

## Best Practices

1. **Polling Interval**: Use a reasonable polling interval (e.g., 5-10 seconds) to avoid excessive server load
2. **Exponential Backoff**: If the server is not ready, consider using exponential backoff for retries
3. **Timeout**: Set a maximum timeout for health checks to avoid hanging
4. **User Feedback**: Show appropriate loading/error messages to users while checking server status
5. **Graceful Degradation**: If the server is not ready, provide fallback behavior or cached data if available
6. **Error Handling**: Always handle network errors and unexpected responses gracefully

---

## Testing

You can test the endpoint using curl:

```bash
curl -X GET http://localhost:8000/api/health
```

Expected response when server is ready:

```json
{
  "ready": true,
  "mongodb": {
    "available": true,
    "connected": true,
    "collection_accessible": true
  },
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

Expected response when server is not ready:

```json
{
  "ready": false,
  "mongodb": {
    "available": false,
    "connected": false,
    "collection_accessible": false
  },
  "timestamp": "2024-01-15T10:30:00.123456"
}
```

---

## Notes

- This endpoint is lightweight and designed for frequent polling
- The endpoint performs minimal operations to verify server readiness
- MongoDB connection is checked using a ping operation
- Users collection accessibility is verified with a lightweight count operation
- The endpoint returns detailed status information to help diagnose issues
- All checks must pass for the server to be considered "ready"

