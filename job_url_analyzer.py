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
token_limit = 100000


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
        logger.info(
            f"[LinkedInParser] Simplified mode - skipping BeautifulSoup extraction, will use Grok"
        )

        # Return empty result to trigger Grok fallback
        # The LLM will handle all extraction via extract_with_grok()
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
        logger.info(f"[IndeedParser] Starting extraction for URL: {url}")

        try:
            # Try JSON-LD structured data first
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            logger.info(f"[IndeedParser] Found {len(json_ld_scripts)} JSON-LD scripts")
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        logger.info("[IndeedParser] Found JobPosting in JSON-LD")
                        result.company = data.get("hiringOrganization", {}).get("name")
                        result.job_title = data.get("title")
                        result.job_description = data.get("description")
                        logger.info(
                            f"[IndeedParser] JSON-LD extracted - Company: '{result.company}', Title: '{result.job_title}', Description: {len(result.job_description) if result.job_description else 0} chars"
                        )
                        if result.has_minimum_data():
                            result.is_complete = True
                            logger.info(
                                "[IndeedParser] JSON-LD extraction successful, returning result"
                            )
                            return result
                except (json.JSONDecodeError, AttributeError) as e:
                    logger.debug(f"[IndeedParser] JSON-LD parse error: {e}")
                    continue

            # Company name
            logger.info("[IndeedParser] Trying CSS selectors for company name...")
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
                    logger.info(
                        f"[IndeedParser] Found company using selector '{selector}': '{result.company}'"
                    )
                    break
            if not result.company:
                logger.warning(
                    "[IndeedParser] Could not find company name with any selector"
                )

            # Job title
            logger.info("[IndeedParser] Trying CSS selectors for job title...")
            title_selectors = [
                "h1.jobTitle",
                'h1[data-testid="job-title"]',
                ".jobsearch-JobInfoHeader-title",
            ]
            for selector in title_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_title = element.get_text(strip=True)
                    logger.info(
                        f"[IndeedParser] Found job title using selector '{selector}': '{result.job_title}'"
                    )
                    break
            if not result.job_title:
                logger.warning(
                    "[IndeedParser] Could not find job title with any selector"
                )

            # Job description
            logger.info("[IndeedParser] Trying CSS selectors for job description...")
            desc_selectors = [
                "#jobDescriptionText",
                '[data-testid="job-description"]',
                ".jobsearch-jobDescriptionText",
            ]
            for selector in desc_selectors:
                element = soup.select_one(selector)
                if element:
                    result.job_description = element.get_text(strip=True)
                    logger.info(
                        f"[IndeedParser] Found job description using selector '{selector}': {len(result.job_description)} chars"
                    )
                    break
            if not result.job_description:
                logger.warning(
                    "[IndeedParser] Could not find job description with any selector"
                )

            result.is_complete = result.has_minimum_data()

            logger.info(
                f"[IndeedParser] Final extraction - Company: '{result.company or 'None'}', Title: '{result.job_title or 'None'}', Description: {len(result.job_description) if result.job_description else 0} chars"
            )
            logger.info(
                f"[IndeedParser] Has minimum data: {result.has_minimum_data()}, Is complete: {result.is_complete}"
            )

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
                            result.company = data.get("hiringOrganization", {}).get(
                                "name"
                            )
                            result.job_title = data.get("title")
                            result.job_description = data.get("description")
                        elif isinstance(data, list):
                            for item in data:
                                if item.get("@type") == "JobPosting":
                                    result.company = item.get(
                                        "hiringOrganization", {}
                                    ).get("name")
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
                        if (
                            text and len(text) > 100
                        ):  # Description should be substantial
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

    has_job_content = any(
        indicator in html_lower for indicator in job_content_indicators
    )

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
    has_strong_captcha = any(
        indicator in html_lower for indicator in strong_captcha_indicators
    )

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
            logger.info(
                f"CAPTCHA detected: found weak indicator '{indicator}' (no job content)"
            )
            return True

    return False


def fetch_html(
    url: str, timeout: int = 10
) -> Tuple[Optional[str], Optional[str], Optional[bool]]:
    """
    Fetch HTML content from URL

    Returns:
        Tuple of (html_content, error_message, captcha_detected)
        captcha_detected is True if CAPTCHA is detected, False otherwise, None on error
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

        # Check for CAPTCHA BEFORE checking status code
        # Some sites (like Indeed) may return 403 or redirect to CAPTCHA page
        captcha_detected = detect_captcha(html)

        # If CAPTCHA is detected, return it even if status is not 200
        if captcha_detected:
            logger.warning(
                f"CAPTCHA detected for URL: {url} (status: {response.status_code})"
            )
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
    logger.info(f"Using {site} parser for extraction...")
    result = parser.parse(soup, url)

    # Log extraction details
    logger.info(
        f"Parser result - Company: {result.company or 'None'}, Title: {result.job_title or 'None'}, Description length: {len(result.job_description) if result.job_description else 0}"
    )
    logger.info(
        f"Parser result - Has minimum data: {result.has_minimum_data()}, Is complete: {result.is_complete}"
    )

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
                parent = (
                    pattern_match.parent if hasattr(pattern_match, "parent") else None
                )
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

    logger.info(
        f"BeautifulSoup extraction from HTML: method={result.method}, complete={result.is_complete}, ad_source={result.ad_source}"
    )
    return result


def extract_with_beautifulsoup(url: str) -> JobExtractionResult:
    """
    Extract job information using BeautifulSoup

    Returns:
        JobExtractionResult object
    """
    # Fetch HTML
    logger.info(f"[extract_with_beautifulsoup] Fetching HTML from URL: {url}")
    html, error, captcha_detected = fetch_html(url)

    if error or not html:
        logger.warning(f"Failed to fetch HTML: {error}")
        result = JobExtractionResult()
        result.method = "beautifulsoup-failed"
        return result

    logger.info(
        f"[extract_with_beautifulsoup] HTML fetched successfully - Length: {len(html)} chars, CAPTCHA detected: {captcha_detected}"
    )
    logger.debug(
        f"[extract_with_beautifulsoup] HTML preview (first 500 chars): {html[:500]}"
    )

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
    logger.info(f"Detected site: {site} for URL: {url}")

    parsers = {
        "linkedin": LinkedInParser(),
        "indeed": IndeedParser(),
        "glassdoor": GlassdoorParser(),
        "generic": GenericParser(),
    }

    parser = parsers.get(site, GenericParser())
    logger.info(f"Using {site} parser for extraction...")
    result = parser.parse(soup, url)

    # Log extraction details
    logger.info(
        f"Parser result - Company: {result.company or 'None'}, Title: {result.job_title or 'None'}, Description length: {len(result.job_description) if result.job_description else 0}"
    )
    logger.info(
        f"Parser result - Has minimum data: {result.has_minimum_data()}, Is complete: {result.is_complete}"
    )

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
                    parent = (
                        pattern_match.parent
                        if hasattr(pattern_match, "parent")
                        else None
                    )
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


def extract_with_grok(
    html: str, grok_client: Optional[Grok] = None
) -> JobExtractionResult:
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
        html_content = html[:token_limit] if len(html) > token_limit else html

        # Create Grok client if not provided
        if grok_client is None:
            import os

            api_key = os.getenv("XAI_API_KEY")
            if not api_key:
                logger.error("XAI_API_KEY not configured")
                return result
            grok_client = Grok(api_key=api_key)

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

If any information cannot be extracted, use "Not specified" as the value (except hiring_manager which should be empty string "" if not found, and ad_source which should be "generic" if uncertain)."""

        # Log the prompt being sent to Grok
        logger.info("=" * 80)
        logger.info("GROK PROMPT BEING SENT:")
        logger.info("=" * 80)
        logger.info(prompt)
        logger.info("=" * 80)
        logger.info(f"Prompt length: {len(prompt)} characters")
        logger.info(f"HTML content length: {len(html_content)} characters")

        # Call Grok API - increased max_tokens to handle longer descriptions
        response = grok_client.chat.completions.create(
            model="grok-beta",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=8000,  # Increased to handle full job descriptions
        )

        # Log the raw response from Grok
        raw_response = response.choices[0].message.content.strip()
        logger.info("=" * 80)
        logger.info("GROK RAW RESPONSE:")
        logger.info("=" * 80)
        logger.info(raw_response[:2000])  # Log first 2000 chars
        if len(raw_response) > 2000:
            logger.info(
                f"... (truncated, total length: {len(raw_response)} characters)"
            )
        logger.info("=" * 80)

        # Parse response
        content = raw_response

        # Remove markdown code blocks if present
        if content.startswith("```"):
            content = re.sub(r"^```(?:json)?\s*\n", "", content)
            content = re.sub(r"\n```\s*$", "", content)

        # Parse JSON
        data = json.loads(content)

        # Log the parsed data
        logger.info("=" * 80)
        logger.info("GROK PARSED EXTRACTION RESULTS:")
        logger.info("=" * 80)
        logger.info(f"Company: {data.get('company', 'Not found')}")
        logger.info(f"Job Title: {data.get('job_title', 'Not found')}")
        logger.info(f"Full Description: {len(data.get('full_description', ''))} chars")
        logger.info(f"Hiring Manager: '{data.get('hiring_manager', '')}'")
        logger.info(f"Ad Source: {data.get('ad_source', 'Not found')}")
        logger.info("=" * 80)

        result.company = data.get("company", "Not specified")
        result.job_title = data.get("job_title") or data.get(
            "jobTitle", "Not specified"
        )
        result.job_description = data.get("full_description") or data.get(
            "jobDescription", "Not specified"
        )
        result.hiring_manager = data.get("hiring_manager", "") or ""
        result.ad_source = data.get("ad_source", "generic") or "generic"
        result.is_complete = result.has_minimum_data()

        logger.info(
            f"Grok extraction completed: complete={result.is_complete}, hiring_manager='{result.hiring_manager}'"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse Grok JSON response: {e}")
        logger.debug(f"Grok response content: {content[:500]}")
    except Exception as e:
        logger.error(f"Grok extraction error: {e}")

    return result


async def analyze_job_url(
    url: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    use_grok_fallback: bool = True,
    grok_client: Optional[Grok] = None,
    html_content: Optional[str] = None,
) -> Dict:
    """
    Analyze job URL using hybrid BeautifulSoup + Grok approach

    Args:
        url: Job posting URL
        user_id: Optional user ID for logging
        user_email: Optional user email for logging
        use_grok_fallback: Whether to use Grok if BeautifulSoup fails
        grok_client: Optional Grok client instance
        html_content: Optional HTML content (from CAPTCHA completion) - if provided, skips fetching

    Returns:
        Dictionary matching API response format
    """
    logger.info(
        f"Analyzing job URL: {url} (user_id={user_id}, user_email={user_email}, has_html={bool(html_content)})"
    )

    # Validate URL
    if not url.startswith(("http://", "https://")):
        raise ValueError("Invalid URL format. URL must start with http:// or https://")

    # Detect ad_source from URL (needed for both methods)
    ad_source = detect_site(url)

    # Step 1: Try BeautifulSoup first (fast, free)
    # If HTML content is provided, use it directly (from CAPTCHA completion)
    if html_content:
        logger.info("Using provided HTML content for extraction...")
        result = extract_from_html(html_content, url)
    else:
        logger.info("Attempting BeautifulSoup extraction...")
        result = extract_with_beautifulsoup(url)

    # Check if CAPTCHA is required (only if extraction failed AND HTML was not provided)
    # If HTML was provided, it's already from a verified page, so don't return captcha_required
    if result.method == "captcha-required":
        if html_content:
            # HTML was provided, so CAPTCHA is already completed - don't return captcha_required
            logger.warning(
                "Extraction failed even with provided HTML content - resetting method and continuing"
            )
            # Reset method to indicate failure, not CAPTCHA requirement
            result.method = "beautifulsoup-failed"
            # Continue with Grok fallback instead of returning early
        else:
            # No HTML provided, so CAPTCHA is actually required
            logger.info(
                "CAPTCHA required and extraction failed - returning special response"
            )
            return {
                "success": False,
                "captcha_required": True,
                "url": url,
                "message": "CAPTCHA or human verification required. The website is blocking automated access.",
                "company": "Not specified",
                "job_title": "Not specified",
                "ad_source": ad_source,
                "full_description": "Not specified",
                "hiring_manager": "",
                "extractionMethod": "error",
            }

    # Step 2: If BeautifulSoup didn't get complete data, try Grok
    if not result.is_complete and use_grok_fallback:
        logger.info("BeautifulSoup extraction incomplete, falling back to Grok...")

        # Use provided HTML if available, otherwise fetch it
        if html_content:
            html = html_content
            error = None
            captcha_detected = False
        else:
            # Fetch HTML for Grok (if not already fetched)
            html, error, captcha_detected = fetch_html(url)

        # Check for CAPTCHA again before using Grok (only if we fetched)
        # But try Grok extraction anyway - CAPTCHA might already be completed
        if captcha_detected:
            logger.warning(
                "CAPTCHA detected during Grok fallback, but attempting extraction anyway..."
            )
            # Continue with Grok extraction - if it succeeds, CAPTCHA was already completed

        if html and not error:
            grok_result = extract_with_grok(html, grok_client)

            # Set ad_source for Grok result
            grok_result.ad_source = ad_source

            # If CAPTCHA was detected but Grok got valid data, CAPTCHA was already completed
            if captcha_detected and grok_result.has_minimum_data():
                logger.info(
                    "✅ Successfully extracted job data with Grok despite CAPTCHA detection - CAPTCHA appears to be already completed"
                )
                # Use Grok results directly
                result = grok_result
            # Combine results intelligently: prefer Grok for better quality, but keep BS if Grok fails
            elif grok_result.is_complete or (
                not result.has_minimum_data() and grok_result.has_minimum_data()
            ):
                # Use Grok results, but preserve BeautifulSoup ad_source
                grok_result.ad_source = result.ad_source or ad_source
                result = grok_result
                logger.info("Using Grok extraction results")
            # If CAPTCHA was detected and Grok also failed, mark as captcha-required
            # BUT only if HTML was not provided (if HTML was provided, it's already verified)
            elif (
                captcha_detected
                and not grok_result.has_minimum_data()
                and not html_content
            ):
                logger.warning(
                    "❌ CAPTCHA detected and Grok extraction also failed - CAPTCHA required"
                )
                result.method = "captcha-required"
                return {
                    "success": False,
                    "captcha_required": True,
                    "url": url,
                    "message": "CAPTCHA or human verification required. The website is blocking automated access.",
                    "company": "Not specified",
                    "job_title": "Not specified",
                    "ad_source": ad_source,
                    "full_description": "Not specified",
                    "hiring_manager": "",
                    "extractionMethod": "error",
                }
            # If HTML was provided but Grok extraction failed, just return the failed result
            elif not grok_result.has_minimum_data() and html_content:
                logger.warning(
                    "❌ Grok extraction failed even with provided HTML content"
                )
                # Use whatever data we have, even if incomplete
                if grok_result.has_minimum_data():
                    result = grok_result
                # Otherwise keep the BeautifulSoup result (even if incomplete)
                # Ensure method is not set to captcha-required when HTML was provided
                if result.method == "captcha-required":
                    result.method = "grok-failed"
            else:
                # Combine: use Grok values where BS has "Not specified"
                if (
                    result.company == "Not specified"
                    and grok_result.company != "Not specified"
                ):
                    result.company = grok_result.company
                if (
                    result.job_title == "Not specified"
                    and grok_result.job_title != "Not specified"
                ):
                    result.job_title = grok_result.job_title
                if (
                    result.job_description == "Not specified"
                    and grok_result.job_description != "Not specified"
                ):
                    result.job_description = grok_result.job_description
                if not result.hiring_manager and grok_result.hiring_manager:
                    result.hiring_manager = grok_result.hiring_manager
                logger.info("Combined BeautifulSoup and Grok extraction results")
        else:
            logger.warning(f"Failed to fetch HTML for Grok fallback: {error}")

    # Ensure ad_source is set
    if not result.ad_source:
        result.ad_source = ad_source

    # Prepare response
    response_data = result.to_dict()
    response_data["url"] = url

    # Set success based on whether we have valid data
    has_valid_data = result.has_minimum_data()
    response_data["success"] = has_valid_data

    # If HTML was provided, never return captcha_required (HTML is already verified)
    # This is a safety check - we should have already handled this above, but ensure it here too
    if html_content:
        # Remove any captcha_required flag that might have been set
        if "captcha_required" in response_data:
            logger.warning(
                "Removing captcha_required flag since HTML was provided from verified page"
            )
            del response_data["captcha_required"]
        # If extraction failed, add a helpful message but don't set captcha_required
        if not has_valid_data:
            response_data["message"] = (
                "Unable to extract job data from the provided HTML. The page may not contain a valid job posting, or the structure may have changed."
            )

    # Detailed logging for debugging
    logger.info("=" * 80)
    logger.info("FINAL EXTRACTION RESULT")
    logger.info("=" * 80)
    logger.info(f"URL: {url}")
    logger.info(f"Method: {result.method}")
    logger.info(f"Ad Source: {result.ad_source}")
    logger.info(f"Success: {has_valid_data}")
    logger.info(
        f"Company: {result.company or 'None'} (valid: {bool(result.company and result.company != 'Not specified')})"
    )
    logger.info(
        f"Job Title: {result.job_title or 'None'} (valid: {bool(result.job_title and result.job_title != 'Not specified')})"
    )
    logger.info(
        f"Description: {'Present' if result.job_description else 'None'} (length: {len(result.job_description) if result.job_description else 0}, valid: {bool(result.job_description and result.job_description != 'Not specified')})"
    )
    logger.info(f"Hiring Manager: {result.hiring_manager or 'None'}")
    logger.info(f"Has Minimum Data: {result.has_minimum_data()}")
    logger.info(f"HTML Provided: {bool(html_content)}")
    logger.info(f"Response Success: {response_data.get('success')}")
    logger.info(f"Response Message: {response_data.get('message', 'None')}")
    logger.info("=" * 80)

    return response_data
