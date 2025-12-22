"""
File management related Pydantic models
"""
from pydantic import BaseModel
from typing import Optional


class FileUploadRequest(BaseModel):
    fileName: str
    fileData: str  # base64 encoded
    contentType: str = "application/pdf"
    user_id: Optional[str] = None
    user_email: Optional[str] = None


class FileRenameRequest(BaseModel):
    oldKey: str  # Current S3 key (user_id/filename)
    newFileName: str  # New filename (just the filename, not the full path)
    user_id: Optional[str] = None
    user_email: Optional[str] = None


class FileDeleteRequest(BaseModel):
    key: str  # S3 key (user_id/filename)
    user_id: Optional[str] = None
    user_email: Optional[str] = None

