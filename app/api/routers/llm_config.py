"""
LLM configuration API routes
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.core.auth import get_current_user
from app.models.user import UserResponse

try:
    from llm_config_endpoint import load_llm_config
    LLM_CONFIG_AVAILABLE = True
except ImportError:
    LLM_CONFIG_AVAILABLE = False
    logging.warning("llm_config_endpoint module not available")

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["llm-config"],
    dependencies=[Depends(get_current_user)]
)


@router.get("/llms")
async def get_llms(current_user: UserResponse = Depends(get_current_user)):
    """
    Get available LLM models configuration.
    Requires authentication.
    
    Returns:
        JSON response with llms array, defaultModel, and internalModel
        
    Raises:
        HTTPException: If configuration cannot be loaded or user is not authenticated
    """
    if not LLM_CONFIG_AVAILABLE:
        raise HTTPException(
            status_code=500,
            detail="LLM configuration module not available"
        )
    
    try:
        config = load_llm_config()
        return JSONResponse(content=config)
    except FileNotFoundError as e:
        logger.error(f"LLM configuration file not found: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"LLM configuration file not found: {str(e)}"
        )
    except ValueError as e:
        logger.error(f"Invalid LLM configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Invalid LLM configuration: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to load LLM configuration: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load LLM configuration: {str(e)}"
        )

