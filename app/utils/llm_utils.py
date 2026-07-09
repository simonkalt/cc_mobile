"""
LLM communication utilities
"""
import logging
import json
from typing import Optional

from app.core.config import settings
from app.utils.grok_client import (
    GROK_MODEL_ID,
    grok_chat_completions,
    is_grok_model,
)
from app.utils.llm_token_limits import (
    max_output_tokens_for_model,
    resolve_openai_model,
    uses_openai_max_completion_tokens,
)
from app.utils.openrouter_client import (
    openrouter_chat,
    openrouter_configured,
    use_openrouter,
)

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


def _post_to_llm_direct(prompt: str, model: str) -> Optional[str]:
    """Legacy per-provider path (LLM_PROVIDER=direct)."""
    return_response = None

    if model == "gpt-4.1" or model == "gpt-5.5" or model.startswith("gpt-"):
        if not OPENAI_AVAILABLE or not settings.OPENAI_API_KEY:
            logger.error("OpenAI not available or API key not set")
            return None

        openai_model = resolve_openai_model(model)
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        openai_max_tokens = max_output_tokens_for_model(openai_model)
        if uses_openai_max_completion_tokens(openai_model):
            response = client.chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_completion_tokens=openai_max_tokens,
            )
        else:
            response = client.chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=openai_max_tokens,
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
            max_tokens=max_output_tokens_for_model("claude-sonnet-4-6"),
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
            max_tokens=max_output_tokens_for_model("claude-haiku-4-5"),
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

    elif is_grok_model(model):
        if not REQUESTS_AVAILABLE:
            logger.error("requests not available for Grok/OCI calls")
            return None
        try:
            return_response = grok_chat_completions(
                [
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
            )
        except Exception as exc:
            logger.error("Grok/OCI chat completion failed: %s", exc)
            return None

    return return_response


def post_to_llm(prompt: str, model: str = "gpt-5.5") -> Optional[str]:
    """
    Send a prompt to an LLM and return the response
    
    Args:
        prompt: The prompt to send
        model: The model name to use
        
    Returns:
        LLM response text or None if error
    """
    if model == "llama3.2" or (isinstance(model, str) and "llama" in model.lower()):
        if not OLLAMA_AVAILABLE:
            logger.error("ollama not available")
            return None
        try:
            response = ollama.chat(
                model="llama3.2",
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
            )
            return response["message"]["content"]
        except Exception as exc:
            logger.error("Ollama chat failed: %s", exc)
            return None

    if use_openrouter() and openrouter_configured():
        try:
            return openrouter_chat(
                app_model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=max_output_tokens_for_model(normalize_llm_name(model)),
            )
        except Exception as exc:
            logger.error("OpenRouter chat failed: %s", exc)
            return None

    if use_openrouter() and not openrouter_configured():
        logger.warning(
            "LLM_PROVIDER=openrouter but OPENROUTER_API_KEY missing; "
            "falling back to direct providers"
        )

    return _post_to_llm_direct(prompt, model)


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
        return "gpt-5.5"
    elif llm == "gpt-5.5" or llm_lower == "gpt-5.5":
        return "gpt-5.5"
    elif llm == "gpt-4.1" or llm_lower == "gpt-4.1":
        return "gpt-4.1"
    elif "gpt" in llm_lower or llm == "ChatGPT":
        return "gpt-5.5"
    elif is_grok_model(llm) or llm == "Grok":
        return GROK_MODEL_ID
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
