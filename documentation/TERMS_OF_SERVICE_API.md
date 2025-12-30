# Terms of Service API Documentation

API endpoint for retrieving the Terms of Service as HTML converted from a PDF document stored in S3. This is a public endpoint that requires no authentication.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoint

### Get Terms of Service HTML

**GET** `/api/files/terms-of-service`

Retrieves the Terms of Service as HTML content, converted from a PDF document stored in S3. This endpoint is public and requires no authentication or credentials. The HTML can be displayed directly in the browser or embedded in your application.

**Request:**

- Method: `GET`
- Headers: None required
- Authentication: None required (public endpoint)
- Query Parameters: None

**Response (200 OK):**

The response is an HTML document with the following headers:

- `Content-Type: text/html; charset=utf-8`
- `Content-Disposition: inline; filename="Terms of Service.html"`

**Response Body:**

The response body contains a complete HTML document with the Terms of Service content. The HTML includes:
- Proper document structure (`<!DOCTYPE html>`, `<html>`, `<head>`, `<body>`)
- Embedded CSS styling for readability
- Responsive design with max-width constraints
- Formatted text content extracted from the PDF

**Example Response Structure:**

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms of Service</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }
        /* ... additional styles ... */
    </style>
</head>
<body>
    <!-- Terms of Service content here -->
</body>
</html>
```

**Error Responses:**

- `503 Service Unavailable`: S3 service is not available (boto3 not installed) or PDF conversion libraries are missing
- `404 Not Found`: Terms of Service PDF not found in S3
- `500 Internal Server Error`: Failed to retrieve or convert the PDF from S3

**Error Response Format:**

```json
{
  "detail": "Failed to retrieve Terms of Service: [error message]"
}
```

## React/JavaScript Implementation Examples

### Using Fetch API - Display HTML Directly

#### Basic Example - Display in Component

```javascript
const TermsOfServiceViewer = () => {
  const [htmlContent, setHtmlContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const fetchTermsOfService = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch("http://localhost:8000/api/files/terms-of-service");
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to fetch Terms of Service");
      }
      
      const html = await response.text();
      setHtmlContent(html);
    } catch (err) {
      setError(err.message);
      console.error("Error fetching Terms of Service:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchTermsOfService();
  }, []);

  if (loading) return <div>Loading Terms of Service...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div 
      dangerouslySetInnerHTML={{ __html: htmlContent }}
      style={{ maxWidth: "100%", overflow: "auto" }}
    />
  );
};
```

#### Display HTML in iframe

```javascript
const TermsOfServiceViewer = () => {
  const [htmlUrl, setHtmlUrl] = useState(null);
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
      
      const html = await response.text();
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      setHtmlUrl(url);
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
      if (htmlUrl) {
        URL.revokeObjectURL(htmlUrl);
      }
    };
  }, []);

  if (loading) return <div>Loading Terms of Service...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!htmlUrl) return null;

  return (
    <iframe
      src={htmlUrl}
      width="100%"
      height="600px"
      title="Terms of Service"
      style={{ border: "none" }}
    />
  );
};
```

#### Open HTML in New Window

```javascript
const viewTermsOfService = async () => {
  try {
    const response = await fetch("http://localhost:8000/api/files/terms-of-service");
    
    if (!response.ok) {
      throw new Error("Failed to load Terms of Service");
    }
    
    const html = await response.text();
    const blob = new Blob([html], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    
    // Open in new window
    window.open(url, "_blank");
    
    // Clean up URL after a delay
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch (error) {
    console.error("Error viewing Terms of Service:", error);
    alert("Failed to load Terms of Service. Please try again.");
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
        responseType: "text", // Important: specify text response type for HTML
      }
    );

    // response.data contains the HTML string
    return response.data;
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

// Usage: Display HTML
const displayTerms = async () => {
  const html = await fetchTermsOfService();
  // Use dangerouslySetInnerHTML or create a blob URL
  const blob = new Blob([html], { type: "text/html" });
  const url = URL.createObjectURL(blob);
  window.open(url, "_blank");
};
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
      
      const html = await response.text();
      return html;
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
      const html = await fetchTermsOfService();
      const blob = new Blob([html], { type: "text/html" });
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank");
      
      // Clean up after a delay (optional)
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (err) {
      console.error("Error viewing Terms of Service:", err);
    }
  }, [fetchTermsOfService]);

  const getTermsOfServiceHTML = useCallback(async () => {
    try {
      const html = await fetchTermsOfService();
      return html;
    } catch (err) {
      console.error("Error fetching Terms of Service:", err);
      return null;
    }
  }, [fetchTermsOfService]);

  return {
    fetchTermsOfService,
    viewTermsOfService,
    getTermsOfServiceHTML,
    loading,
    error,
  };
};

// Usage in component
const MyComponent = () => {
  const { 
    viewTermsOfService, 
    getTermsOfServiceHTML, 
    loading, 
    error 
  } = useTermsOfService();
  
  const [htmlContent, setHtmlContent] = useState("");

  const handleDisplayInline = async () => {
    const html = await getTermsOfServiceHTML();
    if (html) {
      setHtmlContent(html);
    }
  };

  return (
    <div>
      <button onClick={viewTermsOfService} disabled={loading}>
        {loading ? "Loading..." : "View Terms of Service"}
      </button>
      <button onClick={handleDisplayInline} disabled={loading}>
        Display Inline
      </button>
      {error && <div style={{ color: "red" }}>Error: {error}</div>}
      {htmlContent && (
        <div 
          dangerouslySetInnerHTML={{ __html: htmlContent }}
          style={{ marginTop: "20px", border: "1px solid #ccc", padding: "20px" }}
        />
      )}
    </div>
  );
};
```

### React Component with Modal/Dialog

```javascript
import React, { useState } from "react";

const TermsOfServiceModal = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [htmlContent, setHtmlContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const loadTermsOfService = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch("http://localhost:8000/api/files/terms-of-service");
      
      if (!response.ok) {
        throw new Error("Failed to load Terms of Service");
      }
      
      const html = await response.text();
      setHtmlContent(html);
      setIsOpen(true);
    } catch (err) {
      setError(err.message);
      console.error("Error loading Terms of Service:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <button onClick={loadTermsOfService} disabled={loading}>
        {loading ? "Loading..." : "View Terms of Service"}
      </button>
      
      {isOpen && (
        <div style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundColor: "rgba(0, 0, 0, 0.5)",
          display: "flex",
          justifyContent: "center",
          alignItems: "center",
          zIndex: 1000
        }}>
          <div style={{
            backgroundColor: "white",
            width: "90%",
            maxWidth: "800px",
            maxHeight: "90vh",
            overflow: "auto",
            padding: "20px",
            borderRadius: "8px",
            position: "relative"
          }}>
            <button 
              onClick={() => setIsOpen(false)}
              style={{
                position: "absolute",
                top: "10px",
                right: "10px",
                background: "none",
                border: "none",
                fontSize: "24px",
                cursor: "pointer"
              }}
            >
              ×
            </button>
            {error ? (
              <div style={{ color: "red" }}>Error: {error}</div>
            ) : (
              <div dangerouslySetInnerHTML={{ __html: htmlContent }} />
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default TermsOfServiceModal;
```

## Important Notes

1. **No Authentication Required**: This endpoint is public and does not require any authentication credentials or tokens.

2. **Response Type**: The endpoint returns HTML content (text/html), not JSON or binary PDF data. Make sure to handle it as text.

3. **HTML Content**: The returned HTML is a complete, self-contained document with embedded CSS styling. It can be:
   - Displayed directly using `dangerouslySetInnerHTML` (React)
   - Loaded in an iframe
   - Opened in a new window/tab
   - Embedded in your application's layout

4. **CORS**: Make sure your frontend URL is included in the `CORS_ORIGINS` environment variable on the backend, or it's in the default allowed origins (localhost:3000, localhost:3001, etc.).

5. **Base URL**: For production, replace `http://localhost:8000` with your actual backend URL (e.g., `https://your-app.onrender.com`).

6. **Memory Management**: When creating blob URLs with `URL.createObjectURL()`, remember to revoke them with `URL.revokeObjectURL()` to prevent memory leaks, especially in long-running applications.

7. **Error Handling**: Always handle errors appropriately and provide user feedback. The endpoint may fail if:
   - S3 service is unavailable
   - The PDF file doesn't exist in S3
   - PDF conversion libraries are not installed
   - Network connectivity issues occur

8. **PDF Conversion**: The endpoint automatically converts the PDF to HTML using:
   - PyMuPDF (fitz) if available - provides better formatting preservation
   - PyPDF2 as fallback - extracts text with basic HTML formatting

9. **File Location**: The source PDF is stored at `s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.pdf` in S3.

10. **Security Note**: When using `dangerouslySetInnerHTML` in React, ensure the HTML content is trusted. Since this content comes from your own backend, it should be safe, but be aware of XSS risks if the content is modified.

## Related Endpoints

- **List Files**: `GET /api/files/list` - Get list of user files
- **Upload File**: `POST /api/files/upload` - Upload a new file
- **Delete File**: `DELETE /api/files/delete` - Delete a file
- **Rename File**: `PUT /api/files/rename` - Rename a file
