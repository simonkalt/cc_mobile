"""
PDF generation service
"""

import logging
import base64
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Use project-local browser path so Render (and other hosts) find Chromium installed at build time.
# Must be set before importing playwright.
if "PLAYWRIGHT_BROWSERS_PATH" not in os.environ:
    _pdf_service_root = Path(__file__).resolve().parent
    _project_root = _pdf_service_root.parent.parent
    _playwright_browsers = _project_root / "playwright-browsers"
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = str(_playwright_browsers)


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


def _normalize_line_breaks_in_html(html_content: str) -> str:
    """
    Ensure line breaks render in PDF: convert literal newlines in text content to <br />.
    Only replaces \\n outside of HTML tags so we don't break attribute values or tag structure.
    Collapses multiple newlines to one <br /> so we don't add excess vertical space.
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
            # Collapse any run of \\r/\\n to a single newline, then convert to one <br />
            normalized = re.sub(r"[\r\n]+", "\n", part)
            result.append(normalized.replace("\n", "<br />"))
    return "".join(result)


def _save_debug_pdf(pdf_bytes: bytes, source: str, html_snippet: Optional[str] = None) -> None:
    """For testing: save a copy of the generated PDF in the project debug folder."""
    project_root = Path(__file__).resolve().parent.parent.parent
    debug_dir = project_root / "debug"
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    try:
        debug_dir.mkdir(parents=True, exist_ok=True)
        path = debug_dir / f"{source}_{timestamp}.pdf"
        path.write_bytes(pdf_bytes)
        logger.info("Debug copy saved: %s", path.resolve())
    except Exception as e:
        logger.warning("Could not save debug PDF copy: %s", e)


# Try to import PDF generation libraries
try:
    import markdown

    PDF_GENERATION_AVAILABLE = True
except ImportError:
    PDF_GENERATION_AVAILABLE = False
    logger.warning("markdown not available. PDF generation will not work.")

try:
    from weasyprint import HTML

    WEASYPRINT_AVAILABLE = True
except (ImportError, OSError) as e:
    WEASYPRINT_AVAILABLE = False
    logger.warning(f"weasyprint not available. PDF generation will not work. Error: {str(e)}")

try:
    from playwright.async_api import async_playwright

    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    async_playwright = None
    logger.info(
        "playwright not installed. PDF will use WeasyPrint (install playwright for more reliable margins)."
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
    if not WEASYPRINT_AVAILABLE:
        raise ImportError("weasyprint library is not installed. Cannot generate PDF.")

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
        # Remove carriage returns and normalize line feeds to spaces (HTML doesn't need them)
        html_content = html_content.replace("\r", "").replace("\n", " ")
        # Collapse multiple spaces to single space
        html_content = re.sub(r" +", " ", html_content)

        # Extract print properties with defaults
        margins = print_properties.get("margins", {})
        font_family = print_properties.get("fontFamily", "Times New Roman")
        font_size = print_properties.get("fontSize", 12)
        line_height = print_properties.get("lineHeight", 1.6)
        page_size = print_properties.get("pageSize", {"width": 8.5, "height": 11.0})
        use_default_fonts = print_properties.get("useDefaultFonts", False)

        # Use @page margin: 0 and body padding for margins so all four sides are reliably inset
        # (WeasyPrint can ignore @page margin-right in some cases; body padding always applies)
        mt, mr, mb, ml = (
            margins.get("top", 1.0),
            margins.get("right", 0.75),
            margins.get("bottom", 0.25),
            margins.get("left", 0.75),
        )
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: {page_size['width']}in {page_size['height']}in;
                    margin: 0;
                }}
                body {{
                    font-family: "{font_family}", serif;
                    font-size: {font_size}pt;
                    line-height: {line_height};
                    margin: 0;
                    padding: {mt}in {mr}in {mb}in {ml}in;
                    box-sizing: border-box;
                    color: #000;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    font-weight: bold;
                    margin-top: 1em;
                    margin-bottom: 0.5em;
                    page-break-after: avoid;
                }}
                h1 {{ font-size: 2em; }}
                h2 {{ font-size: 1.5em; }}
                h3 {{ font-size: 1.25em; }}
                h4 {{ font-size: 1.1em; }}
                h5 {{ font-size: 1em; }}
                h6 {{ font-size: 0.9em; }}
                strong, b {{ font-weight: bold; }}
                em, i {{ font-style: italic; }}
                ul, ol {{
                    margin: 1em 0;
                    padding-left: 2em;
                }}
                li {{
                    margin: 0.5em 0;
                }}
                p {{
                    margin: 0.5em 0;
                }}
                code {{
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: "Courier New", monospace;
                    font-size: 0.9em;
                }}
                pre {{
                    background-color: #f4f4f4;
                    padding: 10px;
                    border-radius: 3px;
                    page-break-inside: avoid;
                }}
                pre code {{
                    background-color: transparent;
                    padding: 0;
                }}
                blockquote {{
                    border-left: 4px solid #ddd;
                    padding-left: 1em;
                    margin: 1em 0;
                    font-style: italic;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                    page-break-inside: avoid;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                a {{
                    color: #0066cc;
                    text-decoration: underline;
                }}
                hr {{
                    border: none;
                    border-top: 1px solid #ddd;
                    margin: 1em 0;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF using WeasyPrint
        pdf_bytes = HTML(string=styled_html).write_pdf()

        # For testing: save a copy in the debug folder
        _save_debug_pdf(pdf_bytes, "generate_pdf")

        # Encode to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        logger.info(f"Successfully generated PDF from Markdown ({len(pdf_bytes)} bytes)")
        return pdf_base64

    except Exception as e:
        logger.error(f"Error generating PDF from Markdown: {str(e)}")
        raise Exception(f"Failed to generate PDF: {str(e)}")


async def _generate_pdf_via_playwright(html_content: str, print_properties: Dict) -> bytes:
    """
    Generate PDF using Playwright (Chromium) Async API. Safe to call from asyncio.
    Margins are applied via page.pdf(margin={...}) so Chromium applies them on every page.
    """
    margins = print_properties.get("margins", {})
    font_family = print_properties.get("fontFamily", "Times New Roman")
    font_size = print_properties.get("fontSize", 12)
    line_height = print_properties.get("lineHeight", 1.6)
    page_size = print_properties.get("pageSize", {"width": 8.5, "height": 11.0})
    use_default_fonts = print_properties.get("useDefaultFonts", False)

    margin_top = margins.get("top", 1.0)
    margin_right = margins.get("right", 0.75)
    margin_bottom = margins.get("bottom", 0.75)
    margin_left = margins.get("left", 0.75)
    width_in = page_size.get("width", 8.5)
    height_in = page_size.get("height", 11.0)

    body_style = "margin: 0; padding: 0; box-sizing: border-box;"
    if not use_default_fonts:
        if font_family and str(font_family).strip().lower() == "default":
            body_style += " font-family: Arial, sans-serif; font-size: 12pt; line-height: {0}; color: #000;".format(
                line_height
            )
        else:
            body_style += f' font-family: "{font_family}", serif; font-size: {font_size}pt; line-height: {line_height}; color: #000;'

    # Apply user margins in @page so Chromium respects them (API margin can be ignored when prefer_css_page_size is True)
    logger.info(
        "Playwright PDF margins (in): top=%s, right=%s, bottom=%s, left=%s",
        margin_top,
        margin_right,
        margin_bottom,
        margin_left,
    )
    html_doc = f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8">
<style>
@page {{
  size: {width_in}in {height_in}in;
  margin: {margin_top}in {margin_right}in {margin_bottom}in {margin_left}in;
}}
*, *::before, *::after {{ box-sizing: border-box; }}
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
.print-content p {{ page-break-inside: avoid; margin: 0 0 0.2em 0; }}
.print-content br {{ display: block; margin-top: 0.12em; }}
</style>
</head>
<body>
<div class="print-content">{html_content}</div>
</body>
</html>"""

    # Margins applied via @page in HTML above; prefer_css_page_size so Chromium uses CSS for size and margin
    pdf_options = {
        "prefer_css_page_size": True,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    }
    if not (abs(width_in - 8.5) < 0.01 and abs(height_in - 11.0) < 0.01):
        pdf_options["width"] = f"{width_in}in"
        pdf_options["height"] = f"{height_in}in"

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
            ],
        )
        page = await browser.new_page()
        await page.set_content(html_doc, wait_until="networkidle")
        pdf_bytes = await page.pdf(**pdf_options)
        await browser.close()

    return pdf_bytes


def _generate_pdf_via_weasyprint(html_content: str, print_properties: Dict) -> bytes:
    """
    Generate PDF from HTML using WeasyPrint. Uses @page with explicit size and
    margins so WeasyPrint handles page breaks correctly on every page. Page-break
    CSS (orphans, widows, page-break-inside/after) is applied per WeasyPrint docs.
    Use when PRINT_PREVIEW_USE_WEASYPRINT_ONLY is True or as fallback when Playwright fails.
    """
    margins = print_properties.get("margins", {})
    font_family = print_properties.get("fontFamily", "Times New Roman")
    font_size = print_properties.get("fontSize", 12)
    line_height = print_properties.get("lineHeight", 1.6)
    page_size = print_properties.get("pageSize", {"width": 8.5, "height": 11.0})
    use_default_fonts = print_properties.get("useDefaultFonts", False)

    margin_top = margins.get("top", 1.0)
    margin_right = margins.get("right", 0.75)
    margin_bottom = margins.get("bottom", 0.75)
    margin_left = margins.get("left", 0.75)
    width_in = page_size.get("width", 8.5)
    height_in = page_size.get("height", 11.0)

    # Body: no padding (margins are in @page). Orphans/widows 1 so breaks are more natural (2 can force weird spots).
    body_style = (
        "margin: 0; padding: 0; box-sizing: border-box; max-width: 100%; "
        "orphans: 1; widows: 1; hyphens: none;"
    )
    if not use_default_fonts:
        if font_family and str(font_family).strip().lower() == "default":
            body_style += " font-family: Arial, sans-serif; font-size: 12pt; line-height: {0}; color: #000;".format(
                line_height
            )
        else:
            body_style += f' font-family: "{font_family}", serif; font-size: {font_size}pt; line-height: {line_height}; color: #000;'

    wrapper = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        /* Critical: @page with size and margins so WeasyPrint handles breaks on every page */
        @page {{
            size: {width_in}in {height_in}in;
            margin: {margin_top}in {margin_right}in {margin_bottom}in {margin_left}in;
        }}
        *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ {body_style} }}
        /* Baseline only on body; we do not set font on .print-content or .print-content * so inline font/size/family win */
        /* Minimal p margin so any remaining <p> from rich editor don't add extra line height in PDF */
        .print-content p {{ margin: 0 0 0.2em 0; padding: 0; }}
        /* Single <br /> = one line break; keep margin small so PDF matches on-screen spacing */
        .print-content br {{ display: block; margin-top: 0.12em; }}
        /* Keep heading with the next block (avoid break right after a heading) */
        .print-content h1, .print-content h2, .print-content h3 {{
            page-break-after: avoid;
            margin: 0;
            padding: 0;
        }}
        /* Do NOT use page-break-inside: avoid on .letter-section: it forces the whole body
           onto the next page when the first section is just header/company, causing a
           break right after the company name. Let content flow naturally; paragraphs
           and headings still control breaks. */
        /* Optional: frontend can add <div class="page-break"></div> to force a new page */
        .print-content .page-break {{ page-break-after: always; }}
        .print-content {{
            max-width: 100%;
            width: 100%;
            /* WeasyPrint does not support overflow-x; use overflow-wrap for long words */
            overflow-wrap: break-word;
            word-wrap: break-word;
            word-break: normal;
            hyphens: none;
        }}
        .print-content * {{ max-width: 100%; }}
        .print-content table {{ table-layout: fixed; width: 100% !important; }}
        .print-content img, .print-content pre, .print-content code {{ max-width: 100%; }}
    </style>
</head>
<body>
<div class="print-content">{html_content}</div>
</body>
</html>
"""
    return HTML(string=wrapper).write_pdf()


def _generate_pdf_raw_html(html_content: str, print_properties: Dict) -> bytes:
    """
    Generate PDF from raw HTML with minimal wrapper only: no @page, no .print-content.
    Uses print_properties font size so WeasyPrint default (e.g. 16px) doesn't make text too large.
    Use when PRINT_PREVIEW_RAW_HTML is True.
    """
    font_family = print_properties.get("fontFamily", "Times New Roman")
    font_size = print_properties.get("fontSize", 12)
    line_height = print_properties.get("lineHeight", 1.6)
    use_default_fonts = print_properties.get("useDefaultFonts", False)
    body_css = "margin: 0; padding: 0;"
    if not use_default_fonts:
        body_css += f' font-family: "{font_family}", serif; font-size: {font_size}pt; line-height: {line_height};'
    minimal = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  body {{ {body_css} }}
  p, div, h1, h2, h3, ul, ol, li {{ margin: 0; padding: 0; }}
</style>
</head>
<body>
{html_content}
</body>
</html>"""
    return HTML(string=minimal).write_pdf()


async def generate_pdf_from_html(html_content: str, print_properties: Dict) -> str:
    """
    Generate a PDF from HTML content using user print preferences.
    Uses Playwright (Chromium) only for now; WeasyPrint is disabled for print preview.
    Set PRINT_PREVIEW_USE_WEASYPRINT_ONLY later to switch to WeasyPrint exclusively.

    Args:
        html_content: The HTML fragment to convert (placed inside body).
        print_properties: User print preferences (same shape as generate_pdf_from_markdown).

    Returns:
        Base64-encoded PDF data as a string (without data URI prefix).

    Raises:
        ImportError: If playwright is not available.
        Exception: If PDF generation fails (no WeasyPrint fallback).
    """
    font_family = print_properties.get("fontFamily", "Times New Roman")
    font_size = print_properties.get("fontSize", 12)

    # Normalize for PDF: merge </p><p> to <br /> (editor-friendly HTML → compact PDF), collapse redundant <br />, then \n → <br />
    html_content = _normalize_html_for_pdf(html_content)
    html_content = _normalize_line_breaks_in_html(html_content)

    # Raw HTML: minimal wrapper (requires WeasyPrint; if disabled, use Playwright path instead)
    if settings.PRINT_PREVIEW_RAW_HTML:
        if not WEASYPRINT_AVAILABLE:
            raise ImportError(
                "PRINT_PREVIEW_RAW_HTML is True but WeasyPrint is disabled for print preview."
            )
        pdf_bytes = _generate_pdf_raw_html(html_content, print_properties)
        _save_debug_pdf(pdf_bytes, "print_preview_pdf_raw", html_snippet=html_content)
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
        logger.info("PDF from HTML (raw, no server styling) (%s bytes)", len(pdf_bytes))
        return pdf_base64

    # Playwright only for print preview (WeasyPrint disabled for now)
    if not PLAYWRIGHT_AVAILABLE or not async_playwright:
        raise ImportError(
            "Playwright is required for print preview PDF. "
            "Install with: pip install playwright && playwright install chromium"
        )

    pdf_bytes = await _generate_pdf_via_playwright(html_content, print_properties)
    _save_debug_pdf(pdf_bytes, "print_preview_pdf", html_snippet=html_content)
    pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")
    logger.info(
        "PDF from HTML via Playwright (%s bytes, font=%s, size=%spt)",
        len(pdf_bytes),
        font_family,
        font_size,
    )
    return pdf_base64
