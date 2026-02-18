"""
Generate a .docx (Word) document from cover letter content (markdown or HTML).

Preserves bold, italic, and lists in the output. Used so the server can return
a fully adorned .docx to the client for editing; print preview then uses
POST /api/files/docx-to-pdf with that (possibly edited) .docx.
"""

import io
import os
import html as htmllib
import logging
import re
from html.parser import HTMLParser
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.enum.text import WD_BREAK

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False
    Document = None
    RGBColor = None
    WD_BREAK = None


def _parse_span_style(style_attr: str) -> Dict:
    """Parse style='...' into color_hex, font_size_pt, font_family (for docx runs)."""
    out = {}
    if not style_attr or not isinstance(style_attr, str):
        return out
    # color: #RRGGBB or color:#RRGGBB
    m = re.search(r"color\s*:\s*#([0-9a-fA-F]{3,8})\b", style_attr)
    if m:
        hex_val = m.group(1)
        if len(hex_val) == 3:
            hex_val = "".join(c * 2 for c in hex_val)
        if len(hex_val) >= 6:
            out["color_hex"] = "#" + hex_val[:6]
    # font-size: 14pt or font-size:14pt
    m = re.search(r"font-size\s*:\s*(\d+(?:\.\d+)?)\s*pt\b", style_attr, re.IGNORECASE)
    if m:
        try:
            out["font_size_pt"] = float(m.group(1))
        except (TypeError, ValueError):
            pass
    # font-family: 'Arial' or font-family: Arial, sans-serif
    m = re.search(r"font-family\s*:\s*['\"]?([^'\";,}]+)", style_attr, re.IGNORECASE)
    if m:
        out["font_family"] = m.group(1).strip().strip("'\"").split(",")[0].strip()
    return out


class _HTMLToBlocksParser(HTMLParser):
    """Parse HTML into blocks; each run can have text, bold, italic, color, font_size_pt, font_family."""

    def __init__(self):
        super().__init__()
        self.blocks: List[Dict] = []
        self._current_block_type = "p"
        self._current_runs: List[Dict] = []
        self._bold = 0
        self._italic = 0
        self._style_stack: List[Dict] = []  # stack of {color_hex, font_size_pt, font_family} from <span>

    def _current_style(self) -> Dict:
        if not self._style_stack:
            return {}
        return dict(self._style_stack[-1])

    def _flush_run(self, text: str):
        if not text:
            return
        # Pure: no paragraph splitting from newlines; only \n → line break within current block
        parts = (text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n")
        for i, part in enumerate(parts):
            run = {"text": part, "bold": self._bold > 0, "italic": self._italic > 0}
            run.update(self._current_style())
            self._current_runs.append(run)
            if i < len(parts) - 1:
                self._current_runs.append({"line_break": True})

    def _emit_block(self):
        if not self._current_runs:
            return
        self.blocks.append({
            "type": self._current_block_type,
            "runs": self._current_runs,
        })
        self._current_runs = []
        self._current_block_type = "p"

    def handle_starttag(self, tag: str, attrs: list):
        tag = tag.lower()
        if tag in ("p", "div", "br"):
            if tag == "br":
                # Double <br/> = paragraph break (new <w:p>); single <br/> = line break
                if self._current_runs and self._current_runs[-1].get("line_break"):
                    self._emit_block()
                else:
                    self._current_runs.append({"line_break": True})
            else:
                self._emit_block()
        elif tag in ("strong", "b"):
            self._bold += 1
        elif tag in ("em", "i"):
            self._italic += 1
        elif tag == "span":
            style_dict = {}
            for k, v in attrs:
                if k and k.lower() == "style" and v:
                    style_dict = _parse_span_style(v)
                    break
            self._style_stack.append(style_dict)
        elif tag == "li":
            self._emit_block()
            self._current_block_type = "li"
        elif tag in ("ul", "ol"):
            pass

    def handle_endtag(self, tag: str):
        tag = tag.lower()
        if tag in ("p", "div"):
            self._emit_block()
        elif tag in ("strong", "b"):
            self._bold = max(0, self._bold - 1)
        elif tag in ("em", "i"):
            self._italic = max(0, self._italic - 1)
        elif tag == "span":
            if self._style_stack:
                self._style_stack.pop()
        elif tag == "li":
            self._emit_block()
            self._current_block_type = "p"
        elif tag in ("ul", "ol"):
            pass

    def handle_data(self, data: str):
        if not data:
            return
        data = htmllib.unescape(data)
        # \n\n = new paragraph (emit block); \n = line break within paragraph
        segments = data.replace("\r\n", "\n").replace("\r", "\n").split("\n\n")
        for i, seg in enumerate(segments):
            if i > 0:
                self._emit_block()
            self._flush_run(seg)

    def get_blocks(self) -> List[Dict]:
        self._emit_block()
        return self.blocks


def _html_to_blocks(html: str) -> List[Dict]:
    """Convert HTML to a list of blocks with runs (text, bold, italic, line_break)."""
    if not html or not html.strip():
        return []
    # Keep <br/> so the parser can emit line_break runs
    parser = _HTMLToBlocksParser()
    try:
        parser.feed(html)
        return parser.get_blocks()
    except Exception as e:
        logger.warning("HTML parse failed, falling back to plain paragraphs: %s", e)
        return [{"type": "p", "runs": [{"text": re.sub(r"<[^>]+>", "", html), "bold": False, "italic": False}]}]


def _html_to_plain_paragraphs(html: str) -> list:
    """Convert HTML to a list of paragraph texts (one string per paragraph). Fallback when no formatting needed."""
    if not html or not html.strip():
        return [""]
    text = re.sub(r"</p>\s*<p(\s[^>]*)?>", "\n\n", html, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</(div|h[1-6]|li|tr)>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = re.sub(r" +", " ", text)
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    return paragraphs if paragraphs else [""]


# def insert_line_breaks_in_long_paragraphs(text: str, max_chars: int = 80) -> str:
#     """
#     Insert single newlines in long paragraphs so the .docx gets line breaks at sentence
#     boundaries instead of one dense block. Only affects paragraphs that have no internal
#     newlines and exceed max_chars. Preserves existing \\n and \\n\\n.
#     """
#     if not text or not text.strip():
#         return text
#     normalized = (text or "").replace("\r\n", "\n\n").replace("\r", "\n\n")
#     paragraphs = re.split(r"\n\s*\n", normalized)
#     out = []
#     for para in paragraphs:
#         para = para.strip()
#         if not para:
#             out.append("")
#             continue
#         # Already has internal line breaks, or short enough
#         if "\n" in para or len(para) <= max_chars:
#             out.append(para)
#             continue
#         # Break at sentence boundaries: . " or .) " or ? " or ?) " when next char is A-Z
#         result_lines = []
#         rest = para
#         while len(rest) > max_chars:
#             chunk = rest[: max_chars + 1]
#             best_pos = -1
#             best_len = 0
#             for ending in [".) ", ". ", "?) ", "? "]:
#                 pos = chunk.rfind(ending)
#                 if pos != -1:
#                     next_idx = pos + len(ending)
#                     if next_idx < len(rest) and rest[next_idx].isalpha() and rest[next_idx].isupper():
#                         if pos > best_pos:
#                             best_pos = pos
#                             best_len = len(ending)
#             if best_pos == -1:
#                 # No sentence end; break at last space
#                 pos = chunk.rfind(" ")
#                 if pos != -1:
#                     best_pos = pos
#                     best_len = 1
#             if best_pos == -1:
#                 result_lines.append(rest)
#                 rest = ""
#                 break
#             end = best_pos + best_len
#             result_lines.append(rest[:end].rstrip())
#             rest = rest[end:].lstrip()
#         if rest:
#             result_lines.append(rest)
#         out.append("\n".join(result_lines))
#     return "\n\n".join(out)


def _strip_html_from_plain(text: str) -> str:
    """Remove HTML tags and decode entities from plain-text content so the docx never shows raw HTML."""
    if not text:
        return ""
    s = re.sub(r"<[^>]+>", "", text)
    s = htmllib.unescape(s)
    return s


def _ensure_paragraph_breaks(text: str) -> str:
    """
    Ensure we have \\n\\n at paragraph boundaries so the docx gets multiple <w:p>.
    If content already has \\n\\n, keep it. Otherwise insert \\n\\n at every sentence
    boundary: . ? ! followed by (newline or space) and then a capital letter.
    Avoids splitting after abbreviations (Mr., Dr.) by requiring 3+ chars before .?!
    for inline boundaries.
    """
    if not text:
        return ""
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    if "\n\n" in normalized:
        return normalized
    # 1) .?! then newline(s) then capital — likely real paragraph break
    normalized = re.sub(r"([.?!])\s*\n+\s*([A-Z])", r"\1\n\n\2", normalized)
    if "\n\n" in normalized:
        return normalized
    # 2) Inline: .?! then space(s) or no space, then capital. Require 3+ chars before .?!
    # so we don't split "Mr. Smith" or "Dr. Jones"
    normalized = re.sub(r"(?<=.{3})([.?!])\s{2,}([A-Z])", r"\1\n\n\2", normalized)
    normalized = re.sub(r"(?<=.{3})([.?!])\s+([A-Z])", r"\1\n\n\2", normalized)
    normalized = re.sub(r"(?<=.{3})([.?!])([A-Z])", r"\1\n\n\2", normalized)
    return normalized


def _strip_style_tags_from_plain(text: str) -> str:
    """
    Remove only the tag delimiters [tag:value] and [/tag], leaving all content in place.
    So tags never appear in output and we never remove or replace content.
    """
    if not text:
        return text
    # Remove opening tags: [color:#x], [ size : 14pt ], [font: Arial]
    text = re.sub(
        r"\[\s*(?:color|size|font)\s*:\s*[^\]]+\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Remove closing tags: [/color], [ / size ]
    text = re.sub(
        r"\[\s*/\s*(?:color|size|font)\s*\]",
        "",
        text,
        flags=re.IGNORECASE,
    )
    return text


def _parse_style_segments(line: str) -> List[tuple]:
    """
    Split line by [color:#xxx]...[/color], [size:Npt]...[/size], [font:Name]...[/font].
    Returns list of (style_dict, text). style_dict may have color_hex, font_size_pt, font_family.
    Revert: remove this and have _plain_line_to_runs ignore style tags.
    """
    segments = []
    rest = line
    # Match [tag:value]...[/tag] with optional whitespace so LLM output is matched
    pattern = re.compile(
        r"\[\s*(color|size|font)\s*:\s*([^\]]+)\]\s*(.*?)\s*\[\s*/\s*\1\s*\]",
        re.DOTALL | re.IGNORECASE,
    )
    while rest:
        m = pattern.search(rest)
        if not m:
            # Strip any remaining tag-like spans so they never show in the doc
            rest = _strip_style_tags_from_plain(rest)
            segments.append(({}, rest))
            break
        tag_type, tag_value, content = m.group(1).lower(), m.group(2), m.group(3)
        before = rest[: m.start()]
        if before:
            before = _strip_style_tags_from_plain(before)
            if before:
                segments.append(({}, before))
        style = {}
        if tag_type == "color":
            hex_val = tag_value.strip().lstrip("#")
            if len(hex_val) == 3:
                hex_val = "".join(c * 2 for c in hex_val)
            if len(hex_val) >= 6:
                style["color_hex"] = "#" + hex_val[:6]
        elif tag_type == "size":
            try:
                num = re.match(r"[\d.]+", tag_value.strip())
                if num:
                    style["font_size_pt"] = float(num.group())
            except (TypeError, ValueError):
                pass
        elif tag_type == "font":
            style["font_family"] = tag_value.strip()
        # Strip any nested/adjacent tags from content so they never show as literal text
        content = _strip_style_tags_from_plain(content)
        segments.append((style, content))
        rest = rest[m.end() :]
    return segments


def _bold_italic_to_runs(text: str) -> List[Dict]:
    """Parse **bold**, *italic*, __bold__, _italic_ only; return list of runs (text, bold, italic)."""
    runs = []
    rest = text
    while rest:
        m = re.search(r"\*\*(.+?)\*\*", rest)
        if m:
            before = rest[: m.start()]
            if before:
                runs.append({"text": before, "bold": False, "italic": False})
            runs.append({"text": m.group(1), "bold": True, "italic": False})
            rest = rest[m.end() :]
            continue
        m = re.search(r"\*(.+?)\*", rest)
        if m:
            before = rest[: m.start()]
            if before:
                runs.append({"text": before, "bold": False, "italic": False})
            runs.append({"text": m.group(1), "bold": False, "italic": True})
            rest = rest[m.end() :]
            continue
        m = re.search(r"__(.+?)__", rest)
        if m:
            before = rest[: m.start()]
            if before:
                runs.append({"text": before, "bold": False, "italic": False})
            runs.append({"text": m.group(1), "bold": True, "italic": False})
            rest = rest[m.end() :]
            continue
        m = re.search(r"_(.+?)_", rest)
        if m:
            before = rest[: m.start()]
            if before:
                runs.append({"text": before, "bold": False, "italic": False})
            runs.append({"text": m.group(1), "bold": False, "italic": True})
            rest = rest[m.end() :]
            continue
        runs.append({"text": rest, "bold": False, "italic": False})
        break
    return runs if runs else [{"text": text, "bold": False, "italic": False}]


def _plain_line_to_runs(line: str) -> List[Dict]:
    """Parse one line: [color:#x][/color], [size:Npt][/size], [font:Name][/font] plus **bold** and *italic*."""
    runs = []
    for style_dict, segment_text in _parse_style_segments(line):
        for run in _bold_italic_to_runs(segment_text):
            run = dict(run)
            if style_dict:
                if "color_hex" in style_dict:
                    run["color_hex"] = style_dict["color_hex"]
                if "font_size_pt" in style_dict:
                    run["font_size_pt"] = style_dict["font_size_pt"]
                if "font_family" in style_dict:
                    run["font_family"] = style_dict["font_family"]
            runs.append(run)
    return runs if runs else [{"text": line, "bold": False, "italic": False}]


def _plain_text_to_blocks(text: str) -> List[Dict]:
    """\\n\\n = new paragraph (<w:p>); \\n = line break within paragraph. ** and * = bold/italic."""
    if not text:
        return []
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    normalized = _ensure_paragraph_breaks(normalized)
    paragraphs = re.split(r"\n\s*\n", normalized.strip() if normalized else "")
    blocks = []
    for para in paragraphs:
        lines = para.split("\n")
        runs = []
        for i, line in enumerate(lines):
            runs.extend(_plain_line_to_runs(line))
            if i < len(lines) - 1:
                runs.append({"line_break": True})
        blocks.append({"type": "p", "runs": runs})
    return blocks


def _markdown_to_blocks(markdown: str) -> List[Dict]:
    """Convert markdown to blocks with runs (preserve ** and * as bold/italic)."""
    if not markdown or not markdown.strip():
        return []
    blocks = []
    # Split into paragraphs (double newline)
    raw_paras = re.split(r"\n\s*\n", markdown.strip())
    for raw in raw_paras:
        line = " ".join(raw.splitlines()).strip()
        if not line:
            continue
        # Detect list item
        is_li = bool(re.match(r"^[\-\*]\s+", line) or re.match(r"^\d+\.\s+", line))
        line = re.sub(r"^[\-\*]\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        # Split into runs by ** and *
        runs = []
        rest = line
        while rest:
            # Bold: **text**
            m = re.search(r"\*\*(.+?)\*\*", rest)
            if m:
                before = rest[: m.start()]
                if before:
                    runs.append({"text": before, "bold": False, "italic": False})
                runs.append({"text": m.group(1), "bold": True, "italic": False})
                rest = rest[m.end() :]
                continue
            # Italic: *text*
            m = re.search(r"\*(.+?)\*", rest)
            if m:
                before = rest[: m.start()]
                if before:
                    runs.append({"text": before, "bold": False, "italic": False})
                runs.append({"text": m.group(1), "bold": False, "italic": True})
                rest = rest[m.end() :]
                continue
            # __bold__
            m = re.search(r"__(.+?)__", rest)
            if m:
                before = rest[: m.start()]
                if before:
                    runs.append({"text": before, "bold": False, "italic": False})
                runs.append({"text": m.group(1), "bold": True, "italic": False})
                rest = rest[m.end() :]
                continue
            # _italic_
            m = re.search(r"_(.+?)_", rest)
            if m:
                before = rest[: m.start()]
                if before:
                    runs.append({"text": before, "bold": False, "italic": False})
                runs.append({"text": m.group(1), "bold": False, "italic": True})
                rest = rest[m.end() :]
                continue
            runs.append({"text": rest, "bold": False, "italic": False})
            break
        if not runs:
            runs = [{"text": line, "bold": False, "italic": False}]
        blocks.append({"type": "li" if is_li else "p", "runs": runs})
    return blocks


def build_docx_from_content(
    content: str,
    *,
    from_html: bool = False,
    from_plain_text: bool = False,
    print_properties: Optional[Dict] = None,
) -> bytes:
    """
    Build a Word .docx from cover letter content.

    Args:
        content: The cover letter body (plain text, markdown, or HTML).
        from_html: If True, treat content as HTML.
        from_plain_text: If True, treat content as plain text (\\n = line break, \\n\\n = paragraph). No markup.
        print_properties: Optional dict with fontFamily, fontSize, lineHeight.

    Returns:
        .docx file as bytes.
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

    if from_plain_text:
        content = _strip_html_from_plain(content or "")
        blocks = _plain_text_to_blocks(content)
    elif from_html:
        blocks = _html_to_blocks(content)
    else:
        blocks = _markdown_to_blocks(content or "")

    # Heuristic: paragraphs whose first run starts with • or - or * become list items (LLM may not use <ul><li>)
    for block in blocks:
        if block.get("type") != "p" or not block.get("runs"):
            continue
        first_run = block["runs"][0]
        if first_run.get("line_break"):
            continue
        first_text = first_run.get("text", "")
        if re.match(r"^[•\-*]\s+", first_text):
            block["type"] = "li"
            first_run["text"] = re.sub(r"^[•\-*]\s+", "", first_text)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = font_family
    style.font.size = Pt(font_size_pt)

    space_after = Pt(round(font_size_pt * line_height * 0.4))

    # One <w:p> per block (see BACKEND_DOCX_PARAGRAPH_AND_LINE_BREAKS.md)
    for block in blocks:
        p = doc.add_paragraph()
        if block["type"] == "li":
            p.style = "List Bullet"
            # Don't set space_after; let Word's list style control bullet spacing
        else:
            p.paragraph_format.space_after = space_after
        last_ended_with_space = True  # avoid leading space before first run
        for run_spec in block["runs"]:
            if run_spec.get("line_break"):
                if WD_BREAK is not None:
                    p.add_run().add_break(WD_BREAK.LINE)
                last_ended_with_space = True
                continue
            text = run_spec.get("text", "")
            if not text:
                continue
            # Preserve space around inline/spans: add space if previous run didn't end with space and this doesn't start with one
            if not last_ended_with_space and not (text.startswith(" ") or text.startswith("\t")):
                text = " " + text
            last_ended_with_space = text.endswith(" ") or text.endswith("\t")
            run = p.add_run(text)
            run_font = run.font
            run_font.name = (run_spec.get("font_family") or "").strip() or font_family
            size_pt = run_spec.get("font_size_pt")
            run_font.size = Pt(size_pt if size_pt is not None and size_pt > 0 else font_size_pt)
            run.bold = run_spec.get("bold", False)
            run.italic = run_spec.get("italic", False)
            color_hex = run_spec.get("color_hex")
            if color_hex and RGBColor is not None:
                hex_val = color_hex.lstrip("#")
                if len(hex_val) >= 6:
                    try:
                        r = int(hex_val[0:2], 16)
                        g = int(hex_val[2:4], 16)
                        b = int(hex_val[4:6], 16)
                        run_font.color.rgb = RGBColor(r, g, b)
                    except (ValueError, TypeError):
                        pass

    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    docx_bytes = buf.read()

    # Debug: always write docx + info to tmp/ after every build (so we see which path ran: plain_text vs html vs markdown).
    _source = "plain_text" if from_plain_text else ("html" if from_html else "markdown")
    _written = []
    _bases = [
        os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")),
        os.getcwd(),
    ]
    for _base in _bases:
        _tmp = os.path.join(_base, "tmp")
        _docx_path = os.path.join(_tmp, "raw-debug.docx")
        _info_path = os.path.join(_tmp, "raw-debug-info.txt")
        try:
            os.makedirs(_tmp, exist_ok=True)
            with open(_docx_path, "wb") as f:
                f.write(docx_bytes)
            with open(_info_path, "w", encoding="utf-8") as f:
                f.write(f"source={_source}\n")
                f.write(f"block_count={len(blocks)}\n")
                raw = (content or "")[:1200]
                has_double = "\n\n" in raw
                f.write(f"content_has_double_newline={has_double}\n")
                f.write(f"content_preview (repr)=\n{repr(raw)}\n")
            _written.append(os.path.abspath(_tmp))
        except Exception as e:
            logger.warning("Docx debug: could not write to %s: %s", os.path.abspath(_tmp), e)
    if _written:
        logger.info("Docx debug: wrote raw-debug.docx, raw-debug-info.txt (source=%s, blocks=%s) to %s", _source, len(blocks), _written)
    else:
        logger.warning("Docx debug: no tmp dir was writable")

    return docx_bytes


def build_docx_from_generation_result(
    content: Optional[str] = None,
    markdown: Optional[str] = None,
    html: Optional[str] = None,
    print_properties: Optional[Dict] = None,
    *,
    use_plain_text: bool = False,
) -> bytes:
    """
    Build .docx from cover letter generation result.
    When use_plain_text is True (docx-only flow), content is plain text only.
    Otherwise: prefers content as plain text if use_plain_text; else prefers html, then markdown.
    """
    if use_plain_text and content:
        return build_docx_from_content(
            content, from_plain_text=True, print_properties=print_properties
        )
    if html and html.strip():
        return build_docx_from_content(html, from_html=True, print_properties=print_properties)
    raw = content or markdown or ""
    if use_plain_text:
        return build_docx_from_content(raw, from_plain_text=True, print_properties=print_properties)
    return build_docx_from_content(raw, from_html=False, print_properties=print_properties)
