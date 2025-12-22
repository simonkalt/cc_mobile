# Service Refactoring Guide

This document outlines the remaining service extraction work needed to complete the refactoring.

## ✅ Completed Utilities

1. **PDF Utilities** (`app/utils/pdf_utils.py`)
   - `read_pdf_from_bytes()` - Extract text from PDF bytes
   - `read_pdf_file()` - Read PDF from local filesystem

2. **S3 Utilities** (`app/utils/s3_utils.py`)
   - `get_s3_client()` - Get S3 client with credentials
   - `download_pdf_from_s3()` - Download PDF from S3
   - `ensure_user_s3_folder()` - Ensure user S3 folder exists
   - `ensure_cover_letter_subfolder()` - Ensure cover letter subfolder exists

3. **LLM Utilities** (`app/utils/llm_utils.py`)
   - `load_system_prompt()` - Load system prompt from config
   - `post_to_llm()` - Send prompt to LLM and get response

4. **PDF Service** (`app/services/pdf_service.py`)
   - `generate_pdf_from_markdown()` - Generate PDF from markdown content

## 📋 Remaining Service Extraction

### 1. Cover Letter Service (`app/services/cover_letter_service.py`)

**Function to extract:** `get_job_info()` from `main.py` (lines ~1005-1400)

**Dependencies:**
- `app/utils/pdf_utils.py` - For reading PDFs
- `app/utils/s3_utils.py` - For S3 operations
- `app/utils/llm_utils.py` - For LLM communication
- `app/services/user_service.py` - For user profile retrieval
- `app/core/config.py` - For configuration

**Key responsibilities:**
- Resume PDF reading (base64, S3, local file)
- User personality profile retrieval
- Cover letter generation via LLM
- Return markdown and HTML formats

**Steps:**
1. Create `app/services/cover_letter_service.py`
2. Copy `get_job_info()` function
3. Update imports to use new utilities
4. Update `app/api/routers/cover_letter.py` to import from service
5. Test thoroughly

### 2. File Service (`app/services/file_service.py`)

**Functions to extract from `main.py`:**
- File upload logic (already in router, but should be in service)
- File rename logic
- File delete logic
- File listing logic

**Dependencies:**
- `app/utils/s3_utils.py`
- `app/services/user_service.py`

**Steps:**
1. Create `app/services/file_service.py`
2. Extract file management business logic
3. Update `app/api/routers/files.py` to use service
4. Test thoroughly

### 3. LLM Configuration Service (`app/services/llm_config_service.py`)

**Functions to extract:**
- `get_available_llms()` from `main.py`
- LLM model normalization logic

**Dependencies:**
- `app/core/config.py`
- `app/utils/llm_utils.py`

## 🔄 Migration Strategy

### Phase 1: Update Routers to Use New Utilities
- Update `app/api/routers/files.py` to use `app/utils/s3_utils.py`
- Update `app/api/routers/pdf.py` to use `app/services/pdf_service.py`
- Update `app/api/routers/cover_letter.py` to use utilities

### Phase 2: Extract Cover Letter Service
- Create `app/services/cover_letter_service.py`
- Move `get_job_info()` logic
- Update router to use service

### Phase 3: Extract File Service
- Create `app/services/file_service.py`
- Move file management logic
- Update router to use service

### Phase 4: Cleanup
- Remove old function definitions from `main.py`
- Update all imports
- Remove temporary import workarounds

## 📝 Notes

- The current routers import functions from `main.py` temporarily
- This allows gradual migration without breaking functionality
- Once services are extracted, routers should only import from `app/` modules
- Test each migration step before proceeding

## 🧪 Testing

After each service extraction:
1. Run existing tests
2. Test API endpoints manually
3. Verify no regressions
4. Check logs for errors

## 📚 Example: Cover Letter Service Structure

```python
# app/services/cover_letter_service.py
from app.models.cover_letter import JobInfoRequest
from app.utils.pdf_utils import read_pdf_from_bytes, read_pdf_file
from app.utils.s3_utils import download_pdf_from_s3, get_s3_client
from app.utils.llm_utils import post_to_llm, load_system_prompt
from app.services.user_service import get_user_by_id, get_user_by_email

def generate_cover_letter(request: JobInfoRequest) -> dict:
    """Generate cover letter based on job information"""
    # 1. Process resume (PDF reading)
    # 2. Get user personality profile
    # 3. Build prompt
    # 4. Call LLM
    # 5. Return markdown and HTML
    pass
```

## 🎯 Priority

1. **High Priority:** Cover Letter Service (most complex, most used)
2. **Medium Priority:** File Service (well-defined, easier to extract)
3. **Low Priority:** LLM Config Service (simple, can wait)

