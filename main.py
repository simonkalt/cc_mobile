from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError, EmailStr, Field
from contextlib import asynccontextmanager
from typing import Optional
from bson import ObjectId
from datetime import datetime

import os
import json
import datetime
import base64
import re
import warnings
from dotenv import load_dotenv
from openai import OpenAI
import anthropic

# Suppress deprecation warnings
# - google.generativeai deprecation (still works, will migrate to google.genai later)
# - Python version warning from google.api_core (informational, not critical)
# - importlib.metadata compatibility warnings for Python 3.9
with warnings.catch_warnings():
    warnings.filterwarnings("ignore", category=FutureWarning, message=".*google.generativeai.*")
    warnings.filterwarnings("ignore", category=FutureWarning, message=".*Python version.*")
    warnings.filterwarnings("ignore", message=".*importlib.metadata.*packages_distributions.*")
    warnings.filterwarnings("ignore", message=".*module 'importlib.metadata' has no attribute.*")

    # Patch importlib.metadata for Python 3.9 compatibility
    try:
        import importlib.metadata

        if not hasattr(importlib.metadata, "packages_distributions"):
            # Add a stub function for Python 3.9 compatibility
            def _packages_distributions_stub():
                return {}

            importlib.metadata.packages_distributions = _packages_distributions_stub
    except (ImportError, AttributeError):
        pass

    import google.generativeai as genai

from huggingface_hub import login
import requests
import oci
import logging
import sys

# Import MongoDB client - use refactored module
try:
    from app.db.mongodb import (
        connect_to_mongodb,
        close_mongodb_connection,
        is_connected,
        get_collection,
    )

    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.warning("MongoDB module not available. Some features will be disabled.")

# Try to import ollama, make it optional
try:
    import ollama

    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

# Configure logging - use INFO level for better visibility on Render
# Render and many cloud platforms filter DEBUG logs
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],  # Explicitly use stdout for Render
    force=True,  # Override any existing configuration
)

# Get a logger for this application and set to INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure uvicorn loggers
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

# Import job URL analyzer (after logger is defined)
try:
    from job_url_analyzer import analyze_job_url as analyze_job_url_hybrid

    JOB_URL_ANALYZER_AVAILABLE = True
except ImportError:
    JOB_URL_ANALYZER_AVAILABLE = False
    logger.warning(
        "job_url_analyzer module not available. Falling back to ChatGPT-only extraction."
    )

# Import LLM configuration endpoint (after logger is defined)
try:
    from llm_config_endpoint import get_llms_endpoint, load_llm_config

    LLM_CONFIG_AVAILABLE = True
except ImportError:
    LLM_CONFIG_AVAILABLE = False
    logger.warning(
        "llm_config_endpoint module not available. LLM configuration endpoint will use fallback."
    )

XAI_SDK_AVAILABLE = False

# MongoDB client already imported above - using app.db.mongodb

# Try to import PyPDF2 for PDF reading (after logger is defined)
try:
    import PyPDF2

    PDF_AVAILABLE = True
except ImportError:
    PDF_AVAILABLE = False
    logger.warning("PyPDF2 not available. PDF reading will not work.")

# Try to import boto3 for AWS S3 access
try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError

    S3_AVAILABLE = True
except ImportError:
    S3_AVAILABLE = False
    logger.warning("boto3 not available. S3 PDF reading will not work.")

# Try to import markdown and weasyprint for PDF generation
try:
    import markdown

    PDF_GENERATION_AVAILABLE = True
except ImportError:
    PDF_GENERATION_AVAILABLE = False
    logger.warning("markdown not available. PDF generation will not work.")

try:
    from weasyprint import HTML

    WEASYPRINT_AVAILABLE = True
except ImportError:
    WEASYPRINT_AVAILABLE = False
    logger.warning("weasyprint not available. PDF generation will not work.")


def send_ntfy_notification(message: str, title: str = "CoverLetter App"):
    """Send a notification to ntfy topic CustomCoverLetter"""
    try:
        requests.post(
            "https://ntfy.sh/CustomCoverLetter",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "default"},
            timeout=5,
        )
    except Exception as e:
        # Silently fail - don't break the app if notifications fail
        logger.debug(f"Failed to send ntfy notification: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )

    # Connect to MongoDB Atlas
    if MONGODB_AVAILABLE:
        connect_to_mongodb()

    # Log OCI configuration variables
    # logger.info(f"oci_config_file: {oci_config_file}")
    # logger.info(f"oci_region: {oci_region}")
    # logger.info(f"oci_compartment_id: {oci_compartment_id}")
    # logger.info(f"oci_config_profile: {oci_config_profile}")
    # logger.info(f"oci_model_id: {oci_model_id}")

    # Send OCI configuration via ntfy
    #     config_summary = f"""OCI Configuration:
    # - Config file: {oci_config_file}
    # - Region: {oci_region}
    # - Compartment ID: {oci_compartment_id}
    # - Config profile: {oci_config_profile}
    # - Model ID: {oci_model_id}
    # - Config exists: {os.path.exists(oci_config_file)}
    # - Compartment ID set: {bool(oci_compartment_id)}"""
    # send_ntfy_notification(config_summary, "OCI Config")

    if not os.path.exists("oci_api_key.pem"):
        #     send_ntfy_notification("File exists!","oci_api_key.pem")
        # else:
        send_ntfy_notification("oci_api_key.pem File does NOT exist.", "oci_api_key.pem")

    yield
    # Shutdown
    if MONGODB_AVAILABLE:
        close_mongodb_connection()


# Create the FastAPI app instance
app = FastAPI(
    title="Cover Letter API",
    description="API for cover letter generation and user management",
    version="1.0.0",
    lifespan=lifespan,
)


# Configure CORS for React app
# Get allowed origins from environment variable or use defaults
cors_origins = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
# Add default localhost origins for development
default_origins = [
    "http://localhost:3000",  # React dev server
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
]
# Combine and filter out empty strings
all_origins = [origin.strip() for origin in cors_origins + default_origins if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=all_origins,
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods (GET, POST, PUT, DELETE, etc.)
    allow_headers=["*"],  # Allows all headers
)

# Register LLM configuration endpoint if available
if LLM_CONFIG_AVAILABLE:
    try:
        get_llms_endpoint(app)
    except Exception as e:
        logger.error(f"Failed to register LLM configuration endpoint: {e}")
        LLM_CONFIG_AVAILABLE = False

# Register refactored API routers
try:
    from app.api.routers import users

    app.include_router(users.router)
except Exception as e:
    logger.error(f"Failed to register users router: {e}", exc_info=True)

try:
    from app.api.routers import (
        job_url,
        llm_config,
        personality,
        config,
        cover_letter,
        files,
        cover_letters,
        pdf,
        sms,
    )

    app.include_router(job_url.router)
    app.include_router(llm_config.router)
    app.include_router(personality.router)
    app.include_router(config.router)
    app.include_router(cover_letter.router)
    app.include_router(files.router)
    app.include_router(cover_letters.router)
    app.include_router(pdf.router)
    app.include_router(sms.router)
except ImportError as e:
    logger.warning(f"Some routers could not be imported: {e}")
except Exception as e:
    logger.error(f"Failed to register some routers: {e}", exc_info=True)


# Add exception handler for validation errors to help debug 422 errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors and log them for debugging"""
    body = await request.body()
    logger.error(f"Validation error on {request.url.path}: {exc.errors()}")
    logger.error(f"Request body: {body.decode('utf-8') if body else 'Empty body'}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "body": body.decode("utf-8") if body else "Empty body",
        },
    )


hf_token = os.getenv("HF_TOKEN")
google_api_key = os.getenv("GOOGLE_API_KEY")
google_places_api_key = os.getenv("GOOGLE_PLACES_API_KEY")
openai_api_key = os.getenv("OPENAI_API_KEY")
anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
gemini_api_key = os.getenv("GEMINI_API_KEY")
xai_api_key = os.getenv("XAI_API_KEY")

oci_compartment_id = os.getenv("OCI_COMPARTMENT_ID")
oci_config_file = os.getenv("OCI_CONFIG_FILE", "/etc/secrets/config")  # ← Render path!
# oci_config_file = os.getenv('OCI_CONFIG_FILE', os.path.expanduser('config'))
oci_config_profile = os.getenv("OCI_CONFIG_PROFILE", "CoverLetter")
oci_region = os.getenv("OCI_REGION", "us-phoenix-1")
oci_model_id = os.getenv(
    "OCI_MODEL_ID",
    "ocid1.generativeaimodel.oc1.phx.amaaaaaask7dceya5zq6k7j3k4m5n6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0",
)

# S3 configuration
# Parse S3_BUCKET_URI to extract bucket name
# Format: s3://bucket-name/path/ or s3://bucket-name/
# Note: The path portion (e.g., "PDF Resumes/") is ignored since we use user_id folders
s3_bucket_uri = os.getenv("S3_BUCKET_URI", "s3://custom-cover-user-resumes/")
if s3_bucket_uri.startswith("s3://"):
    # Remove 's3://' prefix and split by '/'
    uri_without_prefix = s3_bucket_uri[5:]  # Remove 's3://'
    # Extract bucket name (first part before '/')
    s3_bucket_name = uri_without_prefix.split("/")[0]
else:
    # Fallback if URI format is incorrect
    s3_bucket_name = s3_bucket_uri.split("/")[0] if "/" in s3_bucket_uri else s3_bucket_uri

# Resumes are organized by user_id folders: {user_id}/{filename}
# The user_id folder is created automatically when files are uploaded to S3

# AWS credentials from environment variables
aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
aws_region = os.getenv("AWS_REGION", "us-east-1")  # Default region

# Log S3 configuration (without exposing secrets)
if S3_AVAILABLE:
    logger.info(
        f"S3 Configuration: bucket={s3_bucket_name}, region={aws_region}, credentials={'configured' if aws_access_key_id and aws_secret_access_key else 'using default/IAM'}"
    )
else:
    logger.warning("S3 is not available - boto3 is not installed")


# Load system prompt from JSON config file
def load_system_prompt():
    """Load system prompt from JSON config file"""
    config_path = "system_prompt.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        system_prompt = config.get("system_prompt", "")
        if not system_prompt:
            logger.warning(f"System prompt not found in {config_path}. Using default.")
            return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information. IMPORTANT: Any returned HTML must not contain backslashes (\\\\) as carriage returns or line breaks - use only whitespace characters (spaces, tabs) for formatting."

        logger.info(f"Loaded system prompt from {config_path} ({len(system_prompt)} characters)")
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


# Load system message at startup
system_message = load_system_prompt()

# Personality profiles are now stored in user preferences in MongoDB
# No longer loading from JSON file - all profiles come from user's appSettings.personalityProfiles

# Model names mapping
# Try to load GPT model from LLM config, fallback to default
gpt_model = "gpt-5.2"  # Default fallback
if LLM_CONFIG_AVAILABLE:
    try:
        config = load_llm_config()
        gpt_model = config.get("internalModel", "gpt-5.2")
        logger.info(f"Loaded GPT model from config: {gpt_model}")
    except Exception as e:
        logger.warning(f"Failed to load GPT model from config, using default: {e}")

claude_model = "claude-sonnet-4-20250514"
ollama_model = "llama3.2"
OLLAMA_API = "http://localhost:11434/api/chat"
xai_model = "grok-4-fast-reasoning"

# we need to move this to the server side and make it dynamic
LLM_ENVIRONMENT_MAPPING = [
    ("ChatGPT", "gpt-4.1", openai_api_key),
    ("Claude", "claude-sonnet-4-20250514", anthropic_api_key),
    ("Gemini", "gemini-2.5-flash", gemini_api_key),
    ("Grok", "grok-4-fast-reasoning", xai_api_key),
    # ("OCI (Llama)", "oci-generative-ai", oci_compartment_id),
]


def get_available_llms():
    """Get available LLMs based on configured API keys/credentials"""
    available = []
    for display_name, model_name, api_key in LLM_ENVIRONMENT_MAPPING:
        # For OCI, api_key is actually oci_compartment_id
        # OCI also needs a config file, so check both
        if model_name == "oci-generative-ai":
            # For OCI, check if compartment_id is set
            # Config file check is done at runtime in post_to_llm with error handling
            has_compartment = bool(api_key)
            has_config = os.path.exists(oci_config_file)
            logger.info(
                f"OCI check - compartment_id: {has_compartment}, config_file: {oci_config_file}, exists: {has_config}"
            )
            if has_compartment:
                # Show OCI option if compartment_id is set, even if config file doesn't exist yet
                # The error will be handled gracefully in post_to_llm
                available.append({"label": display_name, "value": model_name})
            else:
                logger.info(f"Skipping {display_name} - compartment_id not set")
        elif api_key:
            available.append({"label": display_name, "value": model_name})
        else:
            logger.info(f"Skipping {display_name} - no credentials configured")
    # logger.info(f"Available LLMs: {available}")
    return available


# Define the data model we expect to receive from the app
# This ensures the 'prompt' is a string
class ChatRequest(BaseModel):
    prompt: str
    active_model: str = "gpt-4.1"  # Default model

    class Config:
        # Allow extra fields to be ignored
        extra = "ignore"


# Define the data model for job info request
class JobInfoRequest(BaseModel):
    llm: str
    date_input: str
    company_name: str
    hiring_manager: str
    ad_source: str
    resume: str
    jd: str  # Job description
    additional_instructions: str = ""
    tone: str = "Professional"
    address: str = ""  # City, State
    phone_number: str = ""
    user_id: Optional[str] = None  # Optional user ID to access custom personality profiles
    user_email: Optional[str] = None  # Optional user email to access custom personality profiles


# Define the data model for file upload request
class FileUploadRequest(BaseModel):
    fileName: str
    fileData: str  # base64 encoded
    contentType: str = "application/pdf"
    user_id: Optional[str] = None
    user_email: Optional[str] = None


# Define the data model for file rename request
class FileRenameRequest(BaseModel):
    oldKey: str  # Current S3 key (user_id/filename)
    newFileName: str  # New filename (just the filename, not the full path)
    user_id: Optional[str] = None
    user_email: Optional[str] = None


# Define the data model for file delete request
class FileDeleteRequest(BaseModel):
    key: str  # S3 key (user_id/filename)
    user_id: Optional[str] = None
    user_email: Optional[str] = None


# Define the data model for saving cover letter
class SaveCoverLetterRequest(BaseModel):
    coverLetterContent: str  # The cover letter content (markdown, HTML, or base64-encoded PDF)
    fileName: Optional[str] = None  # Optional custom filename (without extension)
    contentType: str = (
        "text/markdown"  # Content type: "text/markdown", "text/html", or "application/pdf"
    )
    user_id: Optional[str] = None
    user_email: Optional[str] = None


# Define the data model for cover letter operations
class CoverLetterRequest(BaseModel):
    key: str  # S3 key (user_id/generated_cover_letters/filename)
    user_id: Optional[str] = None
    user_email: Optional[str] = None


# Define the data models for PDF generation
class Margins(BaseModel):
    top: float
    right: float
    bottom: float
    left: float


class PageSize(BaseModel):
    width: float
    height: float


class PrintProperties(BaseModel):
    margins: Margins
    fontFamily: Optional[str] = "Times New Roman"
    fontSize: Optional[float] = 12
    lineHeight: Optional[float] = 1.6
    pageSize: Optional[PageSize] = Field(default_factory=lambda: PageSize(width=8.5, height=11.0))
    useDefaultFonts: Optional[bool] = False


class GeneratePDFRequest(BaseModel):
    markdownContent: str
    printProperties: PrintProperties
    user_id: Optional[str] = None
    user_email: Optional[str] = None


# Define the data model for job URL analysis request
class JobURLAnalysisRequest(BaseModel):
    url: str  # URL to the job posting page
    user_id: Optional[str] = None
    user_email: Optional[str] = None


def post_to_llm(prompt: str, model: str = "gpt-4.1"):
    return_response = None
    if model == "gpt-4.1" or model == "gpt-5.2" or model.startswith("gpt-"):
        client = OpenAI(api_key=openai_api_key)
        # Use high max_completion_tokens for GPT-5.2 (supports 128,000 max completion tokens)
        if model == "gpt-5.2":
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
    elif model == "claude-sonnet-4-20250514":
        client = anthropic.Anthropic(api_key=anthropic_api_key)
        response = client.messages.create(
            model=model,
            system="You are a helpful assistant.",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=20000,
            temperature=1,
        )
        return_response = response.content[0].text.replace("```json", "").replace("```", "")
    elif model == "gemini-2.5-flash":
        genai.configure(api_key=gemini_api_key)
        client = genai.GenerativeModel(model)
        # client = genai.Client(api_key=gemini_api_key)
        response = client.generate_content(contents=prompt)
        return_response = response.text
    elif model == "grok-4-fast-reasoning":
        # Fallback to direct HTTP requests (no SDK needed)
        headers = {
            "Authorization": f"Bearer {xai_api_key}",
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
    elif model == "oci-generative-ai":
        try:
            # Initialize OCI config from file
            config = oci.config.from_file(oci_config_file, oci_config_profile)

            # Create Generative AI client — FIXED: pass config!
            service_endpoint = f"https://inference.generativeai.{oci_region}.oci.oraclecloud.com"
            generative_ai_client = oci.generative_ai_inference.GenerativeAiInferenceClient(
                config=config,  # ← THIS WAS MISSING
                service_endpoint=service_endpoint,
            )

            # Prepare the serving mode
            serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(
                model_id=oci_model_id
            )

            # Prepare the inference request
            full_prompt = f"You are a helpful assistant.\n\nUser: {prompt}\nAssistant:"

            # Use Cohere request for Cohere models (or Llama if using Llama)
            inference_request = oci.generative_ai_inference.models.LlamaLlmInferenceRequest(
                prompt=full_prompt, max_tokens=2048, temperature=0.7
            )
            # Create generate text details
            generate_text_details = oci.generative_ai_inference.models.GenerateTextDetails(
                serving_mode=serving_mode,
                compartment_id=oci_compartment_id,
                inference_request=inference_request,
            )

            # Make the request
            response = generative_ai_client.generate_text(generate_text_details)
            return_response = response.data.inference_response.generated_texts[0].text

        except Exception as e:
            error_msg = f"Error calling OCI Generative AI: {str(e)}. Ensure OCI config file exists at {oci_config_file} and OCI_COMPARTMENT_ID is set."
            logger.error(error_msg)
            send_ntfy_notification(error_msg, "OCI Error")
            return_response = error_msg

    return return_response


def get_text(contents):
    """Helper function to extract text from OCI content list"""
    text = ""
    for content in contents:
        if hasattr(content, "text"):
            text += content.text
        elif isinstance(content, str):
            text += content
    return text


def read_pdf_from_bytes(pdf_bytes: bytes) -> str:
    """Extract text content from PDF bytes"""
    if not PDF_AVAILABLE:
        raise ImportError("PyPDF2 is not installed. Cannot read PDF files.")

    try:
        text_content = ""
        from io import BytesIO

        pdf_file = BytesIO(pdf_bytes)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        num_pages = len(pdf_reader.pages)

        for page_num in range(num_pages):
            page = pdf_reader.pages[page_num]
            text_content += page.extract_text()
            if page_num < num_pages - 1:
                text_content += "\n\n"

        logger.info(f"Successfully extracted text from PDF ({num_pages} pages)")
        return text_content.strip()
    except Exception as e:
        logger.error(f"Error reading PDF: {str(e)}")
        return f"[Error reading PDF: {str(e)}]"


def get_s3_client():
    """Get S3 client with proper credentials"""
    if not S3_AVAILABLE:
        raise ImportError("boto3 is not installed. Cannot access S3.")

    # Create S3 client with credentials if provided, otherwise use default (IAM role, credentials file, etc.)
    if aws_access_key_id and aws_secret_access_key:
        logger.info("Using AWS credentials from environment variables")
        return boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region,
        )
    else:
        logger.info("Using default AWS credentials (IAM role, credentials file, or environment)")
        return boto3.client("s3", region_name=aws_region)


def ensure_user_s3_folder(user_id: str) -> bool:
    """
    Ensure a user's S3 folder exists. If it doesn't exist, create it.
    In S3, folders are just prefixes, so we create a placeholder object.
    Returns True if folder exists or was created successfully, False otherwise.
    """
    if not S3_AVAILABLE or not s3_bucket_name:
        logger.warning("S3 is not available. Cannot ensure user folder.")
        return False

    if not user_id:
        logger.warning("user_id is required to ensure S3 folder.")
        return False

    try:
        s3_client = get_s3_client()
        folder_prefix = f"{user_id}/"
        placeholder_key = f"{user_id}/.folder_initialized"

        # Check if folder exists by trying to list objects with the prefix
        try:
            response = s3_client.list_objects_v2(
                Bucket=s3_bucket_name, Prefix=folder_prefix, MaxKeys=1
            )

            # If we get any objects (even the placeholder), folder exists
            if "Contents" in response and len(response["Contents"]) > 0:
                logger.info(f"User S3 folder already exists: {folder_prefix}")
                return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AccessDenied":
                logger.warning(f"Cannot check if folder exists (AccessDenied): {e}")
                # Continue to try creating it anyway
            else:
                logger.warning(f"Error checking folder existence: {error_code}")

        # Folder doesn't exist or we can't check, create placeholder
        try:
            s3_client.put_object(
                Bucket=s3_bucket_name,
                Key=placeholder_key,
                Body=b"",
                ContentType="text/plain",
            )
            logger.info(f"Created user S3 folder: {folder_prefix}")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to create user S3 folder: {error_code} - {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error ensuring user S3 folder: {e}")
        return False


def ensure_cover_letter_subfolder(user_id: str) -> bool:
    """
    Ensure a user's generated_cover_letters subfolder exists. If it doesn't exist, create it.
    Returns True if subfolder exists or was created successfully, False otherwise.
    """
    if not S3_AVAILABLE or not s3_bucket_name:
        logger.warning("S3 is not available. Cannot ensure cover letter subfolder.")
        return False

    if not user_id:
        logger.warning("user_id is required to ensure cover letter subfolder.")
        return False

    try:
        # First ensure the main user folder exists
        ensure_user_s3_folder(user_id)

        s3_client = get_s3_client()
        subfolder_prefix = f"{user_id}/generated_cover_letters/"
        placeholder_key = f"{user_id}/generated_cover_letters/.folder_initialized"

        # Check if subfolder exists by trying to list objects with the prefix
        try:
            response = s3_client.list_objects_v2(
                Bucket=s3_bucket_name, Prefix=subfolder_prefix, MaxKeys=1
            )

            # If we get any objects (even the placeholder), subfolder exists
            if "Contents" in response and len(response["Contents"]) > 0:
                logger.info(f"Cover letter subfolder already exists: {subfolder_prefix}")
                return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            if error_code == "AccessDenied":
                logger.warning(f"Cannot check if subfolder exists (AccessDenied): {e}")
                # Continue to try creating it anyway
            else:
                logger.warning(f"Error checking subfolder existence: {error_code}")

        # Subfolder doesn't exist or we can't check, create placeholder
        try:
            s3_client.put_object(
                Bucket=s3_bucket_name,
                Key=placeholder_key,
                Body=b"",
                ContentType="text/plain",
            )
            logger.info(f"Created cover letter subfolder: {subfolder_prefix}")
            return True
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            logger.error(f"Failed to create cover letter subfolder: {error_code} - {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error ensuring cover letter subfolder: {e}")
        return False


def download_pdf_from_s3(s3_path: str) -> bytes:
    """Download PDF from S3 bucket and return as bytes"""
    if not S3_AVAILABLE:
        raise ImportError("boto3 is not installed. Cannot download from S3.")

    try:
        # Parse S3 path - could be s3://bucket/key or just bucket/key
        if s3_path.startswith("s3://"):
            s3_path = s3_path[5:]  # Remove 's3://' prefix

        # Split bucket and key
        parts = s3_path.split("/", 1)
        if len(parts) != 2:
            raise ValueError(
                f"Invalid S3 path format: {s3_path}. Expected format: bucket/key or s3://bucket/key"
            )

        bucket_name = parts[0]
        object_key = parts[1]

        logger.info(f"Downloading PDF from S3: bucket={bucket_name}, key={object_key}")

        # Get S3 client
        s3_client = get_s3_client()

        # Download the object
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        pdf_bytes = response["Body"].read()

        logger.info(f"Successfully downloaded PDF from S3 ({len(pdf_bytes)} bytes)")
        return pdf_bytes

    except NoCredentialsError:
        error_msg = (
            "AWS credentials not found. Cannot download from S3. "
            "Please set AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY environment variables, "
            "or configure AWS credentials file, or use an IAM role."
        )
        logger.error(error_msg)
        raise Exception(error_msg)
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"Error downloading from S3: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)
    except Exception as e:
        error_msg = f"Unexpected error downloading from S3: {str(e)}"
        logger.error(error_msg)
        raise Exception(error_msg)


def read_pdf_file(file_path: str) -> str:
    """Read PDF file from local filesystem and extract text content"""
    if not PDF_AVAILABLE:
        raise ImportError("PyPDF2 is not installed. Cannot read PDF files.")

    if not os.path.exists(file_path):
        logger.warning(f"PDF file not found: {file_path}")
        return f"[PDF file not found: {file_path}]"

    try:
        with open(file_path, "rb") as file:
            pdf_bytes = file.read()
        return read_pdf_from_bytes(pdf_bytes)
    except Exception as e:
        logger.error(f"Error reading PDF file {file_path}: {str(e)}")
        return f"[Error reading PDF file: {str(e)}]"


def get_oc_info(prompt: str):
    """Helper function to get response from OCI Generative AI using GenericChatRequest"""
    try:
        # Initialize OCI config from file
        config = oci.config.from_file(oci_config_file, oci_config_profile)

        # Create Generative AI client
        service_endpoint = f"https://inference.generativeai.{oci_region}.oci.oraclecloud.com"
        generative_ai_inference_client = oci.generative_ai_inference.GenerativeAiInferenceClient(
            config=config,
            service_endpoint=service_endpoint,
            retry_strategy=oci.retry.NoneRetryStrategy(),
            timeout=(10, 240),
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
        oci_chat_detail.serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(
            model_id=oci_model_id
        )
        oci_chat_detail.chat_request = chat_request
        oci_chat_detail.compartment_id = oci_compartment_id

        # Make the chat request
        chat_response = generative_ai_inference_client.chat(oci_chat_detail)

        if not chat_response:
            return json.dumps(
                {
                    "markdown": "Error: No response from OCI",
                    "html": "<p>Error: No response from OCI</p>",
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
        return json.dumps({"markdown": f"Error: {error_msg}", "html": f"<p>Error: {error_msg}</p>"})


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


# Import get_job_info from service (maintained for backward compatibility with existing endpoints)
try:
    from app.services.cover_letter_service import get_job_info
except ImportError:
    logger.warning("Could not import get_job_info from service. Some endpoints may not work.")

    # Fallback: define a stub function that raises an error
    def get_job_info(*args, **kwargs):
        raise ImportError(
            "get_job_info service not available. Please ensure app/services/cover_letter_service.py exists."
        )


# Legacy function definition removed - now imported from app.services.cover_letter_service
# The original function definition (~690 lines) has been moved to app/services/cover_letter_service.py


# Define a simple root endpoint to check if the server is running
@app.get("/")
def read_root():
    return {"status": f"Simon's API is running with Hugging Face token: {hf_token[:8]}"}


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint to verify server is ready to load user preferences.
    Checks MongoDB connection and users collection accessibility.
    This endpoint is designed to be called at intervals by the client.
    """
    health_status = {
        "ready": False,
        "mongodb": {
            "available": False,
            "connected": False,
            "collection_accessible": False,
        },
        "timestamp": datetime.datetime.now().isoformat(),
    }

    # Check MongoDB availability
    if not MONGODB_AVAILABLE:
        health_status["mongodb"]["available"] = False
        return JSONResponse(status_code=503, content=health_status)

    health_status["mongodb"]["available"] = True

    # Check MongoDB connection
    try:
        # is_connected and get_collection already imported from app.db.mongodb above
        if not is_connected():
            health_status["mongodb"]["connected"] = False
            return JSONResponse(status_code=503, content=health_status)

        health_status["mongodb"]["connected"] = True

        # Check if users collection is accessible
        try:
            collection = get_collection("users")
            if collection is None:
                logger.warning("Collection is None - database not initialized")
                health_status["mongodb"]["collection_accessible"] = False
                return JSONResponse(status_code=503, content=health_status)

            # Try a simple operation to verify collection access
            # Use estimated_document_count() for a lightweight check (doesn't scan all documents)
            # This is faster than count_documents() as it uses collection metadata
            try:
                collection.estimated_document_count()
                health_status["mongodb"]["collection_accessible"] = True
            except Exception as count_error:
                # Fallback: try a simple find_one operation
                logger.debug(f"estimated_document_count failed, trying find_one: {count_error}")
                collection.find_one({}, {"_id": 1})  # Just get _id field, very lightweight
                health_status["mongodb"]["collection_accessible"] = True

        except Exception as e:
            logger.error(f"Users collection not accessible: {e}", exc_info=True)
            health_status["mongodb"]["collection_accessible"] = False
            health_status["mongodb"]["error"] = str(e)
            return JSONResponse(status_code=503, content=health_status)

        # All checks passed - server is ready
        health_status["ready"] = True
        return JSONResponse(status_code=200, content=health_status)

    except Exception as e:
        logger.error(f"Health check error: {e}")
        health_status["error"] = str(e)
        return JSONResponse(status_code=503, content=health_status)


# Define the main endpoint your app will call


# Fallback endpoint if llm_config_endpoint is not available
if not LLM_CONFIG_AVAILABLE:

    @app.get("/api/llms")
    def get_llms_fallback():
        """JSON API endpoint to get available LLMs for the mobile app (fallback)"""
        llm_options = get_available_llms()
        return {"llms": llm_options}


@app.get("/api/personality-profiles")
def get_personality_profiles(user_id: Optional[str] = None, user_email: Optional[str] = None):
    """JSON API endpoint to get available personality profiles for the UI from user's preferences"""
    if not user_id and not user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id or user_email is required",
        )

    try:
        from user_api import get_user_by_id, get_user_by_email

        user = None
        if user_id:
            user = get_user_by_id(user_id)
        elif user_email:
            user = get_user_by_email(user_email)

        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get user's custom personality profiles
        # Note: user_doc_to_response already normalizes personalityProfiles to {"id", "name", "description"} structure
        user_prefs = user.preferences if user.preferences else {}
        if isinstance(user_prefs, dict):
            app_settings = user_prefs.get("appSettings", {})
            if isinstance(app_settings, dict):
                custom_profiles = app_settings.get("personalityProfiles", [])
                # Ensure profiles are normalized (should already be normalized, but verify)
                if custom_profiles:
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

        # Format profiles for the UI
        # Structure is already normalized to {"id", "name", "description"}
        profiles = []
        for profile in custom_profiles:
            if isinstance(profile, dict) and profile.get("id") and profile.get("name"):
                # Format for UI (add label and value for compatibility)
                profiles.append(
                    {
                        "id": profile.get("id", ""),
                        "name": profile.get("name", "Unknown"),
                        "description": profile.get("description", ""),
                        "label": profile.get("name", "Unknown"),  # For UI compatibility
                        "value": profile.get("name", "Unknown"),  # For UI compatibility
                    }
                )

        return {"profiles": profiles}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving personality profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving personality profiles: {str(e)}",
        )


@app.get("/api/system-prompt")
def get_system_prompt():
    """JSON API endpoint to get the current system prompt"""
    # Reload system prompt to get latest from file (useful if file is updated)
    global system_message
    system_message = load_system_prompt()
    return {"system_prompt": system_message}


@app.get("/api/config/google-places-key")
def get_google_places_key():
    """JSON API endpoint to get the Google Places API key"""
    return {"apiKey": google_places_api_key}


@app.get("/llm-selector", response_class=HTMLResponse)
def llm_selector():
    llm_options = get_available_llms()
    # Use INFO level and also print for maximum visibility on Render
    logger.info(f"llm_options: {llm_options}")
    print(f"[LLM_SELECTOR] llm_options: {llm_options}")  # Fallback for Render logs
    if not llm_options:
        body = "<p>No large language models are configured.</p>"
    else:
        radio_buttons = "".join(
            f"""
            <label style="display:block; margin-bottom:6px;">
                <input type="radio" name="active_model" value="{option['value']}" {'checked' if index == 0 else ''}>
                {option['label']}
            </label>
            """
            for index, option in enumerate(llm_options)
        )
        body = f"""
        <form id="llm-selector" style="font-family:Arial, sans-serif; max-width:280px;">
            <fieldset style="border:1px solid #ccc; padding:12px;">
                <legend style="padding:0 6px; font-weight:bold;">Choose Your LLM</legend>
                {radio_buttons}
            </fieldset>
        </form>
        """

    return HTMLResponse(content=body, media_type="text/html")


@app.post("/chat")
async def handle_chat(request: Request):
    """Handle both simple chat requests and job info requests"""
    try:
        body = await request.json()

        # Check if resume is an S3 key and needs to be fetched
        resume = body.get("resume")
        user_id = body.get("user_id")

        if resume and S3_AVAILABLE and s3_bucket_name:
            # Check if resume looks like an S3 key (contains '/' or ends with .pdf)
            is_s3_key = "/" in resume or resume.endswith((".pdf", ".PDF"))

            if is_s3_key and user_id:
                try:
                    # Determine the S3 key
                    # If resume already contains user_id/, use it directly
                    if resume.startswith(f"{user_id}/"):
                        s3_key = resume
                    else:
                        # Check if it's already a full S3 key (starts with another user_id)
                        parts = resume.split("/", 1)
                        if len(parts) == 2 and len(parts[0]) == 24:  # MongoDB ObjectId length
                            # Already has a user_id prefix, use as-is
                            s3_key = resume
                        else:
                            # Extract filename and prepend user_id
                            filename = os.path.basename(resume.replace("\\", "/"))
                            s3_key = f"{user_id}/{filename}"

                    s3_path = f"s3://{s3_bucket_name}/{s3_key}"
                    logger.info(f"Fetching PDF from S3: {s3_path}")

                    # Download PDF from S3
                    s3_client = get_s3_client()
                    response = s3_client.get_object(Bucket=s3_bucket_name, Key=s3_key)
                    pdf_bytes = response["Body"].read()

                    # Extract text from PDF
                    resume_text = read_pdf_from_bytes(pdf_bytes)

                    # Replace resume field with extracted text
                    body["resume"] = resume_text

                    # Also update message object if it's being used
                    if "message" in body and body["message"]:
                        try:
                            message_obj = json.loads(body["message"])
                            message_obj["resume"] = resume_text
                            body["message"] = json.dumps(message_obj)
                            logger.info("Updated resume in message object")
                        except (json.JSONDecodeError, TypeError) as e:
                            logger.warning(f"Could not parse message object: {e}")

                    logger.info("Successfully fetched and extracted text from S3 PDF")
                except Exception as e:
                    logger.warning(
                        f"Failed to fetch PDF from S3: {str(e)}. Continuing with original resume value."
                    )

        # Check if this is a job info request
        # Look for job info fields: llm + (company_name OR jd OR resume)
        is_job_info_request = "llm" in body and (
            "company_name" in body or "jd" in body or "resume" in body
        )

        if is_job_info_request:
            logger.info("Detected job info request in /chat endpoint, routing to job-info handler")
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
            try:
                job_request = JobInfoRequest(**body)
            except Exception as e:
                logger.error(f"Invalid job info request: {e}")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "Invalid job info request",
                        "detail": str(e),
                    },
                )
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
            logger.info(
                f"Received chat request - prompt length: {len(chat_request.prompt)}, model: {chat_request.active_model}"
            )
            response = post_to_llm(chat_request.prompt, chat_request.active_model)

            # Increment LLM usage count if user_id or user_email is provided
            if response:  # Only increment if LLM call was successful
                user_id_for_tracking = body.get("user_id")
                user_email_for_tracking = body.get("user_email")

                if user_id_for_tracking:
                    normalized_llm = normalize_llm_name(chat_request.active_model)
                    try:
                        increment_llm_usage_count(user_id_for_tracking, normalized_llm)
                        logger.info(
                            f"Incremented LLM usage count for {normalized_llm} (user_id: {user_id_for_tracking})"
                        )
                    except Exception as e:
                        logger.warning(f"Failed to increment LLM usage count: {e}")
                elif user_email_for_tracking:
                    try:
                        if MONGODB_AVAILABLE:
                            user = get_user_by_email(user_email_for_tracking)
                            normalized_llm = normalize_llm_name(chat_request.active_model)
                            increment_llm_usage_count(user.id, normalized_llm)
                            logger.info(
                                f"Incremented LLM usage count for {normalized_llm} (user_email: {user_email_for_tracking})"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to increment LLM usage count from email: {e}")

            return {
                "response": (
                    response
                    if response
                    else f"Error: No response from LLM {chat_request.active_model}"
                )
            }
    except HTTPException as e:
        # Re-raise HTTPException so FastAPI can handle it properly
        raise
    except Exception as e:
        logger.error(f"Error in handle_chat: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={"error": "Internal server error", "detail": str(e)},
        )


# Debug endpoint to see raw request
@app.post("/chat-debug")
async def handle_chat_debug(request: Request):
    """Debug endpoint to see what's being received"""
    body = await request.body()
    logger.info(f"Raw request body: {body}")
    logger.info(f"Content-Type: {request.headers.get('content-type')}")
    try:
        json_body = await request.json()
        logger.info(f"Parsed JSON: {json_body}")
        return {"received": json_body}
    except Exception as e:
        logger.error(f"Failed to parse JSON: {e}")
        return {"error": str(e), "raw_body": body.decode("utf-8") if body else "Empty"}


@app.post("/api/job-info")
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


# User API Endpoints - DEPRECATED: These endpoints are now handled by app/api/routers/users.py
# Keeping imports for backward compatibility with other parts of main.py that may still use these functions
from user_api import (
    UserRegisterRequest,
    UserUpdateRequest,
    UserResponse,
    UserLoginRequest,
    UserLoginResponse,
    register_user,
    get_user_by_id,
    get_user_by_email,
    update_user,
    delete_user,
    login_user,
    increment_llm_usage_count,
)

# NOTE: User endpoints are now handled by app/api/routers/users.py
# These endpoints below are commented out to avoid conflicts when using app.main:app
# Uncomment only if you need to use main.py directly instead of app.main:app

# @app.post(
#     "/api/users/register",
#     response_model=UserResponse,
#     status_code=status.HTTP_201_CREATED,
# )
# async def register_user_endpoint(user_data: UserRegisterRequest):
#     """Register a new user"""
#     logger.info(f"User registration request: {user_data.email}")
#     user_response = register_user(user_data)
#
#     # Log that form fields have been cleared for new user
#     logger.info(
#         f"✓ New user registered: {user_response.email} (ID: {user_response.id})"
#     )
#     logger.info(f"  Form fields initialized to empty/placeholder values")
#     logger.info(f"  - Company Name: ''")
#     logger.info(f"  - Hiring Manager: ''")
#     logger.info(f"  - Ad Source: ''")
#     logger.info(f"  - Job Description: ''")
#     logger.info(f"  - Additional Instructions: ''")
#     logger.info(f"  - Tone: 'Professional' (default)")
#     logger.info(f"  - Address: ''")
#     logger.info(f"  - Phone Number: ''")
#     logger.info(f"  - Resume: ''")
#
#     return user_response


# @app.post("/api/users/login", response_model=UserLoginResponse)
# async def login_user_endpoint(login_data: UserLoginRequest):
#     """Authenticate user login"""
#     logger.info(f"Login attempt: {login_data.email}")
#     login_response = login_user(login_data)
#
#     # After successful login, ensure user's S3 folder exists and log details
#     if login_response.success and login_response.user:
#         user_id = login_response.user.id
#         user_name = login_response.user.name
#         user_email = login_response.user.email
#
#         # Log successful login
#         logger.info("=" * 80)
#         logger.info(f"✓ USER LOGGED IN SUCCESSFULLY")
#         logger.info(f"  User ID: {user_id}")
#         logger.info(f"  Name: {user_name}")
#         logger.info(f"  Email: {user_email}")
#         logger.info("=" * 80)
#
#         # Check and ensure S3 folder exists
#         logger.info(f"Checking AWS S3 folder for user_id: {user_id}")
#         folder_exists = False
#         file_count = 0
#
#         if S3_AVAILABLE and s3_bucket_name:
#             try:
#                 s3_client = get_s3_client()
#                 folder_prefix = f"{user_id}/"
#
#                 # Check if folder exists by listing objects
#                 try:
#                     response = s3_client.list_objects_v2(
#                         Bucket=s3_bucket_name,
#                         Prefix=folder_prefix,
#                         MaxKeys=1000,  # Get up to 1000 files to count
#                     )
#
#                     if "Contents" in response:
#                         # Count actual files (exclude placeholder)
#                         files = [
#                             obj
#                             for obj in response["Contents"]
#                             if not obj["Key"].endswith("/")
#                             and not obj["Key"].endswith(".folder_initialized")
#                         ]
#                         file_count = len(files)
#                         folder_exists = True
#
#                         logger.info(f"✓ AWS S3 folder EXISTS: {folder_prefix}")
#                         logger.info(f"  Files in folder: {file_count}")
#                         if file_count > 0:
#                             logger.info(f"  Sample files (first 5):")
#                             for i, obj in enumerate(files[:5], 1):
#                                 filename = obj["Key"].replace(folder_prefix, "")
#                                 logger.info(
#                                     f"    {i}. {filename} ({obj['Size']} bytes)"
#                                 )
#                     else:
#                         # Folder might exist but be empty, or doesn't exist
#                         folder_exists = False
#                         logger.info(
#                             f"⚠ AWS S3 folder appears empty or doesn't exist: {folder_prefix}"
#                         )
#
#                 except ClientError as e:
#                     error_code = e.response.get("Error", {}).get("Code", "Unknown")
#                     if error_code == "AccessDenied":
#                         logger.warning(
#                             f"⚠ Cannot check S3 folder (AccessDenied) - may need permissions"
#                         )
#                     else:
#                         logger.warning(f"⚠ Error checking S3 folder: {error_code}")
#
#                 # Ensure folder exists (create if needed)
#                 folder_created = ensure_user_s3_folder(user_id)
#                 if folder_created and not folder_exists:
#                     logger.info(f"✓ Created new AWS S3 folder: {folder_prefix}")
#                     folder_exists = True
#                 elif folder_created:
#                     logger.info(f"✓ AWS S3 folder verified: {folder_prefix}")
#                 else:
#                     logger.warning(
#                         f"⚠ Could not ensure S3 folder for user_id: {user_id} (non-critical)"
#                     )
#
#             except Exception as e:
#                 logger.error(f"✗ Error checking/creating S3 folder: {str(e)}")
#         else:
#             logger.warning("⚠ S3 is not available - cannot check user folder")
#
#         # Final summary log
#         logger.info("=" * 80)
#         logger.info(f"LOGIN SUMMARY for user_id: {user_id}")
#         logger.info(f"  AWS S3 Folder Exists: {'YES' if folder_exists else 'NO'}")
#         logger.info(f"  Files in Folder: {file_count}")
#         logger.info("=" * 80)
#
#     return login_response


# NOTE: User endpoints are now handled by app/api/routers/users.py
# These endpoints below are commented out to avoid conflicts when using app.main:app
# Uncomment only if you need to use main.py directly instead of app.main:app

# @app.get("/api/users/{user_id}", response_model=UserResponse)
# async def get_user_by_id_endpoint(user_id: str):
#     """Get user by ID"""
#     logger.info(f"Get user request: {user_id}")
#     return get_user_by_id(user_id)


# @app.get("/api/users/email/{email}", response_model=UserResponse)
# async def get_user_by_email_endpoint(email: str):
#     """Get user by email"""
#     logger.info(f"Get user by email request: {email}")
#     return get_user_by_email(email)


# @app.put("/api/users/{user_id}", response_model=UserResponse)
# async def update_user_endpoint(user_id: str, updates: UserUpdateRequest):
#     """Update user information"""
#     logger.info(f"Update user request: {user_id}")
#     return update_user(user_id, updates)


# @app.delete("/api/users/{user_id}")
# async def delete_user_endpoint(user_id: str):
#     """Delete user"""
#     logger.info(f"Delete user request: {user_id}")
#     return delete_user(user_id)


# File API Endpoints (S3 Operations)
@app.get("/api/files/list")
async def list_files(user_id: Optional[str] = None, user_email: Optional[str] = None):
    """
    List files from S3 bucket for the authenticated user.
    Files are organized by user_id folders: {user_id}/{filename}
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email to list files
    if not user_id and not user_email:
        raise HTTPException(
            status_code=400, detail="user_id or user_email is required to list files"
        )

    # If user_email is provided but not user_id, try to get user_id from email
    if user_email and not user_id:
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(user_email)
                user_id = user.user_id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(status_code=404, detail=f"User not found for email: {user_email}")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required to list files")

    try:
        # Ensure user's S3 folder exists before listing
        ensure_user_s3_folder(user_id)

        s3_client = get_s3_client()

        # List objects with user_id prefix
        prefix = f"{user_id}/"
        response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix=prefix)

        files = []
        cover_letters_prefix = f"{user_id}/generated_cover_letters/"
        if "Contents" in response:
            for obj in response["Contents"]:
                # Only return actual files (not folders/directories or placeholder files)
                if not obj["Key"].endswith("/") and not obj["Key"].endswith(".folder_initialized"):
                    # Exclude files from the generated_cover_letters subfolder
                    if obj["Key"].startswith(cover_letters_prefix):
                        continue  # Skip files in the generated_cover_letters subfolder

                    # Only include files directly in the user's main folder (not in any subfolder)
                    # Check if the key has any additional path separators after user_id/
                    key_after_prefix = obj["Key"][len(prefix) :]
                    if "/" in key_after_prefix:
                        continue  # Skip files in subfolders

                    # Extract filename from key (remove user_id/ prefix)
                    filename = obj["Key"].replace(prefix, "")
                    files.append(
                        {
                            "key": obj["Key"],
                            "name": filename,
                            "size": obj["Size"],
                            "lastModified": obj["LastModified"].isoformat(),
                        }
                    )

        # Sort by lastModified (newest first)
        files.sort(key=lambda x: x["lastModified"], reverse=True)

        logger.info(f"Listed {len(files)} files for user_id: {user_id}")
        return {"files": files}

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Error listing files: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/api/files/upload")
async def upload_file(request: FileUploadRequest):
    """
    Upload a file to S3 bucket on behalf of the user.
    Files are organized by user_id folders: {user_id}/{filename}
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email to upload files
    if not request.user_id and not request.user_email:
        raise HTTPException(
            status_code=400, detail="user_id or user_email is required to upload files"
        )

    # If user_email is provided but not user_id, try to get user_id from email
    user_id = request.user_id
    if request.user_email and not user_id:
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(request.user_email)
                user_id = user.user_id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}",
            )

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required to upload files")

    # Ensure user's S3 folder exists before uploading
    ensure_user_s3_folder(user_id)

    try:
        # Decode base64 fileData
        try:
            file_bytes = base64.b64decode(request.fileData)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Invalid base64 fileData: {str(e)}")

        # Validate file type (only PDFs for now)
        if not request.fileName.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are allowed")

        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_bytes) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {max_size / (1024 * 1024)}MB",
            )

        # Sanitize filename to ensure it's safe for S3 (keep original name)
        # Only replace characters that could cause issues, preserve the original structure
        safe_filename = re.sub(r"[^a-zA-Z0-9._\-\s]", "_", request.fileName)
        # Remove any leading/trailing spaces and dots
        safe_filename = safe_filename.strip(". ")

        # Use original filename (sanitized) - no timestamp prefix
        # If a file with the same name exists, S3 will overwrite it
        original_filename = safe_filename

        # Construct S3 key: user_id/filename
        s3_key = f"{user_id}/{original_filename}"

        # Upload to S3
        s3_client = get_s3_client()
        s3_client.put_object(
            Bucket=s3_bucket_name,
            Key=s3_key,
            Body=file_bytes,
            ContentType=request.contentType,
        )

        logger.info(f"Uploaded file to S3: {s3_key} ({len(file_bytes)} bytes)")
        logger.info(f"  Original filename: {request.fileName}")
        logger.info(f"  Stored as: {original_filename}")

        # Get updated file list after upload
        files = []
        try:
            prefix = f"{user_id}/"
            response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix=prefix)

            if "Contents" in response:
                for obj in response["Contents"]:
                    # Only return actual files (not folders/directories or placeholder files)
                    if not obj["Key"].endswith("/") and not obj["Key"].endswith(
                        ".folder_initialized"
                    ):
                        # Extract filename from key (remove user_id/ prefix)
                        filename = obj["Key"].replace(prefix, "")
                        files.append(
                            {
                                "key": obj["Key"],
                                "name": filename,
                                "size": obj["Size"],
                                "lastModified": obj["LastModified"].isoformat(),
                            }
                        )

            # Sort by lastModified (newest first)
            files.sort(key=lambda x: x["lastModified"], reverse=True)
            logger.info(f"Returning updated file list with {len(files)} files")
        except Exception as e:
            logger.warning(f"Could not fetch updated file list: {e}")
            # Continue without file list - upload was successful

        return {
            "success": True,
            "key": s3_key,
            "fileKey": s3_key,
            "fileName": original_filename,
            "originalFileName": request.fileName,
            "message": "File uploaded successfully",
            "files": files,  # Return updated file list
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 upload error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Upload failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.put("/api/files/rename")
async def rename_file(request: FileRenameRequest):
    """
    Rename a file in S3 bucket.
    Files are organized by user_id folders: {user_id}/{filename}
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email
    user_id = request.user_id
    if request.user_email and not user_id:
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(request.user_email)
                user_id = user.id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}",
            )

    if not user_id:
        raise HTTPException(
            status_code=400, detail="user_id or user_email is required to rename files"
        )

    try:
        # Validate that the old key belongs to this user
        if not request.oldKey.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=403,
                detail="Cannot rename files that don't belong to this user",
            )

        # Sanitize new filename
        safe_filename = re.sub(r"[^a-zA-Z0-9._\-\s]", "_", request.newFileName)
        safe_filename = safe_filename.strip(". ")

        if not safe_filename:
            raise HTTPException(status_code=400, detail="Invalid filename")

        # Construct new S3 key
        new_key = f"{user_id}/{safe_filename}"

        # If new key is same as old key, nothing to do
        if new_key == request.oldKey:
            logger.info(f"Filename unchanged: {request.oldKey}")
            return {
                "success": True,
                "key": new_key,
                "fileName": safe_filename,
                "message": "Filename unchanged",
            }

        # Check if new filename already exists
        s3_client = get_s3_client()
        try:
            s3_client.head_object(Bucket=s3_bucket_name, Key=new_key)
            raise HTTPException(
                status_code=409,
                detail=f"A file with the name '{safe_filename}' already exists",
            )
        except ClientError as e:
            if e.response.get("Error", {}).get("Code") != "404":
                raise

        # Copy object to new key
        copy_source = {"Bucket": s3_bucket_name, "Key": request.oldKey}
        s3_client.copy_object(CopySource=copy_source, Bucket=s3_bucket_name, Key=new_key)

        # Delete old object
        s3_client.delete_object(Bucket=s3_bucket_name, Key=request.oldKey)

        logger.info(f"Renamed file from {request.oldKey} to {new_key}")

        # Get updated file list after rename
        files = []
        try:
            prefix = f"{user_id}/"
            response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix=prefix)

            if "Contents" in response:
                for obj in response["Contents"]:
                    if not obj["Key"].endswith("/") and not obj["Key"].endswith(
                        ".folder_initialized"
                    ):
                        filename = obj["Key"].replace(prefix, "")
                        files.append(
                            {
                                "key": obj["Key"],
                                "name": filename,
                                "size": obj["Size"],
                                "lastModified": obj["LastModified"].isoformat(),
                            }
                        )

            files.sort(key=lambda x: x["lastModified"], reverse=True)
        except Exception as e:
            logger.warning(f"Could not fetch updated file list: {e}")

        return {
            "success": True,
            "key": new_key,
            "oldKey": request.oldKey,
            "fileName": safe_filename,
            "message": "File renamed successfully",
            "files": files,  # Return updated file list
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Rename failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.delete("/api/files/delete")
async def delete_file_endpoint(request: FileDeleteRequest):
    """
    Delete a file from S3 bucket.
    Files are organized by user_id folders: {user_id}/{filename}
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email
    user_id = request.user_id
    if request.user_email and not user_id:
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(request.user_email)
                user_id = user.id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}",
            )

    if not user_id:
        raise HTTPException(
            status_code=400, detail="user_id or user_email is required to delete files"
        )

    try:
        # Validate that the key belongs to this user
        if not request.key.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=403,
                detail="Cannot delete files that don't belong to this user",
            )

        # Don't allow deleting the folder initialization file
        if request.key.endswith(".folder_initialized"):
            raise HTTPException(status_code=400, detail="Cannot delete system files")

        s3_client = get_s3_client()

        # Delete the object
        s3_client.delete_object(Bucket=s3_bucket_name, Key=request.key)

        logger.info(f"Deleted file: {request.key}")

        # Get updated file list after delete
        files = []
        try:
            prefix = f"{user_id}/"
            response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix=prefix)

            if "Contents" in response:
                for obj in response["Contents"]:
                    if not obj["Key"].endswith("/") and not obj["Key"].endswith(
                        ".folder_initialized"
                    ):
                        filename = obj["Key"].replace(prefix, "")
                        files.append(
                            {
                                "key": obj["Key"],
                                "name": filename,
                                "size": obj["Size"],
                                "lastModified": obj["LastModified"].isoformat(),
                            }
                        )

            files.sort(key=lambda x: x["lastModified"], reverse=True)
        except Exception as e:
            logger.warning(f"Could not fetch updated file list: {e}")

        return {
            "success": True,
            "key": request.key,
            "message": "File deleted successfully",
            "files": files,  # Return updated file list
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Delete failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.post("/api/files/save-cover-letter")
async def save_cover_letter(request: SaveCoverLetterRequest):
    """
    Save a generated cover letter to S3 bucket in the user's generated_cover_letters subfolder.
    Files are organized by user_id: {user_id}/generated_cover_letters/{filename}
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email
    user_id = request.user_id
    if request.user_email and not user_id:
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(request.user_email)
                user_id = user.id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}",
            )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to save cover letters",
        )

    try:
        # Ensure the generated_cover_letters subfolder exists
        ensure_cover_letter_subfolder(user_id)

        # Generate filename if not provided
        if request.fileName:
            # Sanitize custom filename
            safe_filename = re.sub(r"[^a-zA-Z0-9._\-\s]", "_", request.fileName)
            safe_filename = safe_filename.strip(". ")
            if not safe_filename:
                safe_filename = "cover_letter"
        else:
            # Generate timestamped filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"cover_letter_{timestamp}"

        # Normalize content type for comparison (case-insensitive)
        content_type_lower = request.contentType.lower().strip() if request.contentType else ""

        # Log the received content type for debugging
        logger.info(
            f"Save cover letter request - contentType: '{request.contentType}' (normalized: '{content_type_lower}')"
        )

        # Determine file extension based on content type
        if content_type_lower == "text/html" or content_type_lower == "html":
            file_extension = ".html"
        elif content_type_lower == "application/pdf" or content_type_lower == "pdf":
            file_extension = ".pdf"
        else:
            file_extension = ".md"  # Default to markdown
            if content_type_lower and content_type_lower != "text/markdown":
                logger.warning(f"Unknown content type '{request.contentType}', defaulting to .md")

        # Construct full filename with extension
        # If filename already has an extension, check if it matches the content type
        if safe_filename.endswith((".md", ".html", ".pdf", ".txt")):
            # Filename already has an extension - verify it matches content type
            existing_ext = None
            if safe_filename.endswith(".pdf"):
                existing_ext = ".pdf"
            elif safe_filename.endswith(".html"):
                existing_ext = ".html"
            elif safe_filename.endswith(".md"):
                existing_ext = ".md"

            # If existing extension doesn't match content type, replace it
            if existing_ext and existing_ext != file_extension:
                logger.warning(
                    f"Filename extension '{existing_ext}' doesn't match content type '{content_type_lower}'. Replacing with '{file_extension}'"
                )
                # Remove old extension and add correct one
                base_name = safe_filename.rsplit(".", 1)[0]
                full_filename = f"{base_name}{file_extension}"
            else:
                full_filename = safe_filename
        else:
            # No extension, add the determined one
            full_filename = f"{safe_filename}{file_extension}"

        logger.info(f"Determined file extension: {file_extension}, full filename: {full_filename}")

        # Construct S3 key: user_id/generated_cover_letters/filename
        s3_key = f"{user_id}/generated_cover_letters/{full_filename}"

        # Convert content to bytes based on content type
        if content_type_lower == "application/pdf" or content_type_lower == "pdf":
            # PDF content should be base64-encoded
            try:
                content_bytes = base64.b64decode(request.coverLetterContent)
                # Validate it's actually a PDF by checking the header
                if not content_bytes.startswith(b"%PDF"):
                    raise HTTPException(
                        status_code=400,
                        detail="Invalid PDF data: content does not appear to be a valid PDF file",
                    )
                logger.info("Successfully decoded base64 PDF data")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid base64 PDF data: {str(e)}")
        else:
            # Markdown or HTML content - encode as UTF-8
            content_bytes = request.coverLetterContent.encode("utf-8")
            logger.info(f"Encoded text content as UTF-8 ({len(content_bytes)} bytes)")

        # Determine S3 ContentType based on file extension
        if file_extension == ".pdf":
            s3_content_type = "application/pdf"
        elif file_extension == ".html":
            s3_content_type = "text/html"
        else:
            s3_content_type = "text/markdown"

        # Upload to S3
        s3_client = get_s3_client()
        s3_client.put_object(
            Bucket=s3_bucket_name,
            Key=s3_key,
            Body=content_bytes,
            ContentType=s3_content_type,
        )

        logger.info(f"Saved cover letter to S3: {s3_key} ({len(content_bytes)} bytes)")
        logger.info(f"  Filename: {full_filename}")
        logger.info(f"  Request content type: {request.contentType}")
        logger.info(f"  Normalized content type: {content_type_lower}")
        logger.info(f"  File extension used: {file_extension}")

        return {
            "success": True,
            "key": s3_key,
            "fileName": full_filename,
            "message": "Cover letter saved successfully",
            "fileSize": len(content_bytes),
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Save cover letter failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/api/cover-letters/list")
async def list_cover_letters(user_id: Optional[str] = None, user_email: Optional[str] = None):
    """
    List all saved cover letters from the user's generated_cover_letters subfolder.
    Files are organized by user_id: {user_id}/generated_cover_letters/{filename}
    """
    logger.info(f"Cover letters list request - user_id: {user_id}, user_email: {user_email}")

    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email
    if not user_id and not user_email:
        logger.warning("Cover letters list request missing both user_id and user_email")
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to list cover letters",
        )

    # If user_email is provided but not user_id, try to get user_id from email
    if user_email and not user_id:
        logger.info(f"Resolving user_id from email: {user_email}")
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(user_email)
                user_id = user.id
                logger.info(f"Successfully resolved user_id: {user_id} from email: {user_email}")
            else:
                logger.error("MongoDB not available, cannot resolve user_id from email")
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except HTTPException:
            # Re-raise HTTPExceptions (like 503 or 404 from get_user_by_email) without modification
            logger.warning(f"HTTPException raised during user lookup for email: {user_email}")
            raise
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(status_code=404, detail=f"User not found for email: {user_email}")

    if not user_id:
        logger.error("user_id is still None after email resolution attempt")
        raise HTTPException(status_code=400, detail="user_id is required to list cover letters")

    logger.info(f"Processing cover letters list request for user_id: {user_id}")

    try:
        # Ensure the generated_cover_letters subfolder exists
        ensure_cover_letter_subfolder(user_id)

        s3_client = get_s3_client()

        # List objects in the generated_cover_letters subfolder
        prefix = f"{user_id}/generated_cover_letters/"
        logger.info(f"Listing cover letters for user_id: {user_id}, prefix: {prefix}")

        response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix=prefix)

        files = []
        if "Contents" in response:
            logger.info(f"Found {len(response['Contents'])} objects in S3 for prefix {prefix}")
            for obj in response["Contents"]:
                # Only return actual files (not folders/directories or placeholder files)
                if not obj["Key"].endswith("/") and not obj["Key"].endswith(".folder_initialized"):
                    # Extract filename from key (remove user_id/generated_cover_letters/ prefix)
                    filename = obj["Key"].replace(prefix, "")
                    files.append(
                        {
                            "key": obj["Key"],
                            "name": filename,
                            "size": obj["Size"],
                            "lastModified": obj["LastModified"].isoformat(),
                        }
                    )
        else:
            logger.info(f"No objects found in S3 for prefix {prefix} (empty folder)")

        # Sort by lastModified (newest first)
        files.sort(key=lambda x: x["lastModified"], reverse=True)

        logger.info(f"Returning {len(files)} cover letters for user_id: {user_id}")
        return {"files": files}

    except HTTPException:
        # Re-raise HTTPExceptions without modification
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Error listing cover letters: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.get("/api/cover-letters/download")
async def download_cover_letter(
    key: str, user_id: Optional[str] = None, user_email: Optional[str] = None
):
    """
    Download a cover letter from S3 for previewing.
    Returns the file content with appropriate content type headers.
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email
    if not user_id and not user_email:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to download cover letters",
        )

    # If user_email is provided but not user_id, try to get user_id from email
    if user_email and not user_id:
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(user_email)
                user_id = user.id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(status_code=404, detail=f"User not found for email: {user_email}")

    if not user_id:
        raise HTTPException(status_code=400, detail="user_id is required to download cover letters")

    try:
        # Validate that the key belongs to this user and is in generated_cover_letters
        expected_prefix = f"{user_id}/generated_cover_letters/"
        if not key.startswith(expected_prefix):
            raise HTTPException(
                status_code=403,
                detail="Cannot download cover letters that don't belong to this user",
            )

        s3_client = get_s3_client()

        # Get the object from S3
        response = s3_client.get_object(Bucket=s3_bucket_name, Key=key)

        # Read the file content
        file_content = response["Body"].read()

        # Determine content type based on file extension
        content_type = response.get("ContentType", "application/octet-stream")
        if not content_type or content_type == "application/octet-stream":
            # Try to determine from filename
            if key.endswith(".pdf"):
                content_type = "application/pdf"
            elif key.endswith(".html"):
                content_type = "text/html"
            elif key.endswith(".md"):
                content_type = "text/markdown"

        # Get filename for Content-Disposition header
        filename = key.split("/")[-1]

        logger.info(f"Downloaded cover letter: {key} ({len(file_content)} bytes)")

        # Return file content with appropriate headers
        from fastapi.responses import Response

        headers = {"Content-Disposition": f'inline; filename="{filename}"'}

        return Response(content=file_content, media_type=content_type, headers=headers)

    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "NoSuchKey":
            raise HTTPException(status_code=404, detail="Cover letter not found")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Download failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


@app.delete("/api/cover-letters/delete")
async def delete_cover_letter(request: CoverLetterRequest):
    """
    Delete a cover letter from S3 bucket.
    Files are organized by user_id: {user_id}/generated_cover_letters/{filename}
    """
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    # Require user_id or user_email
    user_id = request.user_id
    if request.user_email and not user_id:
        try:
            if MONGODB_AVAILABLE:
                user = get_user_by_email(request.user_email)
                user_id = user.id
            else:
                raise HTTPException(
                    status_code=503,
                    detail="MongoDB is not available. Cannot resolve user_id from email.",
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}",
            )

    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to delete cover letters",
        )

    try:
        # Validate that the key belongs to this user and is in generated_cover_letters
        expected_prefix = f"{user_id}/generated_cover_letters/"
        if not request.key.startswith(expected_prefix):
            raise HTTPException(
                status_code=403,
                detail="Cannot delete cover letters that don't belong to this user",
            )

        # Don't allow deleting the folder initialization file
        if request.key.endswith(".folder_initialized"):
            raise HTTPException(status_code=400, detail="Cannot delete system files")

        s3_client = get_s3_client()

        # Delete the object
        s3_client.delete_object(Bucket=s3_bucket_name, Key=request.key)

        logger.info(f"Deleted cover letter: {request.key}")

        # Get updated file list after delete
        files = []
        try:
            prefix = f"{user_id}/generated_cover_letters/"
            response = s3_client.list_objects_v2(Bucket=s3_bucket_name, Prefix=prefix)

            if "Contents" in response:
                for obj in response["Contents"]:
                    if not obj["Key"].endswith("/") and not obj["Key"].endswith(
                        ".folder_initialized"
                    ):
                        filename = obj["Key"].replace(prefix, "")
                        files.append(
                            {
                                "key": obj["Key"],
                                "name": filename,
                                "size": obj["Size"],
                                "lastModified": obj["LastModified"].isoformat(),
                            }
                        )

            files.sort(key=lambda x: x["lastModified"], reverse=True)
            logger.info(f"Returning updated cover letter list with {len(files)} files after delete")
        except Exception as e:
            logger.warning(f"Could not fetch updated cover letter list after delete: {e}")

        return {
            "success": True,
            "key": request.key,
            "message": "Cover letter deleted successfully",
            "files": files,  # Return updated file list
        }

    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Delete failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


def generate_pdf_from_markdown(markdown_content: str, print_properties: dict) -> str:
    """
    Generate a PDF from Markdown content with proper formatting support.
    Uses WeasyPrint for PDF generation.

    Args:
        markdown_content: The Markdown content to convert to PDF
        print_properties: Dictionary containing print configuration:
            - margins: dict with top, right, bottom, left (in inches)
            - fontFamily: str (default: "Times New Roman")
            - fontSize: float (default: 12)
            - lineHeight: float (default: 1.6)
            - pageSize: dict with width, height (in inches, default: 8.5 x 11)

    Returns:
        Base64-encoded PDF data as a string (without data URI prefix)
    """
    if not PDF_GENERATION_AVAILABLE:
        raise ImportError("markdown library is not installed. Cannot generate PDF.")
    if not WEASYPRINT_AVAILABLE:
        raise ImportError("weasyprint library is not installed. Cannot generate PDF.")

    try:
        import re

        # Normalize markdown content: replace escaped newlines with actual newlines
        # This prevents backslashes from appearing in the PDF output
        normalized_markdown = markdown_content.replace("\\n", "\n").replace("\\r", "\r")

        # Normalize line endings: convert \r\n to \n, then remove standalone \r
        normalized_markdown = normalized_markdown.replace("\r\n", "\n").replace("\r", "\n")

        # Convert markdown to HTML
        html_content = markdown.markdown(
            normalized_markdown, extensions=["extra", "codehilite", "tables", "nl2br"]
        )

        # Strip unwanted \r and \n characters from HTML output
        # Remove carriage returns and normalize line feeds to spaces (HTML doesn't need them)
        html_content = html_content.replace("\r", "").replace("\n", " ")
        # Collapse multiple spaces to single space
        html_content = re.sub(r" +", " ", html_content)

        # Extract print properties with defaults
        margins = print_properties.get("margins", {})
        font_family = print_properties.get("fontFamily", "Times New Roman")
        font_size = print_properties.get("fontSize", 12)
        line_height = print_properties.get("lineHeight", 1.6)
        page_size = print_properties.get("pageSize", {"width": 8.5, "height": 11.0})

        # Create styled HTML document
        styled_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{
                    size: {page_size['width']}in {page_size['height']}in;
                    margin: {margins.get('top', 1.0)}in
                           {margins.get('right', 0.75)}in
                           {margins.get('bottom', 0.25)}in
                           {margins.get('left', 0.75)}in;
                }}
                body {{
                    font-family: "{font_family}", serif;
                    font-size: {font_size}pt;
                    line-height: {line_height};
                    margin: 0;
                    padding: 0;
                    color: #000;
                }}
                h1, h2, h3, h4, h5, h6 {{
                    font-weight: bold;
                    margin-top: 1em;
                    margin-bottom: 0.5em;
                    page-break-after: avoid;
                }}
                h1 {{ font-size: 2em; }}
                h2 {{ font-size: 1.5em; }}
                h3 {{ font-size: 1.25em; }}
                h4 {{ font-size: 1.1em; }}
                h5 {{ font-size: 1em; }}
                h6 {{ font-size: 0.9em; }}
                strong, b {{ font-weight: bold; }}
                em, i {{ font-style: italic; }}
                ul, ol {{
                    margin: 1em 0;
                    padding-left: 2em;
                }}
                li {{
                    margin: 0.5em 0;
                }}
                p {{
                    margin: 0.5em 0;
                }}
                code {{
                    background-color: #f4f4f4;
                    padding: 2px 4px;
                    border-radius: 3px;
                    font-family: "Courier New", monospace;
                    font-size: 0.9em;
                }}
                pre {{
                    background-color: #f4f4f4;
                    padding: 10px;
                    border-radius: 3px;
                    overflow-x: auto;
                    page-break-inside: avoid;
                }}
                pre code {{
                    background-color: transparent;
                    padding: 0;
                }}
                blockquote {{
                    border-left: 4px solid #ddd;
                    padding-left: 1em;
                    margin: 1em 0;
                    font-style: italic;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 1em 0;
                    page-break-inside: avoid;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                    font-weight: bold;
                }}
                a {{
                    color: #0066cc;
                    text-decoration: underline;
                }}
                hr {{
                    border: none;
                    border-top: 1px solid #ddd;
                    margin: 1em 0;
                }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """

        # Generate PDF using WeasyPrint
        pdf_bytes = HTML(string=styled_html).write_pdf()

        # Encode to base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode("utf-8")

        logger.info(f"Successfully generated PDF from Markdown ({len(pdf_bytes)} bytes)")
        return pdf_base64

    except Exception as e:
        logger.error(f"Error generating PDF from Markdown: {str(e)}")
        raise Exception(f"Failed to generate PDF: {str(e)}")


@app.post("/api/files/generate-pdf")
async def generate_pdf_endpoint(request: GeneratePDFRequest):
    """
    Generate a PDF from Markdown content with proper formatting support.
    The PDF preserves all Markdown formatting including bold, italic, headings, lists, etc.
    """
    logger.info(
        f"PDF generation request received - user_id: {request.user_id}, user_email: {request.user_email}"
    )

    # Check if PDF generation is available
    if not PDF_GENERATION_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation service is not available. markdown library is not installed.",
        )

    if not WEASYPRINT_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="PDF generation service is not available. weasyprint library is not installed.",
        )

    # Validate required fields
    if not request.markdownContent:
        raise HTTPException(status_code=400, detail="markdownContent is required")

    if not request.printProperties:
        raise HTTPException(status_code=400, detail="printProperties is required")

    if not request.printProperties.margins:
        raise HTTPException(status_code=400, detail="printProperties.margins is required")

    try:
        # Convert Pydantic model to dict for the generation function
        print_props_dict = {
            "margins": {
                "top": request.printProperties.margins.top,
                "right": request.printProperties.margins.right,
                "bottom": request.printProperties.margins.bottom,
                "left": request.printProperties.margins.left,
            },
            "fontFamily": request.printProperties.fontFamily,
            "fontSize": request.printProperties.fontSize,
            "lineHeight": request.printProperties.lineHeight,
            "pageSize": {
                "width": request.printProperties.pageSize.width,
                "height": request.printProperties.pageSize.height,
            },
        }

        # Generate PDF
        pdf_base64 = generate_pdf_from_markdown(request.markdownContent, print_props_dict)

        logger.info("PDF generated successfully")
        return {
            "success": True,
            "pdfBase64": pdf_base64,
            "message": "PDF generated successfully",
        }

    except HTTPException:
        raise
    except Exception as e:
        error_msg = f"Failed to generate PDF: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)


def extract_job_info_from_url(url: str) -> dict:
    """
    Use Grok to analyze a job posting URL and extract:
    - Company name
    - Job title
    - Job description

    Args:
        url: The URL to the job posting page

    Returns:
        Dictionary with company, jobTitle, and jobDescription fields
    """
    if not xai_api_key:
        raise ValueError("Grok API key is not configured. Cannot analyze job URL.")

    try:
        # First, fetch the content from the URL
        logger.info(f"Fetching content from URL: {url}")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        page_response = requests.get(url, headers=headers, timeout=30)

        # Check for 403/429 errors
        if page_response.status_code in [403, 429]:
            logger.warning(f"Received {page_response.status_code} from {url} - access forbidden")
            raise ValueError(
                f"Access forbidden ({page_response.status_code}). The website may be blocking automated requests."
            )

        page_response.raise_for_status()
        page_content = page_response.text

        logger.info(f"Successfully fetched page content ({len(page_content)} characters)")

        # Create a prompt for Grok to extract job information
        prompt = f"""Analyze the following job posting webpage content and extract the following information:
1. Company name
2. Job title
3. Job description

Return ONLY a valid JSON object with these exact fields:
{{
    "company": "Company Name",
    "jobTitle": "Job Title",
    "jobDescription": "Full job description text"
}}

Webpage content:
{page_content[:50000]}  # Limit to first 50k characters to avoid token limits

Important:
- Extract the actual company name (not just from the URL)
- Extract the complete job title
- Extract the full job description including responsibilities, requirements, and qualifications
- Return ONLY the JSON object, no additional text or markdown formatting
- If any information is not found, use "Not specified" as the value
"""

        # Call Grok API
        logger.info("Calling Grok API to extract job information")
        headers = {
            "Authorization": f"Bearer {xai_api_key}",
            "Content-Type": "application/json",
        }
        data = {
            "model": xai_model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are an expert at extracting structured information from job postings. Always return valid JSON only.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,  # Lower temperature for more consistent extraction
        }

        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            json=data,
            headers=headers,
            timeout=120,
        )
        response.raise_for_status()
        result = response.json()
        grok_response = result["choices"][0]["message"]["content"]

        logger.info(f"Grok response received ({len(grok_response)} characters)")

        # Parse the JSON response from Grok
        # Remove markdown code blocks if present
        cleaned_response = grok_response.strip()
        if cleaned_response.startswith("```json"):
            cleaned_response = cleaned_response[7:]
        if cleaned_response.startswith("```"):
            cleaned_response = cleaned_response[3:]
        if cleaned_response.endswith("```"):
            cleaned_response = cleaned_response[:-3]
        cleaned_response = cleaned_response.strip()

        # Parse JSON
        try:
            job_info = json.loads(cleaned_response)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse Grok JSON response: {e}")
            logger.error(f"Response was: {grok_response[:500]}")
            # Try to extract JSON from the response
            import re

            json_match = re.search(r'\{[^{}]*"company"[^{}]*\}', grok_response, re.DOTALL)
            if json_match:
                job_info = json.loads(json_match.group())
            else:
                raise ValueError(
                    f"Failed to parse job information from Grok response. Response: {grok_response[:200]}"
                )

        # Validate required fields
        if "company" not in job_info:
            job_info["company"] = "Not specified"
        if "jobTitle" not in job_info:
            job_info["jobTitle"] = "Not specified"
        if "jobDescription" not in job_info:
            job_info["jobDescription"] = "Not specified"

        logger.info(
            f"Successfully extracted job info: Company={job_info.get('company')}, Title={job_info.get('jobTitle')}"
        )
        return job_info

    except requests.exceptions.HTTPError as e:
        if e.response and e.response.status_code in [403, 429]:
            logger.error(f"Access forbidden ({e.response.status_code}) for URL: {url}")
            raise ValueError(
                f"Access forbidden ({e.response.status_code}). The website may be blocking automated requests."
            )
        logger.error(f"HTTP error fetching URL: {str(e)}")
        raise Exception(f"Failed to fetch or analyze job URL: {str(e)}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching URL or calling Grok API: {str(e)}")
        raise Exception(f"Failed to fetch or analyze job URL: {str(e)}")
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON response: {str(e)}")
        raise Exception(f"Failed to parse job information: {str(e)}")
    except ValueError:
        # Re-raise ValueError as-is
        raise
    except Exception as e:
        logger.error(f"Unexpected error extracting job info: {str(e)}")
        raise


@app.post("/api/job-url/analyze")
async def analyze_job_url(request: JobURLAnalysisRequest):
    """
    Analyze a LinkedIn job posting URL and extract company name, job title, and job description.

    Uses hybrid approach:
    1. First tries BeautifulSoup parsing (fast, free) for LinkedIn job postings
    2. Falls back to ChatGPT AI if BeautifulSoup extraction is incomplete

    This endpoint:
    1. Validates that the URL is a LinkedIn job posting URL
    2. Fetches the content from the provided URL
    3. Attempts BeautifulSoup extraction first (LinkedIn-specific parser)
    4. Falls back to ChatGPT AI if needed
    5. Returns the extracted information as JSON with extraction method
    """
    logger.info(
        f"Job URL analysis request received - URL: {request.url}, user_id: {request.user_id}"
    )

    # Validate URL format
    if not request.url or not request.url.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=400,
            detail="Invalid URL format. URL must start with http:// or https://",
        )

    try:
        # Use hybrid analyzer if available, otherwise fall back to ChatGPT-only
        if JOB_URL_ANALYZER_AVAILABLE:
            logger.info("Using hybrid BeautifulSoup + ChatGPT analyzer")
            result = await analyze_job_url_hybrid(
                url=request.url,
                user_id=request.user_id,
                user_email=request.user_email,
                use_chatgpt_fallback=True,
            )
            logger.info(
                f"Job URL analysis completed successfully using {result.get('extractionMethod', 'unknown')}"
            )
            return result
        else:
            # Fallback to old ChatGPT-only method (should not happen if job_url_analyzer is available)
            logger.info("Using ChatGPT-only analyzer (hybrid analyzer not available)")
            if not xai_api_key:
                raise HTTPException(
                    status_code=503,
                    detail="Grok API key is not configured. Cannot analyze job URL.",
                )

            # Detect ad source
            from urllib.parse import urlparse

            domain = urlparse(request.url).netloc.lower()
            if "linkedin.com" in domain:
                ad_source = "linkedin"
            elif "indeed.com" in domain:
                ad_source = "indeed"
            elif "glassdoor.com" in domain:
                ad_source = "glassdoor"
            else:
                ad_source = "generic"

            job_info = extract_job_info_from_url(request.url)
            logger.info(f"Job URL analysis completed successfully")
            return {
                "success": True,
                "url": request.url,
                "company": job_info.get("company", "Not specified"),
                "job_title": job_info.get("jobTitle", "Not specified"),
                "ad_source": ad_source,
                "full_description": job_info.get("jobDescription", "Not specified"),
                "hiring_manager": "",  # Not available in legacy method
                "extractionMethod": "grok-legacy",
            }

    except HTTPException:
        raise
    except ValueError as e:
        # Invalid URL format or LinkedIn validation failed
        error_msg = str(e)
        logger.warning(f"Invalid URL or validation error: {error_msg}")
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        error_msg = f"Failed to analyze job URL: {str(e)}"
        logger.error(error_msg, exc_info=True)
        raise HTTPException(status_code=500, detail=error_msg)


# --- Optional: To run this file directly ---
# You would typically use the 'uvicorn' command below,
# but this is also an option for simple testing.
if __name__ == "__main__":
    import uvicorn

    # Use PORT environment variable (Render provides this) or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
