"""
Cover letter generation service
"""

import os
import json
import datetime
import base64
import logging
import re
from typing import Optional

from fastapi import HTTPException, status

# Try to import colorama for better color support in WSL/Windows
try:
    import colorama

    colorama.init(autoreset=True)
    COLORAMA_AVAILABLE = True
except ImportError:
    COLORAMA_AVAILABLE = False

from app.core.config import settings
from app.utils.pdf_utils import read_pdf_from_bytes, read_pdf_file
from app.utils.s3_utils import download_pdf_from_s3, S3_AVAILABLE
from app.utils.llm_utils import (
    load_system_prompt,
    normalize_llm_name,
    get_oc_info,
)
from app.services.user_service import (
    get_user_by_id,
    get_user_by_email,
    increment_llm_usage_count,
    decrement_generation_credits,
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
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Load system message
system_message = load_system_prompt()

# Model names - defaults, can be overridden by config
gpt_model = "gpt-5.2"
claude_model = "claude-sonnet-4-20250514"
ollama_model = "llama3.2"
xai_model = "grok-4-fast-reasoning"

# Try to load GPT model from LLM config
try:
    from llm_config_endpoint import load_llm_config

    config = load_llm_config()
    gpt_model = config.get("internalModel", "gpt-5.2")
    logger.info(f"Loaded GPT model from config: {gpt_model}")
except Exception as e:
    logger.debug(f"Failed to load GPT model from config, using default: {e}")


def get_job_info(
    llm: str,
    date_input: str,
    company_name: str,
    hiring_manager: str,
    ad_source: str,
    resume: str,
    jd: str,
    additional_instructions: str,
    tone: str,
    address: str = "",
    phone_number: str = "",
    user_id: Optional[str] = None,
    user_email: Optional[str] = None,
    is_plain_text: bool = False,
):
    """
    Generate cover letter based on job information using specified LLM.
    Returns a dictionary with 'markdown' and 'html' fields.

    Args:
        user_id: Optional user ID to access custom personality profiles
        user_email: Optional user email to access custom personality profiles
        is_plain_text: If True, skip all file processing (S3, local files, base64) and treat resume as plain text
    """
    # Get today's date if not provided
    today_date = date_input if date_input else datetime.datetime.now().strftime("%Y-%m-%d")

    # Check if resume is a file path, S3 key, or base64 data
    resume_content = resume

    # If explicitly marked as plain text, skip all file processing
    if is_plain_text:
        logger.info("Resume marked as plain text, skipping file processing")
        resume_content = resume
    # First, check if it's base64 encoded data
    elif (
        resume and len(resume) > 100 and not resume.endswith(".pdf") and not resume.endswith(".PDF")
    ):
        try:
            # Try to decode as base64
            pdf_bytes = base64.b64decode(resume)
            # Verify it's a PDF by checking the header
            if pdf_bytes.startswith(b"%PDF"):
                logger.info("Detected base64 encoded PDF data, decoding...")
                resume_content = read_pdf_from_bytes(pdf_bytes)
                logger.info("Successfully decoded and extracted text from base64 PDF")
            else:
                # Not base64 PDF, treat as regular text
                logger.debug("Resume field appears to be text, not base64 PDF")
        except Exception as e:
            # Not base64, continue with other methods
            logger.debug(f"Resume field is not base64 encoded: {str(e)}")

    # If base64 decode didn't work, try S3 or local file paths
    # Skip if explicitly marked as plain text
    if resume_content == resume and resume and not is_plain_text:
        # Check if it looks like an S3 key (contains '/' - format: user_id/filename or just filename)
        # S3 keys from the client will be in format: user_id/filename.pdf
        is_s3_key = "/" in resume

        # Try S3 download if it looks like an S3 key or PDF filename
        if is_s3_key or resume.endswith(".pdf") or resume.endswith(".PDF"):
            # Try to download from S3 first
            if S3_AVAILABLE and settings.AWS_S3_BUCKET:
                # Require user_id for S3 operations - resumes are organized by user_id folders
                if not user_id:
                    logger.warning(
                        "user_id is required for S3 resume operations. Skipping S3 download."
                    )
                else:
                    try:
                        # Determine the S3 key
                        # If resume already contains user_id/, use it directly
                        if is_s3_key and resume.startswith(f"{user_id}/"):
                            s3_key = resume
                        elif is_s3_key:
                            # It's an S3 key but doesn't start with user_id/
                            # Check if it's already a full S3 key (starts with another user_id)
                            # If so, use it as-is; otherwise prepend user_id
                            parts = resume.split("/", 1)
                            if len(parts) == 2 and len(parts[0]) == 24:  # MongoDB ObjectId length
                                # Already has a user_id prefix, use as-is
                                s3_key = resume
                            else:
                                # Extract filename and prepend user_id
                                filename = os.path.basename(resume.replace("\\", "/"))
                                s3_key = f"{user_id}/{filename}"
                        else:
                            # Extract just the filename if path includes directory
                            filename = os.path.basename(resume.replace("\\", "/"))
                            # Construct S3 path organized by user_id: bucket/user_id/filename
                            s3_key = f"{user_id}/{filename}"

                        s3_path = f"s3://{settings.AWS_S3_BUCKET}/{s3_key}"

                        logger.info(f"Downloading PDF from S3: {s3_path}")
                        pdf_bytes = download_pdf_from_s3(s3_path)
                        resume_content = read_pdf_from_bytes(pdf_bytes)
                        logger.info("Successfully downloaded and extracted text from S3 PDF")
                    except Exception as e:
                        logger.warning(
                            f"Failed to download from S3: {str(e)}. Will try local file paths."
                        )
                        # Continue to try local paths

        # If S3 download failed or S3 not available, try local file paths as fallback
        # Skip local file check if resume is clearly an S3 key (has user_id prefix)
        if resume_content == resume:
            # Check if resume path looks like an S3 key (user_id/filename format)
            # MongoDB ObjectId is 24 characters, so check if first part is 24 chars
            parts = resume.split("/", 1)
            is_s3_key_format = len(parts) == 2 and len(parts[0]) == 24

            # Only try local paths if it doesn't look like an S3 key
            if not is_s3_key_format:
                # Get the current working directory
                cwd = os.getcwd()
                logger.info(f"Trying local file paths. Current working directory: {cwd}")

                # Build list of possible paths to try
                possible_paths = []

                # If it's already an absolute path, try it first
                if os.path.isabs(resume):
                    possible_paths.append(resume)
                else:
                    # If it contains path separators (like "PDF Resumes/file.pdf"), try it as-is first
                    if os.path.sep in resume or "/" in resume:
                        possible_paths.append(resume)
                        # Also try from current directory
                        possible_paths.append(os.path.join(cwd, resume))

                    # Try common locations
                    possible_paths.extend(
                        [
                            os.path.join(cwd, resume),
                            os.path.join(cwd, "PDF Resumes", os.path.basename(resume)),
                            os.path.join(cwd, "PDF Resumes", resume),
                            os.path.join(cwd, "resumes", os.path.basename(resume)),
                            os.path.join(cwd, "resumes", resume),
                            os.path.join(".", resume),
                            os.path.join(".", "PDF Resumes", os.path.basename(resume)),
                            os.path.join(".", "PDF Resumes", resume),
                        ]
                    )

                    # If the resume path already includes "PDF Resumes", try extracting just the filename
                    if "PDF Resumes" in resume or "pdf" in resume.lower():
                        filename = os.path.basename(resume)
                        possible_paths.extend(
                            [
                                os.path.join(cwd, "PDF Resumes", filename),
                                os.path.join(".", "PDF Resumes", filename),
                            ]
                        )

                # Try each path until we find one that exists
                found = False
                for path in possible_paths:
                    # Normalize the path
                    normalized_path = os.path.normpath(path)
                    logger.debug(f"Trying PDF path: {normalized_path}")
                    if os.path.exists(normalized_path) and os.path.isfile(normalized_path):
                        logger.info(f"Found PDF at: {normalized_path}, reading content")
                        resume_content = read_pdf_file(normalized_path)
                        found = True
                        break

                if not found:
                    logger.warning(
                        f"PDF file not found locally. Tried paths: {possible_paths[:5]}... (showing first 5)"
                    )

            # If we haven't successfully extracted content, return the original
            if resume_content == resume:
                if is_s3_key_format:
                    logger.warning(
                        f"Could not read PDF from S3 (path appears to be S3 key: {resume}). Using original resume string."
                    )
                else:
                    logger.warning(
                        f"Could not read PDF from S3 or local filesystem. Using original resume string."
                    )
                resume_content = resume

    # Get personality profile from user's custom profiles (user_id or user_email required)
    selected_profile = None
    profile_source = "user_custom"

    # Require user_id or user_email to access personality profiles
    if not user_id and not user_email:
        logger.warning("No user_id or user_email provided. Cannot retrieve personality profiles.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id or user_email is required to access personality profiles",
        )

    try:
        user = None
        if user_id:
            try:
                user = get_user_by_id(user_id)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Could not get user by ID {user_id}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User not found: {str(e)}",
                )
        elif user_email:
            try:
                user = get_user_by_email(user_email)
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Could not get user by email {user_email}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"User not found: {str(e)}",
                )

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get user's custom personality profiles
        # user is a UserResponse Pydantic model, so access preferences as attribute
        # Note: user_doc_to_response already normalizes personalityProfiles to {"id", "name", "description"} structure
        user_prefs = user.preferences if user.preferences else {}
        if isinstance(user_prefs, dict):
            app_settings = user_prefs.get("appSettings", {})
            if isinstance(app_settings, dict):
                custom_profiles = app_settings.get("personalityProfiles", [])
                # Ensure profiles are normalized (should already be normalized by user_doc_to_response, but double-check)
                if custom_profiles:
                    # Verify structure and filter out invalid profiles
                    normalized_profiles = []
                    for profile in custom_profiles:
                        if isinstance(profile, dict) and profile.get("id") and profile.get("name"):
                            # Extract only id, name, description
                            normalized_profiles.append(
                                {
                                    "id": profile.get("id", ""),
                                    "name": profile.get("name", ""),
                                    "description": profile.get("description", ""),
                                }
                            )
                    custom_profiles = normalized_profiles
            else:
                custom_profiles = []
        else:
            custom_profiles = []

        logger.info(
            f"User preferences retrieved. Custom profiles count: {len(custom_profiles) if isinstance(custom_profiles, list) else 0}"
        )

        if not custom_profiles:
            logger.warning(f"No personality profiles found for user. Available profiles: []")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No personality profiles found for user. Please add personality profiles in your user preferences.",
            )

        logger.info(f"Found {len(custom_profiles)} custom personality profiles for user")
        # Try to find matching profile by name (case-insensitive) or ID
        # Normalize profiles to ensure structure is {"id", "name", "description"} only
        profile_found = False
        for profile in custom_profiles:
            if isinstance(profile, dict):
                # Normalize structure: extract only id, name, description
                profile_id = profile.get("id", "")
                profile_name = profile.get("name", "").lower()
                profile_desc = profile.get("description", "")

                # Match by name (case-insensitive) or ID
                if tone.lower() == profile_name or tone == profile_id:
                    selected_profile = profile_desc
                    logger.info(
                        f"Using custom personality profile: '{profile.get('name')}' (ID: {profile_id})"
                    )
                    logger.info(
                        f"Custom profile text ({len(selected_profile)} chars): {selected_profile}"
                    )
                    profile_found = True
                    break

        if not profile_found:
            # Normalize when getting available names
            available_names = [
                p.get("name", "Unknown")
                for p in custom_profiles
                if isinstance(p, dict) and p.get("name")
            ]
            logger.warning(
                f"Personality profile '{tone}' not found in user's profiles. Available profiles: {available_names}"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Personality profile '{tone}' not found. Available profiles: {available_names}",
            )

    except HTTPException:
        # Re-raise HTTPException
        raise
    except Exception as e:
        logger.error(f"Error accessing user's custom personality profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving personality profiles: {str(e)}",
        )

    if not selected_profile:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve personality profile",
        )

    logger.info(
        f"Personality profile source: {profile_source} (profile retrieved from user's database preferences)"
    )

    # Build personality instruction - make it prominent and direct
    personality_instruction = f"""
=== PERSONALITY PROFILE INSTRUCTION - CRITICAL ===
YOU MUST FOLLOW THIS PERSONALITY PROFILE EXACTLY:
{selected_profile}

Apply this personality throughout the entire cover letter. This instruction takes precedence over default writing styles.
=== END PERSONALITY PROFILE INSTRUCTION ===
"""
    logger.info(
        f"Personality instruction prepared ({len(personality_instruction)} chars): {selected_profile[:100]}..."
    )

    # Get font settings for LLM prompting (if user is available)
    font_instruction = ""
    try:
        if user:
            user_prefs = user.preferences if user.preferences else {}
            if isinstance(user_prefs, dict):
                app_settings = user_prefs.get("appSettings", {})
                if isinstance(app_settings, dict):
                    print_props = app_settings.get("printProperties", {})
                    if isinstance(print_props, dict):
                        font_family = print_props.get("fontFamily", "")
                        # If fontFamily is "default", add font-size instruction to LLM
                        if font_family and font_family.lower() == "default":
                            font_instruction = """
=== HTML FORMATTING INSTRUCTION ===
When generating HTML output, ensure all text uses a minimum base font-size of 14pt. Headers should be larger, etc., so 14pt is the smallest font-size on the document. This method should be applied to the main content and all paragraphs.
Use inline styles like: style="font-size: 14pt;" on your HTML elements to ensure proper text sizing.
=== END HTML FORMATTING INSTRUCTION ===
"""
                            logger.info(
                                "Added font-size: 14pt instruction to LLM prompt (fontFamily is 'default')"
                            )
    except Exception as e:
        logger.warning(f"Could not retrieve font settings for LLM prompting: {e}")

    # Build message payload (without additional_instructions - it will be appended last to override)
    message_data = {
        "llm": llm,
        "today": f"Date: {today_date}",
        "company_name": company_name,
        "hiring_manager": hiring_manager,
        "ad_source": ad_source,
        "resume": resume_content,  # Use extracted PDF content instead of file path
        "jd": jd,
        "tone": f"Use the following tone/personality when generating the result, but do not specifically note the activities within this text: {selected_profile}",
    }

    # Add optional fields
    if address:
        message_data["address"] = address
    if phone_number:
        message_data["phone_number"] = phone_number

    message = json.dumps(message_data)

    # Prepare additional instructions - enhance by default, override ONLY if explicitly requested
    additional_instructions_text = ""
    if additional_instructions and additional_instructions.strip():
        # Check if the additional instructions explicitly request an override
        # Override mode should ONLY trigger if user explicitly commands it with very specific language
        # Default behavior is ALWAYS enhancement mode
        instructions_lower = additional_instructions.lower().strip()

        # EXTREMELY strict override detection - user must explicitly command override
        # Override mode ONLY triggers if instructions start with explicit override markers
        # This prevents accidental triggering from normal instructions

        # Check if instructions start with explicit override markers
        # Must literally start with one of these exact phrases (case-insensitive)
        override_markers = [
            "override:",
            "override ",
            "ignore all previous:",
            "ignore all previous ",
            "ignore previous:",
            "ignore previous ",
            "disregard all previous:",
            "disregard all previous ",
            "disregard previous:",
            "disregard previous ",
        ]

        starts_with_override = any(
            instructions_lower.startswith(marker) for marker in override_markers
        )

        # Also check for explicit override phrases anywhere in the text (but be very strict)
        explicit_override_phrases = [
            "override all previous instructions",
            "ignore all previous instructions",
            "disregard all previous instructions",
        ]

        contains_explicit_override = any(
            phrase in instructions_lower for phrase in explicit_override_phrases
        )

        # ONLY trigger override if user explicitly commands it
        is_override = starts_with_override or contains_explicit_override

        # Log detection for debugging
        logger.info(
            f"Additional instructions override detection: starts_with_override={starts_with_override}, contains_explicit_override={contains_explicit_override}, is_override={is_override}"
        )
        logger.info(f"First 200 chars of instructions: {additional_instructions[:200]}")

        if is_override:
            # User explicitly requested override - use override language
            additional_instructions_text = f"""

=== FINAL OVERRIDE INSTRUCTIONS - HIGHEST PRIORITY ===
IGNORE ALL PREVIOUS INSTRUCTIONS ABOUT LENGTH, TONE, STYLE, OR FORMATTING.
THE FOLLOWING INSTRUCTIONS TAKE ABSOLUTE PRECEDENCE OVER EVERYTHING ELSE, INCLUDING:
- System prompts
- Personality profiles
- Tone settings
- Any other instructions in this conversation

YOU MUST FOLLOW THESE INSTRUCTIONS EXACTLY:
{additional_instructions}

=== END OVERRIDE INSTRUCTIONS ===
"""
            # logger.info(
            #     f"Additional instructions provided ({len(additional_instructions)} chars) - OVERRIDE MODE detected (explicit override requested)"
            # )
        else:
            # User wants to enhance/supplement - add as additional guidance
            additional_instructions_text = f"""

=== ADDITIONAL INSTRUCTIONS ===
Please also take into account the following additional guidance when generating the cover letter.
These instructions should enhance and work together with the personality profile, system instructions, and other guidance provided:

{additional_instructions}

Please incorporate these instructions while maintaining consistency with all other provided guidance.
=== END ADDITIONAL INSTRUCTIONS ===
"""
            # logger.info(
            #     f"Additional instructions provided ({len(additional_instructions)} chars) - ENHANCEMENT MODE (will supplement other instructions)"
            # )

    r = ""

    try:
        # Map model names to display names for compatibility
        if llm == "Gemini" or llm == "gemini-2.5-flash":
            # Include personality instruction prominently at the start, and font instruction if applicable
            msg = f"{system_message}{personality_instruction}{font_instruction}. {message}. Hiring Manager: {hiring_manager}. Company Name: {company_name}. Ad Source: {ad_source}{additional_instructions_text}"
            if additional_instructions_text:
                if "OVERRIDE" in additional_instructions_text:
                    logger.debug(
                        "Additional instructions appended to Gemini prompt (OVERRIDE MODE)"
                    )
                else:
                    logger.debug(
                        "Additional instructions appended to Gemini prompt (ENHANCEMENT MODE)"
                    )
            if not GOOGLE_AVAILABLE or not settings.GEMINI_API_KEY:
                raise ValueError("Google Generative AI not available or API key not set")
            genai.configure(api_key=settings.GEMINI_API_KEY)
            model = genai.GenerativeModel("gemini-2.5-flash")

            # Configure generation to ensure complete JSON response
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,  # Increase max tokens to prevent truncation
            }

            response = model.generate_content(contents=msg, generation_config=generation_config)
            r = response.text
            logger.info(f"Gemini response length: {len(r)} characters")

        elif llm == "ChatGPT" or llm == gpt_model or llm == "gpt-4.1":
            if not OPENAI_AVAILABLE or not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI not available or API key not set")
            client = OpenAI(api_key=settings.OPENAI_API_KEY)
            messages = [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": personality_instruction.strip(),
                },  # Add personality instruction as separate, prominent message
            ]
            # Add font instruction if applicable
            if font_instruction:
                messages.append({"role": "user", "content": font_instruction.strip()})
            messages.extend(
                [
                    {"role": "user", "content": message},
                    {"role": "user", "content": f"Hiring Manager: {hiring_manager}"},
                    {"role": "user", "content": f"Company Name: {company_name}"},
                    {"role": "user", "content": f"Ad Source: {ad_source}"},
                ]
            )
            # Append additional instructions last as a separate message
            if additional_instructions_text:
                messages.append({"role": "user", "content": additional_instructions_text.strip()})
                if "OVERRIDE" in additional_instructions_text:
                    logger.debug(
                        "Additional instructions appended to ChatGPT messages (OVERRIDE MODE)"
                    )
                else:
                    logger.debug(
                        "Additional instructions appended to ChatGPT messages (ENHANCEMENT MODE)"
                    )
            # Use high max_completion_tokens for GPT-5.2 (supports 128,000 max completion tokens)
            if gpt_model == "gpt-5.2":
                response = client.chat.completions.create(
                    model=gpt_model,
                    messages=messages,
                    max_completion_tokens=128000,  # GPT-5.2 uses max_completion_tokens
                )
            else:
                response = client.chat.completions.create(
                    model=gpt_model,
                    messages=messages,
                    max_tokens=16000,  # Older GPT models use max_tokens
                )
            r = response.choices[0].message.content

        elif llm == "Grok" or llm == xai_model or llm == "grok-4-fast-reasoning":
            if not REQUESTS_AVAILABLE or not settings.XAI_API_KEY:
                raise ValueError("XAI API not available or API key not set")
            # Use HTTP API (xai SDK has different API structure)
            headers = {
                "Authorization": f"Bearer {settings.XAI_API_KEY}",
                "Content-Type": "application/json",
            }
            messages_list = [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": personality_instruction.strip(),
                },  # Add personality instruction as separate, prominent message
            ]
            # Add font instruction if applicable
            if font_instruction:
                messages_list.append({"role": "user", "content": font_instruction.strip()})
            messages_list.extend(
                [
                    {"role": "user", "content": message},
                    {"role": "user", "content": f"Hiring Manager: {hiring_manager}"},
                    {"role": "user", "content": f"Company Name: {company_name}"},
                    {"role": "user", "content": f"Ad Source: {ad_source}"},
                ]
            )
            # Append additional instructions last
            if additional_instructions_text:
                messages_list.append(
                    {"role": "user", "content": additional_instructions_text.strip()}
                )
                if "OVERRIDE" in additional_instructions_text:
                    logger.debug(
                        "Additional instructions appended to Grok messages (OVERRIDE MODE)"
                    )
                else:
                    logger.debug(
                        "Additional instructions appended to Grok messages (ENHANCEMENT MODE)"
                    )
            data = {"model": xai_model, "messages": messages_list}
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                json=data,
                headers=headers,
                timeout=3600,
            )
            response.raise_for_status()
            result = response.json()
            r = result["choices"][0]["message"]["content"]

        elif llm == "OCI" or llm == "oci-generative-ai":
            # Include personality instruction prominently at the start, and font instruction if applicable
            full_prompt = f"{system_message}{personality_instruction}{font_instruction}. {message}. Hiring Manager: {hiring_manager}. Company Name: {company_name}. Ad Source: {ad_source}{additional_instructions_text}"
            r = get_oc_info(full_prompt)
            logger.info(f"OCI response received ({len(r)} characters)")

        elif llm == "Llama" or llm == ollama_model or llm == "llama3.2":
            if not OLLAMA_AVAILABLE:
                raise ImportError(
                    "ollama library is not installed. Please install it with: pip install ollama"
                )

            # Use the same message_data that includes the personality profile (tone field)
            # This ensures the personality profile description is included in Llama prompts
            message_llama = (
                message  # Use the original message which includes the tone/personality profile
            )
            messages = [
                {"role": "system", "content": system_message},
                {
                    "role": "user",
                    "content": personality_instruction.strip(),
                },  # Add personality instruction as separate, prominent message
            ]
            # Add font instruction if applicable
            if font_instruction:
                messages.append({"role": "user", "content": font_instruction.strip()})
            messages.append({"role": "user", "content": message_llama})
            # Append additional instructions last
            if additional_instructions_text:
                messages.append({"role": "user", "content": additional_instructions_text.strip()})
                if "OVERRIDE" in additional_instructions_text:
                    logger.debug(
                        "Additional instructions appended to Llama messages (OVERRIDE MODE)"
                    )
                else:
                    logger.debug(
                        "Additional instructions appended to Llama messages (ENHANCEMENT MODE)"
                    )
            response = ollama.chat(model=ollama_model, messages=messages)
            r = response["message"]["content"]

        elif llm == "Claude" or llm == claude_model or llm == "claude-sonnet-4-20250514":
            if not ANTHROPIC_AVAILABLE or not settings.ANTHROPIC_API_KEY:
                raise ValueError("Anthropic not available or API key not set")
            client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            content_list = [
                {
                    "type": "text",
                    "text": personality_instruction.strip(),
                },  # Add personality instruction as separate, prominent message
            ]
            # Add font instruction if applicable
            if font_instruction:
                content_list.append({"type": "text", "text": font_instruction.strip()})
            content_list.extend(
                [
                    {"type": "text", "text": message},
                    {"type": "text", "text": f"Hiring Manager: {hiring_manager}"},
                    {"type": "text", "text": f"Company Name: {company_name}"},
                    {"type": "text", "text": f"Ad Source: {ad_source}"},
                ]
            )
            # Append additional instructions last
            if additional_instructions_text:
                content_list.append({"type": "text", "text": additional_instructions_text.strip()})
                if "OVERRIDE" in additional_instructions_text:
                    logger.debug(
                        "Additional instructions appended to Claude messages (OVERRIDE MODE)"
                    )
                else:
                    logger.debug(
                        "Additional instructions appended to Claude messages (ENHANCEMENT MODE)"
                    )
            messages = [{"role": "user", "content": content_list}]
            response = client.messages.create(
                model=claude_model,
                system=system_message,
                messages=messages,
                max_tokens=20000,
                temperature=1,
            )
            r = response.content[0].text
        else:
            raise ValueError(f"Unsupported LLM: {llm}")

        # Increment LLM usage count for the user (after successful LLM call)
        if user_id:
            normalized_llm = normalize_llm_name(llm)
            try:
                increment_llm_usage_count(user_id, normalized_llm)
                logger.info(
                    f"Incremented LLM usage count for {normalized_llm} (user_id: {user_id})"
                )
            except Exception as e:
                logger.warning(f"Failed to increment LLM usage count: {e}")

            # Decrement generation credits if user has no subscription
            try:
                decrement_generation_credits(user_id)
                logger.info(f"Decremented generation credits for user {user_id} (if applicable)")
            except Exception as e:
                logger.warning(f"Failed to decrement generation credits: {e}")
        elif user_email:
            # Try to get user_id from email
            try:
                user = get_user_by_email(user_email)
                normalized_llm = normalize_llm_name(llm)
                increment_llm_usage_count(user.id, normalized_llm)
                logger.info(
                    f"Incremented LLM usage count for {normalized_llm} (user_email: {user_email})"
                )

                # Decrement generation credits if user has no subscription
                try:
                    decrement_generation_credits(user.id)
                    logger.info(
                        f"Decremented generation credits for user {user.id} (if applicable)"
                    )
                except Exception as e:
                    logger.warning(f"Failed to decrement generation credits: {e}")
            except Exception as e:
                logger.warning(f"Failed to increment LLM usage count from email: {e}")

        # Clean and parse the response
        r = r.replace("```json", "").replace("```", "").strip()

        # Try to extract JSON if it's embedded in text
        # Look for JSON object boundaries
        start_idx = r.find("{")
        end_idx = r.rfind("}")

        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # Extract just the JSON portion
            json_str = r[start_idx : end_idx + 1]
        else:
            json_str = r

        try:
            json_r = json.loads(json_str)
        except json.JSONDecodeError as e:
            # If parsing fails, try to fix common issues
            logger.warning(f"Initial JSON parse failed: {e}, attempting to fix...")

            # Fix 1: Look for the last complete JSON object (balanced braces)
            brace_count = 0
            last_valid_end = -1
            for i, char in enumerate(json_str):
                if char == "{":
                    brace_count += 1
                elif char == "}":
                    brace_count -= 1
                    if brace_count == 0:
                        last_valid_end = i
                        break

            if last_valid_end > 0:
                try:
                    json_r = json.loads(json_str[: last_valid_end + 1])
                    logger.info("Successfully fixed truncated JSON (balanced braces)")
                except json.JSONDecodeError:
                    json_r = None
            else:
                json_r = None

            # Fix 2: If still no parse (e.g. unterminated string), recover "markdown" from start
            if json_r is None and ("Unterminated string" in str(e) or "Expecting" in str(e)):
                markdown_match = re.search(r'"markdown"\s*:\s*"', json_str)
                if markdown_match:
                    value_start = markdown_match.end()
                    raw_markdown = json_str[value_start:]
                    # Escape for JSON: backslash and quote first, then newlines
                    escaped = (
                        raw_markdown.replace("\\", "\\\\")
                        .replace('"', '\\"')
                        .replace("\n", "\\n")
                        .replace("\r", "\\r")
                    )
                    try:
                        fixed_str = '{"markdown": "' + escaped + '", "html": ""}'
                        json_r = json.loads(fixed_str)
                        logger.info(
                            "Recovered from unterminated string: using markdown content, html empty"
                        )
                    except json.JSONDecodeError:
                        pass

            if json_r is None:
                raise e

        # Clean up the markdown field - remove "markdown " prefix if Gemini added it
        markdown_content = json_r.get("markdown", "")
        if markdown_content.startswith("markdown "):
            markdown_content = markdown_content[9:]  # Remove "markdown " (9 characters)
            logger.info("Removed 'markdown ' prefix from Gemini response")

        # Get raw HTML from LLM response (may be empty if we recovered from truncated JSON)
        raw_html = json_r.get("html", "")
        if not raw_html and markdown_content:
            try:
                import markdown

                raw_html = markdown.markdown(
                    markdown_content,
                    extensions=["extra", "nl2br"],
                )
                logger.info("Converted recovered markdown to HTML for display")
            except Exception as md_err:
                logger.warning(f"Could not convert markdown to HTML: {md_err}")

        # Keep line breaks: strip \r, convert \n to <br /> so they render in print preview/PDF
        raw_html = raw_html.replace("\r", "")
        raw_html = raw_html.replace("\n", "<br />")
        raw_html = re.sub(r" +", " ", raw_html)

        # Apply user's print settings to HTML
        # Reuse the user object that was already retrieved earlier for personality profiles
        styled_html = raw_html
        try:
            # Reuse the user object that was already fetched (avoid duplicate database call)
            user_for_styling = user  # Use the user object from earlier in the function

            if user_for_styling and user_for_styling.preferences:
                app_settings = user_for_styling.preferences.get("appSettings", {})
                if isinstance(app_settings, dict):
                    print_props = app_settings.get("printProperties", {})
                    if isinstance(print_props, dict) and print_props:
                        # Check if user wants to use default fonts from LLM HTML
                        use_default_fonts = print_props.get("useDefaultFonts", False)

                        if use_default_fonts:
                            # Don't apply font styling - let LLM HTML dictate formatting
                            logger.info(
                                "useDefaultFonts is True - skipping font styling, using raw LLM HTML"
                            )
                            styled_html = raw_html
                        else:
                            # Get print properties with defaults
                            font_family = print_props.get("fontFamily", "Times New Roman")
                            font_size = print_props.get("fontSize", 12)
                            line_height = print_props.get("lineHeight", 1.6)

                            # Wrap HTML with CSS styling using inline styles
                            # Escape any quotes in font family name
                            font_family_escaped = font_family.replace("'", "\\'")
                            styled_html = f"""<div style="font-family: '{font_family_escaped}', serif; font-size: {font_size}pt; line-height: {line_height}; color: #000;">{raw_html}</div>"""
                            logger.info(
                                f"Applied print settings to HTML: fontFamily={font_family}, fontSize={font_size}pt, lineHeight={line_height}"
                            )
        except Exception as e:
            logger.warning(f"Could not apply print settings to HTML: {e}")
            # Continue with unstyled HTML if styling fails

        # Final cleanup: strip \r, convert any remaining \n to <br /> so line breaks render
        styled_html = styled_html.replace("\r", "")
        styled_html = styled_html.replace("\n", "<br />")
        styled_html = re.sub(r" +", " ", styled_html)

        return {"markdown": markdown_content, "html": styled_html}

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response length: {len(r)} characters")
        error_html = f"<p>Error: Failed to parse LLM response as JSON. The response may be truncated or malformed.</p><p>Error: {str(e)}</p><pre>{r[:500]}</pre>"
        # Clean HTML: strip \r, preserve line breaks as <br />
        error_html = error_html.replace("\r", "").replace("\n", "<br />")
        error_html = re.sub(r" +", " ", error_html)

        return {
            "markdown": f"Error: Failed to parse LLM response as JSON. The response may be truncated or malformed.\n\nError: {str(e)}\n\nFirst 500 chars of response:\n{r[:500]}",
            "html": error_html,
        }
    except Exception as e:
        logger.error(f"Error in get_job_info: {str(e)}")
        error_html = f"<p>Error: {str(e)}</p>"
        # Clean HTML: strip \r, preserve line breaks as <br />
        error_html = error_html.replace("\r", "").replace("\n", "<br />")
        error_html = re.sub(r" +", " ", error_html)
        return {"markdown": f"Error: {str(e)}", "html": error_html}
