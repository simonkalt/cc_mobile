# Cover Letter Generation API Documentation

API endpoints for generating cover letters using AI/LLM models. These endpoints accept job information and resume content to generate personalized cover letters.

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
  "resume": "John Doe\nSoftware Engineer\n...",  // Can be text, S3 key, or base64 PDF
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

**Response (200 OK):**

```json
{
  "markdown": "# Cover Letter\n\nDear John Doe,\n\n...",
  "html": "<h1>Cover Letter</h1>\n<p>Dear John Doe,</p>\n<p>...</p>"
}
```

**Response Fields:**

- `markdown`: Cover letter content in Markdown format
- `html`: Cover letter content in HTML format

**Error Responses:**

- `400 Bad Request`: Missing required fields or invalid request format
- `500 Internal Server Error`: Error generating cover letter or processing resume
- `503 Service Unavailable`: LLM service unavailable or S3 unavailable (when using S3 resume)

---

### 2. Generate Cover Letter with Pasted Resume Text

**POST** `/api/cover-letter/generate-with-text-resume`

Generate a cover letter using explicitly pasted resume text. This endpoint is designed for cases where the user pastes resume content directly into a text field instead of uploading a file.

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

- `llm` (required): LLM model to use
- `date_input` (required): Date for the cover letter (format: YYYY-MM-DD)
- `company_name` (required): Name of the company
- `hiring_manager` (required): Name of the hiring manager (can be empty string)
- `ad_source` (required): Source of the job posting (can be empty string)
- `resume_text` (required): **Plain text resume content** (pasted by user)
- `jd` (required): Job description text
- `additional_instructions` (optional): Additional instructions (default: "")
- `tone` (optional): Tone of the cover letter (default: "Professional")
- `address` (optional): Address (City, State) (default: "")
- `phone_number` (optional): Phone number (default: "")
- `user_id` (optional): User ID for accessing custom personality profiles
- `user_email` (optional): User email (will be resolved to user_id)

**Response (200 OK):**

```json
{
  "markdown": "# Cover Letter\n\nDear John Doe,\n\n...",
  "html": "<h1>Cover Letter</h1>\n<p>Dear John Doe,</p>\n<p>...</p>"
}
```

**Response Fields:**

- `markdown`: Cover letter content in Markdown format
- `html`: Cover letter content in HTML format

**Error Responses:**

- `400 Bad Request`: Missing required fields or invalid request format
- `500 Internal Server Error`: Error generating cover letter
- `503 Service Unavailable`: LLM service unavailable

---

## Usage Examples

### JavaScript/React - Using Pasted Resume Text

```javascript
async function generateCoverLetterWithPastedResume(resumeText, jobInfo, userId) {
  const response = await fetch('http://localhost:8000/api/cover-letter/generate-with-text-resume', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      llm: 'gpt-4',
      date_input: new Date().toISOString().split('T')[0],
      company_name: jobInfo.companyName,
      hiring_manager: jobInfo.hiringManager || '',
      ad_source: jobInfo.adSource || '',
      resume_text: resumeText,  // Pasted resume text
      jd: jobInfo.jobDescription,
      additional_instructions: jobInfo.additionalInstructions || '',
      tone: jobInfo.tone || 'Professional',
      address: jobInfo.address || '',
      phone_number: jobInfo.phoneNumber || '',
      user_id: userId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to generate cover letter');
  }

  return await response.json();
}

// Usage
const resumeText = document.getElementById('resume-textarea').value;
const coverLetter = await generateCoverLetterWithPastedResume(
  resumeText,
  {
    companyName: 'Tech Corp',
    hiringManager: 'John Doe',
    jobDescription: 'We are looking for...',
  },
  '507f1f77bcf86cd799439011'
);

console.log(coverLetter.markdown);  // Markdown format
console.log(coverLetter.html);      // HTML format
```

### JavaScript/React - Using S3 Resume File

```javascript
async function generateCoverLetterWithS3Resume(s3Key, jobInfo, userId) {
  const response = await fetch('http://localhost:8000/api/job-info', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      llm: 'gpt-4',
      date_input: new Date().toISOString().split('T')[0],
      company_name: jobInfo.companyName,
      hiring_manager: jobInfo.hiringManager || '',
      ad_source: jobInfo.adSource || '',
      resume: `${userId}/${s3Key}`,  // S3 key format: user_id/filename.pdf
      jd: jobInfo.jobDescription,
      additional_instructions: jobInfo.additionalInstructions || '',
      tone: jobInfo.tone || 'Professional',
      address: jobInfo.address || '',
      phone_number: jobInfo.phoneNumber || '',
      user_id: userId,
    }),
  });

  if (!response.ok) {
    const error = await response.json();
    throw new Error(error.detail || 'Failed to generate cover letter');
  }

  return await response.json();
}
```

### Using Axios

```javascript
import axios from 'axios';

const generateCoverLetter = async (resumeText, jobInfo, userId) => {
  try {
    const response = await axios.post(
      'http://localhost:8000/api/cover-letter/generate-with-text-resume',
      {
        llm: 'gpt-4',
        date_input: new Date().toISOString().split('T')[0],
        company_name: jobInfo.companyName,
        hiring_manager: jobInfo.hiringManager || '',
        ad_source: jobInfo.adSource || '',
        resume_text: resumeText,
        jd: jobInfo.jobDescription,
        additional_instructions: jobInfo.additionalInstructions || '',
        tone: jobInfo.tone || 'Professional',
        address: jobInfo.address || '',
        phone_number: jobInfo.phoneNumber || '',
        user_id: userId,
      }
    );

    return response.data;
  } catch (error) {
    console.error('Error generating cover letter:', error.response?.data || error.message);
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
    "user_id": "507f1f77bcf86cd799439011"
  }'
```

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
  const coverLetter = await generateCoverLetterWithPastedResume(resumeText, jobInfo, userId);
  // Use coverLetter.markdown or coverLetter.html
} catch (error) {
  if (error.response?.status === 400) {
    console.error('Invalid request:', error.response.data.detail);
  } else if (error.response?.status === 503) {
    console.error('Service unavailable:', error.response.data.detail);
  } else {
    console.error('Unexpected error:', error.message);
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

2. **User Identification**: Providing `user_id` or `user_email` enables access to custom personality profiles and user preferences.

3. **Date Format**: The `date_input` should be in `YYYY-MM-DD` format (e.g., "2024-01-15").

4. **Response Format**: Both endpoints return the cover letter in both Markdown and HTML formats for flexibility in display.

5. **Performance**: Cover letter generation typically takes 5-30 seconds depending on the LLM model and content length.

6. **Rate Limiting**: Be aware of rate limits for your LLM provider when making multiple requests.

