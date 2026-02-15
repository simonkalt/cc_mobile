"""
Cover letter related Pydantic models
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict


class ChatRequest(BaseModel):
    prompt: str
    active_model: str = "gpt-4.1"  # Default model

    class Config:
        # Allow extra fields to be ignored
        extra = "ignore"


class JobInfoRequest(BaseModel):
    llm: str
    date_input: str
    company_name: str
    hiring_manager: str
    ad_source: str
    resume: str  # Can be: plain text, S3 key (user_id/filename.pdf), or base64-encoded PDF
    jd: str  # Job description
    additional_instructions: str = ""
    tone: str = "Professional"
    address: str = ""  # City, State
    phone_number: str = ""
    user_id: Optional[str] = None  # Optional user ID to access custom personality profiles
    user_email: Optional[str] = None  # Optional user email to access custom personality profiles


class CoverLetterWithTextResumeRequest(BaseModel):
    """Request model for generating cover letter with pasted resume text"""
    llm: str
    date_input: str
    company_name: str
    hiring_manager: str
    ad_source: str
    resume_text: str  # Plain text resume content (pasted by user)
    jd: str  # Job description
    additional_instructions: str = ""
    tone: str = "Professional"
    address: str = ""  # City, State
    phone_number: str = ""
    user_id: Optional[str] = None  # Optional user ID to access custom personality profiles
    user_email: Optional[str] = None  # Optional user email to access custom personality profiles


class SaveCoverLetterRequest(BaseModel):
    coverLetterContent: str  # The cover letter content (markdown text, or base64-encoded DOCX/PDF)
    fileName: Optional[str] = None  # Optional custom filename (without extension)
    contentType: str = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"  # "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/pdf", "text/markdown"
    user_id: Optional[str] = None
    user_email: Optional[str] = None


class CoverLetterRequest(BaseModel):
    key: str  # S3 key (user_id/generated_cover_letters/filename)
    user_id: Optional[str] = None
    user_email: Optional[str] = None


class DocxTemplateHints(BaseModel):
    version: str = "1.0"
    sourceFormat: str = "markdown"
    outputFormat: str = "docx"
    styleProfile: str = "cover_letter_standard"
    fields: Dict[str, str] = Field(default_factory=dict)


class CoverLetterGenerationResponse(BaseModel):
    markdown: str
    docxTemplateHints: DocxTemplateHints

