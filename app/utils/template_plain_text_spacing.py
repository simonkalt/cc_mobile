"""
Minimal plain-text normalization before DOCX generation.

The DOCX builder maps each input line (including blank lines) 1:1 to a Word
paragraph with zero extra spacing, so the LLM's newlines directly control
vertical layout.  The only post-processing that remains here is:

* List compaction  – remove blank lines between consecutive bullet/number items.
* Triple-newline collapse – safety net for non-template letters where the LLM
  occasionally emits excessive blank lines.
"""

from __future__ import annotations

import re
from typing import List, Optional


def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _collapse_triple_newlines_in_plain_text(text: str) -> str:
    """Collapse runs of three or more newlines to exactly two (one blank line)."""
    return re.sub(r"\n{3,}", "\n\n", _normalize_newlines(text))


def _is_plain_text_list_line(line: str) -> bool:
    """Match bullet/number list lines (aligned with docx_generator list detection)."""
    if not line or not line.strip():
        return False
    if re.match(r"^\s*(?:\(?[1-9]\d?\)?[.)])\s+", line):
        return True
    if re.match(r"^\s*(?:[•◦▪▸\-\*\+])\s+", line):
        return True
    return False


def compact_blank_lines_between_consecutive_list_lines(lines: List[str]) -> List[str]:
    """
    Drop blank lines between two consecutive list items so bullets/numbers pack tightly.
    Paragraph-to-list spacing (non-list followed by list) is unchanged.
    """
    out: List[str] = []
    for i, line in enumerate(lines):
        if not line.strip():
            prev_text = None
            for j in range(i - 1, -1, -1):
                if lines[j].strip():
                    prev_text = lines[j]
                    break
            next_text = None
            for j in range(i + 1, len(lines)):
                if lines[j].strip():
                    next_text = lines[j]
                    break
            if (
                prev_text
                and next_text
                and _is_plain_text_list_line(prev_text)
                and _is_plain_text_list_line(next_text)
            ):
                continue
        out.append(line)
    return out


def finalize_plain_text_for_docx(content: str, template: Optional[str]) -> str:
    """
    Last pass on plain-text cover letter before DOCX build.

    When a template is present the LLM is trusted to produce the correct spacing;
    only list compaction runs.  Without a template, excessive blank-line runs
    (3+ newlines) are collapsed as a safety net.
    """
    text = _normalize_newlines(content or "")
    if not text.strip():
        return text
    if not (template and template.strip()):
        text = _collapse_triple_newlines_in_plain_text(text)
    lines = compact_blank_lines_between_consecutive_list_lines(text.split("\n"))
    return "\n".join(lines)
