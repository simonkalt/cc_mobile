# Terms of Service API Documentation

API endpoint for retrieving the Terms of Service as markdown from a file stored in S3. This is a public endpoint that requires no authentication.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoint

### Get Terms of Service Markdown

**GET** `/api/files/terms-of-service`

Retrieves the Terms of Service as markdown content from a file stored in S3. This endpoint is public and requires no authentication or credentials. The markdown can be displayed directly or rendered using a markdown renderer in your application.

**Request:**

- Method: `GET`
- Headers: None required
- Authentication: None required (public endpoint)
- Query Parameters: None

**Response (200 OK):**

The response is a markdown document with the following headers:

- `Content-Type: text/markdown; charset=utf-8`
- `Content-Disposition: inline; filename="Terms of Service.md"`

**Response Body:**

The response body contains the raw markdown content of the Terms of Service document. The markdown can be:
- Displayed as plain text
- Rendered to HTML using a markdown parser (e.g., `marked`, `markdown-it`, `react-markdown`)
- Processed and formatted according to your application's needs

**Example Response:**

```markdown
# Terms of Service

## 1. Introduction

Welcome to sAImon Software...

## 2. Acceptance of Terms

By accessing and using this Service...
```

**Error Responses:**

- `503 Service Unavailable`: S3 service is not available (boto3 not installed)
- `404 Not Found`: Terms of Service markdown file not found in S3
- `500 Internal Server Error`: Failed to retrieve the markdown file from S3

**Error Response Format:**

```json
{
  "detail": "Failed to retrieve Terms of Service: [error message]"
}
```

## React/JavaScript Implementation Examples

### Using Fetch API - Display Markdown

#### Basic Example - Display as Text

```javascript
const TermsOfServiceViewer = () => {
  const [markdownContent, setMarkdownContent] = useState("");
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
      
      const markdown = await response.text();
      setMarkdownContent(markdown);
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
    <pre style={{ whiteSpace: "pre-wrap", fontFamily: "monospace" }}>
      {markdownContent}
    </pre>
  );
};
```

#### Render Markdown to HTML using react-markdown

```javascript
import ReactMarkdown from 'react-markdown';

const TermsOfServiceViewer = () => {
  const [markdownContent, setMarkdownContent] = useState("");
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
      
      const markdown = await response.text();
      setMarkdownContent(markdown);
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
    <div style={{ maxWidth: "800px", margin: "0 auto", padding: "20px" }}>
      <ReactMarkdown>{markdownContent}</ReactMarkdown>
    </div>
  );
};
```

#### Render Markdown using marked library

```javascript
import { marked } from 'marked';

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
      
      const markdown = await response.text();
      // Convert markdown to HTML
      const html = marked(markdown);
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
      style={{ maxWidth: "800px", margin: "0 auto", padding: "20px" }}
    />
  );
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
        responseType: "text", // Important: specify text response type for markdown
      }
    );

    // response.data contains the markdown string
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

// Usage: Display markdown
const displayTerms = async () => {
  const markdown = await fetchTermsOfService();
  // Render markdown using your preferred library
  console.log(markdown);
};
```

### Complete React Hook Example

```javascript
import { useState, useCallback } from "react";
import ReactMarkdown from 'react-markdown';

const useTermsOfService = (baseUrl = "http://localhost:8000") => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [markdown, setMarkdown] = useState("");

  const fetchTermsOfService = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const response = await fetch(`${baseUrl}/api/files/terms-of-service`);
      
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || "Failed to fetch Terms of Service");
      }
      
      const markdownContent = await response.text();
      setMarkdown(markdownContent);
      return markdownContent;
    } catch (err) {
      const errorMessage = err.message || "Unknown error occurred";
      setError(errorMessage);
      throw err;
    } finally {
      setLoading(false);
    }
  }, [baseUrl]);

  return {
    fetchTermsOfService,
    markdown,
    loading,
    error,
  };
};

// Usage in component
const MyComponent = () => {
  const { 
    fetchTermsOfService, 
    markdown, 
    loading, 
    error 
  } = useTermsOfService();

  useEffect(() => {
    fetchTermsOfService();
  }, [fetchTermsOfService]);

  return (
    <div>
      {loading && <div>Loading Terms of Service...</div>}
      {error && <div style={{ color: "red" }}>Error: {error}</div>}
      {markdown && (
        <div style={{ maxWidth: "800px", margin: "0 auto", padding: "20px" }}>
          <ReactMarkdown>{markdown}</ReactMarkdown>
        </div>
      )}
    </div>
  );
};
```

### React Component with Modal/Dialog

```javascript
import React, { useState } from "react";
import ReactMarkdown from 'react-markdown';

const TermsOfServiceModal = () => {
  const [isOpen, setIsOpen] = useState(false);
  const [markdownContent, setMarkdownContent] = useState("");
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
      
      const markdown = await response.text();
      setMarkdownContent(markdown);
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
              <ReactMarkdown>{markdownContent}</ReactMarkdown>
            )}
          </div>
        </div>
      )}
    </>
  );
};

export default TermsOfServiceModal;
```

## Markdown Rendering Libraries

### Popular Options:

1. **react-markdown** (React)
   ```bash
   npm install react-markdown
   ```
   ```javascript
   import ReactMarkdown from 'react-markdown';
   <ReactMarkdown>{markdown}</ReactMarkdown>
   ```

2. **marked** (Vanilla JS / React)
   ```bash
   npm install marked
   ```
   ```javascript
   import { marked } from 'marked';
   const html = marked(markdown);
   ```

3. **markdown-it** (Vanilla JS)
   ```bash
   npm install markdown-it
   ```
   ```javascript
   import MarkdownIt from 'markdown-it';
   const md = new MarkdownIt();
   const html = md.render(markdown);
   ```

4. **remark** (Unified ecosystem)
   ```bash
   npm install remark remark-react
   ```
   ```javascript
   import { remark } from 'remark';
   import remarkReact from 'remark-react';
   const result = await remark().use(remarkReact).process(markdown);
   ```

## Important Notes

1. **No Authentication Required**: This endpoint is public and does not require any authentication credentials or tokens.

2. **Response Type**: The endpoint returns markdown content (text/markdown), not HTML or JSON. Make sure to handle it as text.

3. **Markdown Content**: The returned markdown is plain text that can be:
   - Displayed as-is (plain text)
   - Rendered to HTML using a markdown parser
   - Processed and formatted according to your application's needs

4. **CORS**: Make sure your frontend URL is included in the `CORS_ORIGINS` environment variable on the backend, or it's in the default allowed origins (localhost:3000, localhost:3001, etc.).

5. **Base URL**: For production, replace `http://localhost:8000` with your actual backend URL (e.g., `https://your-app.onrender.com`).

6. **Error Handling**: Always handle errors appropriately and provide user feedback. The endpoint may fail if:
   - S3 service is unavailable
   - The markdown file doesn't exist in S3
   - Network connectivity issues occur

7. **File Location**: The source markdown file is stored at `s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.md` in S3.

8. **Security Note**: When rendering markdown to HTML, ensure you're using a trusted markdown parser that sanitizes HTML output to prevent XSS attacks. Libraries like `react-markdown` handle this automatically.

## Related Endpoints

- **List Files**: `GET /api/files/list` - Get list of user files
- **Upload File**: `POST /api/files/upload` - Upload a new file
- **Delete File**: `DELETE /api/files/delete` - Delete a file
- **Rename File**: `PUT /api/files/rename` - Rename a file
