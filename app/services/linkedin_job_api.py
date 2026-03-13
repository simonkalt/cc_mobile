"""
LinkedIn Job API client.

Supports two auth modes:
1. 3-legged OAuth (user auth): build_authorization_url, exchange_code_for_token,
   then fetch_job_from_library(access_token, job_id) using /rest/jobLibrary FINDER.
2. Client credentials (2-legged): get_access_token, fetch_job_by_id (simpleJobPostings).
   Only works if your app has a product that allows "create application tokens".

Requires LINKEDIN_CLIENT_ID, LINKEDIN_CLIENT_SECRET; for 3-legged also LINKEDIN_REDIRECT_URI, LINKEDIN_SCOPE.

Ref: https://learn.microsoft.com/en-us/linkedin/shared/authentication/authorization-code-flow
"""

import logging
import urllib.parse
from typing import Any, Dict, Optional

import requests

logger = logging.getLogger(__name__)

LINKEDIN_AUTHORIZE_URL = "https://www.linkedin.com/oauth/v2/authorization"
LINKEDIN_TOKEN_URL = "https://www.linkedin.com/oauth/v2/accessToken"
LINKEDIN_API_BASE = "https://api.linkedin.com/rest"
LINKEDIN_VERSION_HEADER = "202501"


def _mask(s: str, show: int = 4) -> str:
    """Return masked string for logging (e.g. 'abcd...' or '****')."""
    if not s or len(s) <= show:
        return "****" if s else "(empty)"
    return s[:show] + "..."


# ---------------------------------------------------------------------------
# 3-legged OAuth (user auth) for jobLibrary FINDER
# ---------------------------------------------------------------------------


def build_authorization_url(
    client_id: str,
    redirect_uri: str,
    state: str,
    scope: str,
) -> str:
    """
    Build the LinkedIn OAuth 2.0 authorization URL for 3-legged flow.

    User opens this URL in a browser, signs in to LinkedIn, authorizes the app,
    and is redirected to redirect_uri with ?code=...&state=...

    Args:
        client_id: LINKEDIN_CLIENT_ID.
        redirect_uri: Must match a Redirect URL in your LinkedIn app (Auth tab).
        state: Opaque value (e.g. user_id) to pass back in callback; use for CSRF.
        scope: Space-separated scopes (e.g. r_ads_library or the scope for jobLibrary).

    Returns:
        Full URL to redirect the user to.
    """
    params = {
        "response_type": "code",
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "state": state,
        "scope": scope,
    }
    return LINKEDIN_AUTHORIZE_URL + "?" + urllib.parse.urlencode(params)


def exchange_code_for_token(
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
) -> Optional[Dict[str, Any]]:
    """
    Exchange an authorization code for an access token (3-legged OAuth).

    Call this in your callback after receiving ?code=... from LinkedIn.

    Args:
        client_id: LINKEDIN_CLIENT_ID.
        client_secret: LINKEDIN_CLIENT_SECRET.
        code: The authorization code from the callback query.
        redirect_uri: Same redirect_uri used in the authorization request.

    Returns:
        Dict with access_token, expires_in, refresh_token (if any), scope; or None on failure.
    """
    if not all([client_id, client_secret, code, redirect_uri]):
        logger.warning("LinkedIn API: missing param for code exchange")
        return None
    try:
        response = requests.post(
            LINKEDIN_TOKEN_URL,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            },
            timeout=15,
        )
        logger.debug("LinkedIn API: code exchange response status=%s", response.status_code)
        if response.status_code != 200:
            try:
                err_body = response.json()
                logger.warning(
                    "LinkedIn API: code exchange failed status=%s body=%s",
                    response.status_code,
                    err_body,
                )
            except Exception:
                logger.warning(
                    "LinkedIn API: code exchange failed status=%s body=%s",
                    response.status_code,
                    response.text[:500] if response.text else "(empty)",
                )
            return None
        data = response.json()
        logger.info(
            "LinkedIn API: exchanged code for token (expires_in=%s)",
            data.get("expires_in"),
        )
        return data
    except requests.RequestException as e:
        logger.warning("LinkedIn API: code exchange request failed: %s", e)
        return None
    except Exception as e:
        logger.warning("LinkedIn API: code exchange error: %s", e, exc_info=True)
        return None


def fetch_job_from_library(
    access_token: str,
    job_id: str,
    criteria_param: str = "id",
) -> Optional[Dict[str, Any]]:
    """
    Fetch a job by ID from the LinkedIn jobLibrary FINDER (3-legged auth).

    Uses GET /rest/jobLibrary with criteria query param. The exact param name
    may depend on your product (e.g. id, jobId, criteria); set criteria_param
    to match your portal if needed.

    Args:
        access_token: User's access token from exchange_code_for_token().
        job_id: Job ID from URL (e.g. 4337608168 from linkedin.com/jobs/view/4337608168).
        criteria_param: Query param name for job ID (default "id"; try "jobId" if 400).

    Returns:
        Parsed JSON response (structure depends on LinkedIn API); or None on failure.
    """
    if not access_token or not job_id:
        logger.warning("LinkedIn API: missing access_token or job_id for jobLibrary")
        return None
    url = f"{LINKEDIN_API_BASE}/jobLibrary"
    params = {criteria_param: job_id}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "LinkedIn-Version": LINKEDIN_VERSION_HEADER,
    }
    logger.debug("LinkedIn API: jobLibrary FINDER url=%s params=%s", url, params)
    try:
        response = requests.get(url, params=params, headers=headers, timeout=15)
        logger.debug("LinkedIn API: jobLibrary response status=%s", response.status_code)
        if response.status_code == 404:
            logger.info("LinkedIn API: jobLibrary job not found (404) for id=%s", job_id)
            return None
        if response.status_code != 200:
            try:
                err_body = response.json()
                logger.warning(
                    "LinkedIn API: jobLibrary failed id=%s status=%s body=%s",
                    job_id,
                    response.status_code,
                    err_body,
                )
            except Exception:
                logger.warning(
                    "LinkedIn API: jobLibrary failed id=%s status=%s body=%s",
                    job_id,
                    response.status_code,
                    response.text[:500] if response.text else "(empty)",
                )
            return None
        data = response.json()
        logger.info("LinkedIn API: jobLibrary fetched job id=%s", job_id)
        return data
    except requests.RequestException as e:
        logger.warning("LinkedIn API: jobLibrary request failed for id=%s: %s", job_id, e)
        return None
    except Exception as e:
        logger.warning("LinkedIn API: jobLibrary error for id=%s: %s", job_id, e, exc_info=True)
        return None


# ---------------------------------------------------------------------------
# 2-legged OAuth (client credentials) – only if your app has that product
# ---------------------------------------------------------------------------


def get_access_token(client_id: str, client_secret: str) -> Optional[str]:
    """
    Obtain a LinkedIn API access token using client credentials (2-legged OAuth).

    Args:
        client_id: LINKEDIN_CLIENT_ID from app config.
        client_secret: LINKEDIN_CLIENT_SECRET from app config.

    Returns:
        Access token string, or None on failure.
    """
    logger.debug(
        "LinkedIn API: token request url=%s client_id=%s",
        LINKEDIN_TOKEN_URL,
        _mask(client_id, 8) if client_id else "(missing)",
    )
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
        logger.debug("LinkedIn API: token response status=%s", response.status_code)
        if response.status_code != 200:
            try:
                err_body = response.json()
                logger.warning(
                    "LinkedIn API: token auth failed status=%s body=%s",
                    response.status_code,
                    err_body,
                )
            except Exception:
                logger.warning(
                    "LinkedIn API: token auth failed status=%s body=%s",
                    response.status_code,
                    response.text[:500] if response.text else "(empty)",
                )
            return None
        data = response.json()
        token = data.get("access_token")
        expires_in = data.get("expires_in")
        if token:
            logger.info(
                "LinkedIn API: obtained access token (expires_in=%s token=%s)",
                expires_in,
                _mask(token, 6),
            )
        else:
            logger.warning(
                "LinkedIn API: token response missing access_token keys=%s", list(data.keys())
            )
        return token
    except requests.RequestException as e:
        logger.warning("LinkedIn API: token request failed: %s", e)
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                logger.debug("LinkedIn API: token error response body=%s", resp.json())
            except Exception:
                logger.debug(
                    "LinkedIn API: token error response text=%s",
                    (resp.text[:500] if resp.text else "(empty)"),
                )
        return None
    except Exception as e:
        logger.warning("LinkedIn API: token error: %s", e, exc_info=True)
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
    logger.debug("LinkedIn API: fetch job id=%s url=%s", job_id, url)
    try:
        response = requests.get(url, headers=headers, timeout=15)
        logger.debug("LinkedIn API: fetch job response status=%s", response.status_code)
        if response.status_code == 404:
            logger.info("LinkedIn API: job not found (404) for id=%s", job_id)
            return None
        if response.status_code != 200:
            try:
                err_body = response.json()
                logger.warning(
                    "LinkedIn API: fetch job failed id=%s status=%s body=%s",
                    job_id,
                    response.status_code,
                    err_body,
                )
            except Exception:
                logger.warning(
                    "LinkedIn API: fetch job failed id=%s status=%s body=%s",
                    job_id,
                    response.status_code,
                    response.text[:500] if response.text else "(empty)",
                )
            return None
        data = response.json()
        logger.info("LinkedIn API: fetched job id=%s", job_id)
        return data
    except requests.RequestException as e:
        logger.warning("LinkedIn API: fetch job failed for id=%s: %s", job_id, e)
        resp = getattr(e, "response", None)
        if resp is not None:
            try:
                logger.debug("LinkedIn API: fetch job error response body=%s", resp.json())
            except Exception:
                logger.debug(
                    "LinkedIn API: fetch job error response text=%s",
                    (resp.text[:500] if resp.text else "(empty)"),
                )
        return None
    except Exception as e:
        logger.warning("LinkedIn API: fetch job error for id=%s: %s", job_id, e, exc_info=True)
        return None
