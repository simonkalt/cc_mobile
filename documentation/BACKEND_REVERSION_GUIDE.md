# Backend Reversion Guide: Remove CAPTCHA Logic and Restore LinkedIn-Only URLs

This document outlines the changes needed to revert the backend to remove CAPTCHA handling logic and restore LinkedIn-only URL validation.

## Overview

The backend was modified to:
1. Support CAPTCHA detection and handling
2. Accept HTML content directly from the frontend (for CAPTCHA completion)
3. Support multiple job sites (Indeed, Glassdoor, etc.) instead of just LinkedIn

This guide will help you revert these changes to restore LinkedIn-only functionality without CAPTCHA handling.

## Files to Modify

### 1. `backend/job_url_api_endpoint.py`

**Changes to revert:**
- Remove `html_content` parameter from `JobURLRequest` model
- Remove passing `html_content` to `analyze_job_url` function

**Before (current):**
```python
class JobURLRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = None
    user_email: Optional[str] = None
    html_content: Optional[str] = None  # Remove this line

@router.post("/api/job-url/analyze")
async def analyze_job_url_endpoint(request: JobURLRequest):
    result = await analyze_job_url(
        url=url_str,
        user_id=request.user_id,
        user_email=request.user_email,
        use_grok_fallback=True,
        html_content=request.html_content,  # Remove this parameter
    )
```

**After (reverted):**
```python
class JobURLRequest(BaseModel):
    url: HttpUrl
    user_id: Optional[str] = None
    user_email: Optional[str] = None

@router.post("/api/job-url/analyze")
async def analyze_job_url_endpoint(request: JobURLRequest):
    result = await analyze_job_url(
        url=url_str,
        user_id=request.user_id,
        user_email=request.user_email,
        use_grok_fallback=True,
    )
```

### 2. `backend/job_url_analyzer.py`

This file has extensive CAPTCHA-related changes. Here's what needs to be reverted:

#### A. Remove CAPTCHA Detection Function

**Remove entirely:**
- `detect_captcha(html: str) -> bool` function (lines ~412-521)

#### B. Simplify `fetch_html` Function

**Current:** Returns `(html_content, error_message, captcha_detected)`

**Revert to:** Return `(html_content, error_message)` and remove all CAPTCHA detection logic

**Key changes:**
- Remove all calls to `detect_captcha()`
- Remove CAPTCHA detection for error status codes (403, 429, 503)
- Remove Indeed-specific CAPTCHA handling
- Simplify to basic HTTP fetch with error handling

**Simplified version:**
```python
def fetch_html(url: str, timeout: int = 10) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch HTML content from URL

    Returns:
        Tuple of (html_content, error_message)
    """
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        response = requests.get(
            url, headers=headers, timeout=timeout, allow_redirects=True
        )

        # Try to detect encoding
        if response.encoding:
            html = response.text
        else:
            html = response.content.decode("utf-8", errors="ignore")

        # Check status code
        response.raise_for_status()

        return html, None

    except requests.exceptions.Timeout:
        return None, "Request timeout"
    except requests.exceptions.RequestException as e:
        return None, f"Failed to fetch URL: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error fetching URL: {str(e)}"
```

#### C. Remove `extract_from_html` Function

**Remove entirely:**
- `extract_from_html(html: str, url: str) -> JobExtractionResult` function (lines ~645-720)

#### D. Simplify `extract_with_beautifulsoup` Function

**Remove:**
- All CAPTCHA detection logic
- The `captcha_detected` variable and related checks
- The logic that marks results as `captcha-required`

**Key change:**
```python
def extract_with_beautifulsoup(url: str) -> JobExtractionResult:
    # Fetch HTML (simplified - no CAPTCHA detection)
    html, error = fetch_html(url)  # Changed from 3-tuple to 2-tuple

    if error or not html:
        logger.warning(f"Failed to fetch HTML: {error}")
        result = JobExtractionResult()
        result.method = "beautifulsoup-failed"
        return result

    # ... rest of parsing logic (no CAPTCHA checks) ...
    
    # Remove this entire block:
    # if captcha_detected:
    #     if result.has_minimum_data():
    #         ...
    #     else:
    #         result.method = "captcha-required"
    #         return result
```

#### E. Update `analyze_job_url` Function

**Remove:**
- `html_content: Optional[str] = None` parameter
- All logic that handles `html_content`
- All CAPTCHA-related return statements
- The final response preparation logic that removes `captcha_required`

**Key changes:**

1. **Remove html_content parameter:**
```python
async def analyze_job_url(
    url: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    use_grok_fallback: bool = True,
    grok_client: Optional[Grok] = None,
    # Remove: html_content: Optional[str] = None,
) -> Dict:
```

2. **Simplify extraction logic:**
```python
# Remove this conditional:
# if html_content:
#     logger.info("Using provided HTML content for extraction...")
#     result = extract_from_html(html_content, url)
# else:
#     logger.info("Attempting BeautifulSoup extraction...")
#     result = extract_with_beautifulsoup(url)

# Replace with:
logger.info("Attempting BeautifulSoup extraction...")
result = extract_with_beautifulsoup(url)
```

3. **Remove CAPTCHA check:**
```python
# Remove this entire block:
# if result.method == "captcha-required":
#     if html_content:
#         ...
#     else:
#         return {
#             "success": False,
#             "captcha_required": True,
#             ...
#         }
```

4. **Simplify Grok fallback:**
```python
# Remove html_content checks from Grok fallback
# Change from:
# if html_content:
#     html = html_content
#     error = None
#     captcha_detected = False
# else:
#     html, error, captcha_detected = fetch_html(url)

# To:
html, error = fetch_html(url)  # Simplified to 2-tuple

# Remove all captcha_detected checks in Grok fallback section
```

5. **Simplify final response:**
```python
# Prepare response
response_data = result.to_dict()
response_data["url"] = url

# Set success based on whether we have valid data
has_valid_data = result.has_minimum_data()
response_data["success"] = has_valid_data

# Remove this entire block:
# if html_content:
#     if "captcha_required" in response_data:
#         ...
#     if not has_valid_data:
#         response_data["message"] = ...
```

#### F. Add LinkedIn URL Validation

**Add at the beginning of `analyze_job_url`:**
```python
async def analyze_job_url(
    url: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    use_grok_fallback: bool = True,
    grok_client: Optional[Grok] = None,
) -> Dict:
    logger.info(
        f"Analyzing job URL: {url} (user_id={user_id}, user_email={user_email})"
    )

    # Validate URL format
    if not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL format. URL must start with http:// or https://")

    # Validate LinkedIn URL
    if "linkedin.com/jobs" not in url.lower():
        raise ValueError("Only LinkedIn job posting URLs are supported. Please provide a LinkedIn job URL (e.g., https://www.linkedin.com/jobs/view/...)")

    # ... rest of function ...
```

#### G. Simplify `detect_site` Function (Optional)

**If you want to enforce LinkedIn-only:**
```python
def detect_site(url: str) -> str:
    """
    Detect the job site from URL
    
    Returns:
        Site identifier: "linkedin", "indeed", "glassdoor", or "generic"
    """
    url_lower = url.lower()
    
    # Only support LinkedIn
    if "linkedin.com" in url_lower:
        return "linkedin"
    
    # Reject all other sites
    raise ValueError("Only LinkedIn job posting URLs are supported")
```

### 3. Remove Parser Classes (Optional)

If you want to enforce LinkedIn-only, you can remove:
- `IndeedParser` class
- `GlassdoorParser` class  
- `GenericParser` class (or keep as fallback)

Keep only:
- `BaseJobParser` class
- `LinkedInParser` class

## Summary of Changes

### Functions to Remove:
1. `detect_captcha()` - Entire function
2. `extract_from_html()` - Entire function

### Functions to Simplify:
1. `fetch_html()` - Remove CAPTCHA detection, return 2-tuple instead of 3-tuple
2. `extract_with_beautifulsoup()` - Remove CAPTCHA checks
3. `analyze_job_url()` - Remove html_content parameter and all CAPTCHA logic
4. `detect_site()` - Optionally enforce LinkedIn-only

### API Changes:
1. Remove `html_content` from `JobURLRequest` model
2. Remove `captcha_required` from response format
3. Add LinkedIn URL validation

### Response Format Changes:

**Remove from response:**
- `captcha_required` field
- CAPTCHA-related error messages

**Keep:**
- `success` (boolean)
- `company`, `job_title`, `full_description`, `hiring_manager`
- `ad_source` (should always be "linkedin")
- `extractionMethod`
- `url`

## Testing Checklist

After reverting, verify:
- [ ] LinkedIn URLs are accepted and parsed correctly
- [ ] Non-LinkedIn URLs are rejected with appropriate error
- [ ] No CAPTCHA-related code remains
- [ ] Error handling works for invalid URLs
- [ ] Error handling works for failed extractions
- [ ] Grok fallback still works if BeautifulSoup fails

## Notes

- The frontend has already been updated to remove CAPTCHA logic and enforce LinkedIn-only URLs
- This reversion will make the backend match the frontend's simplified approach
- All CAPTCHA-related functionality should be completely removed
- The backend should only support LinkedIn job posting URLs

