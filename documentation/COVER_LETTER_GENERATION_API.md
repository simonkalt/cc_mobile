# Cover Letter Generation API Documentation

API endpoints for generating cover letters using AI/LLM models. These endpoints accept job information and resume content to generate personalized cover letters.

**Contract: docx-only.** The API returns a single formatted artifact—the .docx file (`docxBase64`). No HTML or Markdown is returned; optional `content` is plain text only. The frontend should use the .docx for display, editing, print preview (via POST /api/files/docx-to-pdf), and save.

## Base URL

```
http://localhost:8000  (local)
https://your-domain.com  (production)
```

## Endpoints

### 1. Generate Cover Letter (General)

**POST** `/api/job-info`

Generate a cover letter based on job information. This endpoint accepts resume content in multiple formats:

- Plain text resume content
- S3 key (format: `user_id/filename.pdf`) - will be downloaded from S3
- Base64-encoded PDF data - will be decoded and text extracted

**Request Body:**

```json
{
  "llm": "gpt-4",
  "date_input": "2024-01-15",
  "company_name": "Tech Corp",
  "hiring_manager": "John Doe",
  "ad_source": "LinkedIn",
  "resume": "John Doe\nSoftware Engineer\n...", // Can be text, S3 key, or base64 PDF
  "jd": "We are looking for a software engineer...",
  "additional_instructions": "Emphasize my experience with React",
  "tone": "Professional",
  "address": "San Francisco, CA",
  "phone_number": "+1-555-123-4567",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

**Request Fields:**

- `llm` (required): LLM model to use (e.g., "gpt-4", "gpt-3.5-turbo", "claude-3-opus", "grok-4-fast-reasoning")
- `date_input` (required): Date for the cover letter (format: YYYY-MM-DD)
- `company_name` (required): Name of the company
- `hiring_manager` (required): Name of the hiring manager (can be empty string)
- `ad_source` (required): Source of the job posting (can be empty string)
- `resume` (required): Resume content in one of these formats:
  - **Plain text**: Direct resume text content
  - **S3 key**: Format `user_id/filename.pdf` (e.g., `507f1f77bcf86cd799439011/resume.pdf`)
  - **Base64 PDF**: Base64-encoded PDF data (will be decoded automatically)
- `jd` (required): Job description text
- `additional_instructions` (optional): Additional instructions for the cover letter (default: "")
- `tone` (optional): Tone of the cover letter (default: "Professional")
- `address` (optional): Address (City, State) (default: "")
- `phone_number` (optional): Phone number (default: "")
- `user_id` (optional): User ID for accessing custom personality profiles
- `user_email` (optional): User email for accessing custom personality profiles (will be resolved to user_id)
- `print_properties` (optional): User print/layout settings. **If provided, the backend applies these when creating the .docx** so the first-run letter has the correct margins and font. See [print_properties shape](#print_properties-shape-request) below.

**Response (200 OK):**

```json
{
  "docxBase64": "<base64-encoded .docx bytes>",
  "docxTemplateHints": {
    "version": "1.0",
    "sourceFormat": "markdown",
    "outputFormat": "docx",
    "styleProfile": "cover_letter_standard",
    "fields": {
      "date_input": "2024-01-15",
      "company_name": "Tech Corp",
      "hiring_manager": "John Doe"
    }
  },
  "content": "Optional plain text of the letter (for search/fallback)."
}
```

**Response Fields (docx-only contract):**

- `docxBase64`: The cover letter as a .docx file (base64). Single formatted artifact; display/edit or convert to PDF via POST /api/files/docx-to-pdf.
- `docxTemplateHints`: Metadata for frontend (fields, style profile).
- `content`: Optional plain text. No `html` or `markdown` is returned.

**Error Responses:**

- `400 Bad Request`: Missing required fields or invalid request format
- `500 Internal Server Error`: Error generating cover letter or processing resume
- `503 Service Unavailable`: LLM service unavailable or S3 unavailable (when using S3 resume)

---

### 2. Generate Cover Letter with Pasted Resume Text

**POST** `/api/cover-letter/generate-with-text-resume`

Generate a cover letter using explicitly pasted resume text. This endpoint is designed for cases where the user pastes resume content directly into a text field instead of uploading a file.

**Important:** This endpoint accepts **all the same parameters** as `/api/job-info`, including:

- Personality profiles (via `user_id` or `user_email`)
- Custom tone settings
- Additional instructions
- Company name, hiring manager, ad source
- Address and phone number
- Job description

The only difference is that this endpoint uses `resume_text` (plain text) instead of `resume` (which can be text, S3 key, or base64 PDF). The frontend may also send `print_properties` (margins, fontFamily, fontSize, etc.) so the server can apply user margins when creating the .docx.

**Use this endpoint when:**

- User pastes resume text directly into a text field
- You want to explicitly indicate that the resume is plain text (not a file path or S3 key)
- You want clearer separation between file-based and text-based resume input

**Request Body:**

```json
{
  "llm": "gpt-4",
  "date_input": "2024-01-15",
  "company_name": "Tech Corp",
  "hiring_manager": "John Doe",
  "ad_source": "LinkedIn",
  "resume_text": "John Doe\nSoftware Engineer\n123 Main St\nSan Francisco, CA 94102\n\nEXPERIENCE\n\nSenior Software Engineer\nTech Company Inc.\n2020 - Present\n...",
  "jd": "We are looking for a software engineer...",
  "additional_instructions": "Emphasize my experience with React",
  "tone": "Professional",
  "address": "San Francisco, CA",
  "phone_number": "+1-555-123-4567",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

**Request Fields:**

All fields are identical to `/api/job-info` except for the resume field:

- `llm` (required): LLM model to use (e.g., "gpt-4", "gpt-3.5-turbo", "claude-3-opus", "grok-4-fast-reasoning")
- `date_input` (required): Date for the cover letter (format: YYYY-MM-DD)
- `company_name` (required): Name of the company
- `hiring_manager` (required): Name of the hiring manager (can be empty string)
- `ad_source` (required): Source of the job posting (can be empty string)
- `resume_text` (required): **Plain text resume content** (pasted by user) - This is the only difference from `/api/job-info` (which uses `resume`)
- `jd` (required): Job description text
- `additional_instructions` (optional): Additional instructions for customizing the cover letter (default: "")
- `tone` (optional): Tone of the cover letter (default: "Professional"). Can be customized based on personality profiles when `user_id` or `user_email` is provided
- `address` (optional): Address (City, State) (default: "")
- `phone_number` (optional): Phone number (default: "")
- `user_id` (optional): User ID for accessing custom personality profiles and user preferences
- `user_email` (optional): User email for accessing custom personality profiles (will be resolved to user_id)
- `print_properties` (optional): Same as `/api/job-info`. See [print_properties shape](#print_properties-shape-request) below.

**Response (200 OK):** Same as `/api/job-info`: `docxBase64`, `docxTemplateHints`, optional `content`. No `html` or `markdown`.

**Error Responses:**

- `400 Bad Request`: Missing required fields or invalid request format
- `500 Internal Server Error`: Error generating cover letter
- `503 Service Unavailable`: LLM service unavailable

---

### print_properties shape (request)

The client may send `print_properties` on **POST /api/job-info** and **POST /api/cover-letter/generate-with-text-resume**. The backend applies it when building the .docx so the first-run letter has the correct margins and font.

| Field | Type | Description |
|-------|------|-------------|
| `margins` | `{ top, right, bottom, left }` | Page margins in **inches** (e.g. `0.75`). All optional. |
| `fontFamily` | string | Optional. Default font (e.g. `"Times New Roman"`). |
| `fontSize` | number | Optional. Default font size in points (e.g. `12`). |
| `lineHeight` | number | Optional. Line height multiplier (e.g. `1.6`). |
| `pageSize` | `{ width, height }` | Optional. Page size in **inches** (e.g. `8.5`, `11`). |

Example request fragment:

```json
"print_properties": {
  "margins": { "top": 0.75, "right": 0.75, "bottom": 0.75, "left": 0.75 },
  "fontFamily": "Times New Roman",
  "fontSize": 12,
  "lineHeight": 1.6,
  "pageSize": { "width": 8.5, "height": 11 }
}
```

If the server does not support `print_properties`, it ignores the field; the client can still apply margins on load when the WebView parse/serialize succeeds.

---

### Expected response to the client

- **Request:** The backend accepts optional `print_properties` in the JSON body for **POST /api/job-info** and **POST /api/cover-letter/generate-with-text-resume**, with the shape above. Request body `print_properties` takes precedence over user preferences when building the .docx.
- **Response:** Unchanged. The server returns:
  - `docxBase64`: base64-encoded .docx (with margins and font applied when `print_properties` was sent)
  - `docxTemplateHints`: metadata (version, fields, style profile)
  - `content`: optional plain text of the letter
- No `html` or `markdown` in the response (docx-only contract). Once the server applies margins and optional font/pageSize when generating the .docx, the "initial generation not applying user margins on first run" issue is addressed at the source.

---

## Usage Examples

### JavaScript/React - Using Pasted Resume Text

```javascript
async function generateCoverLetterWithPastedResume(
  resumeText,
  jobInfo,
  userId,
) {
  const response = await fetch(
    "http://localhost:8000/api/cover-letter/generate-with-text-resume",
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        llm: "gpt-4",
        date_input: new Date().toISOString().split("T")[0],
        company_name: jobInfo.companyName,
        hiring_manager: jobInfo.hiringManager || "",
        ad_source: jobInfo.adSource || "",
        resume_text: resumeText, // Pasted resume text (only difference from file version)
        jd: jobInfo.jobDescription,
        additional_instructions: jobInfo.additionalInstructions || "", // Custom instructions
        tone: jobInfo.tone || "Professional", // Tone setting (can use personality profiles)
        address: jobInfo.address || "",
        phone_number: jobInfo.phoneNumber || "",
        user_id: userId, // Enables personality profiles and user preferences
        // user_email: 'user@example.com',  // Alternative to user_id
      }),
    },
  );

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to generate cover letter");
  }

  return await response.json();
}

// Usage
const resumeText = document.getElementById("resume-textarea").value;
const coverLetter = await generateCoverLetterWithPastedResume(
  resumeText,
  {
    companyName: "Tech Corp",
    hiringManager: "John Doe",
    jobDescription: "We are looking for...",
  },
  "507f1f77bcf86cd799439011",
);

console.log(coverLetter.markdown); // Markdown format
console.log(coverLetter.docxTemplateHints); // DOCX generation/editing hints
```

### JavaScript/React - Using S3 Resume File

```javascript
async function generateCoverLetterWithS3Resume(s3Key, jobInfo, userId) {
  const response = await fetch("http://localhost:8000/api/job-info", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      llm: "gpt-4",
      date_input: new Date().toISOString().split("T")[0],
      company_name: jobInfo.companyName,
      hiring_manager: jobInfo.hiringManager || "",
      ad_source: jobInfo.adSource || "",
      resume: `${userId}/${s3Key}`, // S3 key format: user_id/filename.pdf
      jd: jobInfo.jobDescription,
      additional_instructions: jobInfo.additionalInstructions || "",
      tone: jobInfo.tone || "Professional",
      address: jobInfo.address || "",
      phone_number: jobInfo.phoneNumber || "",
      user_id: userId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || "Failed to generate cover letter");
  }

  return await response.json();
}
```

### Using Axios

```javascript
import axios from "axios";

const generateCoverLetter = async (resumeText, jobInfo, userId) => {
  try {
    const response = await axios.post(
      "http://localhost:8000/api/cover-letter/generate-with-text-resume",
      {
        llm: "gpt-4",
        date_input: new Date().toISOString().split("T")[0],
        company_name: jobInfo.companyName,
        hiring_manager: jobInfo.hiringManager || "",
        ad_source: jobInfo.adSource || "",
        resume_text: resumeText,
        jd: jobInfo.jobDescription,
        additional_instructions: jobInfo.additionalInstructions || "",
        tone: jobInfo.tone || "Professional",
        address: jobInfo.address || "",
        phone_number: jobInfo.phoneNumber || "",
        user_id: userId,
      },
    );

    return response.data;
  } catch (error) {
    console.error(
      "Error generating cover letter:",
      error.response?.data || error.message,
    );
    throw error;
  }
};
```

### cURL Examples

#### Generate with Pasted Resume Text

```bash
curl -X POST "http://localhost:8000/api/cover-letter/generate-with-text-resume" \
  -H "Content-Type: application/json" \
  -d '{
    "llm": "gpt-4",
    "date_input": "2024-01-15",
    "company_name": "Tech Corp",
    "hiring_manager": "John Doe",
    "ad_source": "LinkedIn",
    "resume_text": "John Doe\nSoftware Engineer\n123 Main St\nSan Francisco, CA\n\nEXPERIENCE\n\nSenior Software Engineer\nTech Company\n2020 - Present",
    "jd": "We are looking for a software engineer with experience in React and Node.js.",
    "additional_instructions": "Emphasize my React experience",
    "tone": "Professional",
    "address": "San Francisco, CA",
    "phone_number": "+1-555-123-4567",
    "user_id": "507f1f77bcf86cd799439011"
  }'
```

**Note:** All parameters shown above (including `additional_instructions`, `tone`, `address`, `phone_number`, and `user_id` for personality profiles) work exactly the same as the `/api/job-info` endpoint. The only difference is using `resume_text` instead of `resume`.

#### Generate with S3 Resume File

```bash
curl -X POST "http://localhost:8000/api/job-info" \
  -H "Content-Type: application/json" \
  -d '{
    "llm": "gpt-4",
    "date_input": "2024-01-15",
    "company_name": "Tech Corp",
    "hiring_manager": "John Doe",
    "ad_source": "LinkedIn",
    "resume": "507f1f77bcf86cd799439011/resume.pdf",
    "jd": "We are looking for a software engineer...",
    "user_id": "507f1f77bcf86cd799439011"
  }'
```

---

## Resume Format Handling

### Plain Text Resume

When using `/api/cover-letter/generate-with-text-resume`, the `resume_text` parameter should contain plain text resume content. The text will be used directly without any processing.

**Example:**

```
John Doe
Software Engineer
123 Main St, San Francisco, CA 94102
john.doe@email.com
(555) 123-4567

EXPERIENCE

Senior Software Engineer
Tech Company Inc.
2020 - Present
- Developed React applications...
```

### S3 Resume File

When using `/api/job-info` with an S3 key:

- Format: `user_id/filename.pdf` (e.g., `507f1f77bcf86cd799439011/resume.pdf`)
- The file will be downloaded from S3
- Text will be extracted from the PDF automatically
- Requires `user_id` to be provided

### Base64 PDF Resume

When using `/api/job-info` with base64-encoded PDF:

- The PDF data should be base64-encoded
- The endpoint will automatically detect and decode it
- Text will be extracted from the PDF

---

## Personality Profiles

Both endpoints support custom personality profiles when `user_id` or `user_email` is provided. The personality profile will be used to customize the tone and style of the generated cover letter.

If no `user_id` or `user_email` is provided, a default personality profile will be used.

---

## Supported LLM Models

The `llm` parameter accepts various model identifiers. Common options include:

- `gpt-4` - OpenAI GPT-4
- `gpt-3.5-turbo` - OpenAI GPT-3.5 Turbo
- `claude-3-opus` - Anthropic Claude 3 Opus
- `claude-3-sonnet` - Anthropic Claude 3 Sonnet
- `grok-4-fast-reasoning` - xAI Grok 4
- `gemini-pro` - Google Gemini Pro

Check your LLM configuration for available models.

---

## Error Handling

Always handle errors appropriately:

```javascript
try {
  const coverLetter = await generateCoverLetterWithPastedResume(
    resumeText,
    jobInfo,
    userId,
  );
  // Use coverLetter.markdown + coverLetter.docxTemplateHints
} catch (error) {
  if (error.response?.status === 400) {
    console.error("Invalid request:", error.response.data.detail);
  } else if (error.response?.status === 503) {
    console.error("Service unavailable:", error.response.data.detail);
  } else {
    console.error("Unexpected error:", error.message);
  }
}
```

---

## Related Endpoints

- **Save Cover Letter**: `POST /api/files/save-cover-letter` - Save generated cover letter to S3
- **List Cover Letters**: `GET /api/cover-letters/list` - List saved cover letters
- **Download Cover Letter**: `GET /api/cover-letters/download` - Download a saved cover letter
- **Delete Cover Letter**: `DELETE /api/cover-letters/delete` - Delete a saved cover letter

---

## Notes

1. **Resume Processing**: The `/api/job-info` endpoint automatically detects the resume format (text, S3 key, or base64 PDF). For explicit text input, use `/api/cover-letter/generate-with-text-resume`.

2. **Parameter Parity**: Both endpoints (`/api/job-info` and `/api/cover-letter/generate-with-text-resume`) accept **exactly the same parameters** except for the resume field:
   - `/api/job-info` uses `resume` (can be text, S3 key, or base64 PDF)
   - `/api/cover-letter/generate-with-text-resume` uses `resume_text` (plain text only)

   All other parameters (personality profiles via `user_id`/`user_email`, `tone`, `additional_instructions`, `company_name`, `hiring_manager`, `ad_source`, `address`, `phone_number`, etc.) work identically on both endpoints.

3. **User Identification**: Providing `user_id` or `user_email` enables access to custom personality profiles and user preferences.

4. **Date Format**: The `date_input` should be in `YYYY-MM-DD` format (e.g., "2024-01-15").

5. **Response Format**: Both endpoints return markdown content and `docxTemplateHints` (HTML is deprecated and removed from generation responses).

6. **Performance**: Cover letter generation typically takes 5-30 seconds depending on the LLM model and content length.

7. **Rate Limiting**: Be aware of rate limits for your LLM provider when making multiple requests.
