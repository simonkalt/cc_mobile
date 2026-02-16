"""
PDF generation service
"""

import asyncio
import hashlib
import logging
import base64
import io
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Optional

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    import colorama
    colorama.init(autoreset=True)
    def _yellow(msg: str) -> str:
        return f"{colorama.Fore.YELLOW}{msg}{colorama.Style.RESET_ALL}"
except ImportError:
    def _yellow(msg: str) -> str:
        return msg

# Use project-local browser path so Render (and other hosts) find Chromium installed at build time.
# Must be set before importing playwright.
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    _pdf_service_root = Path(__file__).resolve().parent
    _project_root = _pdf_service_root.parent.parent
    _playwright_browsers = _project_root / "playwright-browsers"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_playwright_browsers)


# Placeholder used when returning template without content (for frontend to inject)
PRINT_TEMPLATE_CONTENT_PLACEHOLDER = "{{LETTER_CONTENT}}"

# Named colors that may appear in Additional Instructions -> CSS color
_STYLE_NAMED_COLORS = {
    "black": "#000000",
    "white": "#ffffff",
    "blue": "#0000ff",
    "navy": "#000080",
    "red": "#ff0000",
    "green": "#008000",
    "gray": "#808080",
    "grey": "#808080",
    "dark gray": "#404040",
    "dark grey": "#404040",
}


def parse_style_instructions(text: Optional[str]) -> Dict:
    """
    Parse free-text style instructions (e.g. from Additional Instructions) for font size,
    font family, line height, and color. Returns a dict of overrides to merge into print_properties.
    """
    if not text or not str(text).strip():
        return {}
    t = " " + str(text).lower() + " "
    out = {}
    # Font size: e.g. "12pt", "14pt", "12 pt", "14px"
    m = re.search(r"\b(\d{1,2})\s*pt\b", t, re.IGNORECASE)
    if m:
        out["fontSize"] = float(m.group(1))
    else:
        m = re.search(r"\b(\d{1,2})\s*px\b", t, re.IGNORECASE)
        if m:
            px = int(m.group(1))
            out["fontSize"] = max(8, min(24, round(px * 0.75)))  # rough px -> pt
    # Font family: common names (must be whole-word)
    for name in ("arial", "times new roman", "georgia", "verdana", "helvetica", "garamond", "calibri"):
        if re.search(rf"\b{re.escape(name)}\b", t):
            out["fontFamily"] = name.title()
            break
    # Line height: e.g. "line height 1.5", "1.6 line height"
    m = re.search(r"(?:line\s*height|line-height)\s*[:\s]*(\d+(?:\.\d+)?)", t, re.IGNORECASE)
    if m:
        out["lineHeight"] = float(m.group(1))
    else:
        m = re.search(r"\b(1\.\d{1,2})\s*(?:line|spacing)\b", t, re.IGNORECASE)
        if m:
            out["lineHeight"] = float(m.group(1))
    # Color: #hex, rgb(...), or named
    m = re.search(r"#([0-9a-f]{3}(?:[0-9a-f]{3})?)\b", t, re.IGNORECASE)
    if m:
        hex_val = m.group(1)
        if len(hex_val) == 3:
            hex_val = "".join(c * 2 for c in hex_val)
        out["color"] = "#" + hex_val
    else:
        m = re.search(r"rgb\s*\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", t, re.IGNORECASE)
        if m:
            r, g, b = m.group(1), m.group(2), m.group(3)
            out["color"] = f"rgb({r},{g},{b})"
        else:
            for name, hex_val in _STYLE_NAMED_COLORS.items():
                if re.search(rf"\b{re.escape(name)}\b", t):
                    out["color"] = hex_val
                    break
    return out


def _build_print_template_css_and_body(
    print_properties: Dict,
) -> tuple[str, str]:
    """
    Build the CSS and body_style for the print template.
    Returns (css_block, body_style_string) used by both PDF generation and get_print_template.
    """
    margins = print_properties.get("margins", {})
    font_family = print_properties.get("fontFamily", "Times New Roman")
    font_size = print_properties.get("fontSize", 12)
    line_height = print_properties.get("lineHeight", 1.6)
    page_size = print_properties.get("pageSize", {"width": 8.5, "height": 11.0})
    use_default_fonts = print_properties.get("useDefaultFonts", False)
    color = print_properties.get("color", "#000")

    margin_top = margins.get("top", 1.0)
    margin_right = margins.get("right", 0.75)
    margin_bottom = margins.get("bottom", 0.75)
    margin_left = margins.get("left", 0.75)
    width_in = page_size.get("width", 8.5)
    height_in = page_size.get("height", 11.0)

    body_style = (
        "margin: 0; padding: 0; box-sizing: border-box; "
        "white-space: pre-wrap; word-wrap: break-word;"
    )
    if not use_default_fonts:
        if font_family and str(font_family).strip().lower() == "default":
            body_style += " font-family: Arial, sans-serif; font-size: 12pt; line-height: {0}; color: {1};".format(
                line_height, color
            )
        else:
            body_style += f' font-family: "{font_family}", serif; font-size: {font_size}pt; line-height: {line_height}; color: {color};'

    css_block = f"""
@page {{
  size: {width_in}in {height_in}in;
  margin: {margin_top}in {margin_right}in {margin_bottom}in {margin_left}in;
}}
*, *::before, *::after {{ box-sizing: border-box; }}
/* Force zero margin/padding on all content so only @page margin applies */
.print-content * {{ margin: 0 !important; padding: 0 !important; }}
/* Explicit p/div reset for line-break fidelity (Nutrient.io and general PDF) */
.print-content p, .print-content div {{ margin: 0 !important; padding: 0 !important; }}
body {{ {body_style} }}
.print-content {{
  max-width: 100%;
  width: 100%;
  overflow-x: hidden;
  overflow-wrap: break-word;
  word-wrap: break-word;
}}
.print-content * {{ max-width: 100%; }}
.print-content table {{ table-layout: fixed; width: 100% !important; }}
.print-content img, .print-content pre, .print-content code {{ max-width: 100%; }}
.print-content p {{ page-break-inside: avoid; margin: 0 !important; padding: 0 !important; }}
/* Single <br /> = one line break; 0.12em matches PDF spacing */
.print-content br {{ display: block; margin-top: 0.12em !important; }}
.print-content ul, .print-content ol {{ padding-left: 1.2em !important; }}
"""
    return css_block.strip(), body_style


def get_print_template(
    print_properties: Dict,
    html_content: Optional[str] = None,
) -> Dict[str, str]:
    """
    Return the exact HTML/CSS wrapper used for PDF generation.

    When htmlContent is provided: normalizes it (same as PDF pipeline), injects into
    the template, and returns the full document. Use this for "Match PDF" or "Print
    Preview" view—render the returned HTML and it will match the PDF.

    When htmlContent is omitted: returns the template with {{LETTER_CONTENT}} placeholder.
    Frontend can replace that placeholder with normalized content.

    Returns:
        {
            "html": full HTML document string,
            "contentPlaceholder": "{{LETTER_CONTENT}}" (when no htmlContent provided)
        }
    """
    css_block, _ = _build_print_template_css_and_body(print_properties)

    if html_content and html_content.strip():
        # Same normalization as PDF pipeline—single source of truth
        content = _normalize_html_for_pdf(html_content)
        content = _strip_newlines_adjacent_to_br(content)
        content = _normalize_line_breaks_in_html(content)
    else:
        content = PRINT_TEMPLATE_CONTENT_PLACEHOLDER

    full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
{css_block}
</style>
</head>
<body>
<div class="print-content">{content}</div>
</body>
</html>"""

    result: Dict[str, str] = {"html": full_html}
    if not (html_content and html_content.strip()):
        result["contentPlaceholder"] = PRINT_TEMPLATE_CONTENT_PLACEHOLDER
    return result


def normalize_html_for_print(html_content: str) -> str:
    """
    Normalize HTML for print/PDF. Single pipeline—use this for both display (Match PDF
    view) and PDF generation to ensure consistency.

    - Merges </p><p> to <br />
    - Collapses redundant <br />
    - Ensures break before Sincerely,
    - Strips newlines adjacent to <br />
    - Converts literal \\n to <br />
    """
    if not html_content:
        return html_content
    html_content = _normalize_html_for_pdf(html_content)
    html_content = _strip_newlines_adjacent_to_br(html_content)
    html_content = _normalize_line_breaks_in_html(html_content)
    return html_content


def _normalize_html_for_pdf(html_content: str) -> str:
    """
    Normalize HTML for PDF so spacing is consistent regardless of editor output.
    Rich editors (e.g. react-native-pell-rich-editor) often use <p> per line, which
    adds paragraph margins and makes the PDF look double-spaced. We merge adjacent
    </p><p> into a single <br /> here so the PDF has single-line spacing while the
    same HTML can still look correct in the editor.
    """
    if not html_content:
        return html_content
    # Merge adjacent paragraphs so we don't get 0.75em margin between every line in PDF
    html_content = re.sub(
        r"</p>\s*<p(\s[^>]*)?>",
        "<br />",
        html_content,
        flags=re.IGNORECASE,
    )
    html_content = _collapse_br_for_pdf(html_content)
    # Ensure there is always a line break before "Sincerely," so the closing never runs into the body
    html_content = re.sub(
        r"([.>])\s*Sincerely\s*,",
        r"\1<br />Sincerely,",
        html_content,
        flags=re.IGNORECASE,
    )
    return html_content


def _collapse_br_for_pdf(html_content: str) -> str:
    """
    Prevent oversized line breaks in PDF: collapse redundant <br> and newlines so we
    don't end up with double breaks (e.g. <br /> + newline converted to another <br />).
    """
    if not html_content:
        return html_content
    # Collapse any whitespace (including newlines) around <br> variants to a single <br />
    html_content = re.sub(r"\s*<br\s*/?\s*>\s*", "<br />", html_content, flags=re.IGNORECASE)
    # Collapse multiple consecutive <br /> to a single one
    html_content = re.sub(r"(<br\s*/?\s*>)+", "<br />", html_content, flags=re.IGNORECASE)
    return html_content


def _strip_newlines_adjacent_to_br(html_content: str) -> str:
    """
    Remove newlines that are immediately adjacent to <br /> so that when we later
    convert \\n to <br /> we don't create double line breaks (one from existing
    <br /> and one from the newline).
    """
    if not html_content:
        return html_content
    # After <br />: remove following newlines (so "\n" after br doesn't become extra <br />)
    html_content = re.sub(
        r"(<br\s*/?\s*>)\s*[\r\n]+\s*",
        r"\1",
        html_content,
        flags=re.IGNORECASE,
    )
    # Before <br />: remove preceding newlines
    html_content = re.sub(
        r"\s*[\r\n]+\s*(<br\s*/?\s*>)",
        r"\1",
        html_content,
        flags=re.IGNORECASE,
    )
    return html_content


def _normalize_line_breaks_in_html(html_content: str) -> str:
    """
    Ensure line breaks render in PDF: convert literal newlines in text content to <br />.
    Only replaces \\n outside of HTML tags so we don't break attribute values or tag structure.
    - Single newline (\\n) → one <br /> (single line break).
    - Double (or more) newlines (\\n\\n) → two <br /> (blank line) so intentional
      blank lines are preserved.
    """
    if not html_content or ("\n" not in html_content and "\r" not in html_content):
        return html_content
    # Split on tags (keep tags in the list); odd-indexed parts are tags, even are text
    parts = re.split(r"(<[^>]*>)", html_content)
    result = []
    for part in parts:
        if part.startswith("<") and part.endswith(">"):
            result.append(part)
        else:
            # Normalize \\r\\n to \\n, then: two-or-more newlines → blank line (two br), single → one br
            normalized = re.sub(r"[\r\n]+", "\n", part)
            # Replace \n\n+ with two br (blank line), then remaining single \n with one br
            normalized = re.sub(r"\n\n+", "<br /><br />", normalized)
            result.append(normalized.replace("\n", "<br />"))
    return "".join(result)


# Try to import PDF generation libraries
try:
    import markdown

    PDF_GENERATION_AVAILABLE = True
except ImportError:
    PDF_GENERATION_AVAILABLE = False
    logger.warning("markdown not available. PDF generation will not work.")

# WeasyPrint: remarked out - using LibreOffice only as PDF engine for now.
# try:
#     from weasyprint import HTML
#     WEASYPRINT_AVAILABLE = True
# except (ImportError, OSError) as e:
#     WEASYPRINT_AVAILABLE = False
#     logger.warning(f"weasyprint not available. PDF generation will not work. Error: {str(e)}")
WEASYPRINT_AVAILABLE = False

# Playwright: remarked out - using LibreOffice only as PDF engine for now.
# try:
#     from playwright.async_api import async_playwright
#     PLAYWRIGHT_AVAILABLE = True
# except ImportError:
#     PLAYWRIGHT_AVAILABLE = False
#     async_playwright = None
#     logger.info(
#         "playwright not installed. PDF will use WeasyPrint (install playwright for more reliable margins)."
#     )
PLAYWRIGHT_AVAILABLE = False
async_playwright = None


def _pdf_cache_dir() -> Path:
    """API-level temp folder for per-user last PDF cache. Created on first use."""
    _service_root = Path(__file__).resolve().parent
    _project_root = _service_root.parent.parent
    cache_dir = _project_root / "tmp" / "pdf_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir


def _safe_user_id(user_id: str) -> str:
    """Safe filename segment from user_id (no path separators or special chars)."""
    if not user_id:
        return ""
    safe = re.sub(r"[^\w\-]", "_", user_id)
    return safe or hashlib.sha256(user_id.encode()).hexdigest()[:16]


def _content_hash(html_content: str) -> str:
    """SHA256 hash of normalized HTML for cache key."""
    return hashlib.sha256(html_content.encode("utf-8")).hexdigest()


def get_cached_pdf(user_id: str, content_hash: str) -> Optional[bytes]:
    """
    Return cached PDF bytes if we have a stored PDF for this user and its hash matches.
    Otherwise return None.
    """
    if not user_id or not content_hash:
        return None
    safe_id = _safe_user_id(user_id)
    if not safe_id:
        return None
    cache_dir = _pdf_cache_dir()
    pdf_path = cache_dir / f"{safe_id}_last_pdf.pdf"
    hash_path = cache_dir / f"{safe_id}_last_pdf.hash"
    if not pdf_path.exists() or not hash_path.exists():
        return None
    try:
        stored_hash = hash_path.read_text(encoding="utf-8").strip()
        if stored_hash != content_hash:
            return None
        return pdf_path.read_bytes()
    except OSError:
        return None


def set_cached_pdf(user_id: str, content_hash: str, pdf_bytes: bytes) -> None:
    """
    Store PDF and content hash for this user. Deletes any existing cached PDF for this user first.
    """
    if not user_id or not content_hash:
        return
    safe_id = _safe_user_id(user_id)
    if not safe_id:
        return
    cache_dir = _pdf_cache_dir()
    pdf_path = cache_dir / f"{safe_id}_last_pdf.pdf"
    hash_path = cache_dir / f"{safe_id}_last_pdf.hash"
    try:
        pdf_path.unlink(missing_ok=True)
        hash_path.unlink(missing_ok=True)
        pdf_path.write_bytes(pdf_bytes)
        hash_path.write_text(content_hash, encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write PDF cache for user %s: %s", safe_id, e)


def convert_docx_to_pdf(docx_bytes: bytes) -> bytes:
    """
    Convert a .docx document to PDF using LibreOffice headless.
    Preserves formatting from the .docx (direct conversion, no HTML pipeline).

    Requires LibreOffice to be installed (e.g. apt-get install libreoffice-writer on Linux,
    or LibreOffice on Windows/macOS with 'soffice' on PATH).

    Args:
        docx_bytes: Raw bytes of the .docx file.

    Returns:
        PDF file as bytes.

    Raises:
        FileNotFoundError: If LibreOffice (soffice) is not installed.
        RuntimeError: If conversion fails.
    """
    if not docx_bytes or len(docx_bytes) < 100:
        raise ValueError("Invalid or empty .docx content")

    # Use a single temp directory for both input and output
    with tempfile.TemporaryDirectory(prefix="docx2pdf_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        docx_path = tmpdir_path / "document.docx"
        docx_path.write_bytes(docx_bytes)

        # LibreOffice: --headless --convert-to pdf --outdir <dir> <file>
        # Output will be <dir>/document.pdf
        try:
            subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmpdir_path),
                    str(docx_path),
                ],
                check=True,
                capture_output=True,
                timeout=120,
                cwd=str(tmpdir_path),
            )
        except FileNotFoundError:
            logger.error(
                "LibreOffice (soffice) not found. Install it for docx→PDF (e.g. apt install libreoffice-writer)."
            )
            raise FileNotFoundError(
                "LibreOffice (soffice) is not installed. Required for docx to PDF conversion."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("Docx to PDF conversion timed out")
        except subprocess.CalledProcessError as e:
            logger.error("LibreOffice conversion failed: %s %s", e.stderr, e.stdout)
            raise RuntimeError(f"Docx to PDF conversion failed: {e.stderr.decode() if e.stderr else str(e)}")

        pdf_path = tmpdir_path / "document.pdf"
        if not pdf_path.exists():
            raise RuntimeError("LibreOffice did not produce a PDF file")

        return pdf_path.read_bytes()


def _generate_pdf_via_libreoffice_html(html_doc: str) -> bytes:
    """
    Generate PDF from full HTML document using LibreOffice headless.
    Writes HTML to a temp file and runs: soffice --headless --convert-to pdf --outdir <dir> file.html

    Requires LibreOffice (soffice) on PATH.
    """
    with tempfile.TemporaryDirectory(prefix="pdf_libreoffice_") as tmpdir:
        tmpdir_path = Path(tmpdir)
        html_path = tmpdir_path / "document.html"
        html_path.write_text(html_doc, encoding="utf-8")
        try:
            subprocess.run(
                [
                    "soffice",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    str(tmpdir_path),
                    str(html_path),
                ],
                check=True,
                capture_output=True,
                timeout=120,
                cwd=str(tmpdir_path),
            )
        except FileNotFoundError:
            logger.error(
                "LibreOffice (soffice) not found. Install it (e.g. apt install libreoffice-writer)."
            )
            raise FileNotFoundError(
                "LibreOffice (soffice) is not installed. Required for PDF generation."
            )
        except subprocess.TimeoutExpired:
            raise RuntimeError("HTML to PDF conversion timed out")
        except subprocess.CalledProcessError as e:
            logger.error("LibreOffice HTML→PDF failed: %s %s", e.stderr, e.stdout)
            raise RuntimeError(
                f"LibreOffice HTML to PDF failed: {e.stderr.decode() if e.stderr else str(e)}"
            )
        pdf_path = tmpdir_path / "document.pdf"
        if not pdf_path.exists():
            raise RuntimeError("LibreOffice did not produce a PDF file")
        return pdf_path.read_bytes()


NUTRIENT_PDF_URL = "https://api.nutrient.io/processor/generate_pdf"

# 1 inch = 25.4 mm (for Nutrient.io margin params)
INCH_TO_MM = 25.4


def _nutrient_page_size_from_properties(print_properties: Dict) -> str:
    """Map our pageSize (width/height in inches) to Nutrient page_size (e.g. Letter, A4)."""
    page_size = print_properties.get("pageSize", {})
    width_in = page_size.get("width", 8.5)
    height_in = page_size.get("height", 11.0)
    # Letter = 8.5 x 11 in; A4 ≈ 8.27 x 11.69 in
    if abs(width_in - 8.27) < 0.1 and abs(height_in - 11.69) < 0.1:
        return "A4"
    if abs(width_in - 8.5) < 0.01 and abs(height_in - 11.0) < 0.01:
        return "Letter"
    return "Letter"


def _generate_pdf_via_nutrient_sync(
    html_doc: str, api_key: str, print_properties: Dict
) -> bytes:
    """
    Generate PDF via Nutrient.io API (sync). POST full HTML with form params for
    page size, margins (mm), text_rendering_mode, enable_css, wait_time.
    Raises on non-2xx or network error so caller can fall back to Playwright/WeasyPrint.
    """
    margins = print_properties.get("margins", {})
    margin_top_mm = round(margins.get("top", 1.0) * INCH_TO_MM, 1)
    margin_right_mm = round(margins.get("right", 0.75) * INCH_TO_MM, 1)
    margin_bottom_mm = round(margins.get("bottom", 0.75) * INCH_TO_MM, 1)
    margin_left_mm = round(margins.get("left", 0.75) * INCH_TO_MM, 1)

    data = {
        "page_size": _nutrient_page_size_from_properties(print_properties),
        "page_margin_top": f"{margin_top_mm}mm",
        "page_margin_bottom": f"{margin_bottom_mm}mm",
        "page_margin_left": f"{margin_left_mm}mm",
        "page_margin_right": f"{margin_right_mm}mm",
        "text_rendering_mode": "html",
        "enable_css": "true",
        "wait_time": "1000",
    }

    headers = {"Authorization": f"Bearer {api_key}"}
    files = {
        "html": ("index.html", io.BytesIO(html_doc.encode("utf-8")), "text/html; charset=utf-8"),
    }

    response = requests.post(
        NUTRIENT_PDF_URL,
        headers=headers,
        files=files,
        data=data,
        timeout=60,
        stream=True,
    )
    response.raise_for_status()

    buf = io.BytesIO()
    for chunk in response.iter_content(chunk_size=8096):
        if chunk:
            buf.write(chunk)
    return buf.getvalue()


async def _generate_pdf_via_nutrient(html_content: str, print_properties: Dict) -> bytes:
    """
    Generate PDF using Nutrient.io. Uses same template as get_print_template for consistency.
    Runs the HTTP call in a thread so the event loop is not blocked.
    """
    template_result = get_print_template(print_properties, html_content)
    html_doc = template_result["html"]
    api_key = settings.NUTRIENT_API_KEY or ""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        lambda: _generate_pdf_via_nutrient_sync(html_doc, api_key, print_properties),
    )


def generate_pdf_from_markdown(markdown_content: str, print_properties: Dict) -> str:
    """
    Generate a PDF from Markdown content with proper formatting support.
    Uses WeasyPrint for PDF generation.

    Args:
        markdown_content: The Markdown content to convert to PDF
        print_properties: Dictionary containing print configuration:
            - margins: dict with top, right, bottom, left (in inches)
            - fontFamily: str (default: "Times New Roman")
            - fontSize: float (default: 12)
            - lineHeight: float (default: 1.6)
            - pageSize: dict with width, height (in inches, default: 8.5 x 11)
            - useDefaultFonts: bool (default: False)

    Returns:
        Base64-encoded PDF data as a string (without data URI prefix)

    Raises:
        ImportError: If required libraries are not installed
        Exception: If PDF generation fails
    """
    if not PDF_GENERATION_AVAILABLE:
        raise ImportError("markdown library is not installed. Cannot generate PDF.")

    try:
        # Normalize markdown content: replace escaped newlines with actual newlines
        normalized_markdown = markdown_content.replace("\\n", "\n").replace("\\r", "\r")

        # Normalize line endings: convert \r\n to \n, then remove standalone \r
        normalized_markdown = normalized_markdown.replace("\r\n", "\n").replace("\r", "\n")

        # Convert markdown to HTML
        html_content = markdown.markdown(
            normalized_markdown, extensions=["extra", "codehilite", "tables", "nl2br"]
        )

        # Strip unwanted \r and \n characters from HTML output
        html_content = html_content.replace("\r", "").replace("\n", " ")
        html_content = re.sub(r" +", " ", html_content)

        # Use same template as get_print_template for consistency; then LibreOffice HTML→PDF
        full_html = get_print_template(print_properties, html_content)["html"]
        pdf_bytes = _generate_pdf_via_libreoffice_html(full_html)
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        logger.info(_yellow("PDF writer: LibreOffice (from markdown) (%s bytes)"), len(pdf_bytes))
        return pdf_base64

    except Exception as e:
        logger.error(f"Error generating PDF from Markdown: {str(e)}")
        raise Exception(f"Failed to generate PDF: {str(e)}")


# Remarked out: Playwright PDF engine (using LibreOffice only for now).
# async def _generate_pdf_via_playwright(html_content: str, print_properties: Dict) -> bytes:
#     """Generate PDF using Playwright (Chromium)."""
#     ...
#     async with async_playwright() as p:
#         browser = await p.chromium.launch(...)
#         ...
#     return pdf_bytes


# Remarked out: WeasyPrint PDF engine (using LibreOffice only for now).
# def _generate_pdf_via_weasyprint(html_content: str, print_properties: Dict) -> bytes:
#     """Generate PDF from HTML using WeasyPrint."""
#     ...
#     return HTML(string=wrapper).write_pdf()


# Remarked out: raw HTML WeasyPrint path (using LibreOffice only for now).
# def _generate_pdf_raw_html(html_content: str, print_properties: Dict) -> bytes:
#     """Generate PDF from raw HTML with minimal wrapper (WeasyPrint)."""
#     ...
#     return HTML(string=minimal).write_pdf()


async def generate_pdf_from_html(
    html_content: str, print_properties: Dict, user_id: Optional[str] = None
) -> str:
    """
    Generate a PDF from HTML content using user print preferences.
    Uses LibreOffice (soffice) as the PDF engine: HTML → temp file → soffice --convert-to pdf.
    When user_id is provided, caches the last PDF per user in tmp/pdf_cache; same HTML returns cached PDF to save cost.

    Args:
        html_content: The HTML fragment to convert (placed inside body).
        print_properties: User print preferences (same shape as generate_pdf_from_markdown).
        user_id: Optional user id for per-user PDF cache (skip generation if HTML unchanged).

    Returns:
        Base64-encoded PDF data as a string (without data URI prefix).

    Raises:
        FileNotFoundError: If LibreOffice (soffice) is not installed.
    """
    font_family = print_properties.get("fontFamily", "Times New Roman")
    font_size = print_properties.get("fontSize", 12)

    # Normalize for PDF: merge </p><p> to <br />, collapse redundant <br />, strip \n adjacent to <br /> (avoid double breaks), then \n → <br /> (single \n = one br, \n\n = blank line)
    html_content = _normalize_html_for_pdf(html_content)
    html_content = _strip_newlines_adjacent_to_br(html_content)
    html_content = _normalize_line_breaks_in_html(html_content)

    content_hash = _content_hash(html_content)
    if user_id:
        cached = get_cached_pdf(user_id, content_hash)
        if cached is not None:
            logger.info("Print preview PDF cache hit for user_id=%s", _safe_user_id(user_id))
            return base64.b64encode(cached).decode("utf-8")

    # LibreOffice only: HTML → temp file → soffice --convert-to pdf
    template_result = get_print_template(print_properties, html_content)
    html_doc = template_result["html"]
    loop = asyncio.get_event_loop()
    pdf_bytes = await loop.run_in_executor(
        None,
        lambda: _generate_pdf_via_libreoffice_html(html_doc),
    )
    if user_id:
        set_cached_pdf(user_id, content_hash, pdf_bytes)
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    logger.info(
        _yellow("PDF writer: LibreOffice (%s bytes, font=%s, size=%spt)"),
        len(pdf_bytes),
        font_family,
        font_size,
    )
    return pdf_base64

    # --- Remarked out: other PDF engines (using LibreOffice only for now) ---
    # # Raw HTML: minimal wrapper (WeasyPrint only)
    # if settings.PRINT_PREVIEW_RAW_HTML:
    #     if not WEASYPRINT_AVAILABLE:
    #         raise ImportError(
    #             "PRINT_PREVIEW_RAW_HTML is True but WeasyPrint is not available."
    #         )
    #     pdf_bytes = _generate_pdf_via_weasyprint(html_content, print_properties)
    #     ...
    # # Nutrient.io: optional external PDF service
    # if settings.PRINT_PREVIEW_USE_NUTRIENT and settings.NUTRIENT_API_KEY:
    #     ...
    # # Playwright when available
    # if PLAYWRIGHT_AVAILABLE and async_playwright:
    #     pdf_bytes = await _generate_pdf_via_playwright(html_content, print_properties)
    #     ...
    # # WeasyPrint fallback
    # if WEASYPRINT_AVAILABLE:
    #     pdf_bytes = _generate_pdf_via_weasyprint(html_content, print_properties)
    #     ...
