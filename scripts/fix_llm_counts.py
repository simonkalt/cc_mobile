#!/usr/bin/env python3
"""
Flatten corrupted llm_counts entries in MongoDB user documents.

MongoDB dot-notation caused model names containing dots (e.g. "gpt-4.1",
"gemini-2.5-flash") to be stored as nested objects instead of flat
integer counts.  This script reconstructs the original model names,
re-normalizes them to canonical forms, and writes back a clean flat dict.

Usage:
    python scripts/fix_llm_counts.py              # dry-run (default)
    python scripts/fix_llm_counts.py --apply       # write changes
"""

import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app.core.env_loader import load_project_env

load_project_env(PROJECT_ROOT)

from app.db.mongodb import connect_to_mongodb, get_database
from app.utils.llm_utils import normalize_llm_name

USERS_COLLECTION = "users"


def flatten_llm_counts(llm_counts: dict) -> dict:
    """
    Walk llm_counts and flatten any nested-object values back into
    dotted model names with integer counts.  Then re-normalize every
    key through normalize_llm_name() and merge duplicates by summing.
    """
    raw_flat: dict[str, int] = {}

    for key, value in llm_counts.items():
        if isinstance(value, (int, float)):
            raw_flat[key] = int(value)
        elif isinstance(value, dict):
            for sub_key, sub_value in value.items():
                reconstructed = f"{key}.{sub_key}"
                if isinstance(sub_value, (int, float)):
                    raw_flat[reconstructed] = raw_flat.get(reconstructed, 0) + int(sub_value)
                elif isinstance(sub_value, dict):
                    for sub2_key, sub2_value in sub_value.items():
                        reconstructed2 = f"{key}.{sub_key}.{sub2_key}"
                        if isinstance(sub2_value, (int, float)):
                            raw_flat[reconstructed2] = raw_flat.get(reconstructed2, 0) + int(sub2_value)

    normalized: dict[str, int] = {}
    for name, count in raw_flat.items():
        canonical = normalize_llm_name(name)
        normalized[canonical] = normalized.get(canonical, 0) + count

    return normalized


def needs_fix(llm_counts: dict) -> bool:
    """Return True if any value in llm_counts is a dict (nested)."""
    return any(isinstance(v, dict) for v in llm_counts.values())


def main():
    parser = argparse.ArgumentParser(description="Flatten corrupted llm_counts in user documents")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    args = parser.parse_args()

    if not connect_to_mongodb():
        print("ERROR: Could not connect to MongoDB. Check MONGODB_URI.", file=sys.stderr)
        sys.exit(1)

    db = get_database()
    collection = db[USERS_COLLECTION]

    users_cursor = collection.find(
        {"llm_counts": {"$exists": True}},
        {"_id": 1, "email": 1, "llm_counts": 1},
    )

    fixed = 0
    skipped = 0
    errors = 0

    for user in users_cursor:
        uid = user["_id"]
        email = user.get("email", "(no email)")
        llm_counts = user.get("llm_counts", {})

        if not isinstance(llm_counts, dict) or not needs_fix(llm_counts):
            skipped += 1
            continue

        try:
            cleaned = flatten_llm_counts(llm_counts)
        except Exception as exc:
            print(f"  ERROR processing {uid} ({email}): {exc}")
            errors += 1
            continue

        print(f"\n  User: {uid} ({email})")
        print(f"    BEFORE: {llm_counts}")
        print(f"    AFTER:  {cleaned}")

        if args.apply:
            collection.update_one({"_id": uid}, {"$set": {"llm_counts": cleaned}})
            print("    -> WRITTEN")
        else:
            print("    -> DRY-RUN (use --apply to write)")

        fixed += 1

    mode = "APPLIED" if args.apply else "DRY-RUN"
    print(f"\nDone ({mode}). Fixed: {fixed}, Skipped (already clean): {skipped}, Errors: {errors}")


if __name__ == "__main__":
    main()
