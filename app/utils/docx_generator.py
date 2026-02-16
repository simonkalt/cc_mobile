"""
Generate a .docx (Word) document from cover letter content (markdown or HTML).

Used so the server can return a fully adorned .docx to the client for editing;
print preview then uses POST /api/files/docx-to-pdf with that (possibly edited) .docx.
"""

import io
import logging
import re
from typing import Dict, Optional

logger = logging.getLogger(__name__)

try:
    from docx import Document
    from docx.shared import Pt

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    Document = None


def _html_to_plain_paragraphs(html: str) -> list:
    """Convert HTML to a list of paragraph texts (one string per paragraph)."""
    if not html or not html.strip():
        return [""]
    # Replace block breaks with a sentinel, then split
    text = re.sub(r"</p>\s*<p(\s[^>]*)?>", "\n\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(div|h[1-6]|li|tr)>", "\n", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r" +", " ", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paragraphs if paragraphs else [""]


def _markdown_to_plain_paragraphs(markdown: str) -> list:
    """Convert markdown to a list of paragraph texts (one string per paragraph)."""
    if not markdown or not markdown.strip():
        return [""]
    # Split on double newline for paragraphs; single newline becomes space within paragraph
    parts = re.split(r"\n\s*\n", markdown.strip())
    paragraphs = []
    for p in parts:
        line = " ".join(p.splitlines()).strip()
        if line:
            # Strip markdown bold/italic for plain docx
            line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
            line = re.sub(r"\*(.+?)\*", r"\1", line)
            line = re.sub(r"__(.+?)__", r"\1", line)
            line = re.sub(r"_(.+?)_", r"\1", line)
            paragraphs.append(line)
    return paragraphs if paragraphs else [""]


def build_docx_from_content(
    content: str,
    *,
    from_html: bool = False,
    print_properties: Optional[Dict] = None,
) -> bytes:
    """
    Build a Word .docx from cover letter content.

    Args:
        content: The cover letter body (markdown or HTML).
        from_html: If True, treat content as HTML; otherwise treat as markdown.
        print_properties: Optional dict with fontFamily, fontSize, lineHeight (for document default style).

    Returns:
        .docx file as bytes.

    Raises:
        ImportError: If python-docx is not installed.
    """
    if not DOCX_AVAILABLE or Document is None:
        raise ImportError("python-docx is not installed. Install with: pip install python-docx")

    props = print_properties or {}
    font_family = props.get("fontFamily", "Times New Roman")
    font_size_pt = props.get("fontSize", 12)
    try:
        font_size_pt = float(font_size_pt)
    except (TypeError, ValueError):
        font_size_pt = 12
    line_height = props.get("lineHeight", 1.6)
    try:
        line_height = float(line_height)
    except (TypeError, ValueError):
        line_height = 1.6

    if from_html:
        paragraphs = _html_to_plain_paragraphs(content)
    else:
        paragraphs = _markdown_to_plain_paragraphs(content)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = font_family
    style.font.size = Pt(font_size_pt)

    for para_text in paragraphs:
        p = doc.add_paragraph()
        p.paragraph_format.space_after = Pt(round(font_size_pt * line_height * 0.4))
        run = p.add_run(para_text)
        run.font.name = font_family
        run.font.size = Pt(font_size_pt)

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def build_docx_from_generation_result(
    markdown: str,
    html: Optional[str] = None,
    print_properties: Optional[Dict] = None,
) -> bytes:
    """
    Build .docx from the same content returned by cover letter generation (markdown + optional html).

    Prefers HTML if provided (matches what the user sees); otherwise uses markdown.
    """
    if html and html.strip():
        return build_docx_from_content(html, from_html=True, print_properties=print_properties)
    return build_docx_from_content(markdown or "", from_html=False, print_properties=print_properties)
