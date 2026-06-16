#!/usr/bin/env python3
"""
Fetch a job URL and print HTML diagnostics (same logic as POST /api/job-url/debug-fetch).

Usage:
  python debug_job_url_fetch.py "https://www.linkedin.com/jobs/view/4284546149/"
  python debug_job_url_fetch.py "https://www.linkedin.com/jobs/view/4284546149/" --save-html /tmp/job.html
"""

import argparse
import json
import sys

from job_url_analyzer import debug_fetch_job_url


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug server-side job URL fetch")
    parser.add_argument("url", help="Job posting URL to fetch")
    parser.add_argument(
        "--save-html",
        metavar="PATH",
        help="Write full HTML response to this file",
    )
    parser.add_argument(
        "--preview-chars",
        type=int,
        default=2500,
        help="Characters of HTML preview in JSON output (default 2500)",
    )
    args = parser.parse_args()

    import os

    os.environ["JOB_URL_DEBUG_PREVIEW_CHARS"] = str(args.preview_chars)

    result = debug_fetch_job_url(args.url)

    if args.save_html and result.get("html_preview") is not None:
        # Re-fetch for full body when saving (debug_fetch only returns preview in dict)
        import requests

        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
        }
        resp = requests.get(args.url, headers=headers, timeout=15)
        with open(args.save_html, "w", encoding="utf-8") as f:
            f.write(resp.text)
        result["saved_html_path"] = args.save_html
        result["saved_html_length"] = len(resp.text)

    print(json.dumps(result, indent=2))

    kind = result.get("page_kind")
    if kind in ("linkedin_authwall", "login_or_signup", "captcha_or_bot_check", "fetch_error", "empty_html"):
        print(f"\n⚠ page_kind={kind} — server fetch likely missing authenticated job content.", file=sys.stderr)
        return 1
    if kind == "job_content_present":
        print("\n✓ page_kind=job_content_present — HTML looks like a real job page.", file=sys.stderr)
        return 0
    print(f"\n? page_kind={kind} — inspect html_preview / saved file.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
