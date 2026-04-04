"""
Enforce vertical spacing from a line-oriented .template file on plain-text cover
letter content before DOCX generation.

The DOCX plain-text path treats \\n\\n as paragraph breaks and single \\n as soft
line breaks inside one paragraph. LLM output often uses only single newlines, so
blank lines from the template disappear. This module rebuilds the letter using
the template's empty-line counts between non-empty template rows.
"""

from __future__ import annotations

import logging
import re
from typing import List, Optional

logger = logging.getLogger(__name__)


def _normalize_newlines(text: str) -> str:
    return (text or "").replace("\r\n", "\n").replace("\r", "\n")


def _blanks_between_nonempty_template_lines(template: str) -> List[int]:
    lines = _normalize_newlines(template).split("\n")
    indices = [i for i, line in enumerate(lines) if line.strip()]
    if len(indices) < 2:
        return []
    return [indices[i + 1] - indices[i] - 1 for i in range(len(indices) - 1)]


def enforce_plain_text_line_spacing_from_template(
    content: str,
    template: str,
) -> str:
    """
    Re-space plain text so blank-line runs match the template file layout.

    Parses the template's non-empty lines in order, finds <<body paragraphs>>,
    and assumes the LLM output has the same logical order: header lines, body
    (possibly multiple lines/paragraphs), footer lines. If the structure cannot
    be inferred safely, returns ``content`` unchanged.
    """
    content = _normalize_newlines(content)
    template = _normalize_newlines(template)
    if not content.strip() or not template.strip():
        return content

    t_lines = template.split("\n")
    nonempty_template = [line.strip() for line in t_lines if line.strip()]
    if not nonempty_template:
        return content

    body_ph_re = re.compile(r"<<\s*body\s+paragraphs\s*>>", re.IGNORECASE)
    body_idx: Optional[int] = None
    for i, line in enumerate(nonempty_template):
        if body_ph_re.search(line):
            body_idx = i
            break
    if body_idx is None:
        return content

    footer_slots = nonempty_template[body_idx + 1 :]
    num_header = body_idx
    num_footer = len(footer_slots)
    if num_header < 1 or num_footer < 1:
        return content

    gaps = _blanks_between_nonempty_template_lines(template)
    if len(gaps) != len(nonempty_template) - 1:
        logger.debug(
            "template_plain_text_spacing: gap count mismatch (gaps=%s nonempty=%s)",
            len(gaps),
            len(nonempty_template),
        )
        return content

    lines = content.split("\n")
    nonempty_indices = [i for i, line in enumerate(lines) if line.strip()]
    if len(nonempty_indices) < num_header + num_footer + 1:
        return content

    body_start_line = nonempty_indices[num_header]
    footer_start_line = nonempty_indices[-num_footer]
    if body_start_line >= footer_start_line:
        return content

    header_nonempty = [lines[i].strip() for i in nonempty_indices[:num_header]]
    footer_nonempty = [lines[i].strip() for i in nonempty_indices[-num_footer:]]
    body_lines = lines[body_start_line:footer_start_line]

    out: List[str] = []
    for i in range(num_header):
        out.append(header_nonempty[i])
        if i < num_header - 1:
            out.extend([""] * gaps[i])
    out.extend([""] * gaps[num_header - 1])
    out.extend(body_lines)
    out.extend([""] * gaps[num_header])
    for j in range(num_footer):
        out.append(footer_nonempty[j])
        if j < num_footer - 1:
            out.extend([""] * gaps[num_header + j + 1])

    return "\n".join(out)
