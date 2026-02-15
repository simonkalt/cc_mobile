"""
LLM communication utilities
"""
import logging
import json
import os
import sys
from pathlib import Path
from typing import Optional

from app.core.config import settings

# Try to import colorama for better color support in WSL/Windows
try:
    import colorama
    colorama.init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

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
    import google.generativeai as genai
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

try:
    import oci
    OCI_AVAILABLE = True
except ImportError:
    OCI_AVAILABLE = False

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False


def load_system_prompt() -> str:
    """
    Load system prompt from JSON config file (when USE_SYSTEM_PROMPT_FILE=true),
    otherwise return built-in default.
    
    Returns:
        System prompt string
    """
    if not settings.USE_SYSTEM_PROMPT_FILE:
        return _default_system_prompt()
    
    config_path = settings.SYSTEM_PROMPT_PATH
    
    try:
        if not config_path.exists():
            logger.warning(f"System prompt file not found: {config_path}. Using default.")
            return _default_system_prompt()
        
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        system_prompt = config.get("system_prompt", "")
        if not system_prompt:
            logger.warning(f"System prompt not found in {config_path}. Using default.")
            return _default_system_prompt()

        logger.info(
            f"Loaded system prompt from {config_path} ({len(system_prompt)} characters)"
        )
        return system_prompt
    except FileNotFoundError:
        logger.warning(f"System prompt file not found: {config_path}. Using default.")
        return _default_system_prompt()
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing system prompt JSON: {e}. Using default.")
        return _default_system_prompt()
    except Exception as e:
        logger.error(f"Error loading system prompt: {e}. Using default.")
        return _default_system_prompt()


def _default_system_prompt() -> str:
    """Default system prompt when JSON is missing or invalid. Uses only the single allowed page-formatting paragraph."""
    return (
        "You are an expert cover letter writer. Generate a professional cover letter based on the provided information. "
        "Return a one-field JSON object: 'markdown'. Do not return HTML. "
        "HEADER LAYOUT (required): First group: your address (one line) then your phone (one line). Second group: hiring manager (one line) then company (one line). After that, two line breaks before the date/Re:/Dear. "
        "PAGE FORMATTING (for DOCX output): All attempts to fit the resulting letter to one 8 1/2 x 11\" page must be made. "
        "Consider all of these factors: page size, font sizes, margins, important job alignments when calculating what and how much text to put on the page. "
        "If content suffers due to lack of job and resume alignment, you may continue to a 2nd page. "
        "Output markdown that converts cleanly to DOCX."
    )


def post_to_llm(prompt: str, model: str = "gpt-4.1") -> Optional[str]:
    """
    Send a prompt to an LLM and return the response
    
    Args:
        prompt: The prompt to send
        model: The model name to use
        
    Returns:
        LLM response text or None if error
    """
    return_response = None
    
    if model == "gpt-4.1" or model == "gpt-5.2" or model.startswith("gpt-"):
        if not OPENAI_AVAILABLE or not settings.OPENAI_API_KEY:
            logger.error("OpenAI not available or API key not set")
            return None
            
        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        # Use high max_completion_tokens for GPT-5.2
        if model == "gpt-5.2":
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_completion_tokens=128000,  # GPT-5.2 uses max_completion_tokens
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                max_tokens=16000,  # Older GPT models use max_tokens
            )
        return_response = response.choices[0].message.content
        
    elif model == "claude-sonnet-4-20250514":
        if not ANTHROPIC_AVAILABLE or not settings.ANTHROPIC_API_KEY:
            logger.error("Anthropic not available or API key not set")
            return None
            
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        messages = [{"role": "user", "content": prompt}]
        response = client.messages.create(
            model=model,
            system="You are a helpful assistant.",
            messages=messages,
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
            
        genai.configure(api_key=settings.GOOGLE_API_KEY)
        client = genai.GenerativeModel(model)
        response = client.generate_content(contents=prompt)
        return_response = response.text
        
    elif model == "grok-4-fast-reasoning":
        if not REQUESTS_AVAILABLE or not settings.XAI_API_KEY:
            logger.error("XAI API not available or API key not set")
            return None
            
        headers = {
            "Authorization": f"Bearer {settings.XAI_API_KEY}",
            "Content-Type": "application/json",
        }
        messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": prompt},
        ]
        data = {
            "model": model,
            "messages": messages,
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
        
    elif model == "oci-generative-ai":
        # OCI integration - requires OCI config file
        return get_oc_info(prompt)

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
    elif "gpt" in llm_lower or llm == "gpt-4.1" or llm == "ChatGPT":
        return "gpt-4.1"
    elif "grok" in llm_lower or llm == "grok-4-fast-reasoning":
        return "grok-4-fast-reasoning"
    elif "claude" in llm_lower or llm == "claude-sonnet-4-20250514":
        return "claude-sonnet-4-20250514"
    elif "llama" in llm_lower or llm == "llama3.2":
        return "llama3.2"
    elif "oci" in llm_lower or llm == "oci-generative-ai":
        return "oci-generative-ai"
    else:
        # Return as-is if no mapping found
        return llm


def get_text(contents):
    """Helper function to extract text from OCI content list"""
    text = ""
    for content in contents:
        if hasattr(content, "text"):
            text += content.text
        elif isinstance(content, str):
            text += content
    return text


def get_oc_info(prompt: str) -> str:
    """Helper function to get response from OCI Generative AI using GenericChatRequest"""
    if not OCI_AVAILABLE:
        logger.error("OCI library not available")
        return json.dumps({
            "markdown": "Error: OCI library not available",
        })
    
    if not settings.OCI_CONFIG_FILE:
        logger.error("OCI_CONFIG_FILE not configured")
        return json.dumps({
            "markdown": "Error: OCI configuration file not set",
        })
    
    try:
        # Initialize OCI config from file
        oci_config_file = settings.OCI_CONFIG_FILE
        oci_config_profile = settings.OCI_CONFIG_PROFILE or "CoverLetter"
        oci_region = settings.OCI_REGION or "us-phoenix-1"
        oci_model_id = settings.OCI_MODEL_ID or "ocid1.generativeaimodel.oc1.phx.amaaaaaask7dceya5zq6k7j3k4m5n6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0"
        oci_compartment_id = settings.OCI_COMPARTMENT_ID
        
        if not oci_compartment_id:
            logger.error("OCI_COMPARTMENT_ID not configured")
            return json.dumps({
                "markdown": "Error: OCI compartment ID not set",
            })
        
        config = oci.config.from_file(oci_config_file, oci_config_profile)

        # Create Generative AI client
        service_endpoint = (
            f"https://inference.generativeai.{oci_region}.oci.oraclecloud.com"
        )
        generative_ai_inference_client = (
            oci.generative_ai_inference.GenerativeAiInferenceClient(
                config=config,
                service_endpoint=service_endpoint,
                retry_strategy=oci.retry.NoneRetryStrategy(),
                timeout=(10, 240),
            )
        )

        # Create text content
        oci_content = oci.generative_ai_inference.models.TextContent()
        oci_content.text = prompt

        # Create message
        message = oci.generative_ai_inference.models.Message()
        message.role = "USER"
        message.content = [oci_content]

        # Create chat request
        chat_request = oci.generative_ai_inference.models.GenericChatRequest()
        chat_request.api_format = (
            oci.generative_ai_inference.models.BaseChatRequest.API_FORMAT_GENERIC
        )
        chat_request.messages = [message]
        chat_request.max_tokens = 1024
        chat_request.temperature = 0
        chat_request.top_p = 1
        chat_request.top_k = 0

        # Create chat detail
        oci_chat_detail = oci.generative_ai_inference.models.ChatDetails()
        oci_chat_detail.serving_mode = (
            oci.generative_ai_inference.models.OnDemandServingMode(
                model_id=oci_model_id
            )
        )
        oci_chat_detail.chat_request = chat_request
        oci_chat_detail.compartment_id = oci_compartment_id

        # Make the chat request
        chat_response = generative_ai_inference_client.chat(oci_chat_detail)

        if not chat_response:
            return json.dumps(
                {
                    "markdown": "Error: No response from OCI",
                }
            )

        # Access the 'data' attribute
        data_obj = chat_response.data

        text = ""
        choices = []
        message_obj = None
        contents = []

        # Drill down using attributes
        chat_response_obj = getattr(data_obj, "chat_response", None)
        if chat_response_obj and hasattr(chat_response_obj, "choices"):
            choices = chat_response_obj.choices
            for choice in choices:
                message_obj = getattr(choice, "message", None)
                if message_obj:
                    contents = getattr(message_obj, "content", [])
                    text = get_text(contents)

                    # Fix of <pre> formatting for OCI only...
                    data = json.loads(text)
                    data["markdown"] = data["markdown"].replace("\\n", "\n")
                    text = json.dumps(data)

        return text

    except Exception as e:
        error_msg = f"Error calling OCI Generative AI: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"markdown": f"Error: {error_msg}"})

