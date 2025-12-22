"""
Cover letter generation API routes
"""
import logging
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse

from app.models.cover_letter import JobInfoRequest, ChatRequest
from app.services.cover_letter_service import get_job_info

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["cover-letter"])


@router.post("/job-info")
async def handle_job_info(request: JobInfoRequest):
    """Generate cover letter based on job information"""
    logger.info(
        f"Received job info request for LLM: {request.llm}, Company: {request.company_name}"
    )
    result = get_job_info(
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
            result = get_job_info(
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

