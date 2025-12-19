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

# Try to import Selenium for JavaScript rendering (optional)
try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.common.exceptions import TimeoutException, WebDriverException

    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

token_limit = 100000

# Log Selenium availability after logger is configured
if not SELENIUM_AVAILABLE:
    logger.warning(
        "Selenium not available - JavaScript rendering will be skipped. Install selenium to enable JavaScript rendering."
    )


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


def fetch_html_with_selenium(
    url: str, timeout: int = 15
) -> Tuple[Optional[str], Optional[str], Optional[bool]]:
    """
    Fetch HTML content from URL using Selenium to render JavaScript

    Returns:
        Tuple of (html_content, error_message, captcha_detected)
        captcha_detected is True if CAPTCHA is detected, False otherwise, None on error
    """
    if not SELENIUM_AVAILABLE:
        return None, "Selenium not available", None

    driver = None
    try:
        logger.info(f"[Selenium] Fetching URL with JavaScript rendering: {url}")

        # Set up Chrome options for headless browsing (optimized for speed)
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")  # Use new headless mode (faster)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        # Disable images and CSS to speed up loading
        prefs = {
            "profile.managed_default_content_settings.images": 2,  # Block images
        }
        chrome_options.add_experimental_option("prefs", prefs)

        # Create driver
        driver = webdriver.Chrome(options=chrome_options)
        driver.set_page_load_timeout(timeout)
        driver.implicitly_wait(2)  # Reduce implicit wait time

        # Navigate to URL
        driver.get(url)

        # Wait for page to load - optimized wait strategy
        try:
            import time

            # Wait for document ready state (faster check)
            WebDriverWait(driver, 5).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )

            # Reduced wait time for dynamic content - check if content is already loaded
            # For LinkedIn, check if job description section exists
            try:
                # Try to find job description content quickly
                WebDriverWait(driver, 3).until(
                    lambda d: len(d.find_elements(By.TAG_NAME, "body")) > 0
                    and (
                        "job" in d.page_source.lower()[:5000]
                        or len(d.page_source) > 10000
                    )  # Reasonable content length
                )
            except TimeoutException:
                # If specific content not found, just wait a short time for any dynamic content
                time.sleep(1)  # Reduced from 3 seconds to 1 second

        except TimeoutException:
            logger.warning(
                "[Selenium] Page load timeout, proceeding with current content"
            )

        # Get the rendered HTML
        html = driver.page_source

        logger.info(
            f"[Selenium] Successfully fetched rendered HTML: {len(html)} characters"
        )

        # Check for CAPTCHA
        captcha_detected = detect_captcha(html)

        # Clean up
        driver.quit()

        return html, None, captcha_detected

    except WebDriverException as e:
        logger.error(f"[Selenium] WebDriver error: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        return None, f"Selenium WebDriver error: {str(e)}", None
    except Exception as e:
        logger.error(f"[Selenium] Unexpected error: {e}", exc_info=True)
        if driver:
            try:
                driver.quit()
            except:
                pass
        return None, f"Selenium error: {str(e)}", None


def fetch_html(
    url: str, timeout: int = 10, use_selenium: bool = True
) -> Tuple[Optional[str], Optional[str], Optional[bool]]:
    """
    Fetch HTML content from URL
    First tries Selenium (if available) to render JavaScript, falls back to requests

    Returns:
        Tuple of (html_content, error_message, captcha_detected)
        captcha_detected is True if CAPTCHA is detected, False otherwise, None on error
    """
    # Try Selenium first for JavaScript rendering (especially for LinkedIn)
    if use_selenium and SELENIUM_AVAILABLE and "linkedin.com" in url.lower():
        logger.info(f"[fetch_html] Using Selenium for LinkedIn URL: {url}")
        html, error, captcha = fetch_html_with_selenium(
            url, timeout=15
        )  # Reduced from 30 to 15 seconds
        if html and not error:
            return html, error, captcha
        logger.warning(
            f"[fetch_html] Selenium failed, falling back to requests: {error}"
        )

    # Fallback to requests
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


def extract_with_chatgpt(
    html: str, openai_client: Optional[OpenAI] = None
) -> JobExtractionResult:
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

        # Log the prompt being sent to ChatGPT
        logger.info("=" * 80)
        logger.info("CHATGPT PROMPT BEING SENT:")
        logger.info("=" * 80)
        logger.info(prompt)
        logger.info("=" * 80)
        logger.info(f"Prompt length: {len(prompt)} characters")
        logger.info(f"HTML content length: {len(html_content)} characters")

        # Call OpenAI ChatGPT API - using gpt-5.2 for better extraction
        # GPT-5.2 supports 128,000 max completion tokens, 400,000 context window
        model_name = "gpt-5.2"
        max_completion_tokens_value = (
            128000  # GPT-5.2 supports up to 128,000 max completion tokens
        )
        response = openai_client.chat.completions.create(
            model=model_name,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_completion_tokens=max_completion_tokens_value,  # GPT-5.2 uses max_completion_tokens instead of max_tokens
            response_format={"type": "json_object"},  # Force JSON response
        )

        # Log the raw response from ChatGPT
        raw_response = response.choices[0].message.content.strip()
        logger.info("=" * 80)
        logger.info("CHATGPT RAW RESPONSE:")
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
        logger.info("CHATGPT PARSED EXTRACTION RESULTS:")
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
            f"ChatGPT extraction completed: complete={result.is_complete}, hiring_manager='{result.hiring_manager}'"
        )

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse ChatGPT JSON response: {e}")
        logger.debug(f"ChatGPT response content: {content[:500]}")
    except Exception as e:
        logger.error(f"ChatGPT extraction error: {e}")

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
        logger.info("Using provided HTML content for extraction...")
        html = html_content
        error = None
    else:
        logger.info("Fetching HTML from URL...")
        html, error, _ = fetch_html(url)

    # Step 2: Always use GPT model to extract all fields
    if html and not error:
        logger.info("Extracting job information using GPT model...")
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
