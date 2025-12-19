"""
FastAPI endpoint for LLM configuration management.

This module provides an endpoint to fetch available LLM models from a JSON configuration file.
"""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import json
import os
from pathlib import Path
from typing import Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Path to LLM configuration file
# Default: same directory as this file
# Can be overridden with LLM_CONFIG_PATH environment variable
LLM_CONFIG_PATH = Path(
    os.getenv("LLM_CONFIG_PATH", Path(__file__).parent / "llms-config.json")
)

# Cache for LLM configuration
_llm_config_cache: Optional[Dict] = None
_cache_timestamp: Optional[float] = None


def load_llm_config() -> Dict:
    """
    Load LLM configuration from JSON file.
    Uses caching to avoid repeated file reads.
    
    Returns:
        Dict containing llms array, defaultModel, and internalModel
        
    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config file is invalid or missing required fields
        json.JSONDecodeError: If config file is invalid JSON
    """
    global _llm_config_cache, _cache_timestamp
    
    # Check if cache is still valid (optional: implement cache invalidation)
    # For now, reload on every request or implement file watching
    
    try:
        if not LLM_CONFIG_PATH.exists():
            raise FileNotFoundError(
                f"LLM configuration file not found at {LLM_CONFIG_PATH}"
            )
        
        with open(LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        # Validate configuration structure
        if not isinstance(config, dict):
            raise ValueError("Configuration must be a JSON object")
        
        if "llms" not in config:
            raise ValueError("Configuration must contain 'llms' array")
        
        if not isinstance(config["llms"], list):
            raise ValueError("'llms' must be an array")
        
        # Validate each LLM entry
        for i, llm in enumerate(config["llms"]):
            if not isinstance(llm, dict):
                raise ValueError(f"LLM entry at index {i} must be an object")
            if "value" not in llm:
                raise ValueError(f"LLM entry at index {i} must have 'value' field")
            if "label" not in llm:
                raise ValueError(f"LLM entry at index {i} must have 'label' field")
        
        # Validate defaultModel exists in llms (if specified)
        if "defaultModel" in config and config["defaultModel"]:
            default_value = config["defaultModel"]
            if not any(llm["value"] == default_value for llm in config["llms"]):
                raise ValueError(
                    f"defaultModel '{default_value}' not found in llms array"
                )
        
        # Validate internalModel exists in llms (if specified)
        if "internalModel" in config and config["internalModel"]:
            internal_value = config["internalModel"]
            if not any(llm["value"] == internal_value for llm in config["llms"]):
                raise ValueError(
                    f"internalModel '{internal_value}' not found in llms array"
                )
        
        _llm_config_cache = config
        logger.info(f"Successfully loaded LLM configuration from {LLM_CONFIG_PATH}")
        return config
        
    except FileNotFoundError as e:
        logger.error(f"LLM configuration file not found: {e}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in LLM configuration file: {e}")
        raise ValueError(f"Invalid JSON in configuration file: {e}")
    except Exception as e:
        logger.error(f"Error loading LLM configuration: {e}")
        raise


def get_llms_endpoint(app: FastAPI):
    """
    Register the LLM configuration endpoint with the FastAPI app.
    
    Args:
        app: FastAPI application instance
    """
    
    @app.get("/api/llms")
    async def get_llms():
        """
        Get available LLM models configuration.
        
        Returns:
            JSON response with llms array, defaultModel, and internalModel
            
        Raises:
            HTTPException: If configuration cannot be loaded
        """
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


# Example usage:
# In your main FastAPI app file:
# from llm_config_endpoint import get_llms_endpoint
# app = FastAPI()
# get_llms_endpoint(app)

