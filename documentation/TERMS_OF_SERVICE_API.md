# Terms of Service API Documentation

API endpoint for retrieving the Terms of Service PDF document from S3. This is a public endpoint that requires no authentication.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoint

### Get Terms of Service PDF

**GET** `/api/files/terms-of-service`

Retrieves the Terms of Service PDF document from S3. This endpoint is public and requires no authentication or credentials.

**Request:**

- Method: `GET`
- Headers: None required
- Authentication: None required (public endpoint)
- Query Parameters: None

**Response (200 OK):**

The response is a PDF file with the following headers:

- `Content-Type: application/pdf`
- `Content-Disposition: inline; filename="Terms of Service.pdf"`

**Response Body:**

The response body contains the PDF file as binary data.

**Error Responses:**

- `503 Service Unavailable`: S3 service is not available (boto3 not installed)
- `500 Internal Server Error`: Failed to retrieve the PDF from S3

**Error Response Format:**

```json
{
  "detail": "Failed to retrieve Terms of Service: [error message]"
}
```

## React/JavaScript Implementation Examples

### Using Fetch API

#### Basic Example

```javascript
const fetchTermsOfService = async () => {
  try {
    const response = await fetch("http://localhost:8000/api/files/terms-of-service", {
      method: "GET",
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || "Failed to fetch Terms of Service");
    }

    // Get the PDF blob
    const pdfBlob = await response.blob();
    
    // Create a URL for the blob
    const pdfUrl = URL.createObjectURL(pdfBlob);
    
    // Open in new window or download
    window.open(pdfUrl, "_blank");
    
    // Clean up the URL after use (optional)
    // URL.revokeObjectURL(pdfUrl);
    
    return pdfBlob;
  } catch (error) {
    console.error("Error fetching Terms of Service:", error);
    throw error;
  }
};
```

#### Display PDF in iframe

```javascript
const TermsOfServiceViewer = () => {
  const [pdfUrl, setPdfUrl] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadTermsOfService = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const response = await fetch("http://localhost:8000/api/files/terms-of-service");
      
      if (!response.ok) {
        throw new Error("Failed to load Terms of Service");
      }
      
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      setPdfUrl(url);
    } catch (err) {
      setError(err.message);
      console.error("Error loading Terms of Service:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTermsOfService();
    
    // Cleanup: revoke URL when component unmounts
    return () => {
      if (pdfUrl) {
        URL.revokeObjectURL(pdfUrl);
      }
    };
  }, []);

  if (loading) return <div>Loading Terms of Service...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!pdfUrl) return null;

  return (
    <iframe
      src={pdfUrl}
      width="100%"
      height="600px"
      title="Terms of Service"
      style={{ border: "none" }}
    />
  );
};
```

#### Download PDF

```javascript
const downloadTermsOfService = async () => {
  try {
    const response = await fetch("http://localhost:8000/api/files/terms-of-service");
    
    if (!response.ok) {
      throw new Error("Failed to download Terms of Service");
    }
    
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    
    // Create a temporary anchor element and trigger download
    const link = document.createElement("a");
    link.href = url;
    link.download = "Terms of Service.pdf";
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    
    // Clean up
    URL.revokeObjectURL(url);
  } catch (error) {
    console.error("Error downloading Terms of Service:", error);
    alert("Failed to download Terms of Service. Please try again.");
  }
};
```

### Using Axios

```javascript
import axios from "axios";

const API_BASE_URL = "http://localhost:8000";

const fetchTermsOfService = async () => {
  try {
    const response = await axios.get(
      `${API_BASE_URL}/api/files/terms-of-service`,
      {
        responseType: "blob", // Important: specify blob response type
      }
    );

    // Create blob URL
    const blob = new Blob([response.data], { type: "application/pdf" });
    const url = URL.createObjectURL(blob);
    
    // Open in new window
    window.open(url, "_blank");
    
    return blob;
  } catch (error) {
    console.error("Error fetching Terms of Service:", error);
    if (error.response) {
      throw new Error(
        error.response.data?.detail || "Failed to fetch Terms of Service"
      );
    }
    throw error;
  }
};
```

### React Component Example

```javascript
import React, { useState } from "react";

const TermsOfServiceButton = () => {
  const [loading, setLoading] = useState(false);

  const handleViewTerms = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        "http://localhost:8000/api/files/terms-of-service"
      );

      if (!response.ok) {
        throw new Error("Failed to load Terms of Service");
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      
      // Open PDF in new tab
      const newWindow = window.open(url, "_blank");
      
      // Clean up URL after window is closed (optional)
      if (newWindow) {
        newWindow.addEventListener("beforeunload", () => {
          URL.revokeObjectURL(url);
        });
      }
    } catch (error) {
      console.error("Error:", error);
      alert("Failed to load Terms of Service. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <button onClick={handleViewTerms} disabled={loading}>
      {loading ? "Loading..." : "View Terms of Service"}
    </button>
  );
};

export default TermsOfServiceButton;
```

### React Native Example

```javascript
import React, { useState } from "react";
import { View, Button, Alert, Linking } from "react-native";
import * as FileSystem from "expo-file-system";

const TermsOfServiceButton = () => {
  const [loading, setLoading] = useState(false);

  const handleViewTerms = async () => {
    setLoading(true);
    try {
      const response = await fetch(
        "http://localhost:8000/api/files/terms-of-service"
      );

      if (!response.ok) {
        throw new Error("Failed to load Terms of Service");
      }

      const blob = await response.blob();
      
      // Convert blob to base64 for React Native
      const reader = new FileReader();
      reader.readAsDataURL(blob);
      
      reader.onloadend = async () => {
        const base64data = reader.result;
        
        // Save to file system
        const fileUri = `${FileSystem.documentDirectory}Terms_of_Service.pdf`;
        await FileSystem.writeAsStringAsync(fileUri, base64data, {
          encoding: FileSystem.EncodingType.Base64,
        });
        
        // Open with default PDF viewer
        const canOpen = await Linking.canOpenURL(fileUri);
        if (canOpen) {
          await Linking.openURL(fileUri);
        } else {
          Alert.alert("Error", "Cannot open PDF file");
        }
      };
    } catch (error) {
      console.error("Error:", error);
      Alert.alert("Error", "Failed to load Terms of Service");
    } finally {
      setLoading(false);
    }
  };

  return (
    <View>
      <Button
        title={loading ? "Loading..." : "View Terms of Service"}
        onPress={handleViewTerms}
        disabled={loading}
      />
    </View>
  );
};

export default TermsOfServiceButton;
```

### Complete React Hook Example

```javascript
import { useState, useCallback } from "react";

const useTermsOfService = (baseUrl = "http://localhost:8000") => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchTermsOfService = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${baseUrl}/api/files/terms-of-service`);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to fetch Terms of Service");
      }
      
      const blob = await response.blob();
      return blob;
    } catch (err) {
      const errorMessage = err.message || "Unknown error occurred";
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [baseUrl]);

  const viewTermsOfService = useCallback(async () => {
    try {
      const blob = await fetchTermsOfService();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      
      // Clean up after a delay (optional)
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      console.error("Error viewing Terms of Service:", err);
    }
  }, [fetchTermsOfService]);

  const downloadTermsOfService = useCallback(async () => {
    try {
      const blob = await fetchTermsOfService();
      const url = URL.createObjectURL(blob);
      
      const link = document.createElement("a");
      link.href = url;
      link.download = "Terms of Service.pdf";
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Error downloading Terms of Service:", err);
    }
  }, [fetchTermsOfService]);

  return {
    fetchTermsOfService,
    viewTermsOfService,
    downloadTermsOfService,
    loading,
    error,
  };
};

// Usage in component
const MyComponent = () => {
  const { viewTermsOfService, downloadTermsOfService, loading, error } =
    useTermsOfService();

  return (
    <div>
      <button onClick={viewTermsOfService} disabled={loading}>
        {loading ? "Loading..." : "View Terms of Service"}
      </button>
      <button onClick={downloadTermsOfService} disabled={loading}>
        Download Terms of Service
      </button>
      {error && <div style={{ color: "red" }}>Error: {error}</div>}
    </div>
  );
};
```

## Important Notes

1. **No Authentication Required**: This endpoint is public and does not require any authentication credentials or tokens.

2. **Response Type**: The endpoint returns a PDF file (binary data), not JSON. Make sure to handle it as a blob or binary response.

3. **CORS**: Make sure your frontend URL is included in the `CORS_ORIGINS` environment variable on the backend, or it's in the default allowed origins (localhost:3000, localhost:3001, etc.).

4. **Base URL**: For production, replace `http://localhost:8000` with your actual backend URL (e.g., `https://your-app.onrender.com`).

5. **Memory Management**: When creating blob URLs with `URL.createObjectURL()`, remember to revoke them with `URL.revokeObjectURL()` to prevent memory leaks, especially in long-running applications.

6. **Error Handling**: Always handle errors appropriately and provide user feedback. The endpoint may fail if:
   - S3 service is unavailable
   - The PDF file doesn't exist in S3
   - Network connectivity issues occur

7. **Browser Compatibility**: Modern browsers (Chrome, Firefox, Safari, Edge) support blob URLs and PDF viewing. For older browsers, you may need to provide a download fallback.

8. **File Location**: The PDF is stored at `s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.pdf` in S3.

## Related Endpoints

- **List Files**: `GET /api/files/list` - Get list of user files
- **Upload File**: `POST /api/files/upload` - Upload a new file
- **Delete File**: `DELETE /api/files/delete` - Delete a file
- **Rename File**: `PUT /api/files/rename` - Rename a file

