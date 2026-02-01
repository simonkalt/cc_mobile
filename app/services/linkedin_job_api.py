"""
LinkedIn Job API client.

Uses OAuth2 client credentials to obtain an access token, then fetches job
posting details by ID. Requires LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET
in config (from .env).

Ref: https://learn.microsoft.com/en-us/linkedin/talent/job-postings/api/job-posting-module1-basics
"""

import logging
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
LINKEDIN_VERSION_HEADER = "202501"


def get_access_token(client_id: str, client_secret: str) -> Optional[str]:
    """
    Obtain a LinkedIn API access token using client credentials (2-legged OAuth).

    Args:
        client_id: LINKEDIN_CLIENT_ID from app config.
        client_secret: LINKEDIN_CLIENT_SECRET from app config.

    Returns:
        Access token string, or None on failure.
    """
    if not client_id or not client_secret:
        logger.warning("LinkedIn API: missing client_id or client_secret")
        return None
    try:
        response = requests.post(
            LINKEDIN_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "client_credentials",
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in")
        if token:
            logger.info("LinkedIn API: obtained access token (expires_in=%s)", expires_in)
        return token
    except requests.RequestException as e:
        logger.warning("LinkedIn API: token request failed: %s", e)
        return None
    except Exception as e:
        logger.warning("LinkedIn API: token error: %s", e)
        return None


def fetch_job_by_id(access_token: str, job_id: str) -> Optional[Dict[str, Any]]:
    """
    Fetch a single job posting by ID from the LinkedIn REST API.

    The job_id should be the numeric ID from the URL path, e.g. "4337608168"
    from https://www.linkedin.com/jobs/view/4337608168.

    Args:
        access_token: Bearer token from get_access_token().
        job_id: Job ID string (e.g. from extract_linkedin_job_id(url)).

    Returns:
        Parsed JSON response dict, or None on failure. Structure depends on
        LinkedIn API; caller should map to JobExtractionResult.
    """
    if not access_token or not job_id:
        logger.warning("LinkedIn API: missing access_token or job_id")
        return None
    url = f"{LINKEDIN_API_BASE}/simpleJobPostings/{job_id}"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": LINKEDIN_VERSION_HEADER,
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        if response.status_code == 404:
            logger.info("LinkedIn API: job not found (404) for id=%s", job_id)
            return None
        response.raise_for_status()
        data = response.json()
        logger.info("LinkedIn API: fetched job id=%s", job_id)
        return data
    except requests.RequestException as e:
        logger.warning("LinkedIn API: fetch job failed for id=%s: %s", job_id, e)
        return None
    except Exception as e:
        logger.warning("LinkedIn API: fetch job error for id=%s: %s", job_id, e)
        return None
