"""
Cover letter generation API routes
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.models.cover_letter import JobInfoRequest, ChatRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cover-letter"])

# Import get_job_info from main.py
# TODO: Refactor get_job_info into app/services/cover_letter_service.py
# For now, we'll import it dynamically to avoid circular imports
JOB_INFO_AVAILABLE = False
get_job_info = None

def _load_job_info_function():
    """Lazy load get_job_info function from main.py"""
    global get_job_info, JOB_INFO_AVAILABLE
    if JOB_INFO_AVAILABLE:
        return get_job_info
    
    try:
        # Import the function from main.py
        import main as main_module
        if hasattr(main_module, 'get_job_info'):
            get_job_info = main_module.get_job_info
            JOB_INFO_AVAILABLE = True
            logger.info("Successfully loaded get_job_info from main.py")
        else:
            logger.warning("get_job_info not found in main.py")
    except Exception as e:
        logger.warning(f"Could not import get_job_info from main.py: {e}")
    
    return get_job_info


@router.post("/job-info")
async def handle_job_info(request: JobInfoRequest):
    """Generate cover letter based on job information"""
    func = _load_job_info_function()
    if not func:
        raise HTTPException(
            status_code=500,
            detail="Cover letter generation service not available"
        )
    
    logger.info(
        f"Received job info request for LLM: {request.llm}, Company: {request.company_name}"
    )
    result = func(
        llm=request.llm,
        date_input=request.date_input,
        company_name=request.company_name,
        hiring_manager=request.hiring_manager,
        ad_source=request.ad_source,
        resume=request.resume,
        jd=request.jd,
        additional_instructions=request.additional_instructions,
        tone=request.tone,
        address=request.address,
        phone_number=request.phone_number,
        user_id=request.user_id,
        user_email=request.user_email,
    )
    return result


@router.post("/chat")
async def handle_chat(request: Request):
    """Handle both simple chat requests and job info requests"""
    func = _load_job_info_function()
    if not func:
        raise HTTPException(
            status_code=500,
            detail="Cover letter generation service not available"
        )
    
    try:
        body = await request.json()

        # Check if this is a job info request (has 'llm', 'company_name', etc.)
        if "llm" in body and "company_name" in body:
            logger.info(
                "Detected job info request in /chat endpoint, routing to job-info handler"
            )
            # Check for required user identification
            if not body.get("user_id") and not body.get("user_email"):
                logger.error("Job info request missing user_id or user_email")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "user_id or user_email is required",
                        "detail": "Please provide either 'user_id' or 'user_email' in your request to access personality profiles.",
                    },
                )
            # Convert to JobInfoRequest and handle it
            job_request = JobInfoRequest(**body)
            result = func(
                llm=job_request.llm,
                date_input=job_request.date_input,
                company_name=job_request.company_name,
                hiring_manager=job_request.hiring_manager,
                ad_source=job_request.ad_source,
                resume=job_request.resume,
                jd=job_request.jd,
                additional_instructions=job_request.additional_instructions,
                tone=job_request.tone,
                address=job_request.address,
                phone_number=job_request.phone_number,
                user_id=job_request.user_id,
                user_email=job_request.user_email,
            )
            return result
        else:
            # Handle as regular chat request
            chat_request = ChatRequest(**body)
            # TODO: Implement chat functionality or return error
            logger.warning("Chat endpoint not fully implemented in refactored structure")
            return JSONResponse(
                status_code=501,
                content={"error": "Chat functionality not yet migrated"}
            )
    except Exception as e:
        logger.error(f"Error handling chat request: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

