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
import codecs
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Configure logging first
logger = logging.getLogger(__name__)

# Try to import OpenAI for ChatGPT (optional)
try:
    from openai import OpenAI

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    logger.warning(
        "OpenAI not available - ChatGPT extraction will be skipped. Install openai to enable ChatGPT extraction."
    )

token_limit = 150000  # Increased by 50% from 100000 to allow more HTML content


class JobExtractionResult:
    """Container for job extraction results"""

    def __init__(self):
        self.company: Optional[str] = None
        self.job_title: Optional[str] = None
        self.job_description: Optional[str] = None
        self.hiring_manager: Optional[str] = None
        self.ad_source: Optional[str] = None
        self.method: Optional[str] = None  # 'beautifulsoup' or 'grok'
        self.is_complete: bool = False

    def to_dict(self) -> Dict:
        """Convert to dictionary matching API response format"""
        return {
            "success": True,
            "company": self.company or "Not specified",
            "job_title": self.job_title or "Not specified",
            "full_description": self.job_description or "Not specified",
            "hiring_manager": self.hiring_manager or "",
            "ad_source": self.ad_source or "generic",
            "extractionMethod": self.method or "unknown",
        }

    def has_minimum_data(self) -> bool:
        """Check if we have at least company and job description"""
        return (
            self.company
            and self.company != "Not specified"
            and self.job_description
            and self.job_description != "Not specified"
        )


class BaseJobParser:
    """Base class for job parsers"""

    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        """Parse job information from BeautifulSoup object"""
        raise NotImplementedError("Subclasses must implement parse()")


class LinkedInParser(BaseJobParser):
    """Parser for LinkedIn job postings"""

    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        """
        LinkedIn parser - SIMPLIFIED: Now relies on Grok LLM for extraction.
        This method returns an empty result to force fallback to Grok extraction.
        Original BeautifulSoup extraction logic is commented out below for potential reversion.
        """
        result = JobExtractionResult()
        result.method = "beautifulsoup-linkedin"
        result.ad_source = "linkedin"  # Set ad_source since we know it's LinkedIn

        # Return empty result to trigger ChatGPT fallback
        # The LLM will handle all extraction via extract_with_chatgpt()
        return result

        # ============================================================================
        # COMMENTED OUT: Original BeautifulSoup extraction logic (for potential reversion)
        # ============================================================================
        # try:
        #     # Try JSON-LD structured data first
        #     json_ld_scripts = soup.find_all("script", type="application/ld+json")
        #     logger.info(
        #         f"[LinkedInParser] Found {len(json_ld_scripts)} JSON-LD scripts"
        #     )
        #     for script in json_ld_scripts:
        #         try:
        #             data = json.loads(script.string)
        #             if isinstance(data, dict) and data.get("@type") == "JobPosting":
        #                 logger.info("[LinkedInParser] Found JobPosting in JSON-LD")
        #                 result.company = data.get("hiringOrganization", {}).get("name")
        #                 result.job_title = data.get("title")
        #                 result.job_description = data.get("description")
        #                 logger.info(
        #                     f"[LinkedInParser] JSON-LD extracted - Company: '{result.company}', Title: '{result.job_title}', Description: {len(result.job_description) if result.job_description else 0} chars"
        #                 )
        #                 if result.has_minimum_data():
        #                     result.is_complete = True
        #                     logger.info(
        #                         "[LinkedInParser] JSON-LD extraction successful, returning result"
        #                     )
        #                     return result
        #         except (json.JSONDecodeError, AttributeError) as e:
        #             logger.debug(f"[LinkedInParser] JSON-LD parse error: {e}")
        #             continue
        #
        #     # Try CSS selectors
        #     # Company name
        #     logger.info("[LinkedInParser] Trying CSS selectors for company name...")
        #     company_selectors = [
        #         '[data-testid="job-poster-name"]',
        #         'a[data-tracking-control-name="job_poster_name"]',
        #         ".job-details-jobs-unified-top-card__company-name",
        #         ".jobs-unified-top-card__company-name",
        #     ]
        #     for selector in company_selectors:
        #         element = soup.select_one(selector)
        #         if element:
        #             result.company = element.get_text(strip=True)
        #             logger.info(
        #                 f"[LinkedInParser] Found company using selector '{selector}': '{result.company}'"
        #             )
        #             break
        #     if not result.company:
        #         logger.warning(
        #             "[LinkedInParser] Could not find company name with any selector"
        #         )
        #
        #     # Job title
        #     logger.info("[LinkedInParser] Trying CSS selectors for job title...")
        #     title_selectors = [
        #         "h1.job-title",
        #         'h1[data-testid="job-title"]',
        #         ".jobs-unified-top-card__job-title",
        #         "h1.jobs-unified-top-card__job-title",
        #     ]
        #     for selector in title_selectors:
        #         element = soup.select_one(selector)
        #         if element:
        #             result.job_title = element.get_text(strip=True)
        #             logger.info(
        #                 f"[LinkedInParser] Found job title using selector '{selector}': '{result.job_title}'"
        #             )
        #             break
        #     if not result.job_title:
        #         logger.warning(
        #             "[LinkedInParser] Could not find job title with any selector"
        #         )
        #
        #     # Job description - LinkedIn uses "About the job" section
        #     # Try multiple strategies to find the full job description
        #     # IMPORTANT: We want the actual readable text, not metadata or structured data
        #
        #     desc_selectors = [
        #         # Modern LinkedIn selectors - these should contain the actual description text
        #         '[data-testid="job-description"]',
        #         ".jobs-description-content__text",
        #         ".jobs-box__html-content",
        #         ".jobs-description__text",
        #         # Look for "About the job" section specifically
        #         'section[aria-labelledby*="job-details"]',
        #         'div[data-testid="job-details"]',
        #         # Generic fallbacks
        #         ".description__text",
        #         "#job-details",
        #     ]
        #
        #     # First try direct selectors - but filter out script/JSON-LD content
        #     for selector in desc_selectors:
        #         try:
        #             element = soup.select_one(selector)
        #             if element:
        #                 # Skip if this is a script tag or contains JSON-LD
        #                 if element.name == "script" or "application/ld+json" in str(
        #                     element
        #                 ):
        #                     continue
        #
        #                 # Get text but exclude script and style tags
        #                 for script in element(["script", "style", "noscript"]):
        #                     script.decompose()
        #
        #                 text = element.get_text(separator="\n", strip=True)
        #                 # Ensure we got substantial content and it's not just metadata
        #                 if (
        #                     text and len(text) > 200
        #                 ):  # Increased threshold to avoid metadata
        #                     # Check if it looks like actual description (has sentences, not just keywords)
        #                     if (
        #                         any(char in text for char in [".", "!", "?"])
        #                         or len(text.split()) > 30
        #                     ):
        #                         result.job_description = text
        #                         logger.info(
        #                             f"[LinkedInParser] Found description using selector '{selector}': {len(text)} chars"
        #                         )
        #                         break
        #         except Exception as e:
        #             logger.debug(f"[LinkedInParser] Selector '{selector}' failed: {e}")
        #             continue
        #
        #     # If not found, try finding "About the job" heading and get following content
        #     if not result.job_description:
        #         logger.info(
        #             "[LinkedInParser] Trying to find 'About the job' section..."
        #         )
        #         # Find heading containing "About the job" - try multiple approaches
        #         headings = soup.find_all(
        #             ["h2", "h3", "h4"], string=re.compile(r"about the job", re.I)
        #         )
        #         if not headings:
        #             # Try finding by aria-label or other attributes
        #             headings = soup.find_all(
        #                 ["h2", "h3", "h4"],
        #                 attrs={"aria-label": re.compile(r"about", re.I)},
        #             )
        #
        #         # Also try finding by text content in any element
        #         if not headings:
        #             all_elements = soup.find_all(["h2", "h3", "h4", "div", "span"])
        #             for elem in all_elements:
        #                 if elem.string and re.search(
        #                     r"about the job", elem.string, re.I
        #                 ):
        #                     headings.append(elem)
        #                     break
        #
        #         for heading in headings:
        #             # Get the next sibling div or section
        #             next_sibling = heading.find_next_sibling(["div", "section"])
        #             if next_sibling:
        #                 # Remove script/style tags
        #                 for script in next_sibling(["script", "style", "noscript"]):
        #                     script.decompose()
        #                 text = next_sibling.get_text(separator="\n", strip=True)
        #                 if (
        #                     text
        #                     and len(text) > 200
        #                     and (
        #                         any(char in text for char in [".", "!", "?"])
        #                         or len(text.split()) > 30
        #                     )
        #                 ):
        #                     result.job_description = text
        #                     logger.info(
        #                         f"[LinkedInParser] Found description after 'About the job' heading: {len(text)} chars"
        #                     )
        #                     break
        #
        #             # Also try parent's next sibling
        #             parent = heading.parent
        #             if parent:
        #                 next_parent = parent.find_next_sibling(["div", "section"])
        #                 if next_parent:
        #                     for script in next_parent(["script", "style", "noscript"]):
        #                         script.decompose()
        #                     text = next_parent.get_text(separator="\n", strip=True)
        #                     if (
        #                         text
        #                         and len(text) > 200
        #                         and (
        #                             any(char in text for char in [".", "!", "?"])
        #                             or len(text.split()) > 30
        #                         )
        #                     ):
        #                         result.job_description = text
        #                         logger.info(
        #                             f"[LinkedInParser] Found description in parent's next sibling: {len(text)} chars"
        #                         )
        #                         break
        #
        #             # Try finding the description container within the same parent
        #             if parent:
        #                 desc_container = parent.find(
        #                     ["div", "section"],
        #                     class_=re.compile(r"description|content|text", re.I),
        #                 )
        #                 if desc_container:
        #                     for script in desc_container(
        #                         ["script", "style", "noscript"]
        #                     ):
        #                         script.decompose()
        #                     text = desc_container.get_text(separator="\n", strip=True)
        #                     if (
        #                         text
        #                         and len(text) > 200
        #                         and (
        #                             any(char in text for char in [".", "!", "?"])
        #                             or len(text.split()) > 30
        #                         )
        #                     ):
        #                         result.job_description = text
        #                         logger.info(
        #                             f"[LinkedInParser] Found description in parent container: {len(text)} chars"
        #                         )
        #                         break
        #
        #     if not result.job_description:
        #         logger.warning(
        #             "[LinkedInParser] Could not find job description with any selector"
        #     )
        #
        #     # Try to extract hiring manager from "Meet the hiring team" section
        #     try:
        #         logger.info(
        #             "[LinkedInParser] Looking for 'Meet the hiring team' section..."
        #         )
        #         # Find heading or text containing "Meet the hiring team"
        #         hiring_team_heading = soup.find(
        #             string=re.compile(r"meet the hiring team", re.I)
        #         )
        #         if not hiring_team_heading:
        #             hiring_team_heading = soup.find(
        #                 string=re.compile(r"hiring team", re.I)
        #             )
        #
        #         if hiring_team_heading:
        #             logger.info("[LinkedInParser] Found 'Meet the hiring team' section")
        #             # Get parent element
        #             parent = (
        #                 hiring_team_heading.parent
        #                 if hasattr(hiring_team_heading, "parent")
        #                 else None
        #             )
        #             if not parent:
        #                 # Try finding the element
        #                 parent = soup.find(
        #                     string=re.compile(r"meet the hiring team", re.I)
        #                 )
        #                 if parent and hasattr(parent, "parent"):
        #                     parent = parent.parent
        #
        #             if parent:
        #                 # Look for name patterns in the same section
        #                 # LinkedIn typically shows names in links or specific divs
        #                 name_elements = parent.find_all(
        #                     ["a", "span", "div"],
        #                     class_=re.compile(r"name|profile|person", re.I),
        #                 )
        #                 for elem in name_elements:
        #                     text = elem.get_text(strip=True)
        #                     # Look for name-like patterns (capitalized words)
        #                     name_match = re.search(
        #                         r"^([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)", text
        #                     )
        #                     if (
        #                         name_match and len(name_match.group(1).split()) <= 4
        #                     ):  # Reasonable name length
        #                         result.hiring_manager = name_match.group(1).strip()
        #                         logger.info(
        #                             f"[LinkedInParser] Found hiring manager: '{result.hiring_manager}'"
        #                         )
        #                         break
        #
        #                 # If not found in class-based search, try finding links with profile URLs
        #                 if not result.hiring_manager:
        #                     profile_links = parent.find_all(
        #                         "a", href=re.compile(r"/in/|/profile/", re.I)
        #                     )
        #                     for link in profile_links:
        #                         text = link.get_text(strip=True)
        #                         if (
        #                             text
        #                             and len(text.split()) <= 4
        #                             and re.match(r"^[A-Z]", text)
        #                         ):
        #                             result.hiring_manager = text
        #                             logger.info(
        #                                 f"[LinkedInParser] Found hiring manager from profile link: '{result.hiring_manager}'"
        #                             )
        #                             break
        #     except Exception as e:
        #         logger.debug(f"[LinkedInParser] Could not extract hiring manager: {e}")
        #
        #     result.is_complete = result.has_minimum_data()
        #
        #     logger.info(
        #         f"[LinkedInParser] Final extraction - Company: '{result.company or 'None'}', Title: '{result.job_title or 'None'}', Description: {len(result.job_description) if result.job_description else 0} chars"
        #     )
        #     logger.info(
        #         f"[LinkedInParser] Has minimum data: {result.has_minimum_data()}, Is complete: {result.is_complete}"
        #     )
        #
        # except Exception as e:
        #     logger.error(f"LinkedIn parser error: {e}", exc_info=True)
        #
        # return result


class IndeedParser(BaseJobParser):
    """Parser for Indeed job postings"""

    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        result = JobExtractionResult()
        result.method = "beautifulsoup-indeed"

        try:
            # Try JSON-LD structured data first
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        result.company = data.get("hiringOrganization", {}).get("name")
                        result.job_title = data.get("title")
                        result.job_description = data.get("description")
                        if result.has_minimum_data():
                            result.is_complete = True
                            return result
                except (json.JSONDecodeError, AttributeError):
                    continue

            # Company name
            company_selectors = [
                '[data-testid="job-poster-name"]',
                '[data-testid="inlineHeader-companyName"]',
                ".jobsearch-InlineCompanyRating",
                'a[data-testid="company-name"]',
            ]
            for selector in company_selectors:
                element = soup.select_one(selector)
                if element:
                    result.company = element.get_text(strip=True)
                    break

            # Job title
            title_selectors = [
                "h1.jobTitle",
                'h1[data-testid="job-title"]',
                ".jobsearch-JobInfoHeader-title",
            ]
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_title = element.get_text(strip=True)
                    break

            # Job description
            desc_selectors = [
                "#jobDescriptionText",
                '[data-testid="job-description"]',
                ".jobsearch-jobDescriptionText",
            ]
            for selector in desc_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_description = element.get_text(strip=True)
                    break

            result.is_complete = result.has_minimum_data()

        except Exception as e:
            logger.error(f"Indeed parser error: {e}", exc_info=True)

        return result


class GlassdoorParser(BaseJobParser):
    """Parser for Glassdoor job postings"""

    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        result = JobExtractionResult()
        result.method = "beautifulsoup-glassdoor"

        try:
            # Try JSON-LD structured data first
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        result.company = data.get("hiringOrganization", {}).get("name")
                        result.job_title = data.get("title")
                        result.job_description = data.get("description")
                        if result.has_minimum_data():
                            result.is_complete = True
                            return result
                except (json.JSONDecodeError, AttributeError):
                    continue

            # Company name
            company_selectors = [
                '[data-test="employer-name"]',
                ".employerName",
                ".jobInfoItem.employer",
            ]
            for selector in company_selectors:
                element = soup.select_one(selector)
                if element:
                    result.company = element.get_text(strip=True)
                    break

            # Job title
            title_selectors = ['h1[data-test="job-title"]', ".jobTitle", "h1.jobTitle"]
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_title = element.get_text(strip=True)
                    break

            # Job description
            desc_selectors = [
                '[data-test="job-description"]',
                ".jobDescriptionContent",
                "#JobDescriptionContainer",
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
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Handle both single objects and arrays
                        if data.get("@type") == "JobPosting":
                            result.company = data.get("hiringOrganization", {}).get("name")
                            result.job_title = data.get("title")
                            result.job_description = data.get("description")
                        elif isinstance(data, list):
                            for item in data:
                                if item.get("@type") == "JobPosting":
                                    result.company = item.get("hiringOrganization", {}).get("name")
                                    result.job_title = item.get("title")
                                    result.job_description = item.get("description")
                                    break

                        if result.has_minimum_data():
                            result.is_complete = True
                            return result
                except (json.JSONDecodeError, AttributeError, TypeError):
                    continue

            # 2. Try Open Graph meta tags
            og_company = soup.find("meta", property="og:company")
            if og_company and og_company.get("content"):
                result.company = og_company["content"]

            og_title = soup.find("meta", property="og:title")
            if og_title and og_title.get("content"):
                result.job_title = og_title["content"]

            og_description = soup.find("meta", property="og:description")
            if og_description and og_description.get("content"):
                result.job_description = og_description["content"]

            # 3. Try common meta tags
            meta_company = soup.find("meta", {"name": "company"}) or soup.find(
                "meta", {"name": "organization"}
            )
            if meta_company and meta_company.get("content"):
                result.company = meta_company["content"]

            meta_title = soup.find("meta", {"name": "title"}) or soup.find("title")
            if meta_title:
                title_text = (
                    meta_title.get("content")
                    if meta_title.name == "meta"
                    else meta_title.get_text(strip=True)
                )
                if title_text and not result.job_title:
                    result.job_title = title_text

            meta_description = soup.find("meta", {"name": "description"})
            if meta_description and meta_description.get("content"):
                result.job_description = meta_description["content"]

            # 4. Try common CSS class patterns
            if not result.company:
                company_patterns = [
                    soup.find(class_=re.compile(r"company", re.I)),
                    soup.find(class_=re.compile(r"employer", re.I)),
                    soup.find(class_=re.compile(r"organization", re.I)),
                ]
                for element in company_patterns:
                    if element:
                        text = element.get_text(strip=True)
                        if text and len(text) < 100:  # Reasonable company name length
                            result.company = text
                            break

            if not result.job_title:
                title_patterns = [
                    soup.find("h1"),
                    soup.find(class_=re.compile(r"job.*title", re.I)),
                    soup.find(class_=re.compile(r"position", re.I)),
                ]
                for element in title_patterns:
                    if element:
                        text = element.get_text(strip=True)
                        if text and len(text) < 200:  # Reasonable title length
                            result.job_title = text
                            break

            if not result.job_description:
                desc_patterns = [
                    soup.find(id=re.compile(r"description", re.I)),
                    soup.find(class_=re.compile(r"description", re.I)),
                    soup.find(class_=re.compile(r"job.*description", re.I)),
                    soup.find("main"),
                    soup.find("article"),
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

    if "linkedin.com" in domain:
        return "linkedin"
    elif "indeed.com" in domain:
        return "indeed"
    elif "glassdoor.com" in domain:
        return "glassdoor"
    else:
        return "generic"


def detect_linkedin_login_wall(html: str) -> bool:
    """
    Detect if LinkedIn returned a sign-in/login page instead of job content.

    When the backend fetches a LinkedIn job URL with requests.get(), LinkedIn
    typically returns a login wall or minimal SPA shell (no job body). The user
    sees company and "About the job" in their browser because they're logged in;
    our server sees "Sign in to LinkedIn" or empty content.

    Returns:
        True if the HTML looks like a LinkedIn login wall (no job content).
    """
    if not html or "linkedin.com" not in html.lower():
        return False
    html_lower = html.lower()
    # Strong indicators of login wall
    login_indicators = [
        "sign in to linkedin",
        "sign in to view",
        "log in to linkedin",
        "join linkedin",
        "authwall",
        "login wall",
        "to view this job",
        "to see this job",
    ]
    has_login_prompt = any(indicator in html_lower for indicator in login_indicators)
    # Job content indicators (what we need to extract)
    job_indicators = [
        "about the job",
        "job description",
        "job-details",
        "jobs-description",
        "jobs-unified-top-card__company-name",
        "job-details-jobs-unified-top-card",
    ]
    has_job_content = any(indicator in html_lower for indicator in job_indicators)
    # If we see login prompt and no job content, it's a login wall
    if has_login_prompt and not has_job_content:
        logger.info("LinkedIn login wall detected: page shows sign-in prompt and no job content")
        return True
    # Also treat very small HTML as likely shell/redirect (no job body)
    if len(html) < 8000 and not has_job_content:
        logger.info(
            "LinkedIn page has little content and no job indicators - likely login wall or SPA shell"
        )
        return True
    return False


def detect_captcha(html: str) -> bool:
    """
    Detect if HTML content contains CAPTCHA or human verification

    This function is smarter - it checks if the page actually contains job content.
    If job content is present, CAPTCHA is likely already completed.

    Returns:
        True if CAPTCHA/human verification is detected, False otherwise
    """
    if not html:
        return False

    html_lower = html.lower()

    # First, check if the page contains job-related content
    # If it does, CAPTCHA is probably already completed
    job_content_indicators = [
        "job description",
        "job title",
        "apply now",
        "job posting",
        "hiring",
        "qualifications",
        "responsibilities",
        "requirements",
        "jobsearch-jobdescriptiontext",  # Indeed-specific
        "job-poster-name",  # Indeed-specific
        "job-title",  # Indeed-specific
        "jobsearch-jobinfobullet",  # Indeed-specific
    ]

    has_job_content = any(indicator in html_lower for indicator in job_content_indicators)

    # If we have job content, be more conservative about CAPTCHA detection
    # Only detect CAPTCHA if there are strong indicators AND no job content
    strong_captcha_indicators = [
        "recaptcha",
        "hcaptcha",
        "cf-browser-verification",
        "cf-challenge",
        "challenge-platform",
        "verify you are human",
        "verify you're human",
        "just a moment",
        "checking your browser",
        "challenge-form",
        "turnstile",
        "access denied",
        "unusual traffic",
        "verify you're not a robot",
        "indeed.com/access-denied",
        "indeed.com/verify",
    ]

    # Check for strong CAPTCHA indicators
    has_strong_captcha = any(indicator in html_lower for indicator in strong_captcha_indicators)

    # If we have job content, don't detect CAPTCHA (it's already completed)
    if has_job_content:
        logger.debug("Job content detected - assuming CAPTCHA already completed")
        return False

    # If no job content but strong CAPTCHA indicators, detect CAPTCHA
    if has_strong_captcha:
        logger.info(f"CAPTCHA detected: found strong indicator")
        return True

    # Check for common CAPTCHA iframe/div patterns (only if no job content)
    captcha_patterns = [
        r"iframe.*recaptcha",
        r"div.*recaptcha",
        r"iframe.*hcaptcha",
        r"div.*hcaptcha",
        r"data-sitekey",  # reCAPTCHA site key
        r"data-callback.*captcha",
    ]

    for pattern in captcha_patterns:
        if re.search(pattern, html_lower):
            logger.info(f"CAPTCHA detected: found pattern '{pattern}'")
            return True

    # Weak indicators - only detect if no job content
    weak_captcha_indicators = [
        "captcha",
        "cloudflare",
        "human verification",
        "please verify",
        "security check",
        "ddos protection",
        "ray id",
        "cf-ray",
        "bot detection",
        "security verification",
    ]

    # Only use weak indicators if we don't have job content
    for indicator in weak_captcha_indicators:
        if indicator in html_lower:
            logger.info(f"CAPTCHA detected: found weak indicator '{indicator}' (no job content)")
            return True

    return False


def fetch_html(url: str, timeout: int = 10) -> Tuple[Optional[str], Optional[str], Optional[bool]]:
    """
    Fetch HTML content from URL using requests

    Returns:
        Tuple of (html_content, error_message, captcha_detected)
        captcha_detected is True if CAPTCHA is detected, False otherwise, None on error
    """
    # Use requests to fetch HTML
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
            "Accept-Encoding": "gzip, deflate",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
        }

        response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)

        # Try to detect encoding
        if response.encoding:
            html = response.text
        else:
            html = response.content.decode("utf-8", errors="ignore")

        # Check for CAPTCHA BEFORE checking status code
        # Some sites (like Indeed) may return 403 or redirect to CAPTCHA page
        captcha_detected = detect_captcha(html)

        # If CAPTCHA is detected, return it even if status is not 200
        if captcha_detected:
            logger.warning(f"CAPTCHA detected for URL: {url} (status: {response.status_code})")
            return html, None, captcha_detected

        # For error status codes (403, 429, 503), check for CAPTCHA
        # BUT: If the page contains job content, CAPTCHA was already completed
        # Only mark as CAPTCHA if there's no job content
        if response.status_code in [403, 429, 503]:
            # First check if page has job content (CAPTCHA already completed)
            html_lower_check = html.lower()
            job_content_indicators = [
                "job description",
                "job title",
                "apply now",
                "job posting",
                "hiring",
                "qualifications",
                "responsibilities",
                "requirements",
                "jobsearch-jobdescriptiontext",
                "job-poster-name",
                "job-title",
            ]
            has_job_content = any(
                indicator in html_lower_check for indicator in job_content_indicators
            )

            if has_job_content:
                # Page has job content despite error status - CAPTCHA was already completed
                logger.info(
                    f"Error status {response.status_code} but job content found - CAPTCHA already completed, proceeding"
                )
                return html, None, False  # No CAPTCHA needed

            # No job content - check for CAPTCHA
            captcha_detected = detect_captcha(html)
            if captcha_detected:
                logger.warning(
                    f"CAPTCHA detected for URL: {url} (status: {response.status_code}, no job content)"
                )
                return html, None, captcha_detected

            # Indeed specifically - 403 without job content likely means CAPTCHA needed
            if "indeed.com" in url.lower() and response.status_code == 403:
                logger.warning(
                    f"Indeed 403 Forbidden for URL: {url} (no job content) - treating as CAPTCHA required"
                )
                return html, None, True

            # For other sites with 403/429/503, check if HTML suggests CAPTCHA
            # Look for common error pages that might indicate verification needed
            if any(
                indicator in html_lower_check
                for indicator in [
                    "access denied",
                    "unusual traffic",
                    "verify",
                    "security",
                ]
            ):
                logger.warning(
                    f"Error status {response.status_code} with security indicators for URL: {url} (no job content) - treating as CAPTCHA"
                )
                return html, None, True

            logger.warning(
                f"Error status {response.status_code} for URL: {url} (no job content) - may require CAPTCHA"
            )
            # Return as CAPTCHA required to trigger modal
            return html, None, True

        # Now check status code (only if no CAPTCHA was detected and not error status)
        response.raise_for_status()

        return html, None, captcha_detected

    except requests.exceptions.Timeout:
        return None, "Request timeout", None
    except requests.exceptions.RequestException as e:
        return None, f"Failed to fetch URL: {str(e)}", None
    except Exception as e:
        return None, f"Unexpected error fetching URL: {str(e)}", None


def extract_from_html(html: str, url: str) -> JobExtractionResult:
    """
    Extract job information from provided HTML content using BeautifulSoup

    Args:
        html: HTML content to parse
        url: URL for site detection and logging

    Returns:
        JobExtractionResult object
    """
    result = JobExtractionResult()

    if not html:
        result.method = "beautifulsoup-failed"
        return result

    # Parse HTML
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        logger.error(f"Failed to parse HTML: {e}")
        result.method = "beautifulsoup-parse-error"
        return result

    # Detect site and use appropriate parser
    site = detect_site(url)
    logger.info(f"Detected site: {site} for URL: {url}")

    parsers = {
        "linkedin": LinkedInParser(),
        "indeed": IndeedParser(),
        "glassdoor": GlassdoorParser(),
        "generic": GenericParser(),
    }

    parser = parsers.get(site, GenericParser())
    result = parser.parse(soup, url)

    # Set ad_source based on detected site
    result.ad_source = site

    # Try to extract hiring manager (common patterns)
    try:
        # Look for hiring manager patterns in the HTML
        hiring_manager_patterns = [
            soup.find(string=re.compile(r"hiring manager", re.I)),
            soup.find(string=re.compile(r"recruiter", re.I)),
            soup.find(string=re.compile(r"contact.*name", re.I)),
        ]

        for pattern_match in hiring_manager_patterns:
            if pattern_match:
                # Try to find the name near the pattern
                parent = pattern_match.parent if hasattr(pattern_match, "parent") else None
                if parent:
                    # Look for name-like text nearby
                    text = parent.get_text(strip=True)
                    # Simple heuristic: look for capitalized words after "hiring manager" or "recruiter"
                    match = re.search(
                        r"(?:hiring manager|recruiter)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                        text,
                        re.I,
                    )
                    if match:
                        result.hiring_manager = match.group(1).strip()
                        break
    except Exception as e:
        logger.debug(f"Could not extract hiring manager: {e}")
        # Leave as None/empty string

    return result


def extract_with_beautifulsoup(url: str) -> JobExtractionResult:
    """
    Extract job information using BeautifulSoup

    Returns:
        JobExtractionResult object
    """
    # Fetch HTML
    html, error, captcha_detected = fetch_html(url)

    if error or not html:
        logger.warning(f"Failed to fetch HTML: {error}")
        result = JobExtractionResult()
        result.method = "beautifulsoup-failed"
        return result

    # Parse HTML
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception as e:
        logger.error(f"Failed to parse HTML: {e}")
        result = JobExtractionResult()
        result.method = "beautifulsoup-parse-error"
        return result

    # Detect site and use appropriate parser
    site = detect_site(url)

    parsers = {
        "linkedin": LinkedInParser(),
        "indeed": IndeedParser(),
        "glassdoor": GlassdoorParser(),
        "generic": GenericParser(),
    }

    parser = parsers.get(site, GenericParser())
    result = parser.parse(soup, url)

    # Set ad_source based on detected site
    result.ad_source = site

    # If CAPTCHA was detected, check if we still got valid job data
    # If we did, use it (CAPTCHA was already completed - don't show modal)
    # If we didn't, mark as captcha-required (show modal for NEW CAPTCHA)
    if captcha_detected:
        logger.info(
            f"CAPTCHA indicators found for URL: {url}, checking if job data can be extracted..."
        )
        if result.has_minimum_data():
            logger.info(
                f"✅ Successfully extracted job data - CAPTCHA was already completed (no modal needed)"
            )
            # CAPTCHA was detected but we got valid data, so it's already completed
            # Return the result normally (don't mark as captcha-required, don't show modal)
            # The detect_captcha function should have caught this, but this is a safety check
        else:
            logger.warning(
                f"❌ CAPTCHA detected and no valid job data extracted - NEW CAPTCHA required (show modal)"
            )
            result.method = "captcha-required"
    return result

    # Try to extract hiring manager (common patterns)
    # Note: LinkedIn hiring manager extraction is handled in LinkedInParser
    # This is a fallback for other sites or if LinkedInParser didn't find it
    if not result.hiring_manager:
        try:
            # Look for hiring manager patterns in the HTML
            hiring_manager_patterns = [
                soup.find(string=re.compile(r"meet the hiring team", re.I)),
                soup.find(string=re.compile(r"hiring manager", re.I)),
                soup.find(string=re.compile(r"recruiter", re.I)),
                soup.find(string=re.compile(r"contact.*name", re.I)),
            ]

            for pattern_match in hiring_manager_patterns:
                if pattern_match:
                    # Try to find the name near the pattern
                    parent = pattern_match.parent if hasattr(pattern_match, "parent") else None
                    if parent:
                        # Look for name-like text nearby
                        text = parent.get_text(strip=True)
                        # Simple heuristic: look for capitalized words after "hiring manager", "recruiter", or "meet the hiring team"
                        match = re.search(
                            r"(?:meet the hiring team|hiring manager|recruiter)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                            text,
                            re.I,
                        )
                        if match:
                            result.hiring_manager = match.group(1).strip()
                            logger.info(
                                f"[extract_with_beautifulsoup] Found hiring manager: '{result.hiring_manager}'"
                            )
                            break
        except Exception as e:
            logger.debug(f"Could not extract hiring manager: {e}")
            # Leave as None/empty string

    logger.info(
        f"BeautifulSoup extraction result: method={result.method}, complete={result.is_complete}, ad_source={result.ad_source}"
    )
    return result


def extract_with_chatgpt(html: str, openai_client: Optional[OpenAI] = None) -> JobExtractionResult:
    """
    Extract job information using ChatGPT (fallback method)

    Args:
        html: HTML content to analyze
        openai_client: Optional OpenAI client instance (will create if not provided)

    Returns:
        JobExtractionResult object
    """
    result = JobExtractionResult()
    result.method = "chatgpt"

    if not OPENAI_AVAILABLE:
        logger.error("OpenAI not available - cannot use ChatGPT extraction")
        return result

    try:
        # Limit HTML size to avoid token limits
        html_content = html[:token_limit] if len(html) > token_limit else html

        # Create OpenAI client if not provided
        if openai_client is None:
            import os

            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                logger.error("OPENAI_API_KEY not configured")
                return result
            openai_client = OpenAI(api_key=api_key)

        # Create simplified prompt for Grok - let the LLM figure it out
        prompt = f"""Scan the provided HTML content and retrieve the following fields: "Company Name", "Job Title", "Hiring Manager", "Ad Source", and "Job Description". The job description should include all responsibilities, requirements, qualifications, and details. It should be the full job description text including all responsibilities, requirements, qualifications, and details. The hiring manager should be the name of the person who is hiring for the job. The ad source should be the source of the job posting. The company name should be the name of the company that is hiring for the job. The job title should be the title of the job. The hiring manager may be called a human resources manager, recruiter, hiring manager, or "meet the hiring team". 

HTML Content:
{html_content}

Extract the following information and return ONLY valid JSON (no markdown, no code blocks):

Return format (JSON only):
{{
    "company": "Company Name",
    "job_title": "Job Title",
    "full_description": "Complete job description text including all responsibilities, requirements, qualifications, and details",
    "hiring_manager": "Hiring Manager Name" or "",
    "ad_source": "linkedin" or "indeed" or "glassdoor" or "generic"
}}

IMPORTANT EXTRACTION INSTRUCTIONS:

1. company: Extract the company name from the job posting (not from the URL)

2. job_title: Extract the complete job title/position name

3. full_description: Extract the complete, full job description text. For LinkedIn job postings, this is typically found in the "About the job" section. Include all responsibilities, requirements, qualifications, and any other job details.
   
   CRITICAL - EXPANDABLE TEXT BOXES: LinkedIn hides the bulk of the job description in expandable text boxes using <span> elements. Before extracting the description, you MUST:
   
   a) Look for <span> elements with expandable/collapsed content. These often have:
      - Attributes like aria-expanded="false" or data-state="collapsed"
      - Classes containing "expand", "collapse", "truncate", or "show-more"
      - Text content that appears truncated or ends with "..."
      - Sibling elements with "more" buttons or expand controls
   
   b) Find the FULL text content within these expandable spans. The HTML structure typically contains:
      - A visible truncated preview (what users see before clicking "more")
      - The full expanded text (often in the same element or a sibling element)
      - Both versions may be present in the HTML simultaneously
   
   c) Extract the COMPLETE text from expandable spans, including:
      - All text within <span> elements that contain the full description
      - Text in data attributes (data-full-text, data-content, etc.)
      - Text in hidden divs or elements with display:none that contain the full content
      - Multiple span elements that together form the complete description
   
   d) Look for patterns like:
      - <span class="...">[truncated text]</span> followed by <span class="...">[full text]</span>
      - <span aria-expanded="false">[preview]</span> with full text in a data attribute
      - Nested spans where inner spans contain the full text
   
   Extract the LONGEST and MOST COMPLETE version of the description available in the HTML. Do not stop at the truncated preview - always look for the expanded/full version within span elements or their data attributes.

4. hiring_manager: CRITICAL - For LinkedIn job postings, look for a section titled "Meet the hiring team" or "Hiring team". In this section, extract the name of the person shown (this could be a hiring manager, recruiter, or team member). The name is typically displayed as:
   - Text near "Meet the hiring team" heading
   - Profile names or links in that section
   - Names associated with profile pictures or cards in that area
   - Look for capitalized names (First Last format) in the "Meet the hiring team" section
   If you find the "Meet the hiring team" section but no name is displayed, return empty string "". If the section doesn't exist, return empty string "".

5. ad_source: Determine the job board source based on the URL or page content:
   - "linkedin" if URL contains linkedin.com
   - "indeed" if URL contains indeed.com
   - "glassdoor" if URL contains glassdoor.com
   - "generic" for any other source

Extraction Guidelines:
- Extract all fields accurately from the HTML content
- For hiring_manager: Return empty string "" if not found
- For ad_source: Return "linkedin", "indeed", "glassdoor", or "generic" based on the URL or page content
- For company, job_title, and full_description: Extract the actual values from the page content
- Ensure full_description includes the complete job description with all responsibilities, requirements, and qualifications"""

        # Call OpenAI ChatGPT API - using gpt-5.2 for better extraction
        # GPT-5.2 supports 128,000 max completion tokens, 400,000 context window
        model_name = "gpt-5.2"
        max_completion_tokens_value = 128000  # GPT-5.2 maximum supported completion tokens
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_completion_tokens=max_completion_tokens_value,  # GPT-5.2 uses max_completion_tokens instead of max_tokens
            response_format={"type": "json_object"},  # Force JSON response
        )

        # Parse response
        raw_response = response.choices[0].message.content.strip()
        content = raw_response

        # Check if response was truncated (check finish_reason)
        finish_reason = response.choices[0].finish_reason
        if finish_reason == "length":
            logger.warning(
                f"ChatGPT response was truncated (finish_reason='length'). "
                f"Response length: {len(content)} characters. "
                f"Consider increasing max_completion_tokens or reducing HTML input size."
            )

        logger.info(
            f"ChatGPT response length: {len(content)} characters, finish_reason: {finish_reason}"
        )
        logger.debug(f"ChatGPT response preview (first 500 chars): {content[:500]}")

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*\n", "", content)
            content = re.sub(r"\n```\s*$", "", content)

        # Try to fix incomplete JSON if response was truncated
        if finish_reason == "length":
            # Attempt to close the JSON properly
            # Find the last complete field and close the JSON
            logger.warning("Attempting to fix truncated JSON response...")

            # Try to find the last complete key-value pair
            # Look for the last complete string value
            last_quote = content.rfind('"')
            if last_quote > 0:
                # Find the opening quote for this string
                opening_quote = content.rfind('"', 0, last_quote)
                if opening_quote > 0:
                    # Check if this looks like an incomplete string value
                    before_opening = content[:opening_quote].rstrip()
                    if before_opening.endswith(":"):
                        # This is likely an incomplete string value - try to close it
                        # Find the key name
                        key_start = before_opening.rfind('"')
                        if key_start > 0:
                            key_end = before_opening.find('"', key_start + 1)
                            if key_end > 0:
                                key = content[key_start + 1 : key_end]
                                logger.info(f"Detected incomplete field: {key}")
                                # Close the string and JSON object
                                content = content[: last_quote + 1] + '"}'
                                logger.info(
                                    "Attempted to fix truncated JSON by closing the last string field"
                                )

        # Parse JSON
        try:
            data = json.loads(content)
        except json.JSONDecodeError as json_error:
            # Log more details about the JSON error
            logger.error(f"JSON parsing error: {json_error}")
            logger.error(f"Error position: line {json_error.lineno}, column {json_error.colno}")
            logger.error(f"Response length: {len(content)} characters")
            logger.error(f"Response ends with: ...{content[-200:]}")

            # Try to extract partial data if possible
            # Look for complete fields before the error
            try:
                logger.warning("Attempting to extract partial data from incomplete JSON...")
                data = {}

                # Extract company (complete field)
                company_match = re.search(r'"company"\s*:\s*"([^"]*)"', content)
                if company_match:
                    data["company"] = company_match.group(1)

                # Extract job_title (complete field)
                job_title_match = re.search(r'"job_title"\s*:\s*"([^"]*)"', content)
                if job_title_match:
                    data["job_title"] = job_title_match.group(1)

                # Extract hiring_manager (complete field)
                hiring_manager_match = re.search(r'"hiring_manager"\s*:\s*"([^"]*)"', content)
                if hiring_manager_match:
                    data["hiring_manager"] = hiring_manager_match.group(1)

                # Extract ad_source (complete field)
                ad_source_match = re.search(r'"ad_source"\s*:\s*"([^"]*)"', content)
                if ad_source_match:
                    data["ad_source"] = ad_source_match.group(1)

                # For full_description, try to extract what we can (may be truncated)
                # Look for the start of full_description and extract up to where it breaks
                desc_match = re.search(
                    r'"full_description"\s*:\s*"(.*?)(?:"\s*[,}])', content, re.DOTALL
                )
                if desc_match:
                    # Found complete description - decode escape sequences properly
                    desc_content = desc_match.group(1)
                    # Decode JSON escape sequences while preserving UTF-8 encoding
                    try:
                        # Check if string contains escape sequences that need decoding
                        if "\\" in desc_content:
                            # Use codecs.decode with unicode_escape to handle escape sequences
                            # Encode to latin-1 first (preserves all byte values 0-255), then decode escapes
                            # This properly decodes \n, \t, \uXXXX, etc. while preserving UTF-8
                            desc_content = desc_content.encode("latin-1").decode("unicode_escape")
                            # The result is now a string with escape sequences decoded
                            # If the original was UTF-8, it should still be valid UTF-8
                        # If no escape sequences, use as-is (already properly decoded)
                    except (UnicodeDecodeError, UnicodeError, ValueError, AttributeError) as e:
                        # Fallback: manually replace common escape sequences
                        logger.warning(
                            f"Error decoding description with codecs, using fallback: {e}"
                        )
                        desc_content = (
                            desc_content.replace("\\n", "\n")
                            .replace("\\t", "\t")
                            .replace("\\r", "\r")
                            .replace('\\"', '"')
                            .replace("\\\\", "\\")
                        )
                    data["full_description"] = desc_content
                else:
                    # Try to extract partial description (truncated)
                    desc_partial_match = re.search(
                        r'"full_description"\s*:\s*"(.*)', content, re.DOTALL
                    )
                    if desc_partial_match:
                        desc_content = desc_partial_match.group(1)
                        # Clean up any trailing incomplete content
                        # Remove trailing backslashes, incomplete escape sequences
                        desc_content = desc_content.rstrip()
                        # Remove trailing incomplete quotes
                        if desc_content.endswith("\\"):
                            desc_content = desc_content[:-1]
                        # Decode JSON escape sequences while preserving UTF-8 encoding
                        try:
                            # Check if string contains escape sequences that need decoding
                            if "\\" in desc_content:
                                # Use codecs.decode with unicode_escape to handle escape sequences
                                # Encode to latin-1 first (preserves all byte values 0-255), then decode escapes
                                # This properly decodes \n, \t, \uXXXX, etc. while preserving UTF-8
                                desc_content = desc_content.encode("latin-1").decode(
                                    "unicode_escape"
                                )
                                # The result is now a string with escape sequences decoded
                                # If the original was UTF-8, it should still be valid UTF-8
                            # If no escape sequences, use as-is (already properly decoded)
                        except (UnicodeDecodeError, UnicodeError, ValueError, AttributeError) as e:
                            # Fallback: manually replace common escape sequences
                            logger.warning(
                                f"Error decoding truncated description with codecs, using fallback: {e}"
                            )
                            desc_content = (
                                desc_content.replace("\\n", "\n")
                                .replace("\\t", "\t")
                                .replace("\\r", "\r")
                                .replace('\\"', '"')
                                .replace("\\\\", "\\")
                            )
                        data["full_description"] = (
                            desc_content + " [TRUNCATED - response exceeded token limit]"
                        )
                    else:
                        data["full_description"] = "[TRUNCATED - could not extract description]"

                # Set defaults for missing fields
                data.setdefault("company", "Not specified")
                data.setdefault("job_title", "Not specified")
                data.setdefault(
                    "full_description", "Description truncated - response exceeded AI Model limit"
                )
                data.setdefault("hiring_manager", "")
                data.setdefault("ad_source", "generic")

                logger.warning(
                    f"✓ Extracted partial data: company={data.get('company')}, job_title={data.get('job_title')}"
                )
                logger.warning("Using partial data extracted from incomplete JSON")
            except Exception as e:
                logger.error(f"Could not extract partial data: {e}")
                raise json_error

        result.company = data.get("company", "Not specified")
        result.job_title = data.get("job_title") or data.get("jobTitle", "Not specified")
        result.job_description = data.get("full_description") or data.get(
            "jobDescription", "Not specified"
        )
        result.hiring_manager = data.get("hiring_manager", "") or ""
        result.ad_source = data.get("ad_source", "generic") or "generic"
        result.is_complete = result.has_minimum_data()

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ChatGPT JSON response: {e}")
        logger.debug(f"ChatGPT response received ({len(content)} characters)")
    except Exception as e:
        logger.error(f"ChatGPT extraction error: {e}")

        # Check if this is an insufficient_quota error and send email notification
        try:
            error_code = None
            error_str = str(e)

            # Try to get error code from OpenAI exception attributes
            # OpenAI SDK exceptions typically have 'response' or 'body' attributes
            if hasattr(e, "response"):
                try:
                    # Check if response has json() method
                    if hasattr(e.response, "json"):
                        error_data = e.response.json()
                        if isinstance(error_data, dict) and "error" in error_data:
                            error_code = error_data["error"].get("code")
                    # Or check if response is a dict directly
                    elif isinstance(e.response, dict) and "error" in e.response:
                        error_code = e.response["error"].get("code")
                except:
                    pass

            # Also check 'body' attribute (some OpenAI exceptions use this)
            if not error_code and hasattr(e, "body"):
                error_body = e.body
                if isinstance(error_body, dict) and "error" in error_body:
                    error_code = error_body["error"].get("code")
                elif isinstance(error_body, str):
                    # Try to parse as JSON if it's a string
                    try:
                        parsed = json.loads(error_body)
                        if isinstance(parsed, dict) and "error" in parsed:
                            error_code = parsed["error"].get("code")
                    except:
                        pass

            # Check 'code' attribute directly
            if not error_code and hasattr(e, "code"):
                error_code = e.code

            # Parse error string representation (fallback)
            # Error log shows: "Error code: 429 - {'error': {'code': 'insufficient_quota', ...}}"
            if not error_code and "'code': 'insufficient_quota'" in error_str:
                error_code = "insufficient_quota"
            elif not error_code and '"code": "insufficient_quota"' in error_str:
                error_code = "insufficient_quota"
            elif not error_code:
                # Try to extract from error string using regex
                import re

                code_match = re.search(r"'code'\s*:\s*['\"]insufficient_quota['\"]", error_str)
                if not code_match:
                    code_match = re.search(r'"code"\s*:\s*["\']insufficient_quota["\']', error_str)
                if code_match:
                    error_code = "insufficient_quota"

            # Check if it's insufficient_quota
            if error_code == "insufficient_quota":
                logger.warning("OpenAI API quota exceeded - sending email notification")
                try:
                    from app.utils.email_utils import send_email

                    send_email(
                        to_email="simonkalt@gmail.com",
                        subject="OpenAI API Quota Exceeded - Job URL Extraction",
                        body=f"""OpenAI API quota has been exceeded for the job URL extraction feature.

Error Details:
- Error Code: insufficient_quota
- Error Message: {error_str}
- Model: gpt-5.2
- Feature: Job URL Extraction

Please check your OpenAI account billing and plan details to resolve this issue.

For more information: https://platform.openai.com/docs/guides/error-codes/api-errors
""",
                    )
                    logger.info(
                        "Email notification sent to simonkalt@gmail.com for OpenAI quota issue"
                    )
                except Exception as email_error:
                    logger.error(f"Failed to send quota exceeded email notification: {email_error}")
        except Exception as check_error:
            # Don't let email notification errors break the extraction flow
            logger.debug(f"Error checking for quota issue: {check_error}")

    return result


async def analyze_job_url(
    url: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    use_chatgpt_fallback: bool = True,
    openai_client: Optional[OpenAI] = None,
    html_content: Optional[str] = None,
) -> Dict:
    """
    Analyze job URL using GPT model to extract all required fields.

    Args:
        url: Job posting URL
        user_id: Optional user ID for logging
        user_email: Optional user email for logging
        use_chatgpt_fallback: Deprecated - kept for compatibility, always uses GPT
        openai_client: Optional OpenAI client instance
        html_content: Optional HTML content - if provided, skips fetching

    Returns:
        Dictionary matching API response format
    """
    logger.info(
        f"Analyzing job URL: {url} (user_id={user_id}, user_email={user_email}, has_html={bool(html_content)})"
    )

    # Validate URL
    if not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL format. URL must start with http:// or https://")

    # Detect ad_source from URL
    ad_source = detect_site(url)

    # Step 1: Fetch HTML from URL (or use provided HTML)
    if html_content:
        html = html_content
        error = None
    else:
        html, error, _ = fetch_html(url)

    # Step 2: For LinkedIn URLs, detect login wall (server gets sign-in page, not job content)
    if html and not error and ad_source == "linkedin" and not html_content:
        if detect_linkedin_login_wall(html):
            logger.warning(
                f"LinkedIn login wall for {url}: server received sign-in page, not job content"
            )
            return {
                "success": False,
                "url": url,
                "message": (
                    "LinkedIn shows the job only when you're signed in. Our server can't sign in, so we received a sign-in page instead of the job. "
                    "Options: (1) Paste the job description and company name below, or (2) In the app, open the job in a browser while logged in and use 'Share page' / send HTML if supported."
                ),
                "company": "Not specified",
                "job_title": "Not specified",
                "ad_source": ad_source,
                "full_description": "Not specified",
                "hiring_manager": "",
                "extractionMethod": "linkedin-login-wall",
            }
        # Log what we got for debugging
        html_lower = html.lower()
        logger.info(
            f"LinkedIn fetch: html_len={len(html)}, has_about_the_job={'about the job' in html_lower}, has_sign_in={'sign in' in html_lower}"
        )

    # Step 3: Always use GPT model to extract all fields
    if html and not error:
        result = extract_with_chatgpt(html, openai_client)
        result.ad_source = ad_source
    else:
        logger.error(f"Failed to fetch HTML: {error}")
        # Return error response
        return {
            "success": False,
            "url": url,
            "message": f"Failed to fetch page content: {error or 'Unknown error'}",
            "company": "Not specified",
            "job_title": "Not specified",
            "ad_source": ad_source,
            "full_description": "Not specified",
            "hiring_manager": "",
            "extractionMethod": "error",
        }

    # Prepare response
    response_data = result.to_dict()
    response_data["url"] = url

    # Set success based on whether we have valid data
    has_valid_data = result.has_minimum_data()
    response_data["success"] = has_valid_data

    # Add error message if extraction failed
    if not has_valid_data:
        response_data["message"] = (
            "Unable to extract job data from the page. The page may not contain a valid job posting, or the structure may have changed."
        )

    return response_data
