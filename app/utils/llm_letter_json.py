"""
Parse and repair LLM cover-letter JSON payloads.

Some models (notably Claude Opus) close {"content": "..."} by writing a literal
quote + } into the letter body, or by escaping that closer so it parses as text.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_LEAKED_JSON_CLOSER_RE = re.compile(
    r'\\?["\u201c\u201d](?:\s|\\[nrt])*\}(?:\s|\\[nrt])*$'
)


def _rewrite_json_quoted_value_escaping_unescaped_control_chars(
    s: str, value_start: int
) -> Tuple[str, int, bool]:
    """
    Walk a JSON string value from the first char after the opening quote, copying
    valid \\-escapes as-is, and replacing unescaped U+00–U+1F (including bare
    newlines) with JSON \\n / \\r / \\t / \\u00xx. Returns
    (escaped_string_body, index_after_closing_double_quote, did_change). If the
    string is not closed, ends at len(s) with did_change True when controls were fixed.
    """
    i = value_start
    out: List[str] = []
    did_change = False
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            out.append(s[i])
            out.append(s[i + 1])
            i += 2
            continue
        if c == '"':
            return ("".join(out), i + 1, did_change)
        o = ord(c)
        if o < 0x20:
            did_change = True
            if c == "\n":
                out.append("\\n")
            elif c == "\r":
                out.append("\\r")
            elif c == "\t":
                out.append("\\t")
            else:
                out.append(f"\\u{o:04x}")
        else:
            out.append(c)
        i += 1
    return ("".join(out), len(s), did_change)


def strip_leaked_json_wrapper(text: str) -> str:
    """Remove a trailing JSON string/object closer that leaked into letter text."""
    if not text:
        return text
    updated, n = _LEAKED_JSON_CLOSER_RE.subn("", text)
    if n:
        logger.info("Removed leaked JSON closing quote/brace from LLM letter field")
        return updated.rstrip()
    return text


def _sanitize_parsed_letter_fields(json_r: Dict[str, Any]) -> Dict[str, Any]:
    for key in ("content", "markdown", "html"):
        val = json_r.get(key)
        if isinstance(val, str):
            json_r[key] = strip_leaked_json_wrapper(val)
    return json_r


def _recover_quoted_field(json_str: str, field: str) -> Optional[str]:
    """Take text after `"field": "` and drop a leaked JSON closer if present."""
    match = re.search(rf'"{re.escape(field)}"\s*:\s*"', json_str)
    if not match:
        return None
    return strip_leaked_json_wrapper(json_str[match.end() :])


def parse_llm_response_json(response_text: str) -> Dict[str, Any]:
    """Parse the LLM's JSON payload, repairing common malformations."""
    r = (response_text or "").replace("```json", "").replace("```", "").strip()
    start_idx = r.find("{")
    end_idx = r.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = r[start_idx : end_idx + 1]
    else:
        json_str = r

    try:
        json_r = json.loads(json_str)
        logger.info("JSON parse of LLM response succeeded")
    except json.JSONDecodeError as e:
        logger.warning(f"Initial JSON parse failed: {e}, attempting to fix...")
        json_r = _repair_llm_response_json(json_str, e)
        if json_r is None:
            logger.warning("JSON parse still failed after all fix attempts; re-raising error")
            raise

    if not isinstance(json_r, dict):
        raise json.JSONDecodeError("LLM response JSON must be an object", json_str, 0)
    return _sanitize_parsed_letter_fields(json_r)


def _repair_llm_response_json(
    json_str: str, _e: json.JSONDecodeError
) -> Optional[Dict[str, Any]]:
    """Best-effort repair when json.loads fails on an LLM cover-letter payload."""
    repaired = _try_repair_json_unescaped_string_controls(json_str)
    json_r: Optional[Dict[str, Any]] = None
    if repaired is not None:
        try:
            json_r = json.loads(repaired)
            logger.info("JSON parse succeeded after re-escaping unescaped string controls")
        except json.JSONDecodeError as e0:
            logger.debug(f"Control-char repair not sufficient: {e0}")
            json_r = None

    if json_r is None:
        brace_count = 0
        last_valid_end = -1
        for i, char in enumerate(json_str):
            if char == "{":
                brace_count += 1
            elif char == "}":
                brace_count -= 1
                if brace_count == 0:
                    last_valid_end = i
                    break

        if last_valid_end > 0:
            try:
                json_r = json.loads(json_str[: last_valid_end + 1])
                logger.info("Successfully fixed truncated JSON (balanced braces)")
            except json.JSONDecodeError:
                json_r = None

    if json_r is None:
        raw_content = _recover_quoted_field(json_str, "content")
        if raw_content is not None:
            escaped = (
                raw_content.replace("\\", "\\\\")
                .replace('"', '\\"')
                .replace("\n", "\\n")
                .replace("\r", "\\r")
            )
            try:
                json_r = json.loads('{"content": "' + escaped + '"}')
                logger.info("Recovered from unterminated string: using content")
            except json.JSONDecodeError:
                json_r = None
        if json_r is None:
            raw_markdown = _recover_quoted_field(json_str, "markdown")
            if raw_markdown is not None:
                escaped = (
                    raw_markdown.replace("\\", "\\\\")
                    .replace('"', '\\"')
                    .replace("\n", "\\n")
                    .replace("\r", "\\r")
                )
                try:
                    json_r = json.loads('{"markdown": "' + escaped + '", "html": ""}')
                    logger.info(
                        "Recovered from unterminated string: using markdown content, html empty"
                    )
                except json.JSONDecodeError:
                    json_r = None

    return json_r


def _try_repair_json_unescaped_string_controls(json_str: str) -> Optional[str]:
    """
    Re-encode known top-level string fields when the model broke JSON with literal
    line breaks or unescaped control characters inside quoted values.
    """
    t = json_str
    for _ in range(8):
        before = t
        for key in ("content", "markdown", "html"):
            m = re.search(rf'"{re.escape(key)}"\s*:\s*"', t)
            if not m:
                continue
            value_start = m.end()
            escaped, end_idx, did_change = (
                _rewrite_json_quoted_value_escaping_unescaped_control_chars(t, value_start)
            )
            # Unterminated value: model often wrote \" then } as if closing JSON.
            if end_idx >= len(t):
                peeled, n = re.subn(r'\\"(?:\\[nrt]|\s)*\}\s*$', "", escaped)
                if n:
                    escaped = peeled
                    did_change = True
                    t = t[:value_start] + escaped + '"}'
                    continue
            if not did_change:
                continue
            t = t[:value_start] + escaped + '"' + t[end_idx:]
            if not t.rstrip().endswith("}"):
                t = t.rstrip() + "}"
        if t == before:
            break
    if t == json_str:
        return None
    return t
