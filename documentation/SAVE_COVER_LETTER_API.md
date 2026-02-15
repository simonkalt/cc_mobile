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
  "coverLetterContent": "<base64_docx_bytes>",
  "fileName": "cover_letter_company_name",
  "contentType": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

**Request Fields:**

- `coverLetterContent` (required): The cover letter content as a string. Can be:
  - Markdown text (for `text/markdown`)
  - Base64-encoded DOCX data (for `application/vnd.openxmlformats-officedocument.wordprocessingml.document`)
  - HTML text (legacy only, for `text/html`)
  - Base64-encoded PDF data (for `application/pdf`)
- `fileName` (optional): Custom filename without extension. If not provided, a timestamped filename will be generated (e.g., `cover_letter_20240115_143022`).
- `contentType` (optional): Content type of the cover letter. Defaults to `"application/vnd.openxmlformats-officedocument.wordprocessingml.document"`. Can be:
  - `"application/vnd.openxmlformats-officedocument.wordprocessingml.document"` - Saves as `.docx` file (requires base64 DOCX data)
  - `"application/pdf"` - Saves as `.pdf` file (requires base64 PDF data)
  - `"text/markdown"` - Saves as `.md` file
  - `"text/html"` - Saves as `.html` file (legacy)
- `user_id` (optional): User ID - required if `user_email` is not provided
- `user_email` (optional): User email - will be resolved to `user_id` if provided

**Response (200 OK):**

```json
{
  "success": true,
  "key": "507f1f77bcf86cd799439011/generated_cover_letters/cover_letter_company_name.docx",
  "fileName": "cover_letter_company_name.docx",
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
- File extension (`.docx`, `.pdf`, `.md`, or `.html`) is automatically added based on `contentType`
- If `fileName` already includes an extension (`.docx`, `.pdf`, `.md`, `.html`, `.txt`), it will be used as-is
- The main user folder (`{user_id}/`) is also created if it doesn't exist
- Filenames are sanitized to ensure S3 compatibility

---

## Client-Side Implementation Examples

### JavaScript/React Example

```javascript
// Function to save a cover letter
async function saveCoverLetter(
  coverLetterContent,
  fileName = null,
  user_id = null,
  user_email = null,
) {
  const API_BASE_URL = "http://localhost:8000"; // or your production URL

  try {
    const requestBody = {
      coverLetterContent: coverLetterContent,
      contentType:
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document", // primary
      user_id: user_id,
      user_email: user_email,
    };

    // Add custom filename if provided
    if (fileName) {
      requestBody.fileName = fileName;
    }

    const response = await fetch(
      `${API_BASE_URL}/api/files/save-cover-letter`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(requestBody),
      },
    );

    if (!response.ok) {
      const errorData = await response.json();
      throw new Error(
        errorData.detail || `HTTP error! status: ${response.status}`,
      );
    }

    const result = await response.json();
    console.log("Cover letter saved successfully:", result);
    return result;
  } catch (error) {
    console.error("Error saving cover letter:", error);
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
  "507f1f77bcf86cd799439011", // user_id
)
  .then((result) => {
    console.log(`Cover letter saved as: ${result.fileName}`);
    console.log(`S3 key: ${result.key}`);
  })
  .catch((error) => {
    console.error("Failed to save cover letter:", error);
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
  "text/html", // Specify HTML content type
).then((result) => {
  console.log(`HTML cover letter saved as: ${result.fileName}`);
});
```

### React Component Example

```jsx
import React, { useState } from "react";

function SaveCoverLetterButton({ coverLetterContent, user_id, user_email }) {
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const handleSave = async () => {
    if (!coverLetterContent) {
      setMessage("No cover letter content to save");
      return;
    }

    setSaving(true);
    setMessage("");

    try {
      const response = await fetch(
        "http://localhost:8000/api/files/save-cover-letter",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            coverLetterContent: coverLetterContent,
            contentType: "text/markdown",
            user_id: user_id,
            user_email: user_email,
          }),
        },
      );

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || "Failed to save cover letter");
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
      <button onClick={handleSave} disabled={saving || !coverLetterContent}>
        {saving ? "Saving..." : "Save Cover Letter"}
      </button>
      {message && <p>{message}</p>}
    </div>
  );
}

export default SaveCoverLetterButton;
```

### React Native Example

```javascript
import { Alert } from "react-native";

async function saveCoverLetter(coverLetterContent, fileName, user_id) {
  const API_BASE_URL = "http://localhost:8000"; // or your production URL

  try {
    const response = await fetch(
      `${API_BASE_URL}/api/files/save-cover-letter`,
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          coverLetterContent: coverLetterContent,
          fileName: fileName,
          contentType: "text/markdown",
          user_id: user_id,
        }),
      },
    );

    const result = await response.json();

    if (!response.ok) {
      throw new Error(result.detail || "Failed to save cover letter");
    }

    Alert.alert("Success", `Cover letter saved as ${result.fileName}`);
    return result;
  } catch (error) {
    Alert.alert("Error", error.message);
    throw error;
  }
}

// Usage
saveCoverLetter(markdownContent, "cover_letter_tech_corp", user_id);
```

### Using with Generated Cover Letter Response

When you receive a cover letter from the `/api/job-info` endpoint, you can save it like this:

```javascript
// After generating a cover letter
const jobInfoResponse = await fetch("http://localhost:8000/api/job-info", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({
    llm: "gpt-4.1",
    company_name: "Tech Corp",
    // ... other fields
    user_id: user_id,
  }),
});

const coverLetterData = await jobInfoResponse.json();

// Save the markdown version
await saveCoverLetter(
  coverLetterData.markdown,
  `cover_letter_tech_corp_${new Date().toISOString().split("T")[0]}`,
  user_id,
);

// Or save the HTML version
await saveCoverLetter(
  coverLetterData.html,
  `cover_letter_tech_corp_${new Date().toISOString().split("T")[0]}`,
  user_id,
  null,
  "text/html",
);
```

### Saving PDF Cover Letters

To save a PDF cover letter, you need to provide base64-encoded PDF data:

```javascript
// Example: Converting HTML/Markdown to PDF and saving
// (This assumes you have a PDF generation library like jsPDF, html2pdf, etc.)

// Method 1: If you already have a PDF as base64 string
const pdfBase64 =
  "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU..."; // Your base64 PDF string

await saveCoverLetter(
  pdfBase64,
  "cover_letter_tech_corp",
  user_id,
  null,
  "application/pdf",
);

// Method 2: Generate PDF from HTML using a library (example with html2pdf.js)
import html2pdf from "html2pdf.js";

async function saveCoverLetterAsPDF(htmlContent, fileName, user_id) {
  // Generate PDF from HTML
  const opt = {
    margin: 1,
    filename: `${fileName}.pdf`,
    image: { type: "jpeg", quality: 0.98 },
    html2canvas: { scale: 2 },
    jsPDF: { unit: "in", format: "letter", orientation: "portrait" },
  };

  // Generate PDF blob
  const pdfBlob = await html2pdf().set(opt).from(htmlContent).outputPdf("blob");

  // Convert blob to base64
  const base64PDF = await new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onloadend = () => {
      // Remove data:application/pdf;base64, prefix
      const base64String = reader.result.split(",")[1];
      resolve(base64String);
    };
    reader.onerror = reject;
    reader.readAsDataURL(pdfBlob);
  });

  // Save to S3
  return await saveCoverLetter(
    base64PDF,
    fileName,
    user_id,
    null,
    "application/pdf",
  );
}

// Usage
await saveCoverLetterAsPDF(htmlContent, "cover_letter_tech_corp", user_id);
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
      cover_letter_company_name.pdf
      ...
```

- Each user has their own folder: `{user_id}/`
- Cover letters are stored in a subfolder: `{user_id}/generated_cover_letters/`
- Files are named with the provided `fileName` or auto-generated timestamp
- File extensions (`.md`, `.html`, or `.pdf`) are added based on `contentType`

---

## Error Handling

### Common Errors

1. **400 Bad Request**: Missing `coverLetterContent` or user identification

   ```json
   {
     "detail": "user_id or user_email is required to save cover letters"
   }
   ```

2. **400 Bad Request**: Invalid PDF data (when contentType is "application/pdf")

   ```json
   {
     "detail": "Invalid PDF data: content does not appear to be a valid PDF file"
   }
   ```

   or

   ```json
   {
     "detail": "Invalid base64 PDF data: ..."
   }
   ```

3. **404 Not Found**: User not found when using `user_email`

   ```json
   {
     "detail": "User not found for email: user@example.com"
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
2. **Use descriptive filenames**: When providing a custom `fileName`, use descriptive names like `cover_letter_company_name_position`
3. **Choose appropriate content type**:
   - Use `text/markdown` for markdown content
   - Use `text/html` for HTML content
   - Use `application/pdf` for PDF files (must be base64-encoded)
4. **PDF encoding**: When saving PDFs, ensure the `coverLetterContent` is base64-encoded. The API will validate that it's a valid PDF by checking the file header.
5. **Handle errors gracefully**: Always wrap API calls in try-catch blocks and provide user feedback
6. **Validate content**: Ensure `coverLetterContent` is not empty before calling the API
7. **Consider file size**: While there's no strict limit, very large cover letters may take longer to upload. PDFs are typically larger than text files.

---

## Testing

You can test the endpoint using curl:

**Test with Markdown:**

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

**Test with PDF (base64-encoded):**

```bash
curl -X POST http://localhost:8000/api/files/save-cover-letter \
  -H "Content-Type: application/json" \
  -d '{
    "coverLetterContent": "JVBERi0xLjQKJeLjz9MKMyAwIG9iago8PC9MZW5ndGggNCAwIFIKL0ZpbHRlciAvRmxhdGVEZWNvZGU+PgpzdHJlYW0KeAGF...",
    "fileName": "test_cover_letter",
    "contentType": "application/pdf",
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

For PDF:

```json
{
  "success": true,
  "key": "507f1f77bcf86cd799439011/generated_cover_letters/test_cover_letter.pdf",
  "fileName": "test_cover_letter.pdf",
  "message": "Cover letter saved successfully",
  "fileSize": 45678
}
```
