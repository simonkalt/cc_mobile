#!/usr/bin/env python3
"""
Validate App Store Server API JWT credentials against Apple using a *real* sandbox
(or production) subscription identifier.

Uses the same signing contract as the FastAPI backend (Issuer ID, Key ID, .p8 /
APP_STORE_PRIVATE_KEY, ``bid`` claim).

What it does
------------
1. Builds a short-lived ES256 JWT from ``.env`` (and optional ``.secrets``).
2. Calls ``GET .../inApps/v1/history/{originalTransactionId}`` (sandbox or production).
3. Prints a clear result: **HTTP 200** ⇒ JWT is accepted by Apple and that
   original transaction exists in that environment.

This does **not** use Xcode ``.storekit`` synthetic ids (e.g. ``1``); you need an
``originalTransactionId`` from a **device or TestFlight sandbox** purchase.

Usage
-----
  .venv/bin/python scripts/validate_app_store_sandbox_api.py <originalTransactionId>
  .venv/bin/python scripts/validate_app_store_sandbox_api.py --try-both-envs <originalTransactionId>
  .venv/bin/python scripts/validate_app_store_sandbox_api.py --transaction-info <transactionId>

Env (same as backend)
---------------------
  APP_STORE_KEY_ID
  APP_STORE_ISSUER_ID
  APP_STORE_BUNDLE_ID
  APP_STORE_PRIVATE_KEY_PATH  and/or  APP_STORE_PRIVATE_KEY
  APP_STORE_USE_SANDBOX=true|false   (default sandbox base URL when not using --production)

Dependencies: PyJWT, cryptography, requests (and python-dotenv optional for .env loading)

Use ``--require-nonempty-history`` if you want exit code 5 when credentials work but
history is empty (wrong/placeholder ``originalTransactionId``).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import textwrap
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.env_loader import load_project_env

load_project_env(ROOT)

try:
    import jwt
except ImportError:
    print(
        "Install PyJWT + cryptography: .venv/bin/python -m pip install PyJWT cryptography",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Install requests: .venv/bin/python -m pip install requests", file=sys.stderr)
    sys.exit(1)


SANDBOX_HOST = "https://api.storekit-sandbox.itunes.apple.com"
PRODUCTION_HOST = "https://api.storekit.itunes.apple.com"


def _abort(msg: str, code: int = 1) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(code)


def _fix_inline_pem(raw: str) -> str:
    raw = raw.strip()
    if "\n" in raw:
        return raw
    begin = "-----BEGIN PRIVATE KEY-----"
    end = "-----END PRIVATE KEY-----"
    body = raw.replace(begin, "").replace(end, "").strip()
    wrapped = "\n".join(textwrap.wrap(body, 64))
    return f"{begin}\n{wrapped}\n{end}"


def _load_private_key_pem() -> str:
    key_id = (os.getenv("APP_STORE_KEY_ID") or "").strip()
    key_path_env = (os.getenv("APP_STORE_PRIVATE_KEY_PATH") or "").strip()

    candidates: list[Path] = []
    if key_path_env:
        candidates.append(ROOT / key_path_env)
    if key_id:
        candidates.append(ROOT / "keys" / f"AuthKey_{key_id}.p8")

    for path in candidates:
        if path.is_file():
            print(f"Using private key file: {path.relative_to(ROOT)}")
            return path.read_text().strip()

    inline = (os.getenv("APP_STORE_PRIVATE_KEY") or "").strip()
    if inline:
        print("Using APP_STORE_PRIVATE_KEY from environment (inline PEM)")
        return _fix_inline_pem(inline)

    _abort(
        "No private key: set APP_STORE_PRIVATE_KEY_PATH or APP_STORE_PRIVATE_KEY "
        "(and ensure keys/AuthKey_{APP_STORE_KEY_ID}.p8 exists if using only Key ID)."
    )


def _build_jwt() -> str:
    issuer = (os.getenv("APP_STORE_ISSUER_ID") or "").strip()
    key_id = (os.getenv("APP_STORE_KEY_ID") or "").strip()
    bundle_id = (os.getenv("APP_STORE_BUNDLE_ID") or "").strip()
    if not issuer or not key_id or not bundle_id:
        _abort("Set APP_STORE_ISSUER_ID, APP_STORE_KEY_ID, and APP_STORE_BUNDLE_ID in .env")

    pem = _load_private_key_pem()
    now = int(time.time())
    return jwt.encode(
        {
            "iss": issuer,
            "iat": now,
            "exp": now + 3600,
            "aud": "appstoreconnect-v1",
            "bid": bundle_id,
        },
        pem,
        algorithm="ES256",
        headers={"kid": key_id, "alg": "ES256"},
    )


def _print_response_summary(resp: requests.Response) -> None:
    print(f"\nHTTP {resp.status_code}")
    ct = resp.headers.get("Content-Type", "")
    body = resp.text
    if "application/json" in ct.lower():
        try:
            parsed = resp.json()
            dumped = json.dumps(parsed, indent=2)
            print(dumped[:8000])
            if len(dumped) > 8000:
                print("… (truncated)")
        except Exception:
            print(body[:4000])
    else:
        print(body[:4000])


def _call_history(base: str, original_tx_id: str, token: str) -> requests.Response:
    url = f"{base}/inApps/v1/history/{original_tx_id}"
    print(f"\nGET {url}")
    return requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def _call_transaction_info(base: str, transaction_id: str, token: str) -> requests.Response:
    """Single-transaction lookup (matches backend ``get_transaction_info`` style)."""
    url = f"{base}/inApps/v1/transactions/{transaction_id}"
    print(f"\nGET {url}")
    return requests.get(
        url,
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument(
        "identifier",
        nargs="?",
        help="originalTransactionId (history) unless --transaction-info is used",
    )
    p.add_argument(
        "--transaction-info",
        action="store_true",
        help="Treat identifier as StoreKit transactionId (GET /inApps/v1/transactions/{id})",
    )
    p.add_argument(
        "--sandbox",
        action="store_true",
        help=f"Force sandbox host ({SANDBOX_HOST})",
    )
    p.add_argument(
        "--production",
        action="store_true",
        help=f"Force production host ({PRODUCTION_HOST})",
    )
    p.add_argument(
        "--try-both-envs",
        action="store_true",
        help="Try sandbox then production",
    )
    p.add_argument(
        "--require-nonempty-history",
        action="store_true",
        help="Exit 5 if HTTP 200 but signedTransactions is empty (JWT ok but id not linked to purchases)",
    )
    args = p.parse_args()

    if not args.identifier:
        _abort(
            "Pass a real sandbox originalTransactionId (or transaction id with "
            "--transaction-info).\n"
            "Example:\n"
            "  .venv/bin/python scripts/validate_app_store_sandbox_api.py 2000000123456789"
        )

    use_sandbox_default = os.getenv("APP_STORE_USE_SANDBOX", "true").lower().strip() in (
        "true",
        "1",
        "yes",
    )
    retry_alt = os.getenv("APP_STORE_RETRY_ALTERNATE_ENVIRONMENT", "true").lower().strip() in (
        "true",
        "1",
        "yes",
    )

    if args.sandbox and args.production:
        _abort("Use only one of --sandbox or --production")

    if args.try_both_envs:
        hosts = [SANDBOX_HOST, PRODUCTION_HOST]
    elif args.sandbox:
        hosts = [SANDBOX_HOST]
    elif args.production:
        hosts = [PRODUCTION_HOST]
    else:
        primary = SANDBOX_HOST if use_sandbox_default else PRODUCTION_HOST
        secondary = PRODUCTION_HOST if primary == SANDBOX_HOST else SANDBOX_HOST
        hosts = [primary]
        if retry_alt:
            hosts.append(secondary)

    token = _build_jwt()
    ident = args.identifier.strip()

    print("=== App Store Server API credential check ===")
    print(f"  Bundle ID: {os.getenv('APP_STORE_BUNDLE_ID', '')}")
    print(f"  Key ID:    {os.getenv('APP_STORE_KEY_ID', '')}")
    print(f"  Issuer:    {os.getenv('APP_STORE_ISSUER_ID', '')}")

    last_resp: requests.Response | None = None
    for host in hosts:
        label = "sandbox" if "sandbox" in host else "production"
        print(f"\n--- {label} ---")
        if args.transaction_info:
            last_resp = _call_transaction_info(host, ident, token)
        else:
            last_resp = _call_history(host, ident, token)

        if last_resp.status_code == 200:
            _print_response_summary(last_resp)
            if args.transaction_info:
                data = last_resp.json()
                if data.get("signedTransactionInfo"):
                    print(
                        "\nPASS: HTTP 200 — Apple accepted the JWT and returned "
                        "signedTransactionInfo."
                    )
                else:
                    print(
                        "\nPASS: HTTP 200 — but response missing signedTransactionInfo (unexpected)."
                    )
            else:
                data = last_resp.json()
                n = len(data.get("signedTransactions") or [])
                print(
                    "\n--- Interpretation ---\n"
                    "  • Credentials: OK — Apple returned HTTP 200 (JWT + key + issuer accepted).\n"
                )
                if n:
                    print(
                        f"  • Transaction history for this id: {n} signedTransaction(s) — "
                        "full check passed.\n"
                    )
                    sys.exit(0)
                print(
                    "  • Transaction history for this id: EMPTY.\n\n"
                    "Apple often responds 200 with an empty signedTransactions array when "
                    "the requested originalTransactionId is not tied to sandbox purchases "
                    "for this bundle — e.g. a placeholder/example id, typo, or .storekit-only id.\n\n"
                    "Next step: use the originalTransactionId from a real Sandbox purchase "
                    "(device / TestFlight), or try:\n"
                    "  .venv/bin/python scripts/validate_app_store_sandbox_api.py "
                    "--transaction-info <renewal_transaction_id_from_logs>\n"
                )
                if args.require_nonempty_history:
                    print(
                        "FAIL: --require-nonempty-history set and history is empty (exit 5).",
                        file=sys.stderr,
                    )
                    sys.exit(5)
            sys.exit(0)

        _print_response_summary(last_resp)

        if last_resp.status_code == 401:
            print(
                "\nFAIL: HTTP 401 — Apple rejected the JWT. Check that Key ID, Issuer ID, "
                "and the .p8 / APP_STORE_PRIVATE_KEY belong to the *same* App Store Connect "
                "API key.",
                file=sys.stderr,
            )
            sys.exit(2)

        if last_resp.status_code == 404:
            print(
                f"\nNot found in {label} — try the other environment or confirm the id is from "
                f"a real {'sandbox' if label == 'sandbox' else 'production'} purchase "
                f"(not a .storekit synthetic id).",
            )
            continue

        print(f"\nFAIL: HTTP {last_resp.status_code}", file=sys.stderr)
        sys.exit(3)

    if last_resp is not None and last_resp.status_code == 404:
        print(
            "\nFAIL: Transaction not found in any tried environment. "
            "JWT may still be valid if you never saw 401 above.",
            file=sys.stderr,
        )
        sys.exit(4)

    _abort("No response from Apple (unexpected).")


if __name__ == "__main__":
    main()
