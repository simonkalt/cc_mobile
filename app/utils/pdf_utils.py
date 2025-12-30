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
try:
    import fitz  # PyMuPDF
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
    # Try to import fitz if not already available (in case it was installed after module load)
    if not PYMUPDF_AVAILABLE:
        try:
            import fitz
            # Update the global flag
            globals()['PYMUPDF_AVAILABLE'] = True
            globals()['fitz'] = fitz
            logger.info("PyMuPDF (fitz) imported successfully on demand")
        except ImportError:
            raise ImportError("PyMuPDF (fitz) is not installed. Cannot convert PDF to HTML. Install with: pip install pymupdf")
    
    # Use fitz from globals or import it
    if 'fitz' not in globals():
        import fitz
    
    try:
        # Open PDF from bytes
        pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
        
        # Extract HTML using PyMuPDF's built-in HTML conversion
        # This preserves layout, fonts, and formatting automatically
        html_content = ""
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            # Use get_text("xhtml") which outputs HTML with layout preserved
            page_html = page.get_text("xhtml")
            html_content += page_html
            
            # Add page break between pages (except last page)
            if page_num < len(pdf_document) - 1:
                html_content += '<div style="page-break-after: always;"></div>'
        
        pdf_document.close()
        
        # Wrap in a proper HTML document structure if needed
        # PyMuPDF's xhtml output should already be valid HTML, but we'll ensure it has proper structure
        if not html_content.strip().startswith('<!DOCTYPE'):
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
    </style>
</head>
<body>
{html_content}
</body>
</html>"""
        else:
            # Already has DOCTYPE, just return as-is
            html_document = html_content
        
        logger.info(f"Successfully converted PDF to HTML using PyMuPDF ({len(pdf_document)} pages)")
        return html_document
        
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

