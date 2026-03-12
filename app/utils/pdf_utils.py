"""
PDF reading and processing utilities
"""
import logging
import os
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

# Try to import PyMuPDF (fitz) for markdown/layout-aware extraction.
_fitz_module = None
PYMUPDF_AVAILABLE = False
try:
    import fitz  # type: ignore[import-untyped]

    _fitz_module = fitz
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


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


def read_pdf_markdown_from_bytes(pdf_bytes: bytes) -> str:
    """
    Extract markdown-like text from PDF bytes with layout-aware parsing.
    Prefers PyMuPDF markdown extraction when available; falls back to plain text.
    """
    # Prefer PyMuPDF for richer structure (headings/lists/paragraphs).
    if PYMUPDF_AVAILABLE and _fitz_module is not None:
        try:
            pdf_file = BytesIO(pdf_bytes)
            pdf_document = _fitz_module.open(stream=pdf_file, filetype="pdf")
            page_count = len(pdf_document)
            chunks = []
            try:
                for page_num in range(page_count):
                    page = pdf_document[page_num]
                    # Newer PyMuPDF supports markdown extraction directly.
                    md = page.get_text("markdown")
                    if md:
                        chunks.append(str(md).strip())
            finally:
                pdf_document.close()

            markdown_text = "\n\n".join([c for c in chunks if c]).strip()
            if markdown_text:
                logger.info(
                    f"Successfully extracted markdown from PDF using PyMuPDF ({page_count} pages)"
                )
                return markdown_text
        except Exception as e:
            logger.warning(f"PyMuPDF markdown extraction failed, falling back to plain text: {e}")

    # Fallback to plain text extraction path.
    return read_pdf_from_bytes(pdf_bytes)


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

