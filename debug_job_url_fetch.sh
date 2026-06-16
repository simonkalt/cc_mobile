#!/usr/bin/env bash
# Run debug_job_url_fetch.py from repo root (creates .venv if needed).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
VENV="$ROOT/.venv"

if [[ ! -d "$VENV" ]]; then
  echo "Creating .venv and installing requirements..."
  python3 -m venv "$VENV"
  "$VENV/bin/pip" install -q -r requirements.txt
fi

exec "$VENV/bin/python" "$ROOT/debug_job_url_fetch.py" "$@"
