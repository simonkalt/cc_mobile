#!/usr/bin/env python3
"""Report distinct preferences.appSettings.selectedModel values; flag retired OpenAI IDs."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.env_loader import load_project_env
from app.utils.llm_token_limits import RETIRED_OPENAI_MODEL_IDS

load_project_env(PROJECT_ROOT)

from app.db.mongodb import connect_to_mongodb, get_database  # noqa: E402

FIELD = "preferences.appSettings.selectedModel"
MOBILE_ALIASES = frozenset({"gpt-5.6-sol", "gpt-5.6-luna"})


def main() -> int:
    if not connect_to_mongodb():
        print("ERROR: Could not connect to MongoDB.", file=sys.stderr)
        return 1

    db = get_database()
    pipeline = [
        {"$match": {FIELD: {"$exists": True, "$nin": [None, ""]}}},
        {"$group": {"_id": f"${FIELD}", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    rows = list(db["users"].aggregate(pipeline))
    print(f"Distinct {FIELD} values: {len(rows)}\n")
    retired = set(RETIRED_OPENAI_MODEL_IDS)
    flagged = []
    for row in rows:
        model = row["_id"]
        count = row["count"]
        key = (model or "").strip().lower()
        mark = ""
        if key in retired:
            mark = "  RETIRED"
            flagged.append((model, count))
        elif key in MOBILE_ALIASES:
            mark = "  (alias → gpt-6.2-sol after deploy)"
        print(f"  {count:6d}  {model!r}{mark}")

    if flagged:
        print(f"\n{len(flagged)} value(s) match retiring OpenAI API IDs.")
        return 2
    print("\nNo retired OpenAI model IDs found in selectedModel.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())