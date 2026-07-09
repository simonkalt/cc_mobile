"""
Job URL Analyzer - Hybrid BeautifulSoup + Claude Haiku Implementation

This module implements a hybrid approach to extract job information from URLs:
1. First attempts BeautifulSoup parsing (fast, free)
2. Falls back to Claude Haiku 4.5 if BeautifulSoup fails (handles complex cases)
"""

import json
import os
import re
import logging
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

# Configure logging
logger = logging.getLogger(__name__)

# Always use Claude Haiku 4.5 for LLM HTML parsing (override via env if needed).
JOB_URL_LLM_MODEL = os.getenv("JOB_URL_LLM_MODEL", "claude-haiku-4-5")


class JobExtractionResult:
    """Container for job extraction results"""

    def __init__(self):
        self.company: Optional[str] = None
        self.job_title: Optional[str] = None
        self.job_description: Optional[str] = None
        self.hiring_manager: Optional[str] = None
        self.ad_source: Optional[str] = None
        self.method: Optional[str] = None  # 'beautifulsoup-*' or JOB_URL_LLM_MODEL
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


def _clean_optional_field(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    text = re.sub(r"\s+", " ", value.strip())
    if not text or text.lower() in ("not specified", "n/a", "none"):
        return None
    return text


_BLOCK_TAGS_WITH_BREAKS = (
    "p",
    "div",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "tr",
    "ul",
    "ol",
)

_LINE_BREAK_TAGS = ("li",)


def _clean_description_text(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    from html import unescape

    text = unescape(value.strip())
    text = re.sub(r"\r\n?", "\n", text)

    paragraphs = []
    current_lines = []
    for raw_line in text.split("\n"):
        line = re.sub(r"[ \t]+", " ", raw_line).strip()
        if not line:
            if current_lines:
                paragraphs.append("\n".join(current_lines))
                current_lines = []
            continue
        current_lines.append(line)

    if current_lines:
        paragraphs.append("\n".join(current_lines))

    text = "\n\n".join(paragraphs)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text or text.lower() in ("not specified", "n/a", "none"):
        return None
    return text


def _html_element_to_text(element) -> Optional[str]:
    if element is None:
        return None
    fragment = BeautifulSoup(str(element), "html.parser")
    root = fragment.find() if fragment.find() else fragment
    for br in root.find_all("br"):
        br.replace_with("\n")
    for tag in root.find_all(list(_BLOCK_TAGS_WITH_BREAKS)):
        tag.append("\n\n")
    for tag in root.find_all(list(_LINE_BREAK_TAGS)):
        tag.append("\n")
    return _clean_description_text(root.get_text())


def _normalize_job_description(value: Optional[str]) -> Optional[str]:
    if not value:
        return None
    if "<" in value and ">" in value:
        parsed = _html_element_to_text(BeautifulSoup(value, "html.parser"))
        if parsed:
            return parsed
    return _clean_description_text(value)


def _first_selector_description(soup: BeautifulSoup, selectors) -> Optional[str]:
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = _html_element_to_text(element)
            if text:
                return text
    return None


_HIRING_MANAGER_REJECT = frozenset(
    {
        "for this",
        "this role",
        "the team",
        "our team",
        "linkedin",
        "recruiter",
        "hiring manager",
        "see who",
        "contact",
    }
)


def _is_plausible_person_name(name: str) -> bool:
    cleaned = _clean_optional_field(name)
    if not cleaned or len(cleaned) < 3:
        return False
    if cleaned.lower() in _HIRING_MANAGER_REJECT:
        return False
    if not re.match(
        r"^[A-Za-z][A-Za-z'.-]*(?:\s+[A-Za-z][A-Za-z'.-]+)+$",
        cleaned,
    ):
        return False
    return True


def _find_linkedin_section_heading(soup: BeautifulSoup, *labels: str):
    labels_lower = {label.lower() for label in labels}
    partial_phrases = ("meet the hiring team", "meet the team")
    for tag in soup.find_all(["h2", "h3", "h4", "strong", "span", "p", "div"]):
        text = tag.get_text(strip=True)
        if not text:
            continue
        lower = text.lower()
        if lower in labels_lower:
            return tag
        if len(text) < 80 and any(phrase in lower for phrase in partial_phrases):
            return tag
    return None


def _linkedin_section_container(heading):
    if heading is None:
        return None
    for ancestor in heading.parents:
        if ancestor.name in ("section", "article"):
            return ancestor
        if ancestor.name == "div":
            classes = " ".join(ancestor.get("class") or [])
            if any(token in classes for token in ("section", "container", "module")):
                return ancestor
    return heading.parent


def _parse_linkedin_og_title(soup: BeautifulSoup) -> Tuple[Optional[str], Optional[str]]:
    meta = soup.find("meta", property="og:title") or soup.find(
        "meta", attrs={"name": "og:title"}
    )
    if not meta or not meta.get("content"):
        return None, None

    content = meta["content"]
    if "&" in content:
        from html import unescape

        content = unescape(content)

    match = re.match(
        r"^(.+?)\s+hiring\s+(.+?)\s+in\s+.+\|\s*LinkedIn\s*$",
        content,
        re.I,
    )
    if not match:
        return None, None

    return _clean_optional_field(match.group(1)), _clean_optional_field(match.group(2))


def _first_selector_text(soup: BeautifulSoup, selectors) -> Optional[str]:
    for selector in selectors:
        element = soup.select_one(selector)
        if element:
            text = _clean_optional_field(element.get_text(strip=True))
            if text:
                return text
    return None


def _extract_linkedin_company_from_about_section(soup: BeautifulSoup) -> Optional[str]:
    heading = _find_linkedin_section_heading(soup, "About the company")
    container = _linkedin_section_container(heading)
    if container is None:
        return None

    for anchor in container.select('a[href*="/company/"]'):
        name = _clean_optional_field(anchor.get_text(strip=True))
        if name and name.lower() != "about the company":
            return name

    return _first_selector_text(
        container,
        [
            ".jobs-company__company-name",
            ".artdeco-entity-lockup__title",
            "h3",
            "h4",
            "strong",
        ],
    )


def _extract_person_name_from_container(container) -> Optional[str]:
    if container is None:
        return None

    for selector in [
        ".hirer-card__hirer-information",
        ".jobs-poster__name",
        '[data-testid="job-poster-name"]',
        "h3.base-main-card__title",
        ".artdeco-entity-lockup__title",
        ".base-main-card__title",
    ]:
        for element in container.select(selector):
            name = _clean_optional_field(element.get_text(strip=True))
            if name and _is_plausible_person_name(name):
                return name

    for anchor in container.select('a[href*="/in/"]'):
        sr = anchor.select_one(".sr-only")
        if sr:
            name = _clean_optional_field(sr.get_text(strip=True))
            if name and _is_plausible_person_name(name):
                return name

    return None


def _extract_linkedin_hiring_team_member(soup: BeautifulSoup) -> Optional[str]:
    heading = _find_linkedin_section_heading(
        soup, "Meet the hiring team", "Meet the team"
    )
    name = _extract_person_name_from_container(_linkedin_section_container(heading))
    if name:
        return name

    for selector in (
        ".message-the-recruiter",
        '[data-testid="job-poster-card"]',
        ".jobs-poster-card",
        ".jobs-poster",
    ):
        name = _extract_person_name_from_container(soup.select_one(selector))
        if name:
            return name

    return None


class LinkedInParser(BaseJobParser):
    """Parser for LinkedIn job postings"""

    def parse(self, soup: BeautifulSoup, url: str) -> JobExtractionResult:
        result = JobExtractionResult()
        result.method = "beautifulsoup-linkedin"

        try:
            # Try JSON-LD structured data first
            json_ld_scripts = soup.find_all("script", type="application/ld+json")
            for script in json_ld_scripts:
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict) and data.get("@type") == "JobPosting":
                        result.company = _clean_optional_field(
                            data.get("hiringOrganization", {}).get("name")
                        )
                        result.job_title = _clean_optional_field(data.get("title"))
                        result.job_description = _normalize_job_description(
                            data.get("description")
                        )
                        if result.has_minimum_data():
                            result.is_complete = True
                            result.hiring_manager = (
                                _extract_linkedin_hiring_team_member(soup) or None
                            )
                            return result
                except (json.JSONDecodeError, AttributeError):
                    continue

            og_company, og_title = _parse_linkedin_og_title(soup)

            result.company = (
                _extract_linkedin_company_from_about_section(soup)
                or _first_selector_text(
                    soup,
                    [
                        "a.topcard__org-name-link",
                        ".topcard__org-name-link",
                        ".job-details-jobs-unified-top-card__company-name",
                        ".job-details-jobs-unified-top-card__company-name a",
                        ".jobs-unified-top-card__company-name",
                        'a[data-tracking-control-name="public_jobs_topcard-org-name"]',
                    ],
                )
                or og_company
            )

            result.job_title = _first_selector_text(
                soup,
                [
                    "h1.top-card-layout__title",
                    "h1.topcard__title",
                    ".topcard__title",
                    "h1.job-title",
                    'h1[data-testid="job-title"]',
                    ".job-details-jobs-unified-top-card__job-title",
                    ".jobs-unified-top-card__job-title",
                    "h1.jobs-unified-top-card__job-title",
                ],
            ) or og_title

            result.job_description = _first_selector_description(
                soup,
                [
                    "div.show-more-less-html__markup",
                    ".description__text",
                    "#job-details",
                    ".jobs-description__text",
                    '[data-testid="job-description"]',
                ],
            )

            result.hiring_manager = _extract_linkedin_hiring_team_member(soup)
            result.is_complete = result.has_minimum_data()

        except Exception as e:
            logger.error(f"LinkedIn parser error: {e}")

        return result


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
                        result.job_description = _normalize_job_description(
                            data.get("description")
                        )
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
                    result.job_description = _html_element_to_text(element)
                    logger.info(
                        f"[IndeedParser] Found job description using selector '{selector}': {len(result.job_description) if result.job_description else 0} chars"
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
                        result.job_description = _normalize_job_description(
                            data.get("description")
                        )
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
                    result.job_description = _html_element_to_text(element)
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
                            result.job_description = _normalize_job_description(
                            data.get("description")
                        )
                        elif isinstance(data, list):
                            for item in data:
                                if item.get("@type") == "JobPosting":
                                    result.company = item.get(
                                        "hiringOrganization", {}
                                    ).get("name")
                                    result.job_title = item.get("title")
                                    result.job_description = _normalize_job_description(
                                        item.get("description")
                                    )
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
                result.job_description = _normalize_job_description(
                    og_description["content"]
                )

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
                result.job_description = _normalize_job_description(
                    meta_description["content"]
                )

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
                        text = _html_element_to_text(element)
                        if text and len(text) > 100:
                            result.job_description = text[:5000]
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
    elif "ziprecruiter.com" in domain:
        return "ziprecruiter"
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


LINKEDIN_AUTHWALL_SIGNALS = [
    "authwall",
    "sign in to see",
    "sign in to view",
    "join linkedin",
    "login-form",
    "session_key",
    "checkpoint/challenge",
    "global-nav__guest",
    "guest_homepage",
]

LOGIN_SIGNUP_SIGNALS = [
    "sign in",
    "log in",
    "create account",
    "continue with google",
    "email or phone",
]


def _extract_html_title(html: str) -> Optional[str]:
    if not html:
        return None
    match = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    title = re.sub(r"\s+", " ", match.group(1)).strip()
    return title[:300] if title else None


def _has_linkedin_job_posting_json_ld(html: str) -> bool:
    if not html:
        return False
    try:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script", type="application/ld+json"):
            raw = script.string or script.get_text()
            if not raw:
                continue
            data = json.loads(raw)
            items = data if isinstance(data, list) else [data]
            for item in items:
                if isinstance(item, dict) and item.get("@type") == "JobPosting":
                    return True
    except (json.JSONDecodeError, TypeError, AttributeError):
        pass
    return False


def inspect_job_page_html(
    html: Optional[str],
    url: str,
    *,
    captcha_detected: Optional[bool] = None,
    fetch_error: Optional[str] = None,
    http_status: Optional[int] = None,
    final_url: Optional[str] = None,
) -> Dict:
    """
    Summarize fetched HTML to diagnose auth walls, CAPTCHA, and missing job content.
    """
    html_lower = (html or "").lower()
    html_length = len(html or "")

    job_content_indicators = [
        "job description",
        "jobsearch-jobdescriptiontext",
        "jobs-unified-top-card",
        "job-details-jobs-unified-top-card",
        "description__text",
        "show-more-less-html",
    ]
    matched_job_signals = [
        s for s in job_content_indicators if s in html_lower
    ]
    matched_linkedin_auth = [
        s for s in LINKEDIN_AUTHWALL_SIGNALS if s in html_lower
    ]
    matched_login = [s for s in LOGIN_SIGNUP_SIGNALS if s in html_lower]

    has_json_ld_job = _has_linkedin_job_posting_json_ld(html or "")
    captcha = (
        captcha_detected
        if captcha_detected is not None
        else detect_captcha(html or "")
    )

    if fetch_error:
        page_kind = "fetch_error"
    elif not html:
        page_kind = "empty_html"
    elif matched_job_signals or has_json_ld_job:
        page_kind = "job_content_present"
    elif "linkedin.com" in url.lower() and matched_linkedin_auth:
        page_kind = "linkedin_authwall"
    elif captcha:
        page_kind = "captcha_or_bot_check"
    elif matched_login:
        page_kind = "login_or_signup"
    else:
        page_kind = "unknown"

    preview_len = int(os.getenv("JOB_URL_DEBUG_PREVIEW_CHARS", "2500"))
    preview = (html or "")[:preview_len]

    return {
        "requested_url": url,
        "final_url": final_url or url,
        "http_status": http_status,
        "fetch_error": fetch_error,
        "html_length": html_length,
        "title": _extract_html_title(html or ""),
        "page_kind": page_kind,
        "captcha_detected": captcha,
        "has_job_posting_json_ld": has_json_ld_job,
        "matched_job_content_signals": matched_job_signals,
        "matched_linkedin_auth_signals": matched_linkedin_auth,
        "matched_login_signals": matched_login[:8],
        "html_preview": preview,
        "html_preview_truncated": html_length > preview_len,
    }


def debug_fetch_job_url(url: str, timeout: int = 15) -> Dict:
    """
    Fetch a job URL and return diagnostic metadata + HTML preview (for debugging).
    Does not call the LLM.
    """
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    try:
        response = requests.get(
            url,
            headers=headers,
            timeout=timeout,
            allow_redirects=True,
        )
        if response.encoding:
            html = response.text
        else:
            html = response.content.decode("utf-8", errors="ignore")

        captcha_detected = detect_captcha(html)
        inspection = inspect_job_page_html(
            html,
            url,
            captcha_detected=captcha_detected,
            http_status=response.status_code,
            final_url=str(response.url),
        )
        inspection["redirect_chain"] = [str(r.url) for r in response.history]
        return inspection

    except requests.exceptions.Timeout:
        return inspect_job_page_html(
            None,
            url,
            fetch_error="Request timeout",
        )
    except requests.exceptions.RequestException as e:
        return inspect_job_page_html(
            None,
            url,
            fetch_error=str(e),
        )
    except Exception as e:
        return inspect_job_page_html(
            None,
            url,
            fetch_error=f"Unexpected error: {e}",
        )


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

    # LinkedIn hiring manager comes from "Meet the hiring team" in LinkedInParser only.
    if site != "linkedin":
        try:
            hiring_manager_patterns = [
                soup.find(string=re.compile(r"hiring manager", re.I)),
                soup.find(string=re.compile(r"recruiter", re.I)),
                soup.find(string=re.compile(r"contact.*name", re.I)),
            ]

            for pattern_match in hiring_manager_patterns:
                if pattern_match:
                    parent = (
                        pattern_match.parent
                        if hasattr(pattern_match, "parent")
                        else None
                    )
                    if parent:
                        text = parent.get_text(strip=True)
                        match = re.search(
                            r"(?:hiring manager|recruiter)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                            text,
                            re.I,
                        )
                        if match:
                            candidate = match.group(1).strip()
                            if _is_plausible_person_name(candidate):
                                result.hiring_manager = candidate
                                break
        except Exception as e:
            logger.debug(f"Could not extract hiring manager: {e}")

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

    if site != "linkedin":
        try:
            hiring_manager_patterns = [
                soup.find(string=re.compile(r"hiring manager", re.I)),
                soup.find(string=re.compile(r"recruiter", re.I)),
                soup.find(string=re.compile(r"contact.*name", re.I)),
            ]

            for pattern_match in hiring_manager_patterns:
                if pattern_match:
                    parent = (
                        pattern_match.parent
                        if hasattr(pattern_match, "parent")
                        else None
                    )
                    if parent:
                        text = parent.get_text(strip=True)
                        match = re.search(
                            r"(?:hiring manager|recruiter)[:\s]+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)",
                            text,
                            re.I,
                        )
                        if match:
                            candidate = match.group(1).strip()
                            if _is_plausible_person_name(candidate):
                                result.hiring_manager = candidate
                                break
        except Exception as e:
            logger.debug(f"Could not extract hiring manager: {e}")

    logger.info(
        f"BeautifulSoup extraction result: method={result.method}, complete={result.is_complete}, ad_source={result.ad_source}"
    )
    return result


def _build_job_html_extraction_prompt(html_content: str) -> str:
    return f"""Analyze the following HTML content from a job posting webpage and extract structured information.

HTML Content:
{html_content}

Please extract the following information and return ONLY valid JSON (no markdown, no code blocks):
1. company: The company name from the job posting (for LinkedIn, prefer the "About the company" section; otherwise use the top card or page metadata)
2. job_title: The complete job title/position name
3. full_description: The full job description including responsibilities, requirements, and qualifications
4. hiring_manager: The hiring team member name only if listed under "Meet the hiring team" or the job poster / recruiter card (return empty string "" if not found)

Return format (JSON only):
{{
    "company": "Company Name",
    "job_title": "Job Title",
    "full_description": "Full job description text...",
    "hiring_manager": "Hiring Manager Name" or ""
}}

If company, job_title, or full_description cannot be extracted, use "Not specified". Leave hiring_manager as "" when no hiring team member is clearly named."""


def _parse_llm_job_json(content: str) -> Dict:
    text = content.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n", "", text)
        text = re.sub(r"\n```\s*$", "", text)
    return json.loads(text)


def _apply_llm_job_json(result: JobExtractionResult, data: Dict) -> None:
    result.company = _clean_optional_field(data.get("company", "Not specified"))
    result.job_title = _clean_optional_field(
        data.get("job_title") or data.get("jobTitle", "Not specified")
    )
    result.job_description = _normalize_job_description(
        data.get("full_description") or data.get("jobDescription", "Not specified")
    )
    hiring_manager = data.get("hiring_manager", "") or ""
    result.hiring_manager = (
        hiring_manager if _is_plausible_person_name(hiring_manager) else None
    )
    result.is_complete = result.has_minimum_data()


def extract_with_claude_haiku(
    html: str, anthropic_client=None
) -> JobExtractionResult:
    """
    Extract job information using Claude Haiku 4.5 (LLM fallback).

    Args:
        html: HTML content to analyze
        anthropic_client: Optional Anthropic client instance

    Returns:
        JobExtractionResult object
    """
    result = JobExtractionResult()
    result.method = JOB_URL_LLM_MODEL

    content = ""
    try:
        html_content = html[:50000] if len(html) > 50000 else html
        prompt = _build_job_html_extraction_prompt(html_content)

        # Prefer OpenRouter when enabled; otherwise use Anthropic SDK
        used_openrouter = False
        try:
            from app.utils.openrouter_client import (
                openrouter_chat,
                openrouter_configured,
                use_openrouter,
            )

            if use_openrouter() and openrouter_configured():
                content = openrouter_chat(
                    app_model=JOB_URL_LLM_MODEL,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=4096,
                    temperature=0.1,
                )
                used_openrouter = True
        except Exception as or_exc:
            logger.warning("OpenRouter job extraction failed, falling back to Anthropic: %s", or_exc)

        if not used_openrouter:
            if anthropic_client is None:
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if not api_key:
                    logger.error("ANTHROPIC_API_KEY not configured")
                    return result
                import anthropic

                anthropic_client = anthropic.Anthropic(api_key=api_key)

            response = anthropic_client.messages.create(
                model=JOB_URL_LLM_MODEL,
                max_tokens=4096,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.content[0].text

        data = _parse_llm_job_json(content)
        _apply_llm_job_json(result, data)

        logger.info(
            "Claude Haiku extraction completed: model=%s complete=%s via=%s",
            JOB_URL_LLM_MODEL,
            result.is_complete,
            "openrouter" if used_openrouter else "anthropic",
        )

    except json.JSONDecodeError as e:
        logger.error("Failed to parse Claude Haiku JSON response: %s", e)
        logger.debug("Claude Haiku response content: %s", content[:500])
    except Exception as e:
        logger.error("Claude Haiku extraction error: %s", e)

    return result


async def analyze_job_url(
    url: str,
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    use_llm_fallback: bool = True,
    anthropic_client=None,
    html_content: Optional[str] = None,
) -> Dict:
    """
    Analyze job URL using hybrid BeautifulSoup + Claude Haiku approach

    Args:
        url: Job posting URL
        user_id: Optional user ID for logging
        user_email: Optional user email for logging
        use_llm_fallback: Whether to use Claude Haiku if BeautifulSoup fails
        anthropic_client: Optional Anthropic client instance
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
            # Continue with Claude Haiku fallback instead of returning early
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

    # Step 2: If BeautifulSoup didn't get complete data, try Claude Haiku 4.5
    if not result.is_complete and use_llm_fallback:
        logger.info(
            "BeautifulSoup extraction incomplete, falling back to %s...",
            JOB_URL_LLM_MODEL,
        )

        # Use provided HTML if available, otherwise fetch it
        if html_content:
            html = html_content
            error = None
            captcha_detected = False
        else:
            # Fetch HTML for LLM fallback (if not already fetched)
            html, error, captcha_detected = fetch_html(url)

        # Check for CAPTCHA again before using LLM (only if we fetched)
        if captcha_detected:
            logger.warning(
                "CAPTCHA detected during LLM fallback, but attempting extraction anyway..."
            )

        if html and not error:
            llm_result = extract_with_claude_haiku(html, anthropic_client)

            # Set ad_source for LLM result
            llm_result.ad_source = ad_source

            # If CAPTCHA was detected but LLM got valid data, CAPTCHA was already completed
            if captcha_detected and llm_result.has_minimum_data():
                logger.info(
                    "✅ Successfully extracted job data with %s despite CAPTCHA detection",
                    JOB_URL_LLM_MODEL,
                )
                result = llm_result
            elif llm_result.is_complete or (
                not result.has_minimum_data() and llm_result.has_minimum_data()
            ):
                llm_result.ad_source = result.ad_source or ad_source
                result = llm_result
                logger.info("Using Claude Haiku extraction results")
            elif (
                captcha_detected
                and not llm_result.has_minimum_data()
                and not html_content
            ):
                logger.warning(
                    "❌ CAPTCHA detected and Claude Haiku extraction also failed - CAPTCHA required"
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
            elif not llm_result.has_minimum_data() and html_content:
                logger.warning(
                    "❌ Claude Haiku extraction failed even with provided HTML content"
                )
                if llm_result.has_minimum_data():
                    result = llm_result
                if result.method == "captcha-required":
                    result.method = "llm-failed"
            else:
                # Combine: use LLM values where BS has "Not specified"
                if (
                    result.company == "Not specified"
                    and llm_result.company != "Not specified"
                ):
                    result.company = llm_result.company
                if (
                    result.job_title == "Not specified"
                    and llm_result.job_title != "Not specified"
                ):
                    result.job_title = llm_result.job_title
                if (
                    result.job_description == "Not specified"
                    and llm_result.job_description != "Not specified"
                ):
                    result.job_description = llm_result.job_description
                if not result.hiring_manager and llm_result.hiring_manager:
                    result.hiring_manager = llm_result.hiring_manager
                if llm_result.has_minimum_data():
                    result.method = llm_result.method
                    result.is_complete = result.has_minimum_data()
                logger.info("Combined BeautifulSoup and Claude Haiku extraction results")
        else:
            logger.warning(f"Failed to fetch HTML for LLM fallback: {error}")

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
    elif not has_valid_data:
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
