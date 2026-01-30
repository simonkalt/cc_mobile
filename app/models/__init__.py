"""Pydantic models for request/response validation"""

# Import all models for easy access
from app.models.user import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
    PrintMargins,
    PageSize as UserPageSize,
    PrintProperties,
    PersonalityProfile,
    AppSettings,
    UserPreferences,
)

from app.models.cover_letter import (
    ChatRequest,
    JobInfoRequest,
    SaveCoverLetterRequest,
    CoverLetterRequest,
)

from app.models.file import (
    FileUploadRequest,
    FileRenameRequest,
    FileDeleteRequest,
)

from app.models.pdf import (
    Margins,
    PageSize,
    GeneratePDFRequest,
    PrintPreviewPDFRequest,
)

from app.models.job import (
    JobURLAnalysisRequest,
)

__all__ = [
    # User models
    "UserRegisterRequest",
    "UserUpdateRequest",
    "UserResponse",
    "UserLoginRequest",
    "UserLoginResponse",
    "PrintMargins",
    "UserPageSize",
    "PrintProperties",
    "PersonalityProfile",
    "AppSettings",
    "UserPreferences",
    # Cover letter models
    "ChatRequest",
    "JobInfoRequest",
    "SaveCoverLetterRequest",
    "CoverLetterRequest",
    # File models
    "FileUploadRequest",
    "FileRenameRequest",
    "FileDeleteRequest",
    # PDF models
    "Margins",
    "PageSize",
    "GeneratePDFRequest",
    "PrintPreviewPDFRequest",
    # Job models
    "JobURLAnalysisRequest",
]
