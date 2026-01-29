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
    fontSize: Optional[float] = 11  # Match user settings default; use as-is (no scaling)
    lineHeight: Optional[float] = 1.15  # Match user settings default
    pageSize: Optional[PageSize] = Field(default_factory=lambda: PageSize(width=8.5, height=11.0))
    useDefaultFonts: Optional[bool] = False


class GeneratePDFRequest(BaseModel):
    markdownContent: str
    printProperties: PrintProperties
    user_id: Optional[str] = None
    user_email: Optional[str] = None
