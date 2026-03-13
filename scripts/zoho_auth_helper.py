#!/usr/bin/env python3
"""
Zoho OAuth helper for local development.

Uses .env vars to:
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
from urllib.parse import urlencode

import requests
from dotenv import load_dotenv


ACCOUNTS_BASE = "https://accounts.zoho.com"
MAIL_BASE = "https://mail.zoho.com"


def _require(name: str) -> str:
    value = (os.getenv(name) or "").strip()
    if not value:
        raise ValueError(f"Missing required env var: {name}")
    return value


def _auth_url(client_id: str, redirect_uri: str, scopes: str) -> str:
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
    return f"{ACCOUNTS_BASE}/oauth/v2/auth?{query}"


def _exchange_code(
    client_id: str, client_secret: str, redirect_uri: str, code: str
) -> dict:
    resp = requests.post(
        f"{ACCOUNTS_BASE}/oauth/v2/token",
        data={
            "grant_type": "authorization_code",
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=20,
    )
    return {"status": resp.status_code, "body": resp.json()}


def _refresh_token(client_id: str, client_secret: str, refresh_token: str) -> dict:
    resp = requests.post(
        f"{ACCOUNTS_BASE}/oauth/v2/token",
        data={
            "grant_type": "refresh_token",
            "client_id": client_id,
            "client_secret": client_secret,
            "refresh_token": refresh_token,
        },
        timeout=20,
    )
    return {"status": resp.status_code, "body": resp.json()}


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
    load_dotenv()

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
        help="Authorization code returned by Zoho callback",
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

    try:
        client_id = _require("ZOHO_CLIENT_ID")
        client_secret = _require("ZOHO_CLIENT_SECRET")
    except ValueError as e:
        print(str(e))
        sys.exit(1)

    if args.mode in {"url", "all"}:
        print("Authorize URL:")
        print(_auth_url(client_id, args.redirect_uri, args.scopes))
        print("")

    if args.mode in {"exchange", "all"}:
        code = args.code.strip()
        if not code:
            print("--code is required for exchange mode.")
            if args.mode == "exchange":
                sys.exit(1)
        else:
            result = _exchange_code(client_id, client_secret, args.redirect_uri, code)
            print("Code exchange result:")
            print(json.dumps(result, indent=2))
            print("")
            refresh = (result.get("body") or {}).get("refresh_token")
            if refresh:
                print("Copy this into .env as ZOHO_REFRESH_TOKEN:")
                print(refresh)
                print("")

    if args.mode in {"refresh", "all"}:
        refresh_token = (os.getenv("ZOHO_REFRESH_TOKEN") or "").strip()
        if not refresh_token:
            print("ZOHO_REFRESH_TOKEN is not set; skipping refresh.")
            if args.mode == "refresh":
                sys.exit(1)
        else:
            result = _refresh_token(client_id, client_secret, refresh_token)
            print("Refresh-token result:")
            print(json.dumps(result, indent=2))
            print("")

    if args.mode in {"accounts", "all"}:
        token = args.access_token.strip()
        if not token:
            refresh_token = (os.getenv("ZOHO_REFRESH_TOKEN") or "").strip()
            if refresh_token:
                refreshed = _refresh_token(client_id, client_secret, refresh_token)
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
