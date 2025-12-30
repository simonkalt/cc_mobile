"""
PDF reading and processing utilities
"""
import logging
import os
import html
import re
from io import BytesIO
from typing import Optional

logger = logging.getLogger(__name__)

# Try to import PyPDF2
try:
    import PyPDF2
    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 not available. PDF reading will not work.")

# Try to import PyMuPDF (fitz) for high-quality PDF to HTML conversion with layout preservation
_fitz_module = None
try:
    import fitz  # PyMuPDF
    _fitz_module = fitz
    PYMUPDF_AVAILABLE = True
    logger.info("PyMuPDF (fitz) is available for PDF to HTML conversion")
except ImportError as e:
    PYMUPDF_AVAILABLE = False
    logger.warning(f"PyMuPDF (fitz) not available. PDF to HTML conversion will not work. Error: {e}")


def read_pdf_from_bytes(pdf_bytes: bytes) -> str:
    """
    Extract text content from PDF bytes
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        Extracted text content as string
    """
    if not PDF_AVAILABLE:
        raise ImportError("PyPDF2 is not installed. Cannot read PDF files.")

    try:
        text_content = ""
        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(pdf_reader.pages)

        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text_content += page.extract_text()
            if page_num < num_pages - 1:
                text_content += "\n\n"

        logger.info(f"Successfully extracted text from PDF ({num_pages} pages)")
        return text_content.strip()
    except Exception as e:
        logger.error(f"Error reading PDF: {str(e)}")
        return f"[Error reading PDF: {str(e)}]"


def read_pdf_file(file_path: str) -> str:
    """
    Read PDF file from local filesystem and extract text content
    
    Args:
        file_path: Path to PDF file
        
    Returns:
        Extracted text content as string
    """
    if not PDF_AVAILABLE:
        raise ImportError("PyPDF2 is not installed. Cannot read PDF files.")

    if not os.path.exists(file_path):
        logger.warning(f"PDF file not found: {file_path}")
        return f"[PDF file not found: {file_path}]"

    try:
        with open(file_path, "rb") as file:
            pdf_bytes = file.read()
        return read_pdf_from_bytes(pdf_bytes)
    except Exception as e:
        logger.error(f"Error reading PDF file {file_path}: {str(e)}")
        return f"[Error reading PDF file: {str(e)}]"


def _fix_bullet_formatting(html_content: str) -> str:
    """
    Post-process HTML to convert bullet characters into proper HTML list elements.
    Handles various bullet characters (•, -, *, etc.) and converts them to <ul>/<li> structure.
    
    Args:
        html_content: HTML string that may contain bullet characters as text
        
    Returns:
        HTML string with bullets converted to proper list elements
    """
    try:
        from bs4 import BeautifulSoup
        
        # Parse HTML
        soup = BeautifulSoup(html_content, 'html.parser')
        
        # Find all elements that might contain bullet text
        for element in soup.find_all(['p', 'div', 'span', 'td']):
            if not element.string and not element.get_text():
                continue
            
            # Get the raw HTML content to preserve structure
            element_html = str(element)
            text_content = element.get_text(separator=' ', strip=False)
            
            if not text_content or not text_content.strip():
                continue
            
            # Look for inline bullet patterns: "● Label: description. ● Next: description."
            # Pattern matches: bullet + label (ends with colon) + description (until next bullet or end)
            bullet_pattern = r'([●•\-\*·▪▫◦‣⁃○])\s*([A-Z][^:●•\-\*·▪▫◦‣⁃○]*?):\s*([^●•\-\*·▪▫◦‣⁃○]*?)(?=\s*[●•\-\*·▪▫◦‣⁃○]|$)'
            
            # Find all bullet items in the text
            matches = list(re.finditer(bullet_pattern, text_content))
            
            if len(matches) >= 2:  # Need at least 2 bullets to make a list
                bullet_items = []
                for match in matches:
                    label = match.group(2).strip()
                    description = match.group(3).strip().rstrip('.').strip()
                    # Combine label and description for the list item
                    if description:
                        item_text = f"{label}: {description}"
                    else:
                        item_text = label
                    if item_text:
                        bullet_items.append(item_text)
                
                if bullet_items:
                    # Get text before first bullet
                    first_match_start = matches[0].start()
                    text_before = text_content[:first_match_start].strip()
                    
                    # Get text after last bullet
                    last_match_end = matches[-1].end()
                    text_after = text_content[last_match_end:].strip()
                    
                    # Create a <ul> element for the bullets
                    ul = soup.new_tag('ul')
                    ul['style'] = 'margin: 1em 0; padding-left: 2em;'
                    for item_text in bullet_items:
                        li = soup.new_tag('li')
                        li.string = item_text
                        li['style'] = 'margin: 0.5em 0;'
                        ul.append(li)
                    
                    # Replace the element content
                    element.clear()
                    if text_before:
                        before_p = soup.new_tag('p')
                        before_p.string = text_before
                        element.append(before_p)
                    element.append(ul)
                    if text_after:
                        after_p = soup.new_tag('p')
                        after_p.string = text_after
                        element.append(after_p)
        
        return str(soup)
    except ImportError:
        logger.warning("BeautifulSoup not available. Skipping bullet formatting fix.")
        return html_content
    except Exception as e:
        logger.warning(f"Error fixing bullet formatting: {e}. Returning original HTML.")
        return html_content


def convert_pdf_to_html(pdf_bytes: bytes) -> str:
    """
    Convert PDF bytes to HTML format preserving original layout and structure.
    Uses PyMuPDF (fitz) which can directly output HTML with layout preservation.
    
    Args:
        pdf_bytes: PDF file content as bytes
        
    Returns:
        HTML string representation of the PDF content that closely matches the original format
        
    Raises:
        ImportError: If PyMuPDF is not available
    """
    # Use the module-level fitz or try to import it
    global _fitz_module
    
    # If PYMUPDF_AVAILABLE is True, _fitz_module should already be set at module level
    if not PYMUPDF_AVAILABLE or _fitz_module is None:
        try:
            # Use importlib to avoid scoping issues with 'fitz' variable name
            import importlib
            fitz_module = importlib.import_module('fitz')
            _fitz_module = fitz_module
            if not PYMUPDF_AVAILABLE:
                globals()['PYMUPDF_AVAILABLE'] = True
                logger.info("PyMuPDF (fitz) imported successfully on demand")
        except ImportError:
            raise ImportError("PyMuPDF (fitz) is not installed. Cannot convert PDF to HTML. Install with: pip install pymupdf")
    
    try:
        # Open PDF from bytes using BytesIO
        # PyMuPDF needs the stream to stay open, so we use BytesIO
        pdf_file = BytesIO(pdf_bytes)
        pdf_document = _fitz_module.open(stream=pdf_file, filetype="pdf")
        
        # Extract HTML using PyMuPDF's built-in HTML conversion
        # This preserves layout, fonts, and formatting automatically
        html_content = ""
        page_count = len(pdf_document)  # Get page count before closing
        
        try:
            for page_num in range(page_count):
                page = pdf_document[page_num]
                # Use get_text("xhtml") which outputs HTML with layout preserved
                page_html = page.get_text("xhtml")
                # Ensure page_html is a string
                if page_html:
                    html_content += str(page_html)
                
                # Add page break between pages (except last page)
                if page_num < page_count - 1:
                    html_content += '<div style="page-break-after: always;"></div>'
        finally:
            # Always close the document
            pdf_document.close()
        
        logger.info(f"Successfully converted PDF to HTML using PyMuPDF ({page_count} pages)")
        return html_content
        
    except Exception as e:
        logger.error(f"Error converting PDF to HTML with PyMuPDF: {str(e)}", exc_info=True)
        raise
        
        # Create the HTML document with styling that preserves layout
        html_document = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Terms of Service</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
            background-color: #fff;
        }}
        h1, h2, h3, h4, h5, h6 {{
            margin-top: 1.5em;
            margin-bottom: 0.75em;
            color: #222;
            font-weight: 600;
        }}
        h2 {{
            font-size: 1.5em;
            margin-top: 2em;
        }}
        h3 {{
            font-size: 1.25em;
            margin-top: 1.5em;
        }}
        p {{
            margin-bottom: 1em;
            text-align: left;
            word-wrap: break-word;
        }}
        @media (max-width: 600px) {{
            body {{
                padding: 15px;
            }}
        }}
    </style>
</head>
<body>
{html_body}
</body>
</html>"""
        
        logger.info(f"Successfully converted PDF to HTML using pdfplumber ({len(pdf.pages)} pages)")
        return html_document
        
    except Exception as e:
        logger.error(f"Error converting PDF to HTML with pdfplumber: {str(e)}", exc_info=True)
        raise

