#!/usr/bin/env python3
"""
Clear backend cache keys and local debug cache artifacts.

Default behavior:
- Redis: delete keys matching "cache:*"
- Local files: delete known cache/debug files under ./tmp

Optional:
- --include-verification: also delete Redis registration/verification keys
- --flushdb: flush the selected Redis DB (dangerous)
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Iterable


def _iter_redis_patterns(include_verification: bool) -> list[str]:
    patterns = ["cache:*"]
    if include_verification:
        patterns.extend(["registration:*", "verification:*"])
    return patterns


def _delete_redis_keys(patterns: Iterable[str], flushdb: bool) -> tuple[int, list[str]]:
    deleted = 0
    notes: list[str] = []
    try:
        from app.utils.redis_utils import get_redis_client
    except Exception as exc:
        notes.append(f"Redis utilities unavailable: {exc}")
        return deleted, notes

    try:
        client = get_redis_client()
    except Exception as exc:
        notes.append(f"Redis not reachable: {exc}")
        return deleted, notes

    if flushdb:
        try:
            client.flushdb()
            notes.append("Redis DB flushed.")
            return -1, notes
        except Exception as exc:
            notes.append(f"Failed to flush Redis DB: {exc}")
            return deleted, notes

    for pattern in patterns:
        try:
            keys = list(client.scan_iter(match=pattern, count=500))
        except Exception as exc:
            notes.append(f"Failed scanning '{pattern}': {exc}")
            continue

        if not keys:
            notes.append(f"No keys matched '{pattern}'.")
            continue

        # Delete in chunks to avoid giant command payloads.
        chunk_size = 500
        for i in range(0, len(keys), chunk_size):
            chunk = keys[i : i + chunk_size]
            try:
                deleted += int(client.delete(*chunk))
            except Exception as exc:
                notes.append(f"Failed deleting chunk for '{pattern}': {exc}")
                break
        notes.append(f"Deleted {len(keys)} key(s) matching '{pattern}'.")

    return deleted, notes


def _delete_local_tmp_cache_files(project_root: Path) -> tuple[int, list[str]]:
    removed = 0
    notes: list[str] = []
    tmp_dir = project_root / "tmp"
    if not tmp_dir.exists():
        notes.append("No ./tmp directory found.")
        return removed, notes

    candidates = [
        "llm_prompt_sent.txt",
        "llm_response_received.txt",
        "debug_additional_instructions.txt",
        "client_payload_sent.txt",
        "raw-debug.docx",
        "raw-debug-info.txt",
    ]
    for name in candidates:
        p = tmp_dir / name
        if not p.exists():
            continue
        try:
            p.unlink()
            removed += 1
        except Exception as exc:
            notes.append(f"Failed removing {p}: {exc}")

    if removed == 0:
        notes.append("No local tmp cache/debug files removed.")
    else:
        notes.append(f"Removed {removed} local tmp cache/debug file(s).")
    return removed, notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Clear Redis/local cache artifacts.")
    parser.add_argument(
        "--include-verification",
        action="store_true",
        help="Also clear Redis registration:* and verification:* keys.",
    )
    parser.add_argument(
        "--flushdb",
        action="store_true",
        help="Flush the configured Redis DB (dangerous).",
    )
    args = parser.parse_args()

    project_root = Path(__file__).resolve().parent

    patterns = _iter_redis_patterns(args.include_verification)
    redis_deleted, redis_notes = _delete_redis_keys(patterns, args.flushdb)
    local_removed, local_notes = _delete_local_tmp_cache_files(project_root)

    print("Cache clear summary")
    print("===================")
    if redis_deleted == -1:
        print("Redis: flushed selected DB")
    else:
        print(f"Redis keys deleted: {redis_deleted}")
    print(f"Local tmp files removed: {local_removed}")

    for note in redis_notes + local_notes:
        print(f"- {note}")

    if redis_deleted == 0 and local_removed == 0 and not args.flushdb:
        print("\nNothing to clear.")
    else:
        print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

