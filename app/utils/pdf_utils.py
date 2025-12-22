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

