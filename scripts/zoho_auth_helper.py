#!/usr/bin/env python3
"""
Zoho OAuth helper for local development.

Loads Zoho credentials from repo-root `.env` then `.secrets` (same as the API).

Uses those vars to:
1) print an authorization URL
2) exchange an authorization code for refresh/access tokens
3) test refresh token flow
4) list Zoho Mail accounts to discover accountId
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlparse

import requests

_SCRIPT_ROOT = Path(__file__).resolve().parent.parent
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

from app.core.env_loader import load_project_env, resolve_secrets_path


DEFAULT_ACCOUNTS_BASE = "https://accounts.zoho.com"
MAIL_BASE = "https://mail.zoho.com"


def _accounts_base() -> str:
    return (
        os.getenv("ZOHO_ACCOUNTS_BASE")
        or os.getenv("ZOHO_ACCOUNTS_URL")
        or DEFAULT_ACCOUNTS_BASE
    ).strip().rstrip("/")


def _parse_authorization_code(raw: str) -> str:
    """Accept a bare code or a full callback URL (?code=...)."""
    value = (raw or "").strip()
    if not value:
        return ""
    if "code=" not in value:
        return value
    if value.startswith("http://") or value.startswith("https://"):
        query = parse_qs(urlparse(value).query)
        return (query.get("code") or [""])[0].strip()
    if value.startswith("?"):
        query = parse_qs(value.lstrip("?"))
        return (query.get("code") or [""])[0].strip()
    if "code=" in value:
        fragment = value.split("code=", 1)[1]
        return fragment.split("&", 1)[0].strip()
    return value


def _explain_token_error(body: dict, *, redirect_uri: str) -> None:
    err = (body or {}).get("error")
    if not err:
        return
    print(f"Zoho OAuth error: {err}")
    if err == "invalid_code":
        print(
            "Common causes:\n"
            "  • Code expired (~60 seconds) — get a fresh URL, authorize again, exchange immediately\n"
            "  • Code already used — authorization codes are single-use\n"
            "  • redirect_uri mismatch — must exactly match the authorize URL and Zoho console\n"
            f"    (this run used: {redirect_uri})\n"
            "  • Wrong Zoho data center — set ZOHO_ACCOUNTS_BASE if you use .eu / .in / .com.au\n"
            "  • client_id / client_secret do not match the app that issued the code"
        )
    elif err == "invalid_client":
        print("Check ZOHO_CLIENT_ID and ZOHO_CLIENT_SECRET in .env / .secrets.")
    elif err == "invalid_redirect_uri":
        print(
            "Register this exact redirect URI in the Zoho API console and use the same "
            f"value in --redirect-uri / ZOHO_REDIRECT_URI:\n  {redirect_uri}"
        )
    print("")


def _require(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def _auth_url(client_id: str, redirect_uri: str, scopes: str, accounts_base: str) -> str:
    query = urlencode(
        {
            "scope": scopes,
            "client_id": client_id,
            "response_type": "code",
            "access_type": "offline",
            "prompt": "consent",
            "redirect_uri": redirect_uri,
        }
    )
    return f"{accounts_base}/oauth/v2/auth?{query}"


def _exchange_code(
    client_id: str,
    client_secret: str,
    redirect_uri: str,
    code: str,
    accounts_base: str,
) -> dict:
    resp = requests.post(
        f"{accounts_base}/oauth/v2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=20,
    )
    body: dict
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return {"status": resp.status_code, "body": body}


def _refresh_token(
    client_id: str, client_secret: str, refresh_token: str, accounts_base: str
) -> dict:
    resp = requests.post(
        f"{accounts_base}/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=20,
    )
    body: dict
    try:
        body = resp.json()
    except Exception:
        body = {"raw": resp.text}
    return {"status": resp.status_code, "body": body}


def _list_accounts(access_token: str) -> dict:
    resp = requests.get(
        f"{MAIL_BASE}/api/accounts",
        headers={"Authorization": f"Zoho-oauthtoken {access_token}"},
        timeout=20,
    )
    data: dict
    try:
        data = resp.json()
    except Exception:
        data = {"raw": resp.text}
    return {"status": resp.status_code, "body": data}


def main() -> None:
    load_project_env(_SCRIPT_ROOT)
    secrets_path = resolve_secrets_path(_SCRIPT_ROOT)
    env_path = _SCRIPT_ROOT / ".env"
    loaded = []
    if env_path.is_file():
        loaded.append(str(env_path))
    if secrets_path:
        loaded.append(str(secrets_path))
    if loaded:
        print(f"Loaded env from: {', '.join(loaded)}")
        print("")

    parser = argparse.ArgumentParser(description="Zoho OAuth helper")
    parser.add_argument(
        "--redirect-uri",
        default=os.getenv("ZOHO_REDIRECT_URI", "http://localhost:8675/oauth/callback"),
        help="OAuth redirect URI (must match Zoho app config)",
    )
    parser.add_argument(
        "--scopes",
        default="ZohoMail.messages.CREATE,ZohoMail.messages.READ,ZohoMail.accounts.READ",
        help="Comma-separated OAuth scopes",
    )
    parser.add_argument(
        "--code",
        default="",
        help="Authorization code, or full callback URL containing ?code=",
    )
    parser.add_argument(
        "--access-token",
        default="",
        help="Optional access token to use for --accounts",
    )
    parser.add_argument(
        "--mode",
        choices=["url", "exchange", "refresh", "accounts", "all"],
        default="all",
        help="Action to run",
    )

    args = parser.parse_args()
    accounts_base = _accounts_base()
    redirect_uri = args.redirect_uri.strip()

    try:
        client_id = _require("ZOHO_CLIENT_ID")
        client_secret = _require("ZOHO_CLIENT_SECRET")
    except ValueError as e:
        print(str(e))
        sys.exit(1)

    print(f"ZOHO accounts base: {accounts_base}")
    print(f"redirect_uri: {redirect_uri}")
    print(f"client_id prefix: {client_id[:12]}...")
    print("")

    if args.mode in {"url", "all"}:
        print("Authorize URL (open immediately; exchange the code within ~60 seconds):")
        print(_auth_url(client_id, redirect_uri, args.scopes, accounts_base))
        print("")

    if args.mode in {"exchange", "all"}:
        code = _parse_authorization_code(args.code)
        if not code:
            print("--code is required for exchange mode (bare code or callback URL).")
            if args.mode == "exchange":
                sys.exit(1)
        else:
            print(f"Exchanging authorization code (length {len(code)})...")
            result = _exchange_code(
                client_id, client_secret, redirect_uri, code, accounts_base
            )
            print("Code exchange result:")
            print(json.dumps(result, indent=2))
            print("")
            body = result.get("body") or {}
            if body.get("error"):
                _explain_token_error(body, redirect_uri=redirect_uri)
            refresh = body.get("refresh_token")
            if refresh:
                print("Copy this into .env or .secrets as ZOHO_REFRESH_TOKEN:")
                print(refresh)
                print("")
            elif args.mode == "exchange":
                sys.exit(1)

    if args.mode in {"refresh", "all"}:
        refresh_token = (os.getenv("ZOHO_REFRESH_TOKEN") or "").strip()
        if not refresh_token:
            print("ZOHO_REFRESH_TOKEN is not set; skipping refresh.")
            if args.mode == "refresh":
                sys.exit(1)
        else:
            result = _refresh_token(
                client_id, client_secret, refresh_token, accounts_base
            )
            print("Refresh-token result:")
            print(json.dumps(result, indent=2))
            body = result.get("body") or {}
            if body.get("error"):
                _explain_token_error(body, redirect_uri=redirect_uri)
            print("")

    if args.mode in {"accounts", "all"}:
        token = args.access_token.strip()
        if not token:
            refresh_token = (os.getenv("ZOHO_REFRESH_TOKEN") or "").strip()
            if refresh_token:
                refreshed = _refresh_token(
                    client_id, client_secret, refresh_token, accounts_base
                )
                token = ((refreshed.get("body") or {}).get("access_token") or "").strip()
                print("Using access token from refresh result.")
            else:
                print("No --access-token and no ZOHO_REFRESH_TOKEN; cannot list accounts.")
                if args.mode == "accounts":
                    sys.exit(1)
        if token:
            result = _list_accounts(token)
            print("Accounts result:")
            print(json.dumps(result, indent=2))
            print("")
            body = result.get("body") or {}
            # Try a few common response shapes.
            account_ids = []
            if isinstance(body, dict):
                data = body.get("data")
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict):
                            aid = item.get("accountId") or item.get("id")
                            if aid:
                                account_ids.append(str(aid))
                elif isinstance(data, dict):
                    aid = data.get("accountId") or data.get("id")
                    if aid:
                        account_ids.append(str(aid))
            if account_ids:
                print("Possible ZOHO_ACCOUNT_ID values:")
                for aid in account_ids:
                    print(aid)


if __name__ == "__main__":
    main()
