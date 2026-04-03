"""
Cover letter related Pydantic models
"""
from pydantic import BaseModel, ConfigDict, Field
from typing import Optional, Dict, Any


class ChatRequest(BaseModel):
    prompt: str
    active_model: str = "gpt-4.1"  # Default model

    class Config:
        # Allow extra fields to be ignored
        extra = "ignore"


class JobInfoRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

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
    client_generate_start_ms: Optional[int] = None  # Optional: epoch ms from frontend click on "Generate Letter"
    print_properties: Optional[Dict[str, Any]] = None  # Optional: margins (inches), fontFamily, fontSize, lineHeight, pageSize; applied when building .docx
    # Optional: use this layout for this generation (overrides DB if present). Matches GET /api/letter-templates name + index.
    letter_template_name: Optional[str] = Field(None, alias="letterTemplateName")
    letter_template_index: Optional[Any] = Field(None, alias="letterTemplateIndex")
    letter_template_auto_pick: Optional[bool] = Field(None, alias="letterTemplateAutoPick")


class CoverLetterWithTextResumeRequest(BaseModel):
    """Request model for generating cover letter with pasted resume text"""
    model_config = ConfigDict(populate_by_name=True)

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
    client_generate_start_ms: Optional[int] = None  # Optional: epoch ms from frontend click on "Generate Letter"
    print_properties: Optional[Dict[str, Any]] = None  # Optional: margins (inches), fontFamily, fontSize, lineHeight, pageSize; applied when building .docx
    letter_template_name: Optional[str] = Field(None, alias="letterTemplateName")
    letter_template_index: Optional[Any] = Field(None, alias="letterTemplateIndex")
    letter_template_auto_pick: Optional[bool] = Field(None, alias="letterTemplateAutoPick")


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
    style: Dict[str, Any] = Field(default_factory=dict)
    styleInstructions: str = ""


class CoverLetterGenerationResponse(BaseModel):
    """Docx-only contract: .docx is the single formatted artifact; optional content is plain text."""
    docxBase64: Optional[str] = None  # .docx file (base64); display/edit this; PDF export via Syncfusion (.NET), not POST /api/files/docx-to-pdf
    docxTemplateHints: DocxTemplateHints
    content: Optional[str] = None  # Plain text of the letter (optional; frontend uses docx)
    # When USE_DOCX_COMPONENTS=true, LLM returns these; we assemble .docx from them and may echo in response
    document_xml: Optional[str] = None
    numbering_xml: Optional[str] = None
    styles_xml: Optional[str] = None

