# Job URL Analysis API Documentation

This endpoint uses a hybrid BeautifulSoup + Grok AI approach to analyze a job posting URL and extract structured information including company name, job title, job description, ad source, and hiring manager (if available).

## Quick Reference

**Endpoint**: `POST /api/job-url/analyze`

**Base URL**: `https://your-api-domain.com` (or `http://localhost:8000` for local development)

**Request**:
```json
{
  "url": "https://www.linkedin.com/jobs/view/123456",
  "user_id": "optional-user-id",
  "user_email": "optional@email.com"
}
```

**Success Response** (200 OK):
```json
{
  "success": true,
  "url": "...",
  "company": "Company Name",
  "job_title": "Job Title",
  "ad_source": "linkedin",
  "full_description": "Job description...",
  "hiring_manager": "Name or empty string",
  "extractionMethod": "hybrid-bs-beautifulsoup-linkedin-grok"
}
```

**CAPTCHA Required Response** (200 OK):
```json
{
  "success": false,
  "captcha_required": true,
  "url": "...",
  "message": "CAPTCHA or human verification required...",
  "company": "Not specified",
  "job_title": "Not specified",
  "ad_source": "indeed",
  "full_description": "Not specified",
  "hiring_manager": "",
  "extractionMethod": "error"
}
```

## Endpoint

**POST** `/api/job-url/analyze`

Analyze a job posting webpage and extract key information using hybrid extraction methods.

## Overview

This endpoint:
1. Fetches the HTML content from the provided job posting URL
2. Attempts BeautifulSoup extraction first (fast, site-specific parsers for LinkedIn, Indeed, Glassdoor)
3. Falls back to Grok AI extraction if BeautifulSoup results are incomplete
4. Intelligently combines results from both methods
5. Returns structured information (company, job_title, ad_source, full_description, hiring_manager)
6. Handles CAPTCHA/verification requirements gracefully

## Request Body

```json
{
  "url": "https://www.example.com/jobs/software-engineer",
  "user_id": "507f1f77bcf86cd799439011",
  "user_email": "user@example.com"
}
```

## Request Fields

- `url` (required): The URL to the job posting page. Must start with `http://` or `https://`
- `user_id` (optional): User ID for tracking/logging purposes
- `user_email` (optional): User email for tracking/logging purposes

## Response (200 OK)

```json
{
  "success": true,
  "url": "https://www.example.com/jobs/software-engineer",
  "company": "Example Corporation",
  "job_title": "Senior Software Engineer",
  "ad_source": "linkedin",
  "full_description": "We are seeking a Senior Software Engineer to join our team. Responsibilities include developing and maintaining web applications, collaborating with cross-functional teams, and contributing to technical design decisions. Requirements: 5+ years of experience, proficiency in Python and JavaScript, strong problem-solving skills.",
  "hiring_manager": "John Smith",
  "extractionMethod": "hybrid-bs-beautifulsoup-linkedin-grok"
}
```

## Response Fields

- `success`: Boolean indicating success (always `true` on success)
- `url`: The analyzed URL (echoed back from request)
- `company`: The company name extracted from the job posting
- `job_title`: The job title/position name
- `ad_source`: Source site detected from URL (`linkedin`, `indeed`, `glassdoor`, or `generic`)
- `full_description`: The full job description including responsibilities, requirements, and qualifications
- `hiring_manager`: Name of the hiring manager or recruiter (empty string `""` if not found in the posting)
- `extractionMethod`: Method used for extraction (format: `hybrid-bs-{bs_method}-grok`)

## Error Responses

### 200 OK - CAPTCHA Required (Success: false)

When a website requires CAPTCHA or human verification (common with Indeed and some other sites), the endpoint returns a 200 OK response with `success: false`:

```json
{
  "success": false,
  "captcha_required": true,
  "url": "https://www.indeed.com/viewjob?jk=...",
  "message": "CAPTCHA or human verification required. The website is blocking automated access.",
  "company": "Not specified",
  "job_title": "Not specified",
  "ad_source": "indeed",
  "full_description": "Not specified",
  "hiring_manager": "",
  "extractionMethod": "error"
}
```

**Frontend Handling**: Check for `success: false` and `captcha_required: true` to show a user-friendly message asking them to paste the job description manually.

### 400 Bad Request
```json
{
  "detail": "Invalid URL format. URL must start with http:// or https://"
}
```

### 500 Internal Server Error
```json
{
  "detail": "Failed to fetch or analyze job URL: [error message]"
}
```

### 503 Service Unavailable
```json
{
  "detail": "Grok API key is not configured. Cannot analyze job URL."
}
```

## How It Works

### Extraction Flow

1. **URL Validation**: Validates that the URL starts with `http://` or `https://`

2. **HTML Fetching**: Fetches the HTML content using a browser-like User-Agent header with CAPTCHA detection

3. **CAPTCHA Detection**: Checks for CAPTCHA indicators (Cloudflare, reCAPTCHA, etc.) and returns appropriate error if detected

4. **BeautifulSoup Extraction** (First Attempt):
   - Detects the job site (LinkedIn, Indeed, Glassdoor, or generic)
   - Uses site-specific parsers optimized for each platform
   - Extracts company, job title, description, and hiring manager using CSS selectors and JSON-LD structured data
   - Sets `ad_source` based on detected site

5. **Grok AI Extraction** (Fallback):
   - Only runs if BeautifulSoup extraction is incomplete
   - Uses AI to analyze HTML content (limited to 50,000 characters)
   - Extracts structured information with high accuracy
   - Handles unstructured content better than BeautifulSoup

6. **Result Combination**: Intelligently combines results:
   - Prefers Grok values when available (usually more complete)
   - Falls back to BeautifulSoup values when Grok has "Not specified"
   - Ensures all required fields are present

7. **Response Formatting**: Returns standardized JSON with all fields, using "Not specified" for missing data and empty string `""` for missing hiring manager

## Client-Side Usage Examples

### React/JavaScript - Basic Usage

```javascript
// Function to analyze a job URL
async function analyzeJobURL(jobURL) {
  const API_BASE_URL = 'http://localhost:8000';
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/job-url/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        url: jobURL
      })
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    
    const result = await response.json();
    return result;
  } catch (error) {
    console.error('Error analyzing job URL:', error);
    throw error;
  }
}

// Usage
const handleAnalyzeJob = async () => {
  const jobURL = 'https://www.linkedin.com/jobs/view/1234567890';
  try {
    const jobInfo = await analyzeJobURL(jobURL);
    console.log('Company:', jobInfo.company);
    console.log('Job Title:', jobInfo.job_title);
    console.log('Ad Source:', jobInfo.ad_source);
    console.log('Description:', jobInfo.full_description);
    console.log('Hiring Manager:', jobInfo.hiring_manager || 'Not specified');
    
    // Populate form fields with extracted information
    setCompanyName(jobInfo.company);
    setJobTitle(jobInfo.job_title);
    setJobDescription(jobInfo.full_description);
    setHiringManager(jobInfo.hiring_manager || '');
  } catch (error) {
    alert(`Failed to analyze job URL: ${error.message}`);
  }
};
```

### React/JavaScript - Complete Form Integration

```javascript
import { useState } from 'react';

function JobApplicationForm() {
  const [jobURL, setJobURL] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [jobTitle, setJobTitle] = useState('');
  const [jobDescription, setJobDescription] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleAnalyzeURL = async () => {
    if (!jobURL) {
      setError('Please enter a job URL');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch('http://localhost:8000/api/job-url/analyze', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          url: jobURL,
          user_id: getCurrentUserId() // Your user ID retrieval function
        })
      });

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || 'Failed to analyze URL');
      }

      const result = await response.json();
      
      // Populate form fields
      setCompanyName(result.company);
      setJobTitle(result.job_title);
      setJobDescription(result.full_description);
      setHiringManager(result.hiring_manager || '');
      
      alert('Job information extracted successfully!');
    } catch (err) {
      setError(err.message);
      console.error('Error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <h2>Job Application Form</h2>
      
      <div>
        <label>Job Posting URL:</label>
        <input
          type="url"
          value={jobURL}
          onChange={(e) => setJobURL(e.target.value)}
          placeholder="https://www.example.com/jobs/..."
        />
        <button onClick={handleAnalyzeURL} disabled={loading}>
          {loading ? 'Analyzing...' : 'Extract Job Info'}
        </button>
      </div>

      {error && <div style={{ color: 'red' }}>{error}</div>}

      <div>
        <label>Company Name:</label>
        <input
          type="text"
          value={companyName}
          onChange={(e) => setCompanyName(e.target.value)}
        />
      </div>

      <div>
        <label>Job Title:</label>
        <input
          type="text"
          value={jobTitle}
          onChange={(e) => setJobTitle(e.target.value)}
        />
      </div>

      <div>
        <label>Job Description:</label>
        <textarea
          value={jobDescription}
          onChange={(e) => setJobDescription(e.target.value)}
          rows={10}
        />
      </div>

      <div>
        <label>Hiring Manager:</label>
        <input
          type="text"
          value={hiringManager}
          onChange={(e) => setHiringManager(e.target.value)}
          placeholder="Leave empty if not found"
        />
      </div>

      {/* CAPTCHA Modal */}
      {showCaptchaModal && (
        <div className="modal">
          <div className="modal-content">
            <h3>Manual Entry Required</h3>
            <p>{captchaMessage}</p>
            <p>Please copy and paste the job description from the website:</p>
            <textarea
              placeholder="Paste job description here..."
              rows={10}
              onChange={(e) => setJobDescription(e.target.value)}
            />
            <button onClick={() => setShowCaptchaModal(false)}>Done</button>
          </div>
        </div>
      )}
    </div>
  );
}
```

### React/JavaScript - With User Context

```javascript
async function analyzeJobURLWithUser(jobURL, userId, userEmail) {
  const API_BASE_URL = 'http://localhost:8000';
  
  const requestBody = {
    url: jobURL
  };
  
  // Add user identification if available
  if (userId) {
    requestBody.user_id = userId;
  } else if (userEmail) {
    requestBody.user_email = userEmail;
  }
  
  try {
    const response = await fetch(`${API_BASE_URL}/api/job-url/analyze`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error('Error analyzing job URL:', error);
    throw error;
  }
}
```

## cURL Examples

### Basic Request

```bash
curl -X POST "http://localhost:8000/api/job-url/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.example.com/jobs/software-engineer"
  }'
```

### With User ID

```bash
curl -X POST "http://localhost:8000/api/job-url/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.example.com/jobs/software-engineer",
    "user_id": "507f1f77bcf86cd799439011"
  }'
```

### With User Email

```bash
curl -X POST "http://localhost:8000/api/job-url/analyze" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://www.example.com/jobs/software-engineer",
    "user_email": "user@example.com"
  }'
```

## Integration with Cover Letter Generation

This endpoint can be used to automatically populate the cover letter generation form:

```javascript
async function generateCoverLetterFromJobURL(jobURL, resume, userId) {
  // Step 1: Extract job information from URL
  const jobInfo = await analyzeJobURL(jobURL);
  
  // Step 2: Use extracted information to generate cover letter
  const coverLetterResponse = await fetch('http://localhost:8000/api/job-info', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      llm: 'grok-4-fast-reasoning',
      company_name: jobInfo.company,
      jd: jobInfo.full_description,
      resume: resume,
      hiring_manager: jobInfo.hiring_manager || '',
      user_id: userId,
      // ... other cover letter parameters
    })
  });
  
  return await coverLetterResponse.json();
}
```

## Supported Job Sites

This endpoint works with most job posting websites, including:
- LinkedIn
- Indeed
- Glassdoor
- Company career pages
- Job boards
- Any website with job posting content

## Limitations

1. **Content Size**: The endpoint limits webpage content to the first 50,000 characters to avoid token limits. Very long job descriptions may be truncated.

2. **Protected Content**: Some websites may block automated access or require authentication. The endpoint uses a browser-like User-Agent, but some sites may still block requests.

3. **Dynamic Content**: JavaScript-rendered content may not be captured, as the endpoint fetches the raw HTML. For single-page applications (SPAs), the content may not be fully available.

4. **Rate Limiting**: Grok API has rate limits. Excessive requests may be throttled.

5. **Accuracy**: While Grok is highly accurate, extraction quality depends on the structure and clarity of the job posting page.

## Error Handling Best Practices

```javascript
async function analyzeJobURLWithErrorHandling(jobURL) {
  try {
    const result = await analyzeJobURL(jobURL);
    
    // Check if extraction was successful
    if (result.company === "Not specified" && 
        result.job_title === "Not specified" && 
        result.full_description === "Not specified") {
      throw new Error('Failed to extract any information from the job posting');
    }
    
    // Validate extracted data
    if (result.company === "Not specified") {
      console.warn('Company name could not be extracted');
    }
    
    // Note: hiring_manager may be empty string if not found - this is normal
    
    return result;
  } catch (error) {
    if (error.message.includes('Invalid URL format')) {
      alert('Please enter a valid URL starting with http:// or https://');
    } else if (error.message.includes('Failed to fetch')) {
      alert('Could not access the job posting. The URL may be invalid or the site may be blocking access.');
    } else {
      alert(`Error: ${error.message}`);
    }
    throw error;
  }
}
```

## Notes

### Technical Details

- **Hybrid Approach**: Uses BeautifulSoup first (fast, free), then Grok AI as fallback (comprehensive)
- **Grok AI**: Uses `grok-beta` model for content analysis when needed
- **API Key**: Grok API key must be configured in server environment (`XAI_API_KEY`)
- **JSON Parsing**: Automatically handles JSON parsing, including removal of markdown code blocks
- **Field Defaults**: Missing fields default to "Not specified" (except `hiring_manager` which defaults to empty string `""`)
- **CAPTCHA Detection**: Automatically detects CAPTCHA requirements and returns appropriate error response
- **Logging**: Comprehensive logging for debugging purposes

### Field Behavior

- **company**: Always present, "Not specified" if extraction fails
- **job_title**: Always present, "Not specified" if extraction fails
- **ad_source**: Always present, detected from URL domain (`linkedin`, `indeed`, `glassdoor`, or `generic`)
- **full_description**: Always present, "Not specified" if extraction fails
- **hiring_manager**: Always present, empty string `""` if not found (this is normal - many postings don't include this)
- **extractionMethod**: Shows which method was used (`hybrid-bs-{site}-grok`, `beautifulsoup-{site}`, `grok`, etc.)

### Known Limitations

1. **Indeed.com**: Often blocks automated requests with 403 errors. The endpoint will return `captcha_required: true` in this case.
2. **CAPTCHA Sites**: Sites using Cloudflare, reCAPTCHA, or similar protection will require manual entry.
3. **Dynamic Content**: JavaScript-rendered content may not be captured (BeautifulSoup only sees initial HTML).
4. **Rate Limiting**: Some sites may rate-limit requests. The endpoint handles this gracefully.
5. **Content Size**: HTML content is limited to 50,000 characters for Grok analysis to avoid token limits.

## Troubleshooting

### Issue: "Grok API key is not configured"
**Solution**: Ensure the `XAI_API_KEY` environment variable is set on the server.

### Issue: "Failed to fetch or analyze job URL"
**Possible causes**:
- The URL is invalid or inaccessible
- The website is blocking automated requests
- Network connectivity issues
- The URL requires authentication

**Solution**: Verify the URL is accessible in a browser and try again.

### Issue: Extracted information is incomplete or incorrect
**Possible causes**:
- The job posting page has an unusual structure
- The content is dynamically loaded with JavaScript
- The page content exceeds the 50,000 character limit

**Solution**: Manually review and correct the extracted information, or try a different job posting URL.

