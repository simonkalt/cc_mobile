# Save Cover Letter API Documentation

API endpoint for saving generated cover letters to S3 bucket. Cover letters are stored in a user-specific subfolder: `{user_id}/generated_cover_letters/{filename}`

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoint

### Save Cover Letter

**POST** `/api/files/save-cover-letter`

Save a generated cover letter to the user's `generated_cover_letters` subfolder in S3. The subfolder will be created automatically if it doesn't exist.

**Request Body:**

```json
{
  "coverLetterContent": "# Cover Letter\n\nDear Hiring Manager,\n\n...",
  "fileName": "cover_letter_company_name",
  "contentType": "text/markdown",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

**Request Fields:**

- `coverLetterContent` (required): The cover letter content as a string. Can be markdown or HTML format.
- `fileName` (optional): Custom filename without extension. If not provided, a timestamped filename will be generated (e.g., `cover_letter_20240115_143022`).
- `contentType` (optional): Content type of the cover letter. Defaults to `"text/markdown"`. Can be:
  - `"text/markdown"` - Saves as `.md` file
  - `"text/html"` - Saves as `.html` file
- `user_id` (optional): User ID - required if `user_email` is not provided
- `user_email` (optional): User email - will be resolved to `user_id` if provided

**Response (200 OK):**

```json
{
  "success": true,
  "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_company_name.md",
  "fileName": "cover_letter_company_name.md",
  "message": "Cover letter saved successfully",
  "fileSize": 1234
}
```

**Response Fields:**

- `success`: Boolean indicating success
- `key`: Full S3 key path: `{user_id}/generated_cover_letters/{filename}`
- `fileName`: The saved filename (with extension)
- `message`: Success message
- `fileSize`: Size of the saved file in bytes

**Error Responses:**

- `400 Bad Request`: Missing required fields (`coverLetterContent` or user identification)
- `404 Not Found`: User not found (when using `user_email`)
- `500 Internal Server Error`: S3 error or other server error
- `503 Service Unavailable`: S3 service is not available (boto3 not installed)

**Notes:**

- The `generated_cover_letters` subfolder is created automatically if it doesn't exist
- If `fileName` is provided, it will be sanitized to remove unsafe characters
- File extension (`.md` or `.html`) is automatically added based on `contentType`
- If `fileName` already includes an extension (`.md`, `.html`, `.txt`), it will be used as-is
- The main user folder (`{user_id}/`) is also created if it doesn't exist
- Filenames are sanitized to ensure S3 compatibility

---

## Client-Side Implementation Examples

### JavaScript/React Example

```javascript
// Function to save a cover letter
async function saveCoverLetter(coverLetterContent, fileName = null, user_id = null, user_email = null) {
  const API_BASE_URL = 'http://localhost:8000'; // or your production URL
  
  try {
    const requestBody = {
      coverLetterContent: coverLetterContent,
      contentType: "text/markdown", // or "text/html"
      user_id: user_id,
      user_email: user_email
    };
    
    // Add custom filename if provided
    if (fileName) {
      requestBody.fileName = fileName;
    }
    
    const response = await fetch(`${API_BASE_URL}/api/files/save-cover-letter`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
    }
    
    const result = await response.json();
    console.log('Cover letter saved successfully:', result);
    return result;
    
  } catch (error) {
    console.error('Error saving cover letter:', error);
    throw error;
  }
}

// Usage example - saving markdown cover letter
const markdownContent = `# Cover Letter

Dear Hiring Manager,

I am writing to express my interest in the Software Engineer position...

Sincerely,
John Doe`;

saveCoverLetter(
  markdownContent,
  "cover_letter_tech_corp", // Optional custom filename
  "507f1f77bcf86cd799439011" // user_id
).then(result => {
  console.log(`Cover letter saved as: ${result.fileName}`);
  console.log(`S3 key: ${result.key}`);
}).catch(error => {
  console.error('Failed to save cover letter:', error);
});

// Usage example - saving HTML cover letter
const htmlContent = `<h1>Cover Letter</h1>
<p>Dear Hiring Manager,</p>
<p>I am writing to express my interest...</p>`;

saveCoverLetter(
  htmlContent,
  "cover_letter_tech_corp",
  "507f1f77bcf86cd799439011",
  null,
  "text/html" // Specify HTML content type
).then(result => {
  console.log(`HTML cover letter saved as: ${result.fileName}`);
});
```

### React Component Example

```jsx
import React, { useState } from 'react';

function SaveCoverLetterButton({ coverLetterContent, user_id, user_email }) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  
  const handleSave = async () => {
    if (!coverLetterContent) {
      setMessage('No cover letter content to save');
      return;
    }
    
    setSaving(true);
    setMessage('');
    
    try {
      const response = await fetch('http://localhost:8000/api/files/save-cover-letter', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          coverLetterContent: coverLetterContent,
          contentType: "text/markdown",
          user_id: user_id,
          user_email: user_email
        })
      });
      
      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to save cover letter');
      }
      
      const result = await response.json();
      setMessage(`✓ Cover letter saved as ${result.fileName}`);
      
    } catch (error) {
      setMessage(`✗ Error: ${error.message}`);
    } finally {
      setSaving(false);
    }
  };
  
  return (
    <div>
      <button 
        onClick={handleSave} 
        disabled={saving || !coverLetterContent}
      >
        {saving ? 'Saving...' : 'Save Cover Letter'}
      </button>
      {message && <p>{message}</p>}
    </div>
  );
}

export default SaveCoverLetterButton;
```

### React Native Example

```javascript
import { Alert } from 'react-native';

async function saveCoverLetter(coverLetterContent, fileName, user_id) {
  const API_BASE_URL = 'http://localhost:8000'; // or your production URL
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/files/save-cover-letter`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        coverLetterContent: coverLetterContent,
        fileName: fileName,
        contentType: "text/markdown",
        user_id: user_id
      })
    });
    
    const result = await response.json();
    
    if (!response.ok) {
      throw new Error(result.detail || 'Failed to save cover letter');
    }
    
    Alert.alert('Success', `Cover letter saved as ${result.fileName}`);
    return result;
    
  } catch (error) {
    Alert.alert('Error', error.message);
    throw error;
  }
}

// Usage
saveCoverLetter(
  markdownContent,
  "cover_letter_tech_corp",
  user_id
);
```

### Using with Generated Cover Letter Response

When you receive a cover letter from the `/api/job-info` endpoint, you can save it like this:

```javascript
// After generating a cover letter
const jobInfoResponse = await fetch('http://localhost:8000/api/job-info', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    llm: "gpt-4.1",
    company_name: "Tech Corp",
    // ... other fields
    user_id: user_id
  })
});

const coverLetterData = await jobInfoResponse.json();

// Save the markdown version
await saveCoverLetter(
  coverLetterData.markdown,
  `cover_letter_tech_corp_${new Date().toISOString().split('T')[0]}`,
  user_id
);

// Or save the HTML version
await saveCoverLetter(
  coverLetterData.html,
  `cover_letter_tech_corp_${new Date().toISOString().split('T')[0]}`,
  user_id,
  null,
  "text/html"
);
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
      cover_letter_another_company.html
      ...
```

- Each user has their own folder: `{user_id}/`
- Cover letters are stored in a subfolder: `{user_id}/generated_cover_letters/`
- Files are named with the provided `fileName` or auto-generated timestamp
- File extensions (`.md` or `.html`) are added based on `contentType`

---

## Error Handling

### Common Errors

1. **400 Bad Request**: Missing `coverLetterContent` or user identification
   ```json
   {
     "detail": "user_id or user_email is required to save cover letters"
   }
   ```

2. **404 Not Found**: User not found when using `user_email`
   ```json
   {
     "detail": "User not found for email: user@example.com"
   }
   ```

3. **500 Internal Server Error**: S3 operation failed
   ```json
   {
     "detail": "S3 error: AccessDenied - ..."
   }
   ```

4. **503 Service Unavailable**: S3 service not available
   ```json
   {
     "detail": "S3 service is not available. boto3 is not installed."
   }
   ```

---

## Best Practices

1. **Always provide user identification**: Either `user_id` or `user_email` must be provided
2. **Use descriptive filenames**: When providing a custom `fileName`, use descriptive names like `cover_letter_company_name_position`
3. **Choose appropriate content type**: Use `text/markdown` for markdown content, `text/html` for HTML content
4. **Handle errors gracefully**: Always wrap API calls in try-catch blocks and provide user feedback
5. **Validate content**: Ensure `coverLetterContent` is not empty before calling the API
6. **Consider file size**: While there's no strict limit, very large cover letters may take longer to upload

---

## Testing

You can test the endpoint using curl:

```bash
curl -X POST http://localhost:8000/api/files/save-cover-letter \
  -H "Content-Type: application/json" \
  -d '{
    "coverLetterContent": "# Cover Letter\n\nDear Hiring Manager,\n\nThis is a test cover letter.",
    "fileName": "test_cover_letter",
    "contentType": "text/markdown",
    "user_id": "507f1f77bcf86cd799439011"
  }'
```

Expected response:

```json
{
  "success": true,
  "key": "507f1f77bcf86cd799439011/generated_cover_letters/test_cover_letter.md",
  "fileName": "test_cover_letter.md",
  "message": "Cover letter saved successfully",
  "fileSize": 78
}
```

