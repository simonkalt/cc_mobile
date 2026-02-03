"""
Manual test script for LinkedIn job extraction steps.

Run from project root:
    python scripts/test_linkedin_extract_steps.py

Or with URL for step 1:
    python scripts/test_linkedin_extract_steps.py --step 1 --url "https://www.linkedin.com/jobs/view/4337608168"
"""

import argparse
import os
import sys

# Allow importing job_url_analyzer when run from scripts/ or project root
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


def step1_extract_linkedin_job_id(url: str) -> None:
    """Step 1: Extract LinkedIn job ID from URL."""
    from job_url_analyzer import extract_linkedin_job_id

    print("\n--- Step 1: Extract LinkedIn job ID from URL ---")
    print(f"Input URL: {url}")
    job_id = extract_linkedin_job_id(url)
    if job_id is not None:
        print(f"Result: job_id = {job_id!r}")
    else:
        print("Result: No job ID found (URL may not be a LinkedIn job view URL).")
    print()


def step2_linkedin_config() -> None:
    """Step 2: Verify LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET are loaded from config."""
    from app.core.config import settings

    print("\n--- Step 2: LinkedIn API config (from .env via app config) ---")
    client_id = getattr(settings, "LINKEDIN_CLIENT_ID", None) or ""
    client_secret = getattr(settings, "LINKEDIN_CLIENT_SECRET", None) or ""
    has_id = bool(client_id.strip())
    has_secret = bool(client_secret.strip())
    id_display = (
        ("set (" + (client_id[:8] + "..." if len(client_id) > 8 else client_id) + ")")
        if has_id
        else "NOT SET"
    )
    print(f"LINKEDIN_CLIENT_ID: {id_display}")
    print(f"LINKEDIN_CLIENT_SECRET: {'set (hidden)' if has_secret else 'NOT SET'}")
    if has_id and has_secret:
        print("Result: OK – both credentials loaded.")
    else:
        print("Result: FAIL – set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env")
    print()


def step3_linkedin_api_token_and_fetch(url: str) -> None:
    """Step 3: Get LinkedIn access token and fetch job by ID (from URL)."""
    from app.core.config import settings
    from app.services.linkedin_job_api import fetch_job_by_id, get_access_token
    from job_url_analyzer import extract_linkedin_job_id

    print("\n--- Step 3: LinkedIn API – token + fetch job by ID ---")
    print(f"Input URL: {url}")
    job_id = extract_linkedin_job_id(url)
    if not job_id:
        print("Result: No job ID in URL. Use a LinkedIn job view URL.")
        print()
        return
    print(f"Job ID: {job_id}")

    client_id = getattr(settings, "LINKEDIN_CLIENT_ID", None) or ""
    client_secret = getattr(settings, "LINKEDIN_CLIENT_SECRET", None) or ""
    if not client_id.strip() or not client_secret.strip():
        print(
            "Result: FAIL – set LINKEDIN_CLIENT_ID and LINKEDIN_CLIENT_SECRET in .env (run step 2)."
        )
        print()
        return

    token = get_access_token(client_id, client_secret)
    if not token:
        print("Result: FAIL – could not obtain access token.")
        print()
        return
    print("Token: obtained")

    job_data = fetch_job_by_id(token, job_id)
    if job_data is None:
        print("Result: No job data (API may return 404 or different endpoint for this ID).")
        print()
        return
    print("Job data: received")
    # Print a short preview (avoid dumping huge description)
    import json

    def _preview_val(v):
        s = str(v)
        return (s[:200] + "...") if len(s) > 200 else s

    preview = {k: _preview_val(v) for k, v in job_data.items()}
    print(json.dumps(preview, indent=2))
    print("Result: OK – token and fetch succeeded.")
    print()


def step4_linkedin_auth_url(user_id: str) -> None:
    """Step 4: Build LinkedIn 3-legged OAuth authorization URL (user connects LinkedIn)."""
    from app.core.config import settings
    from app.services.linkedin_job_api import build_authorization_url

    print("\n--- Step 4: LinkedIn 3-legged auth URL ---")
    client_id = getattr(settings, "LINKEDIN_CLIENT_ID", None) or ""
    redirect_uri = getattr(settings, "LINKEDIN_REDIRECT_URI", None) or ""
    scope = (getattr(settings, "LINKEDIN_SCOPE", None) or "").strip()
    if not client_id or not redirect_uri:
        print("Result: FAIL – set LINKEDIN_CLIENT_ID and LINKEDIN_REDIRECT_URI in .env")
        print()
        return
    if not scope:
        print(
            "Result: FAIL – set LINKEDIN_SCOPE in .env (exact scope from Developer Portal → Auth tab)"
        )
        print()
        return
    url = build_authorization_url(
        client_id=client_id,
        redirect_uri=redirect_uri,
        state=user_id,
        scope=scope,
    )
    print("Open this URL in a browser to connect LinkedIn (state = user_id):")
    print(url)
    print("Result: OK – use this URL in app or browser; after auth, callback will store token.")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Test LinkedIn job extraction steps (run from project root)."
    )
    parser.add_argument(
        "--step",
        type=int,
        choices=[1, 2, 3, 4],
        help="Step to run (1=extract job ID, 2=config, 3=2-legged token+fetch, 4=3-legged auth URL).",
    )
    parser.add_argument(
        "--url",
        type=str,
        default="",
        help="Job URL (e.g. https://www.linkedin.com/jobs/view/4337608168). Used by steps 1 and 3.",
    )
    args = parser.parse_args()

    if args.step is not None:
        # Run single step from CLI
        if args.step == 1:
            url = args.url.strip()
            if not url:
                url = input(
                    "Enter LinkedIn job URL (e.g. https://www.linkedin.com/jobs/view/4337608168): "
                ).strip()
            if not url:
                print("No URL provided. Exiting.")
                sys.exit(1)
            step1_extract_linkedin_job_id(url)
        elif args.step == 2:
            step2_linkedin_config()
        elif args.step == 3:
            url = args.url.strip()
            if not url:
                url = input("Enter LinkedIn job URL: ").strip()
            if not url:
                url = "https://www.linkedin.com/jobs/view/4337608168"
                print(f"Using default: {url}")
            step3_linkedin_api_token_and_fetch(url)
        elif args.step == 4:
            user_id = input("Enter user_id (for state in callback): ").strip()
            if not user_id:
                user_id = "test-user-id"
                print(f"Using default: {user_id}")
            step4_linkedin_auth_url(user_id)
        return

    # Interactive menu
    print("LinkedIn job extraction – step tester")
    print("Run from project root: python scripts/test_linkedin_extract_steps.py")
    print()
    print("Steps:")
    print("  1 – Extract LinkedIn job ID from URL")
    print("  2 – Verify LinkedIn API config (LINKEDIN_CLIENT_ID / LINKEDIN_CLIENT_SECRET)")
    print("  3 – 2-legged: get app token and fetch job by ID (from URL)")
    print("  4 – 3-legged: build auth URL to connect LinkedIn (jobLibrary)")
    print("  0 – Exit")
    print()

    choice = input("Select step (0–4): ").strip()
    if choice == "0":
        return
    if choice == "1":
        url = input("Enter LinkedIn job URL: ").strip()
        if not url:
            url = "https://www.linkedin.com/jobs/view/4337608168"
            print(f"Using default: {url}")
        step1_extract_linkedin_job_id(url)
        return
    if choice == "2":
        step2_linkedin_config()
        return
    if choice == "3":
        url = input("Enter LinkedIn job URL (or Enter for default): ").strip()
        if not url:
            url = "https://www.linkedin.com/jobs/view/4337608168"
            print(f"Using default: {url}")
        step3_linkedin_api_token_and_fetch(url)
        return
    if choice == "4":
        user_id = input("Enter user_id (or Enter for default): ").strip()
        if not user_id:
            user_id = "test-user-id"
            print(f"Using default: {user_id}")
        step4_linkedin_auth_url(user_id)
        return
    print("Unknown step.")


if __name__ == "__main__":
    main()
