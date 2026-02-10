"""
PDF generation related Pydantic models
"""

from pydantic import BaseModel, Field
from typing import Optional


class Margins(BaseModel):
    top: float
    right: float
    bottom: float
    left: float


class PageSize(BaseModel):
    width: float
    height: float


class PrintProperties(BaseModel):
    margins: Margins
    fontFamily: Optional[str] = "Times New Roman"
    fontSize: Optional[float] = 12
    lineHeight: Optional[float] = 1.6
    pageSize: Optional[PageSize] = Field(default_factory=lambda: PageSize(width=8.5, height=11.0))
    useDefaultFonts: Optional[bool] = False


class GeneratePDFRequest(BaseModel):
    markdownContent: str
    printProperties: PrintProperties
    user_id: Optional[str] = None
    user_email: Optional[str] = None


class PrintPreviewPDFRequest(BaseModel):
    """Request body for Print Preview. HTML is source of truth: send htmlContent. markdownContent accepted for backward compatibility."""

    htmlContent: Optional[str] = None
    markdownContent: Optional[str] = None
    printProperties: (
        PrintProperties  # User settings: margins, font (if not default), page size, line height
    )
    user_id: Optional[str] = None
    user_email: Optional[str] = None
