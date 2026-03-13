#!/usr/bin/env python3
"""
Branch parity audit for cc_mobile.

Generates a markdown report comparing two git refs:
- commit divergence
- critical file presence by directory
- route decorator parity
- env var reference parity
"""

from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Iterable


ROUTE_RE = re.compile(
    r"@(?:app|router)\.(get|post|put|delete|patch|options|head)\(\s*[\"']([^\"']+)[\"']"
)
ENV_RE = re.compile(r"os\.getenv\(\s*[\"']([A-Z0-9_]+)[\"']")
INCLUDE_ROUTER_RE = re.compile(r"app\.include_router\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\.router\s*\)")

NOISE_PATTERNS = (
    ".DS_Store",
    "__pycache__/",
    ".pyc",
)

CRITICAL_DIRS = (
    "app/api/routers",
    "app/models",
    "app/services",
    "app/utils",
    "templates",
    "website",
    "documents",
)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True, errors="ignore")


def parse_name_status(raw: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split("\t")
        status = parts[0]
        path = parts[-1]
        rows.append((status, path))
    return rows


def not_noise(path: str) -> bool:
    return not any(token in path for token in NOISE_PATTERNS)


def ls_tree(repo: Path, ref: str, path: str) -> set[str]:
    out = git(repo, "ls-tree", "-r", "--name-only", ref, "--", path)
    return {line.strip() for line in out.splitlines() if line.strip()}


def show_file(repo: Path, ref: str, path: str) -> str:
    try:
        return git(repo, "show", f"{ref}:{path}")
    except subprocess.CalledProcessError:
        return ""


def get_py_files(repo: Path, ref: str, path: str) -> Iterable[str]:
    out = git(repo, "ls-tree", "-r", "--name-only", ref, "--", path)
    for line in out.splitlines():
        p = line.strip()
        if p.endswith(".py"):
            yield p


def collect_routes(repo: Path, ref: str) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for p in list(get_py_files(repo, ref, "app/api/routers")) + ["main.py"]:
        text = show_file(repo, ref, p)
        if not text:
            continue
        for m in ROUTE_RE.finditer(text):
            routes.add((m.group(1).upper(), m.group(2)))
    return routes


def collect_env_keys(repo: Path, ref: str) -> set[str]:
    keys: set[str] = set()
    for p in list(get_py_files(repo, ref, "app")) + ["main.py"]:
        text = show_file(repo, ref, p)
        if not text:
            continue
        keys.update(ENV_RE.findall(text))
    return keys


def collect_registered_routers(repo: Path, ref: str) -> set[str]:
    """
    Collect router module names actually registered via app.include_router(<name>.router)
    from main.py. This catches gaps where routes exist in files but are not wired.
    """
    text = show_file(repo, ref, "main.py")
    if not text:
        return set()
    return {m.group(1) for m in INCLUDE_ROUTER_RE.finditer(text)}


def build_report(repo: Path, source: str, target: str) -> str:
    left_right = git(repo, "rev-list", "--left-right", "--count", f"{source}...{target}").strip()
    source_ahead, target_ahead = left_right.split()

    diff_raw = git(repo, "diff", "--name-status", f"{source}...{target}")
    all_changes = parse_name_status(diff_raw)
    filtered_changes = [(s, p) for s, p in all_changes if not_noise(p)]

    section_lines: list[str] = []
    section_lines.append(f"# Branch Parity Audit")
    section_lines.append("")
    section_lines.append(f"- Source ref: `{source}`")
    section_lines.append(f"- Target ref: `{target}`")
    section_lines.append(f"- Divergence: source ahead `{source_ahead}`, target ahead `{target_ahead}`")
    section_lines.append("")

    section_lines.append("## File Change Overview (noise-filtered)")
    section_lines.append(f"- Total changed paths: `{len(all_changes)}`")
    section_lines.append(f"- Noise-filtered paths: `{len(filtered_changes)}`")
    section_lines.append("")
    for status, path in filtered_changes[:120]:
        section_lines.append(f"- `{status}` `{path}`")
    if len(filtered_changes) > 120:
        section_lines.append(f"- ... plus `{len(filtered_changes) - 120}` more")
    section_lines.append("")

    section_lines.append("## Critical Directory Presence")
    section_lines.append("")
    for d in CRITICAL_DIRS:
        s = ls_tree(repo, source, d)
        t = ls_tree(repo, target, d)
        missing_in_source = sorted(t - s)
        section_lines.append(
            f"- `{d}`: missing in source `{len(missing_in_source)}`"
        )
        for p in missing_in_source[:25]:
            section_lines.append(f"  - `{p}`")
        if len(missing_in_source) > 25:
            section_lines.append(f"  - ... plus `{len(missing_in_source) - 25}` more")
    section_lines.append("")

    source_routes = collect_routes(repo, source)
    target_routes = collect_routes(repo, target)
    missing_routes = sorted(target_routes - source_routes)
    section_lines.append("## Route Parity")
    section_lines.append(f"- Source routes: `{len(source_routes)}`")
    section_lines.append(f"- Target routes: `{len(target_routes)}`")
    section_lines.append(f"- Missing in source: `{len(missing_routes)}`")
    for method, route in missing_routes:
        section_lines.append(f"- `{method} {route}`")
    section_lines.append("")

    source_routers = collect_registered_routers(repo, source)
    target_routers = collect_registered_routers(repo, target)
    missing_routers = sorted(target_routers - source_routers)
    section_lines.append("## Router Registration Parity (main.py)")
    section_lines.append(f"- Source registered routers: `{len(source_routers)}`")
    section_lines.append(f"- Target registered routers: `{len(target_routers)}`")
    section_lines.append(f"- Missing in source: `{len(missing_routers)}`")
    for router in missing_routers:
        section_lines.append(f"- `{router}`")
    section_lines.append("")

    source_env = collect_env_keys(repo, source)
    target_env = collect_env_keys(repo, target)
    missing_env = sorted(target_env - source_env)
    section_lines.append("## Environment Key Parity (os.getenv)")
    section_lines.append(f"- Missing in source: `{len(missing_env)}`")
    for key in missing_env:
        section_lines.append(f"- `{key}`")
    section_lines.append("")

    return "\n".join(section_lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate branch parity audit markdown")
    parser.add_argument("--repo", default=".", help="Path to git repository")
    parser.add_argument("--source", default="origin/UAT", help="Source ref to audit")
    parser.add_argument(
        "--target",
        default="origin/MS-Word-Integration",
        help="Target ref considered known-good",
    )
    parser.add_argument(
        "--out",
        default="documentation/BRANCH_PARITY_AUDIT.md",
        help="Output markdown path (relative to repo)",
    )
    args = parser.parse_args()

    repo = Path(args.repo).resolve()
    report = build_report(repo, args.source, args.target)
    out_path = (repo / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"Wrote parity report: {out_path}")


if __name__ == "__main__":
    main()
