"""
LLM communication utilities
"""
import logging
import json
import os
from pathlib import Path
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)

# Try to import LLM libraries
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from google import genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def load_system_prompt() -> str:
    """
    Load system prompt from JSON config file
    
    Returns:
        System prompt string
    """
    config_path = settings.SYSTEM_PROMPT_PATH
    
    try:
        if not config_path.exists():
            logger.warning(f"System prompt file not found: {config_path}. Using default.")
            return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information. IMPORTANT: Any returned HTML must not contain backslashes (\\\\) as carriage returns or line breaks - use only whitespace characters (spaces, tabs) for formatting."
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        system_prompt = config.get("system_prompt", "")
        if not system_prompt:
            logger.warning(f"System prompt not found in {config_path}. Using default.")
            return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information. IMPORTANT: Any returned HTML must not contain backslashes (\\\\) as carriage returns or line breaks - use only whitespace characters (spaces, tabs) for formatting."

        logger.info(
            f"Loaded system prompt from {config_path} ({len(system_prompt)} characters)"
        )
        return system_prompt
    except FileNotFoundError:
        logger.warning(f"System prompt file not found: {config_path}. Using default.")
        return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information. IMPORTANT: Any returned HTML must not contain backslashes (\\\\) as carriage returns or line breaks - use only whitespace characters (spaces, tabs) for formatting."
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing system prompt JSON: {e}. Using default.")
        return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information. IMPORTANT: Any returned HTML must not contain backslashes (\\\\) as carriage returns or line breaks - use only whitespace characters (spaces, tabs) for formatting."
    except Exception as e:
        logger.error(f"Error loading system prompt: {e}. Using default.")
        return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information. IMPORTANT: Any returned HTML must not contain backslashes (\\\\) as carriage returns or line breaks - use only whitespace characters (spaces, tabs) for formatting."


def post_to_llm(prompt: str, model: str = "gpt-5.5") -> Optional[str]:
    """
    Send a prompt to an LLM and return the response
    
    Args:
        prompt: The prompt to send
        model: The model name to use
        
    Returns:
        LLM response text or None if error
    """
    return_response = None
    
    if model == "gpt-4.1" or model == "gpt-5.2" or model == "gpt-5.5" or model.startswith("gpt-"):
        if not OPENAI_AVAILABLE or not settings.OPENAI_API_KEY:
            logger.error("OpenAI not available or API key not set")
            return None
            
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        # Use high max_completion_tokens for GPT-5.2 / GPT-5.5
        if model in ("gpt-5.2", "gpt-5.5"):
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=128000,  # GPT-5.2 uses max_completion_tokens
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=16000,  # Older GPT models use max_tokens
            )
        return_response = response.choices[0].message.content
        
    elif model in ("claude-sonnet-4-6", "claude-sonnet-4-20250514"):
        if not ANTHROPIC_AVAILABLE or not settings.ANTHROPIC_API_KEY:
            logger.error("Anthropic not available or API key not set")
            return None
            
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-sonnet-4-6",
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20000,
            temperature=1,
        )
        return_response = (
            response.content[0].text.replace("```json", "").replace("```", "")
        )
        
    elif model in ("claude-haiku-4-5", "claude-haiku-4-5-20251001"):
        if not ANTHROPIC_AVAILABLE or not settings.ANTHROPIC_API_KEY:
            logger.error("Anthropic not available or API key not set")
            return None
            
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        response = client.messages.create(
            model="claude-haiku-4-5",
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20000,
            temperature=1,
        )
        return_response = (
            response.content[0].text.replace("```json", "").replace("```", "")
        )
        
    elif model == "gemini-2.5-flash":
        if not GOOGLE_AVAILABLE or not settings.GOOGLE_API_KEY:
            logger.error("Google Generative AI not available or API key not set")
            return None

        client = genai.Client(api_key=settings.GOOGLE_API_KEY)
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )
        return_response = response.text
        
    elif model == "grok-4-fast-reasoning":
        if not REQUESTS_AVAILABLE or not settings.XAI_API_KEY:
            logger.error("XAI API not available or API key not set")
            return None
            
        headers = {
            "Authorization": f"Bearer {settings.XAI_API_KEY}",
            "Content-Type": "application/json",
        }
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            json=data,
            headers=headers,
            timeout=3600,
        )
        response.raise_for_status()
        result = response.json()
        return_response = result["choices"][0]["message"]["content"]

    return return_response


def normalize_llm_name(llm: str) -> str:
    """
    Normalize LLM name to a canonical form for tracking.
    Maps display names and aliases to standard model names.
    """
    llm_lower = llm.lower()

    # Map display names and aliases to canonical model names
    if "gemini" in llm_lower or llm == "gemini-2.5-flash":
        return "gemini-2.5-flash"
    elif llm == "gpt-5.2" or llm_lower == "gpt-5.2":
        return "gpt-5.2"
    elif llm == "gpt-5.5" or llm_lower == "gpt-5.5":
        return "gpt-5.5"
    elif llm == "gpt-4.1" or llm_lower == "gpt-4.1":
        return "gpt-4.1"
    elif "gpt" in llm_lower or llm == "ChatGPT":
        return "gpt-5.5"
    elif "grok" in llm_lower or llm == "grok-4-fast-reasoning":
        return "grok-4-fast-reasoning"
    elif "haiku" in llm_lower or llm == "claude-haiku-4-5" or llm == "Claude Haiku":
        return "claude-haiku-4-5"
    elif (
        "sonnet" in llm_lower
        or llm == "claude-sonnet-4-6"
        or llm == "claude-sonnet-4-20250514"
        or llm == "Claude"
    ):
        return "claude-sonnet-4-6"
    elif "claude" in llm_lower:
        return "claude-sonnet-4-6"
    elif "llama" in llm_lower or llm == "llama3.2":
        return "llama3.2"
    else:
        # Return as-is if no mapping found
        return llm

