# Cover Letter Management API Documentation

API endpoints for managing saved cover letters in S3 bucket. Cover letters are stored in a user-specific subfolder: `{user_id}/generated_cover_letters/{filename}`

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoints

### 1. List Cover Letters

**GET** `/api/cover-letters/list`

List all saved cover letters from the user's `generated_cover_letters` subfolder.

**Query Parameters:**

- `user_id` (optional): User ID - required if `user_email` is not provided
- `user_email` (optional): User email - will be resolved to `user_id` if provided

**Request Example:**

```
GET /api/cover-letters/list?user_id=507f1f77bcf86cd799439011
```

or

```
GET /api/cover-letters/list?user_email=user@example.com
```

**Response (200 OK):**

```json
{
  "files": [
    {
      "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_tech_corp_20240115.md",
      "name": "cover_letter_tech_corp_20240115.md",
      "size": 1234,
      "lastModified": "2024-01-15T10:30:00.123456"
    },
    {
      "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_company_xyz_20240114.pdf",
      "name": "cover_letter_company_xyz_20240114.pdf",
      "size": 45678,
      "lastModified": "2024-01-14T09:20:00.123456"
    }
  ]
}
```

**Response Fields:**

- `files`: Array of cover letter file objects
  - `key`: Full S3 key path: `{user_id}/generated_cover_letters/{filename}`
  - `name`: Filename (without path)
  - `size`: File size in bytes
  - `lastModified`: ISO 8601 timestamp of last modification

**Error Responses:**

- `400 Bad Request`: Missing `user_id` or `user_email`
- `404 Not Found`: User not found (when using `user_email`)
- `500 Internal Server Error`: S3 error or other server error
- `503 Service Unavailable`: S3 service is not available

**Notes:**

- Files are sorted by `lastModified` (newest first)
- Only returns actual files (excludes folders and system files)
- The `generated_cover_letters` subfolder is created automatically if it doesn't exist

---

### 2. Download Cover Letter

**GET** `/api/cover-letters/download`

Download a cover letter from S3 for previewing. Returns the file content with appropriate content type headers.

**Query Parameters:**

- `key` (required): Full S3 key of the cover letter (e.g., `{user_id}/generated_cover_letters/{filename}`)
- `user_id` (optional): User ID - required if `user_email` is not provided
- `user_email` (optional): User email - will be resolved to `user_id` if provided

**Request Example:**

```
GET /api/cover-letters/download?key=507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_tech_corp.md&user_id=507f1f77bcf86cd799439011
```

**Response (200 OK):**

The response is the file content with appropriate headers:

- **Content-Type**: Based on file extension:
  - `.pdf` → `application/pdf`
  - `.html` → `text/html`
  - `.md` → `text/markdown`
- **Content-Disposition**: `inline; filename="{filename}"`

**Response Body:**

- For PDF files: Binary PDF data
- For HTML files: HTML text content
- For Markdown files: Markdown text content

**Error Responses:**

- `400 Bad Request`: Missing `key`, `user_id`, or `user_email`
- `403 Forbidden`: Cannot download cover letters that don't belong to this user
- `404 Not Found`: Cover letter not found or user not found
- `500 Internal Server Error`: S3 error or other server error
- `503 Service Unavailable`: S3 service is not available

**Notes:**

- The file is returned with `Content-Disposition: inline` for browser preview
- Content type is automatically determined from file extension
- User validation ensures users can only download their own cover letters

---

### 3. Delete Cover Letter

**DELETE** `/api/cover-letters/delete`

Delete a cover letter from S3 bucket.

**Request Body:**

```json
{
  "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_tech_corp.md",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

**Request Fields:**

- `key` (required): Full S3 key of the cover letter to delete
- `user_id` (optional): User ID - required if `user_email` is not provided
- `user_email` (optional): User email - will be resolved to `user_id` if provided

**Response (200 OK):**

```json
{
  "success": true,
  "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_tech_corp.md",
  "message": "Cover letter deleted successfully",
  "files": [
    {
      "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_company_xyz_20240114.pdf",
      "name": "cover_letter_company_xyz_20240114.pdf",
      "size": 45678,
      "lastModified": "2024-01-14T09:20:00.123456"
    }
  ]
}
```

**Response Fields:**

- `success`: Boolean indicating success
- `key`: S3 key of the deleted file
- `message`: Success message
- `files`: Updated list of all remaining cover letters (sorted by lastModified, newest first)

**Error Responses:**

- `400 Bad Request`: Missing required fields or attempting to delete system files
- `403 Forbidden`: Cannot delete cover letters that don't belong to this user
- `404 Not Found`: User not found (when using `user_email`)
- `500 Internal Server Error`: S3 error or other server error
- `503 Service Unavailable`: S3 service is not available

**Notes:**

- Returns updated file list automatically after deletion
- Cannot delete system files (`.folder_initialized`)
- User validation ensures users can only delete their own cover letters

---

## Client-Side Implementation Examples

### JavaScript/React Example

```javascript
const API_BASE_URL = "http://localhost:8000"; // or your production URL

// 1. List Cover Letters
async function listCoverLetters(user_id, user_email = null) {
  try {
    const params = new URLSearchParams();
    if (user_id) params.append("user_id", user_id);
    if (user_email) params.append("user_email", user_email);

    const response = await fetch(
      `${API_BASE_URL}/api/cover-letters/list?${params.toString()}`,
      {
        method: "GET",
        headers: {
          "Content-Type": "application/json",
        },
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result.files;
  } catch (error) {
    console.error("Error listing cover letters:", error);
    throw error;
  }
}

// 2. Download Cover Letter
async function downloadCoverLetter(key, user_id, user_email = null) {
  try {
    const params = new URLSearchParams({ key });
    if (user_id) params.append("user_id", user_id);
    if (user_email) params.append("user_email", user_email);

    const response = await fetch(
      `${API_BASE_URL}/api/cover-letters/download?${params.toString()}`,
      {
        method: "GET",
      }
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    // Get content type and filename from response
    const contentType = response.headers.get("content-type");
    const contentDisposition = response.headers.get("content-disposition");
    const filename =
      contentDisposition?.match(/filename="(.+)"/)?.[1] || "cover_letter";

    // Handle different content types
    if (contentType === "application/pdf") {
      // For PDF, create blob and open in new tab or download
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      window.open(url, "_blank");
      // Or download: const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
    } else {
      // For text files (markdown, HTML), get as text
      const text = await response.text();
      return { content: text, contentType, filename };
    }
  } catch (error) {
    console.error("Error downloading cover letter:", error);
    throw error;
  }
}

// 3. Delete Cover Letter
async function deleteCoverLetter(key, user_id, user_email = null) {
  try {
    const response = await fetch(`${API_BASE_URL}/api/cover-letters/delete`, {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        key: key,
        user_id: user_id,
        user_email: user_email,
      }),
    });

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }

    const result = await response.json();
    return result;
  } catch (error) {
    console.error("Error deleting cover letter:", error);
    throw error;
  }
}

// Usage examples
const userId = "507f1f77bcf86cd799439011";

// List all cover letters
listCoverLetters(userId).then((files) => {
  console.log(`Found ${files.length} cover letters`);
  files.forEach((file) => {
    console.log(`- ${file.name} (${file.size} bytes)`);
  });
});

// Download a cover letter
const coverLetterKey =
  "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_tech_corp.md";
downloadCoverLetter(coverLetterKey, userId).then((result) => {
  if (result) {
    console.log("Cover letter content:", result.content);
  }
});

// Delete a cover letter
deleteCoverLetter(coverLetterKey, userId).then((result) => {
  console.log("Deleted:", result.message);
  console.log(`Remaining cover letters: ${result.files.length}`);
});
```

### React Component Example

```jsx
import React, { useState, useEffect } from "react";

function CoverLetterManager({ user_id, user_email }) {
  const [coverLetters, setCoverLetters] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const API_BASE_URL = "http://localhost:8000";

  // Load cover letters
  const loadCoverLetters = async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (user_id) params.append("user_id", user_id);
      if (user_email) params.append("user_email", user_email);

      const response = await fetch(
        `${API_BASE_URL}/api/cover-letters/list?${params.toString()}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to load cover letters");
      }

      const result = await response.json();
      setCoverLetters(result.files);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  // Download cover letter
  const handleDownload = async (key) => {
    try {
      const params = new URLSearchParams({ key });
      if (user_id) params.append("user_id", user_id);
      if (user_email) params.append("user_email", user_email);

      const response = await fetch(
        `${API_BASE_URL}/api/cover-letters/download?${params.toString()}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to download cover letter");
      }

      const contentType = response.headers.get("content-type");
      const filename = key.split("/").pop();

      if (contentType === "application/pdf") {
        // Open PDF in new tab
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        window.open(url, "_blank");
      } else {
        // Display text content
        const text = await response.text();
        alert(`Cover Letter Content:\n\n${text.substring(0, 500)}...`);
      }
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  // Delete cover letter
  const handleDelete = async (key) => {
    if (!window.confirm("Are you sure you want to delete this cover letter?")) {
      return;
    }

    try {
      const response = await fetch(`${API_BASE_URL}/api/cover-letters/delete`, {
        method: "DELETE",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          key: key,
          user_id: user_id,
          user_email: user_email,
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to delete cover letter");
      }

      const result = await response.json();
      setCoverLetters(result.files); // Update list with remaining files
      alert("Cover letter deleted successfully");
    } catch (err) {
      alert(`Error: ${err.message}`);
    }
  };

  useEffect(() => {
    loadCoverLetters();
  }, [user_id, user_email]);

  if (loading) return <div>Loading cover letters...</div>;
  if (error) return <div>Error: {error}</div>;

  return (
    <div>
      <h2>Saved Cover Letters</h2>
      <button onClick={loadCoverLetters}>Refresh</button>
      {coverLetters.length === 0 ? (
        <p>No cover letters saved yet.</p>
      ) : (
        <ul>
          {coverLetters.map((file) => (
            <li key={file.key}>
              <strong>{file.name}</strong> ({file.size} bytes) -{" "}
              {new Date(file.lastModified).toLocaleDateString()}
              <button onClick={() => handleDownload(file.key)}>Preview</button>
              <button onClick={() => handleDelete(file.key)}>Delete</button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export default CoverLetterManager;
```

### React Native Example

```javascript
import { useState, useEffect } from "react";
import { View, Text, Button, FlatList, Alert, ActivityIndicator } from "react-native";

function CoverLetterManager({ user_id, user_email }) {
  const [coverLetters, setCoverLetters] = useState([]);
  const [loading, setLoading] = useState(false);

  const API_BASE_URL = "http://localhost:8000";

  const loadCoverLetters = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams();
      if (user_id) params.append("user_id", user_id);
      if (user_email) params.append("user_email", user_email);

      const response = await fetch(
        `${API_BASE_URL}/api/cover-letters/list?${params.toString()}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to load cover letters");
      }

      const result = await response.json();
      setCoverLetters(result.files);
    } catch (error) {
      Alert.alert("Error", error.message);
    } finally {
      setLoading(false);
    }
  };

  const handleDownload = async (key) => {
    try {
      const params = new URLSearchParams({ key });
      if (user_id) params.append("user_id", user_id);
      if (user_email) params.append("user_email", user_email);

      const response = await fetch(
        `${API_BASE_URL}/api/cover-letters/download?${params.toString()}`
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to download cover letter");
      }

      const contentType = response.headers.get("content-type");
      const filename = key.split("/").pop();

      if (contentType === "application/pdf") {
        // For React Native, you might use a library like react-native-pdf
        // or open the URL in a WebView
        Alert.alert("PDF", "PDF preview not implemented. Use a PDF viewer library.");
      } else {
        const text = await response.text();
        Alert.alert("Cover Letter", text.substring(0, 200) + "...");
      }
    } catch (error) {
      Alert.alert("Error", error.message);
    }
  };

  const handleDelete = async (key) => {
    Alert.alert(
      "Delete Cover Letter",
      "Are you sure you want to delete this cover letter?",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: async () => {
            try {
              const response = await fetch(
                `${API_BASE_URL}/api/cover-letters/delete`,
                {
                  method: "DELETE",
                  headers: {
                    "Content-Type": "application/json",
                  },
                  body: JSON.stringify({
                    key: key,
                    user_id: user_id,
                    user_email: user_email,
                  }),
                }
              );

              if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.detail || "Failed to delete cover letter");
              }

              const result = await response.json();
              setCoverLetters(result.files);
              Alert.alert("Success", "Cover letter deleted");
            } catch (error) {
              Alert.alert("Error", error.message);
            }
          },
        },
      ]
    );
  };

  useEffect(() => {
    loadCoverLetters();
  }, [user_id, user_email]);

  if (loading) {
    return (
      <View>
        <ActivityIndicator />
        <Text>Loading cover letters...</Text>
      </View>
    );
  }

  return (
    <View>
      <Button title="Refresh" onPress={loadCoverLetters} />
      <FlatList
        data={coverLetters}
        keyExtractor={(item) => item.key}
        renderItem={({ item }) => (
          <View>
            <Text>{item.name}</Text>
            <Text>{item.size} bytes</Text>
            <Button title="Preview" onPress={() => handleDownload(item.key)} />
            <Button title="Delete" onPress={() => handleDelete(item.key)} />
          </View>
        )}
        ListEmptyComponent={<Text>No cover letters saved yet.</Text>}
      />
    </View>
  );
}

export default CoverLetterManager;
```

---

## File Organization

Cover letters are stored in the following S3 structure:

```
s3://bucket-name/
  {user_id}/
    generated_cover_letters/
      cover_letter_20240115_143022.md
      cover_letter_tech_corp.md
      cover_letter_company_xyz.pdf
      cover_letter_another_company.html
      ...
```

- Each user has their own folder: `{user_id}/`
- Cover letters are stored in a subfolder: `{user_id}/generated_cover_letters/`
- Files can be in multiple formats: `.md`, `.html`, or `.pdf`

---

## Error Handling

### Common Errors

1. **400 Bad Request**: Missing required fields
   ```json
   {
     "detail": "user_id or user_email is required to list cover letters"
   }
   ```

2. **403 Forbidden**: Attempting to access another user's cover letters
   ```json
   {
     "detail": "Cannot download cover letters that don't belong to this user"
   }
   ```

3. **404 Not Found**: Cover letter or user not found
   ```json
   {
     "detail": "Cover letter not found"
   }
   ```

4. **500 Internal Server Error**: S3 operation failed
   ```json
   {
     "detail": "S3 error: AccessDenied - ..."
   }
   ```

5. **503 Service Unavailable**: S3 service not available
   ```json
   {
     "detail": "S3 service is not available. boto3 is not installed."
   }
   ```

---

## Best Practices

1. **Always provide user identification**: Either `user_id` or `user_email` must be provided
2. **Use the key from list response**: When downloading or deleting, use the `key` field from the list response
3. **Handle different content types**: PDFs require blob handling, while text files can be displayed directly
4. **Refresh after operations**: After delete operations, the updated file list is returned automatically
5. **Error handling**: Always wrap API calls in try-catch blocks and provide user feedback
6. **Loading states**: Show loading indicators while fetching cover letters
7. **Confirmation dialogs**: Ask for confirmation before deleting cover letters

---

## Testing

You can test the endpoints using curl:

**List Cover Letters:**
```bash
curl -X GET "http://localhost:8000/api/cover-letters/list?user_id=507f1f77bcf86cd799439011"
```

**Download Cover Letter:**
```bash
curl -X GET "http://localhost:8000/api/cover-letters/download?key=507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_tech_corp.md&user_id=507f1f77bcf86cd799439011" \
  -o cover_letter.md
```

**Delete Cover Letter:**
```bash
curl -X DELETE http://localhost:8000/api/cover-letters/delete \
  -H "Content-Type: application/json" \
  -d '{
    "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_tech_corp.md",
    "user_id": "507f1f77bcf86cd799439011"
  }'
```

---

## Notes

- All endpoints require user authentication via `user_id` or `user_email`
- Files are automatically sorted by modification date (newest first)
- The `generated_cover_letters` subfolder is created automatically if it doesn't exist
- User validation ensures users can only access their own cover letters
- System files (`.folder_initialized`) are excluded from listings and cannot be deleted

