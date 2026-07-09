#!/usr/bin/env python3
"""
Interactive OpenRouter / LLM smoke test.

Pick a model from llm-models-registry.json, type a prompt, print the reply.

Usage:
    python scripts/test_openrouter_prompt.py
    python scripts/test_openrouter_prompt.py --model claude-haiku-4-5 --prompt "Say hello"
    python scripts/test_openrouter_prompt.py -m gpt-5.5 -p "What is 2+2?"

Requires OPENROUTER_API_KEY in .secrets (or LLM_PROVIDER=direct + provider keys).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import settings
from app.utils.llm_utils import post_to_llm
from app.utils.openrouter_client import (
    openrouter_configured,
    to_openrouter_model,
    use_openrouter,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_registry_models() -> list[dict]:
    path = settings.LLM_MODELS_REGISTRY_PATH
    if not path.is_file():
        raise FileNotFoundError(f"Model registry not found: {path}")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    models = data.get("models") or []
    if not models:
        raise ValueError(f"No models listed in {path}")
    return models


def default_model_name(models: list[dict]) -> str:
    for m in models:
        if m.get("default"):
            return m["name"]
    return models[0]["name"]


def print_provider_status() -> None:
    provider = settings.LLM_PROVIDER
    or_ok = openrouter_configured()
    print()
    print(f"  LLM_PROVIDER     : {provider}")
    print(f"  OpenRouter ready : {or_ok}")
    if use_openrouter() and not or_ok:
        print("  WARNING: openrouter selected but OPENROUTER_API_KEY is missing.")
        print("           Will fall back to direct provider keys if present.")
    print()


def choose_model(models: list[dict], preselect: str | None = None) -> str:
    names = [m["name"] for m in models]
    if preselect:
        if preselect not in names:
            print(f"Unknown model {preselect!r}. Choose from: {', '.join(names)}")
            sys.exit(1)
        return preselect

    default = default_model_name(models)
    print("Available models:")
    for i, m in enumerate(models, start=1):
        marker = " (default)" if m.get("default") else ""
        slug = ""
        try:
            slug = f"  →  {to_openrouter_model(m['name'])}"
        except ValueError:
            slug = "  →  (no OpenRouter mapping)"
        print(f"  {i}. {m['name']}{marker}{slug}")
    print()

    while True:
        raw = input(f"Select model [1-{len(models)}] (Enter = {default}): ").strip()
        if not raw:
            return default
        if raw in names:
            return raw
        if raw.isdigit():
            idx = int(raw)
            if 1 <= idx <= len(models):
                return models[idx - 1]["name"]
        print("Invalid choice. Enter a number or exact model name.")


def read_prompt(preselect: str | None = None) -> str:
    if preselect is not None:
        text = preselect.strip()
        if not text:
            print("Prompt is empty.")
            sys.exit(1)
        return text

    print("Enter prompt (end with a blank line, or Ctrl-D):")
    lines: list[str] = []
    try:
        while True:
            line = input()
            if line == "" and lines:
                break
            lines.append(line)
    except EOFError:
        pass

    text = "\n".join(lines).strip()
    if not text:
        print("Prompt is empty.")
        sys.exit(1)
    return text


def run_once(model: str, prompt: str) -> int:
    print()
    print("=" * 72)
    print(f"Model  : {model}")
    if use_openrouter() and openrouter_configured():
        try:
            print(f"Route  : OpenRouter ({to_openrouter_model(model)})")
        except ValueError as e:
            print(f"Route  : OpenRouter (mapping error: {e})")
    else:
        print("Route  : direct providers / shared post_to_llm")
    print(f"Prompt : {prompt[:200]}{'…' if len(prompt) > 200 else ''}")
    print("=" * 72)
    print()

    started = time.perf_counter()
    try:
        response = post_to_llm(prompt, model)
    except Exception as exc:
        logger.exception("LLM call failed: %s", exc)
        return 1
    elapsed = time.perf_counter() - started

    if response is None:
        print("No response (None). Check API keys / provider logs.")
        return 1

    print(response)
    print()
    print("-" * 72)
    print(f"Done in {elapsed:.2f}s  ({len(response)} characters)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactive OpenRouter LLM prompt test")
    parser.add_argument("-m", "--model", help="App model id (e.g. claude-haiku-4-5)")
    parser.add_argument("-p", "--prompt", help="Prompt text (skips interactive prompt entry)")
    parser.add_argument(
        "--loop",
        action="store_true",
        help="After each reply, ask for another prompt (same model)",
    )
    args = parser.parse_args()

    try:
        models = load_registry_models()
    except Exception as exc:
        print(f"Failed to load model registry: {exc}")
        return 1

    print_provider_status()
    model = choose_model(models, args.model)

    if args.prompt is not None and not args.loop:
        return run_once(model, args.prompt)

    first_prompt = args.prompt
    while True:
        prompt = read_prompt(first_prompt)
        first_prompt = None
        code = run_once(model, prompt)
        if code != 0:
            return code
        if not args.loop and args.prompt is not None:
            return 0
        if not args.loop:
            again = input("Send another prompt with this model? [y/N]: ").strip().lower()
            if again not in ("y", "yes"):
                return 0
        print()


if __name__ == "__main__":
    raise SystemExit(main())
