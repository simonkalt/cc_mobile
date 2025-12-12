"""
Job URL Analyzer - Hybrid BeautifulSoup + Grok Implementation

This module implements a hybrid approach to extract job information from URLs:
1. First attempts BeautifulSoup parsing (fast, free)
2. Falls back to Grok AI if BeautifulSoup fails (handles complex cases)

Usage:
    from job_url_analyzer import analyze_job_url
    
    result = await analyze_job_url(
        url="https://www.linkedin.com/jobs/view/123456",
        user_id="507f1f77bcf86cd799439011"
    )
"""

import json
import re
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup
from xai import Grok

# Configure logging
logger = logging.getLogger(__name__)


class JobExtractionResult:
    """Container for job extraction results"""
    
    def __init__(self):
        self.company: Optional[str] = None
        self.job_title: Optional[str] = None
        self.job_description: Optional[str] = None
        self.hiring_manager: Optional[str] = None
        self.method: Optional[str] = None  # 'beautifulsoup' or 'grok'
        self.is_complete: bool = False
    
    def to_dict(self, ad_source: Optional[str] = None) -> Dict:
        """Convert to dictionary matching API response format"""
        return {
            "success": True,
            "company": self.company or "Not specified",
            "job_title": self.job_title or "Not specified",
            "ad_source": ad_source or "Not specified",
            "full_description": self.job_description or "Not specified",
            "hiring_manager": self.hiring_manager or "",  # Empty string if not found
            "extractionMethod": self.method or "unknown"
        }
    
    def has_minimum_data(self) -> bool:
        """Check if we have at least company and job description"""
        return (
            self.company and 
            self.company != "Not specified" and
            self.job_description and 
            self.job_description != "Not specified"
        )


class BaseJobParser:
    """Base class for job parsers"""
    
    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        """Parse job information from BeautifulSoup object"""
        raise NotImplementedError("Subclasses must implement parse()")


class LinkedInParser(BaseJobParser):
    """Parser for LinkedIn job postings"""
    
    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        result = JobExtractionResult()
        result.method = "beautifulsoup-linkedin"
        
        try:
            # Try JSON-LD structured data first
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                        result.company = data.get('hiringOrganization', {}).get('name')
                        result.job_title = data.get('title')
                        result.job_description = data.get('description')
                        if result.has_minimum_data():
                            result.is_complete = True
                            return result
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            # Try CSS selectors
            # Company name
            company_selectors = [
                '[data-testid="job-poster-name"]',
                'a[data-tracking-control-name="job_poster_name"]',
                '.job-details-jobs-unified-top-card__company-name',
                '.jobs-unified-top-card__company-name'
            ]
            for selector in company_selectors:
                element = soup.select_one(selector)
                if element:
                    result.company = element.get_text(strip=True)
                    break
            
            # Job title
            title_selectors = [
                'h1.job-title',
                'h1[data-testid="job-title"]',
                '.jobs-unified-top-card__job-title',
                'h1.jobs-unified-top-card__job-title'
            ]
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_title = element.get_text(strip=True)
                    break
            
            # Job description
            desc_selectors = [
                '.description__text',
                '#job-details',
                '.jobs-description__text',
                '[data-testid="job-description"]'
            ]
            for selector in desc_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_description = element.get_text(strip=True)
                    break
            
            result.is_complete = result.has_minimum_data()
            
        except Exception as e:
            logger.error(f"LinkedIn parser error: {e}")
        
        return result


class IndeedParser(BaseJobParser):
    """Parser for Indeed job postings"""
    
    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        result = JobExtractionResult()
        result.method = "beautifulsoup-indeed"
        
        try:
            # Try JSON-LD structured data first
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                        result.company = data.get('hiringOrganization', {}).get('name')
                        result.job_title = data.get('title')
                        result.job_description = data.get('description')
                        if result.has_minimum_data():
                            result.is_complete = True
                            return result
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            # Company name
            company_selectors = [
                '[data-testid="job-poster-name"]',
                '[data-testid="inlineHeader-companyName"]',
                '.jobsearch-InlineCompanyRating',
                'a[data-testid="company-name"]'
            ]
            for selector in company_selectors:
                element = soup.select_one(selector)
                if element:
                    result.company = element.get_text(strip=True)
                    break
            
            # Job title
            title_selectors = [
                'h1.jobTitle',
                'h1[data-testid="job-title"]',
                '.jobsearch-JobInfoHeader-title'
            ]
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_title = element.get_text(strip=True)
                    break
            
            # Job description
            desc_selectors = [
                '#jobDescriptionText',
                '[data-testid="job-description"]',
                '.jobsearch-jobDescriptionText'
            ]
            for selector in desc_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_description = element.get_text(strip=True)
                    break
            
            result.is_complete = result.has_minimum_data()
            
        except Exception as e:
            logger.error(f"Indeed parser error: {e}")
        
        return result


class GlassdoorParser(BaseJobParser):
    """Parser for Glassdoor job postings"""
    
    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        result = JobExtractionResult()
        result.method = "beautifulsoup-glassdoor"
        
        try:
            # Try JSON-LD structured data first
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get('@type') == 'JobPosting':
                        result.company = data.get('hiringOrganization', {}).get('name')
                        result.job_title = data.get('title')
                        result.job_description = data.get('description')
                        if result.has_minimum_data():
                            result.is_complete = True
                            return result
                except (json.JSONDecodeError, AttributeError):
                    continue
            
            # Company name
            company_selectors = [
                '[data-test="employer-name"]',
                '.employerName',
                '.jobInfoItem.employer'
            ]
            for selector in company_selectors:
                element = soup.select_one(selector)
                if element:
                    result.company = element.get_text(strip=True)
                    break
            
            # Job title
            title_selectors = [
                'h1[data-test="job-title"]',
                '.jobTitle',
                'h1.jobTitle'
            ]
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_title = element.get_text(strip=True)
                    break
            
            # Job description
            desc_selectors = [
                '[data-test="job-description"]',
                '.jobDescriptionContent',
                '#JobDescriptionContainer'
            ]
            for selector in desc_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_description = element.get_text(strip=True)
                    break
            
            result.is_complete = result.has_minimum_data()
            
        except Exception as e:
            logger.error(f"Glassdoor parser error: {e}")
        
        return result


class GenericParser(BaseJobParser):
    """Generic parser that tries common patterns and structured data"""
    
    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        result = JobExtractionResult()
        result.method = "beautifulsoup-generic"
        
        try:
            # 1. Try JSON-LD structured data (most reliable)
            json_ld_scripts = soup.find_all('script', type='application/ld+json')
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Handle both single objects and arrays
                        if data.get('@type') == 'JobPosting':
                            result.company = data.get('hiringOrganization', {}).get('name')
                            result.job_title = data.get('title')
                            result.job_description = data.get('description')
                        elif isinstance(data, list):
                            for item in data:
                                if item.get('@type') == 'JobPosting':
                                    result.company = item.get('hiringOrganization', {}).get('name')
                                    result.job_title = item.get('title')
                                    result.job_description = item.get('description')
                                    break
                        
                        if result.has_minimum_data():
                            result.is_complete = True
                            return result
                except (json.JSONDecodeError, AttributeError, TypeError):
                    continue
            
            # 2. Try Open Graph meta tags
            og_company = soup.find('meta', property='og:company')
            if og_company and og_company.get('content'):
                result.company = og_company['content']
            
            og_title = soup.find('meta', property='og:title')
            if og_title and og_title.get('content'):
                result.job_title = og_title['content']
            
            og_description = soup.find('meta', property='og:description')
            if og_description and og_description.get('content'):
                result.job_description = og_description['content']
            
            # 3. Try common meta tags
            meta_company = soup.find('meta', {'name': 'company'}) or \
                          soup.find('meta', {'name': 'organization'})
            if meta_company and meta_company.get('content'):
                result.company = meta_company['content']
            
            meta_title = soup.find('meta', {'name': 'title'}) or \
                        soup.find('title')
            if meta_title:
                title_text = meta_title.get('content') if meta_title.name == 'meta' else meta_title.get_text(strip=True)
                if title_text and not result.job_title:
                    result.job_title = title_text
            
            meta_description = soup.find('meta', {'name': 'description'})
            if meta_description and meta_description.get('content'):
                result.job_description = meta_description['content']
            
            # 4. Try common CSS class patterns
            if not result.company:
                company_patterns = [
                    soup.find(class_=re.compile(r'company', re.I)),
                    soup.find(class_=re.compile(r'employer', re.I)),
                    soup.find(class_=re.compile(r'organization', re.I))
                ]
                for element in company_patterns:
                    if element:
                        text = element.get_text(strip=True)
                        if text and len(text) < 100:  # Reasonable company name length
                            result.company = text
                            break
            
            if not result.job_title:
                title_patterns = [
                    soup.find('h1'),
                    soup.find(class_=re.compile(r'job.*title', re.I)),
                    soup.find(class_=re.compile(r'position', re.I))
                ]
                for element in title_patterns:
                    if element:
                        text = element.get_text(strip=True)
                        if text and len(text) < 200:  # Reasonable title length
                            result.job_title = text
                            break
            
            if not result.job_description:
                desc_patterns = [
                    soup.find(id=re.compile(r'description', re.I)),
                    soup.find(class_=re.compile(r'description', re.I)),
                    soup.find(class_=re.compile(r'job.*description', re.I)),
                    soup.find('main'),
                    soup.find('article')
                ]
                for element in desc_patterns:
                    if element:
                        text = element.get_text(strip=True)
                        if text and len(text) > 100:  # Description should be substantial
                            result.job_description = text[:5000]  # Limit length
                            break
            
            result.is_complete = result.has_minimum_data()
            
        except Exception as e:
            logger.error(f"Generic parser error: {e}")
        
        return result


def detect_site(url: str) -> str:
    """Detect which job site the URL belongs to"""
    domain = urlparse(url).netloc.lower()
    
    if 'linkedin.com' in domain:
        return 'linkedin'
    elif 'indeed.com' in domain:
        return 'indeed'
    elif 'glassdoor.com' in domain:
        return 'glassdoor'
    else:
        return 'generic'


def fetch_html(url: str, timeout: int = 10) -> Tuple[Optional[str], Optional[str]]:
    """
    Fetch HTML content from URL
    
    Returns:
        Tuple of (html_content, error_message)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }
        
        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
        response.raise_for_status()
        
        # Try to detect encoding
        if response.encoding:
            html = response.text
        else:
            html = response.content.decode('utf-8', errors='ignore')
        
        return html, None
        
    except requests.exceptions.Timeout:
        return None, "Request timeout"
    except requests.exceptions.RequestException as e:
        return None, f"Failed to fetch URL: {str(e)}"
    except Exception as e:
        return None, f"Unexpected error fetching URL: {str(e)}"


def extract_with_beautifulsoup(url: str) -> JobExtractionResult:
    """
    Extract job information using BeautifulSoup
    
    Returns:
        JobExtractionResult object
    """
    # Fetch HTML
    html, error = fetch_html(url)
    if error or not html:
        logger.warning(f"Failed to fetch HTML: {error}")
        result = JobExtractionResult()
        result.method = "beautifulsoup-failed"
        return result
    
    # Parse HTML
    try:
        soup = BeautifulSoup(html, 'html.parser')
    except Exception as e:
        logger.error(f"Failed to parse HTML: {e}")
        result = JobExtractionResult()
        result.method = "beautifulsoup-parse-error"
        return result
    
    # Detect site and use appropriate parser
    site = detect_site(url)
    logger.info(f"Detected site: {site} for URL: {url}")
    
    parsers = {
        'linkedin': LinkedInParser(),
        'indeed': IndeedParser(),
        'glassdoor': GlassdoorParser(),
        'generic': GenericParser()
    }
    
    parser = parsers.get(site, GenericParser())
    result = parser.parse(soup, url)
    
    logger.info(f"BeautifulSoup extraction result: method={result.method}, complete={result.is_complete}")
    return result


def extract_with_grok(html: str, grok_client: Optional[Grok] = None) -> JobExtractionResult:
    """
    Extract job information using Grok AI (fallback method)
    
    Args:
        html: HTML content to analyze
        grok_client: Optional Grok client instance (will create if not provided)
    
    Returns:
        JobExtractionResult object
    """
    result = JobExtractionResult()
    result.method = "grok"
    
    try:
        # Limit HTML size to avoid token limits
        html_content = html[:50000] if len(html) > 50000 else html
        
        # Create Grok client if not provided
        if grok_client is None:
            import os
            api_key = os.getenv('XAI_API_KEY')
            if not api_key:
                logger.error("XAI_API_KEY not configured")
                return result
            grok_client = Grok(api_key=api_key)
        
        # Create prompt for Grok
        prompt = f"""Analyze the following HTML content from a job posting webpage and extract structured information.

HTML Content:
{html_content}

Please extract the following information and return ONLY valid JSON (no markdown, no code blocks):
1. company: The company name (not from URL, but from the actual job posting content)
2. jobTitle: The complete job title/position name
3. jobDescription: The full job description including responsibilities, requirements, and qualifications
4. hiringManager: The name of the hiring manager or recruiter (if mentioned in the posting). Leave empty string "" if not found.

Return format (JSON only):
{{
    "company": "Company Name",
    "jobTitle": "Job Title",
    "jobDescription": "Full job description text...",
    "hiringManager": "Hiring Manager Name" or ""
}}

If company, jobTitle, or jobDescription cannot be extracted, use "Not specified" as the value.
For hiringManager, use empty string "" if not found."""

        # Call Grok API
        response = grok_client.chat.completions.create(
            model="grok-beta",
            messages=[
                {"role": "user", "content": prompt}
            ],
            temperature=0.1,
            max_tokens=4000
        )
        
        # Parse response
        content = response.choices[0].message.content.strip()
        
        # Remove markdown code blocks if present
        if content.startswith('```'):
            content = re.sub(r'^```(?:json)?\s*\n', '', content)
            content = re.sub(r'\n```\s*$', '', content)
        
        # Parse JSON
        data = json.loads(content)
        
        result.company = data.get('company', 'Not specified')
        result.job_title = data.get('jobTitle', 'Not specified')
        result.job_description = data.get('jobDescription', 'Not specified')
        result.hiring_manager = data.get('hiringManager', '') or ''  # Empty string if not found
        result.is_complete = result.has_minimum_data()
        
        logger.info(f"Grok extraction completed: complete={result.is_complete}")
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Grok JSON response: {e}")
        if 'content' in locals():
            logger.debug(f"Grok response content: {content[:500]}")
    except Exception as e:
        logger.error(f"Grok extraction error: {e}")
        # Return empty result so BeautifulSoup results can still be used
    
    return result


async def analyze_job_url(
    url: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    use_grok_fallback: bool = True,
    grok_client: Optional[Grok] = None
) -> Dict:
    """
    Analyze job URL using hybrid BeautifulSoup + Grok approach
    Always runs both methods and combines results intelligently.
    
    Args:
        url: Job posting URL
        user_id: Optional user ID for logging
        user_email: Optional user email for logging
        use_grok_fallback: Whether to use Grok (always True - both methods always run)
        grok_client: Optional Grok client instance
    
    Returns:
        Dictionary with: company, job title, ad source, full_description
    """
    logger.info(f"Analyzing job URL: {url} (user_id={user_id}, user_email={user_email})")
    
    # Validate URL
    if not url.startswith(('http://', 'https://')):
        raise ValueError("Invalid URL format. URL must start with http:// or https://")
    
    # Detect ad source (site)
    ad_source = detect_site(url)
    logger.info(f"Detected ad source: {ad_source}")
    
    # Step 1: Always run BeautifulSoup extraction first
    logger.info("Running BeautifulSoup extraction...")
    bs_result = extract_with_beautifulsoup(url)
    
    # Step 2: Always run Grok extraction (fetch HTML if needed)
    logger.info("Running Grok extraction...")
    html, error = fetch_html(url)
    grok_result = JobExtractionResult()
    grok_result.method = "grok"
    
    if html and not error:
        grok_result = extract_with_grok(html, grok_client)
        logger.info(f"Grok extraction completed: complete={grok_result.is_complete}")
    else:
        logger.warning(f"Failed to fetch HTML for Grok extraction: {error}")
    
    # Step 3: Combine results intelligently
    # Prefer Grok for description (usually more complete), but use BeautifulSoup as fallback
    # Prefer non-"Not specified" values
    combined_result = JobExtractionResult()
    combined_result.method = f"hybrid-bs-{bs_result.method}-grok"
    
    # Company: prefer Grok, fallback to BeautifulSoup
    if grok_result.company and grok_result.company != "Not specified":
        combined_result.company = grok_result.company
    elif bs_result.company and bs_result.company != "Not specified":
        combined_result.company = bs_result.company
    else:
        combined_result.company = grok_result.company or bs_result.company or "Not specified"
    
    # Job title: prefer Grok, fallback to BeautifulSoup
    if grok_result.job_title and grok_result.job_title != "Not specified":
        combined_result.job_title = grok_result.job_title
    elif bs_result.job_title and bs_result.job_title != "Not specified":
        combined_result.job_title = bs_result.job_title
    else:
        combined_result.job_title = grok_result.job_title or bs_result.job_title or "Not specified"
    
    # Full description: prefer Grok (usually more complete), fallback to BeautifulSoup
    if grok_result.job_description and grok_result.job_description != "Not specified":
        combined_result.job_description = grok_result.job_description
    elif bs_result.job_description and bs_result.job_description != "Not specified":
        combined_result.job_description = bs_result.job_description
    else:
        combined_result.job_description = grok_result.job_description or bs_result.job_description or "Not specified"
    
    # Hiring manager: prefer Grok, fallback to BeautifulSoup (may be empty)
    if grok_result.hiring_manager and grok_result.hiring_manager.strip():
        combined_result.hiring_manager = grok_result.hiring_manager
    elif bs_result.hiring_manager and bs_result.hiring_manager.strip():
        combined_result.hiring_manager = bs_result.hiring_manager
    else:
        combined_result.hiring_manager = ""  # Empty string if not found
    
    # Check if we have minimum data
    combined_result.is_complete = combined_result.has_minimum_data()
    
    # Prepare response with new format
    response_data = combined_result.to_dict(ad_source=ad_source)
    response_data['url'] = url
    
    logger.info(f"Final combined result: company={bool(combined_result.company)}, "
                f"title={bool(combined_result.job_title)}, description={bool(combined_result.job_description)}, "
                f"hiring_manager={bool(combined_result.hiring_manager)}, ad_source={ad_source}")
    
    return response_data

