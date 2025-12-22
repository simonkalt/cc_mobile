"""
PDF generation related Pydantic models
"""
from pydantic import BaseModel


class Margins(BaseModel):
    top: float
    right: float
    bottom: float
    left: float


class PageSize(BaseModel):
    width: float
    height: float


class GeneratePDFRequest(BaseModel):
    htmlContent: str
    margins: Margins
    pageSize: PageSize
    fontFamily: str = "Georgia"
    fontSize: float = 11.0
    lineHeight: float = 1.15
    useDefaultFonts: bool = False

