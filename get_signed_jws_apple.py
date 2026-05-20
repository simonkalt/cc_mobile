#!/usr/bin/env python3
"""
Fetch a signedTransaction JWS from the Apple App Store Server API.

Credentials are read from .env and .secrets (loaded from the project root).

Usage:
    .venv/bin/python get_signed_jws_apple.sh <original_transaction_id>
    # or set BILLING_TEST_ORIGINAL_TRANSACTION_ID in .env and run without arg

On success, prints the most recent JWS and a ready-to-paste export line for
BILLING_TEST_SANDBOX_JWS so you can copy it into .env or a smoke-test shell.

Dependencies (already in .venv):
    python-dotenv, PyJWT, cryptography, requests
"""

import sys
import os
import time
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: ensure project root on path and load .env
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from app.core.env_loader import load_project_env

load_project_env(ROOT)

# ---------------------------------------------------------------------------
# Config — all from .env
# ---------------------------------------------------------------------------
KEY_ID    = (os.getenv("APP_STORE_KEY_ID") or "").strip()
ISSUER_ID = (os.getenv("APP_STORE_ISSUER_ID") or "").strip()
BUNDLE_ID = (os.getenv("APP_STORE_BUNDLE_ID") or "").strip()
USE_SANDBOX = os.getenv("APP_STORE_USE_SANDBOX", "true").lower().strip() in ("true", "1", "yes")

# Transaction ID: CLI arg wins, then .env
ORIGINAL_TX_ID = (
    sys.argv[1].strip()
    if len(sys.argv) > 1
    else (os.getenv("BILLING_TEST_ORIGINAL_TRANSACTION_ID") or "").strip()
)

# ---------------------------------------------------------------------------
# Private key loader
# ---------------------------------------------------------------------------

def _fix_inline_pem(raw: str) -> str:
    """Re-wrap a PEM key that was collapsed to a single line (common in .env files)."""
    raw = raw.strip()
    if "\n" in raw:
        return raw  # already has newlines — fine as-is
    # Split at the header/footer markers and re-wrap the base64 body
    begin = "-----BEGIN PRIVATE KEY-----"
    end = "-----END PRIVATE KEY-----"
    raw = raw.replace(begin, "").replace(end, "").strip()
    wrapped = "\n".join(textwrap.wrap(raw, 64))
    return f"{begin}\n{wrapped}\n{end}"


def _load_private_key() -> str:
    """Return the PEM private key string.

    Search order:
      1. APP_STORE_PRIVATE_KEY_PATH  (path relative to project root)
      2. keys/AuthKey_{KEY_ID}.p8    (Apple's default naming convention)
      3. APP_STORE_PRIVATE_KEY       (inline PEM — re-wrapped if collapsed)
    """
    candidates: list[Path] = []

    key_path_env = (os.getenv("APP_STORE_PRIVATE_KEY_PATH") or "").strip()
    if key_path_env:
        candidates.append(ROOT / key_path_env)

    if KEY_ID:
        candidates.append(ROOT / "keys" / f"AuthKey_{KEY_ID}.p8")

    for path in candidates:
        if path.exists():
            print(f"  Private key:  {path.relative_to(ROOT)}")
            return path.read_text().strip()

    inline = (os.getenv("APP_STORE_PRIVATE_KEY") or "").strip()
    if inline:
        print("  Private key:  APP_STORE_PRIVATE_KEY (inline from .env)")
        return _fix_inline_pem(inline)

    raise FileNotFoundError(
        "No App Store private key found.\n"
        "Set APP_STORE_PRIVATE_KEY_PATH or APP_STORE_PRIVATE_KEY in .env, "
        "or place the key at keys/AuthKey_{KEY_ID}.p8"
    )

# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
def _abort(msg: str) -> None:
    print(f"\nERROR: {msg}", file=sys.stderr)
    sys.exit(1)

missing = [name for name, val in [
    ("APP_STORE_KEY_ID", KEY_ID),
    ("APP_STORE_ISSUER_ID", ISSUER_ID),
    ("APP_STORE_BUNDLE_ID", BUNDLE_ID),
] if not val]
if missing:
    _abort(f"missing .env vars: {', '.join(missing)}")

if not ORIGINAL_TX_ID:
    _abort(
        "supply the original transaction ID:\n"
        "  .venv/bin/python get_signed_jws_apple.sh <original_transaction_id>\n"
        "  OR set BILLING_TEST_ORIGINAL_TRANSACTION_ID in .env"
    )

# ---------------------------------------------------------------------------
# Check deps
# ---------------------------------------------------------------------------
try:
    import jwt
except ImportError:
    _abort("PyJWT not installed — run: .venv/bin/python -m pip install PyJWT cryptography")

try:
    import requests
except ImportError:
    _abort("requests not installed — run: .venv/bin/python -m pip install requests")

# ---------------------------------------------------------------------------
# Build App Store Connect API JWT
# ---------------------------------------------------------------------------
private_key = _load_private_key()

env_label = "sandbox" if USE_SANDBOX else "production"
base_url = (
    "https://api.storekit-sandbox.itunes.apple.com"
    if USE_SANDBOX
    else "https://api.storekit.itunes.apple.com"
)

print(f"\nFetching transaction history ({env_label})")
print(f"  Issuer ID:    {ISSUER_ID}")
print(f"  Key ID:       {KEY_ID}")
print(f"  Bundle ID:    {BUNDLE_ID}")
print(f"  Original TX:  {ORIGINAL_TX_ID}")

now = int(time.time())
api_jwt = jwt.encode(
    {
        "iss": ISSUER_ID,
        "iat": now,
        "exp": now + 3600,
        "aud": "appstoreconnect-v1",
        "bid": BUNDLE_ID,
    },
    private_key,
    algorithm="ES256",
    headers={"kid": KEY_ID, "alg": "ES256"},
)

# ---------------------------------------------------------------------------
# Call Apple API
# ---------------------------------------------------------------------------
url = f"{base_url}/inApps/v1/history/{ORIGINAL_TX_ID}"
resp = requests.get(
    url,
    headers={"Authorization": f"Bearer {api_jwt}"},
    timeout=15,
)

if not resp.ok:
    print(f"\nERROR: Apple API → HTTP {resp.status_code}", file=sys.stderr)
    try:
        print(resp.json(), file=sys.stderr)
    except Exception:
        print(resp.text, file=sys.stderr)
    sys.exit(1)

data = resp.json()
signed_txns = data.get("signedTransactions", [])
if not signed_txns:
    _abort(f"No signedTransactions in response:\n{data}")

# Most recent transaction is last in the list
jws = signed_txns[-1]

# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------
print(f"\nFound {len(signed_txns)} signedTransaction(s) — using most recent.\n")
print("=" * 72)
print(jws)
print("=" * 72)
print("\nCopy into .env:")
print(f"  BILLING_TEST_SANDBOX_JWS={jws}")
print("\nOr export for smoke scripts:")
print(f"  export BILLING_TEST_SANDBOX_JWS='{jws}'")
