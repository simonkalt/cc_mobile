from fastapi import FastAPI, Request, status, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError, EmailStr
from contextlib import asynccontextmanager
from typing import Optional
from bson import ObjectId
from datetime import datetime

import os
import json
import datetime
import base64
import re
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
import google.generativeai as genai
from huggingface_hub import login
import requests
import oci
import logging
import sys

# Import MongoDB client
try:
    from mongodb_client import connect_to_mongodb, close_mongodb_connection
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.warning("mongodb_client module not available. MongoDB features will be disabled.")

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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(sys.stdout)  # Explicitly use stdout for Render
    ],
    force=True  # Override any existing configuration
)

# Get a logger for this application and set to INFO
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Configure uvicorn loggers
logging.getLogger("uvicorn").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)

XAI_SDK_AVAILABLE = False

# Import MongoDB client (after logger is defined)
try:
    from mongodb_client import connect_to_mongodb, close_mongodb_connection
    MONGODB_AVAILABLE = True
except ImportError:
    MONGODB_AVAILABLE = False
    logger.warning("mongodb_client module not available. MongoDB features will be disabled.")

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

def send_ntfy_notification(message: str, title: str = "CoverLetter App"):
    """Send a notification to ntfy topic CustomCoverLetter"""
    try:
        requests.post(
            "https://ntfy.sh/CustomCoverLetter",
            data=message.encode('utf-8'),
            headers={
                "Title": title,
                "Priority": "default"
            },
            timeout=5
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True
    )
    logger.info("Application startup - logging configured")
    send_ntfy_notification("Application started and logging configured", "Startup")
    
    # Connect to MongoDB Atlas
    if MONGODB_AVAILABLE:
        logger.info("Attempting to connect to MongoDB Atlas...")
        if connect_to_mongodb():
            logger.info("MongoDB Atlas connection established")
            send_ntfy_notification("MongoDB Atlas connected successfully", "MongoDB")
        else:
            logger.warning("MongoDB Atlas connection failed. Continuing without database.")
    else:
        logger.info("MongoDB not available - skipping connection")
    
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
        send_ntfy_notification("oci_api_key.pem File does NOT exist.","oci_api_key.pem")

    yield
    # Shutdown
    if MONGODB_AVAILABLE:
        logger.info("Closing MongoDB Atlas connection...")
        close_mongodb_connection()
        logger.info("MongoDB Atlas connection closed")

# Create the FastAPI app instance
app = FastAPI(
    title="Cover Letter API",
    description="API for cover letter generation and user management",
    version="1.0.0",
    lifespan=lifespan
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
logger.info(f"CORS configured for origins: {all_origins}")

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
            "body": body.decode('utf-8') if body else 'Empty body'
        }
    )

hf_token = os.getenv('HF_TOKEN')
google_api_key = os.getenv("GOOGLE_API_KEY")
openai_api_key = os.getenv('OPENAI_API_KEY')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
gemini_api_key = os.getenv('GEMINI_API_KEY')
xai_api_key = os.getenv('XAI_API_KEY')

oci_compartment_id = os.getenv('OCI_COMPARTMENT_ID')
oci_config_file = os.getenv('OCI_CONFIG_FILE', '/etc/secrets/config')  # ← Render path!
# oci_config_file = os.getenv('OCI_CONFIG_FILE', os.path.expanduser('config'))
oci_config_profile = os.getenv('OCI_CONFIG_PROFILE', 'CoverLetter')
oci_region = os.getenv('OCI_REGION', 'us-phoenix-1')
oci_model_id = os.getenv('OCI_MODEL_ID', 'ocid1.generativeaimodel.oc1.phx.amaaaaaask7dceya5zq6k7j3k4m5n6p7q8r9s0t1u2v3w4x5y6z7a8b9c0d1e2f3g4h5i6j7k8l9m0n1o2p3q4r5s6t7u8v9w0')

# S3 configuration
# Parse S3_BUCKET_URI to extract bucket name
# Format: s3://bucket-name/path/ or s3://bucket-name/
# Note: The path portion (e.g., "PDF Resumes/") is ignored since we use user_id folders
s3_bucket_uri = os.getenv('S3_BUCKET_URI', 's3://custom-cover-user-resumes/')
if s3_bucket_uri.startswith('s3://'):
    # Remove 's3://' prefix and split by '/'
    uri_without_prefix = s3_bucket_uri[5:]  # Remove 's3://'
    # Extract bucket name (first part before '/')
    s3_bucket_name = uri_without_prefix.split('/')[0]
else:
    # Fallback if URI format is incorrect
    s3_bucket_name = s3_bucket_uri.split('/')[0] if '/' in s3_bucket_uri else s3_bucket_uri

# Resumes are organized by user_id folders: {user_id}/{filename}
# The user_id folder is created automatically when files are uploaded to S3

# AWS credentials from environment variables
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID', '')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY', '')
aws_region = os.getenv('AWS_REGION', 'us-east-1')  # Default region

# Log S3 configuration (without exposing secrets)
if S3_AVAILABLE:
    logger.info(f"S3 Configuration: bucket={s3_bucket_name}, region={aws_region}, credentials={'configured' if aws_access_key_id and aws_secret_access_key else 'using default/IAM'}")
else:
    logger.warning("S3 is not available - boto3 is not installed")

# Load system prompt from JSON config file
def load_system_prompt():


    """Load system prompt from JSON config file"""
    config_path = "system_prompt.json"
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        
        system_prompt = config.get("system_prompt", "")
        if not system_prompt:
            logger.warning(f"System prompt not found in {config_path}. Using default.")
            return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information."
        
        logger.info(f"Loaded system prompt from {config_path} ({len(system_prompt)} characters)")
        return system_prompt
    except FileNotFoundError:
        logger.warning(f"System prompt file not found: {config_path}. Using default.")
        return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information."
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing system prompt JSON: {e}. Using default.")
        return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information."
    except Exception as e:
        logger.error(f"Error loading system prompt: {e}. Using default.")
        return "You are an expert cover letter writer. Generate a professional cover letter based on the provided information."

# Load system message at startup
system_message = load_system_prompt()

# Personality profiles are now stored in user preferences in MongoDB
# No longer loading from JSON file - all profiles come from user's appSettings.personalityProfiles

# Model names mapping
gpt_model = "gpt-4.1"
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
            logger.info(f"OCI check - compartment_id: {has_compartment}, config_file: {oci_config_file}, exists: {has_config}")
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
    coverLetterContent: str  # The cover letter content (markdown or HTML)
    fileName: Optional[str] = None  # Optional custom filename (without extension)
    contentType: str = "text/markdown"  # Content type: "text/markdown" or "text/html"
    user_id: Optional[str] = None
    user_email: Optional[str] = None

def post_to_llm(prompt: str, model: str = "gpt-4.1"):
    return_response = None
    if model == "gpt-4.1":
        client = OpenAI(api_key=openai_api_key)
        response = client.chat.completions.create(model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return_response = response.choices[0].message.content
    elif model == "claude-sonnet-4-20250514":
        client = anthropic.Anthropic(api_key=anthropic_api_key)
        response = client.messages.create(model=model,
            system="You are a helpful assistant.",
            messages=[
                {"role": "user", "content": prompt}
            ],
            max_tokens=20000,
            temperature=1
        )
        return_response = response.content[0].text.replace("```json","").replace("```","")
    elif model == "gemini-2.5-flash":
        genai.configure(api_key=gemini_api_key)
        client = genai.GenerativeModel(model)
        # client = genai.Client(api_key=gemini_api_key)
        response = client.generate_content(
            contents=prompt
        )
        return_response = response.text
    elif model == "grok-4-fast-reasoning":
        # Fallback to direct HTTP requests (no SDK needed)
        headers = {
            "Authorization": f"Bearer {xai_api_key}",
            "Content-Type": "application/json"
        }
        data = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        }
        response = requests.post(
            "https://api.x.ai/v1/chat/completions",
            json=data,
            headers=headers,
            timeout=3600
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
                config=config,                # ← THIS WAS MISSING
                service_endpoint=service_endpoint
            )
            
            # Prepare the serving mode
            serving_mode = oci.generative_ai_inference.models.OnDemandServingMode(
                model_id=oci_model_id
            )
            
            # Prepare the inference request
            full_prompt = f"You are a helpful assistant.\n\nUser: {prompt}\nAssistant:"
            
            # Use Cohere request for Cohere models (or Llama if using Llama)
            inference_request = oci.generative_ai_inference.models.LlamaLlmInferenceRequest(
                prompt=full_prompt,
                max_tokens=2048,
                temperature=0.7
            )            
            # Create generate text details
            generate_text_details = oci.generative_ai_inference.models.GenerateTextDetails(
                serving_mode=serving_mode,
                compartment_id=oci_compartment_id,
                inference_request=inference_request
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
        if hasattr(content, 'text'):
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
            's3',
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region
        )
    else:
        logger.info("Using default AWS credentials (IAM role, credentials file, or environment)")
        return boto3.client('s3', region_name=aws_region)

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
                Bucket=s3_bucket_name,
                Prefix=folder_prefix,
                MaxKeys=1
            )
            
            # If we get any objects (even the placeholder), folder exists
            if 'Contents' in response and len(response['Contents']) > 0:
                logger.info(f"User S3 folder already exists: {folder_prefix}")
                return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                logger.warning(f"Cannot check if folder exists (AccessDenied): {e}")
                # Continue to try creating it anyway
            else:
                logger.warning(f"Error checking folder existence: {error_code}")
        
        # Folder doesn't exist or we can't check, create placeholder
        try:
            s3_client.put_object(
                Bucket=s3_bucket_name,
                Key=placeholder_key,
                Body=b'',
                ContentType='text/plain'
            )
            logger.info(f"Created user S3 folder: {folder_prefix}")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
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
                Bucket=s3_bucket_name,
                Prefix=subfolder_prefix,
                MaxKeys=1
            )
            
            # If we get any objects (even the placeholder), subfolder exists
            if 'Contents' in response and len(response['Contents']) > 0:
                logger.info(f"Cover letter subfolder already exists: {subfolder_prefix}")
                return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
            if error_code == 'AccessDenied':
                logger.warning(f"Cannot check if subfolder exists (AccessDenied): {e}")
                # Continue to try creating it anyway
            else:
                logger.warning(f"Error checking subfolder existence: {error_code}")
        
        # Subfolder doesn't exist or we can't check, create placeholder
        try:
            s3_client.put_object(
                Bucket=s3_bucket_name,
                Key=placeholder_key,
                Body=b'',
                ContentType='text/plain'
            )
            logger.info(f"Created cover letter subfolder: {subfolder_prefix}")
            return True
        except ClientError as e:
            error_code = e.response.get('Error', {}).get('Code', 'Unknown')
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
        if s3_path.startswith('s3://'):
            s3_path = s3_path[5:]  # Remove 's3://' prefix
        
        # Split bucket and key
        parts = s3_path.split('/', 1)
        if len(parts) != 2:
            raise ValueError(f"Invalid S3 path format: {s3_path}. Expected format: bucket/key or s3://bucket/key")
        
        bucket_name = parts[0]
        object_key = parts[1]
        
        logger.info(f"Downloading PDF from S3: bucket={bucket_name}, key={object_key}")
        
        # Get S3 client
        s3_client = get_s3_client()
        
        # Download the object
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        pdf_bytes = response['Body'].read()
        
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
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
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
        with open(file_path, 'rb') as file:
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
            timeout=(10, 240)
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
        chat_request.api_format = oci.generative_ai_inference.models.BaseChatRequest.API_FORMAT_GENERIC
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
            return json.dumps({"markdown": "Error: No response from OCI", "html": "<p>Error: No response from OCI</p>"})
        
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

def get_job_info(llm: str, date_input: str, company_name: str, hiring_manager: str, 
                 ad_source: str, resume: str, jd: str, additional_instructions: str, 
                 tone: str, address: str = "", phone_number: str = "", 
                 user_id: Optional[str] = None, user_email: Optional[str] = None):
    """
    Generate cover letter based on job information using specified LLM.
    Returns a dictionary with 'markdown' and 'html' fields.
    
    Args:
        user_id: Optional user ID to access custom personality profiles
        user_email: Optional user email to access custom personality profiles
    """
    # Get today's date if not provided
    today_date = date_input if date_input else datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Check if resume is a file path, S3 key, or base64 data
    resume_content = resume
    
    # First, check if it's base64 encoded data
    if resume and len(resume) > 100 and not resume.endswith('.pdf') and not resume.endswith('.PDF'):
        try:
            # Try to decode as base64
            pdf_bytes = base64.b64decode(resume)
            # Verify it's a PDF by checking the header
            if pdf_bytes.startswith(b'%PDF'):
                logger.info("Detected base64 encoded PDF data, decoding...")
                resume_content = read_pdf_from_bytes(pdf_bytes)
                logger.info("Successfully decoded and extracted text from base64 PDF")
            else:
                # Not base64 PDF, treat as regular text
                logger.debug("Resume field appears to be text, not base64 PDF")
        except Exception as e:
            # Not base64, continue with other methods
            logger.debug(f"Resume field is not base64 encoded: {str(e)}")
    
    # If not base64, check if it's an S3 key or file path
    if resume_content == resume and resume:
        # Check if it looks like an S3 key (contains '/' - format: user_id/filename or just filename)
        # S3 keys from the client will be in format: user_id/filename.pdf
        is_s3_key = '/' in resume
        
        # If it's an S3 key (contains '/'), try to retrieve from S3
        # Also try if it's a PDF filename (ends with .pdf)
        if is_s3_key or resume.endswith('.pdf') or resume.endswith('.PDF'):
            # Try to download from S3 first
            if S3_AVAILABLE and s3_bucket_name:
                # Require user_id for S3 operations - resumes are organized by user_id folders
                if not user_id:
                    logger.warning("user_id is required for S3 resume operations. Skipping S3 download.")
                else:
                    try:
                        # If it's already an S3 key (contains user_id/), use it directly
                        if is_s3_key and resume.startswith(f"{user_id}/"):
                            s3_key = resume
                        elif is_s3_key:
                            # It's an S3 key but doesn't start with user_id/, prepend user_id
                            # This handles cases where client sends just the filename part
                            filename = os.path.basename(resume.replace('\\', '/'))
                            s3_key = f"{user_id}/{filename}"
                        else:
                            # Extract just the filename if path includes directory
                            filename = os.path.basename(resume.replace('\\', '/'))
                            # Construct S3 path organized by user_id: bucket/user_id/filename
                            s3_key = f"{user_id}/{filename}"
                        
                        s3_path = f"s3://{s3_bucket_name}/{s3_key}"
                        
                        logger.info(f"Downloading PDF from S3: {s3_path}")
                        pdf_bytes = download_pdf_from_s3(s3_path)
                        resume_content = read_pdf_from_bytes(pdf_bytes)
                        logger.info("Successfully downloaded and extracted text from S3 PDF")
                    except Exception as e:
                        logger.warning(f"Failed to download from S3: {str(e)}. Will try local file paths.")
        
        # If S3 download failed or S3 not available, try local file paths
        if resume_content == resume:
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
                if os.path.sep in resume or '/' in resume:
                    possible_paths.append(resume)
                    # Also try from current directory
                    possible_paths.append(os.path.join(cwd, resume))
                
                # Try common locations
                possible_paths.extend([
                    os.path.join(cwd, resume),
                    os.path.join(cwd, "PDF Resumes", os.path.basename(resume)),
                    os.path.join(cwd, "PDF Resumes", resume),
                    os.path.join(cwd, "resumes", os.path.basename(resume)),
                    os.path.join(cwd, "resumes", resume),
                    os.path.join(".", resume),
                    os.path.join(".", "PDF Resumes", os.path.basename(resume)),
                    os.path.join(".", "PDF Resumes", resume),
                ])
                
                # If the resume path already includes "PDF Resumes", try extracting just the filename
                if "PDF Resumes" in resume or "pdf" in resume.lower():
                    filename = os.path.basename(resume)
                    possible_paths.extend([
                        os.path.join(cwd, "PDF Resumes", filename),
                        os.path.join(".", "PDF Resumes", filename),
                    ])
            
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
                logger.warning(f"PDF file not found locally. Tried paths: {possible_paths[:5]}... (showing first 5)")
                # If we haven't successfully extracted content, return the original
                if resume_content == resume:
                    logger.warning(f"Could not read PDF from S3 or local filesystem. Using original resume string.")
                    resume_content = resume
    
    # Get personality profile from user's custom profiles (user_id or user_email required)
    selected_profile = None
    profile_source = "user_custom"
    
    # Require user_id or user_email to access personality profiles
    if not user_id and not user_email:
        logger.warning("No user_id or user_email provided. Cannot retrieve personality profiles.")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id or user_email is required to access personality profiles"
        )
    
    try:
        from user_api import get_user_by_id, get_user_by_email
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
                    detail=f"User not found: {str(e)}"
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
                    detail=f"User not found: {str(e)}"
                )
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user's custom personality profiles
        # user is a UserResponse Pydantic model, so access preferences as attribute
        user_prefs = user.preferences if user.preferences else {}
        if isinstance(user_prefs, dict):
            app_settings = user_prefs.get("appSettings", {})
            if isinstance(app_settings, dict):
                custom_profiles = app_settings.get("personalityProfiles", [])
            else:
                custom_profiles = []
        else:
            custom_profiles = []
        
        logger.info(f"User preferences retrieved. Custom profiles count: {len(custom_profiles) if isinstance(custom_profiles, list) else 0}")
        
        if not custom_profiles:
            logger.warning(f"No personality profiles found for user. Available profiles: []")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No personality profiles found for user. Please add personality profiles in your user preferences."
            )
        
        logger.info(f"Found {len(custom_profiles)} custom personality profiles for user")
        # Try to find matching profile by name (case-insensitive) or ID
        profile_found = False
        for profile in custom_profiles:
            if isinstance(profile, dict):
                profile_name = profile.get("name", "").lower()
                profile_id = profile.get("id", "")
                profile_desc = profile.get("description", "")
                
                # Match by name (case-insensitive) or ID
                if tone.lower() == profile_name or tone == profile_id:
                    selected_profile = profile_desc
                    logger.info(f"Using custom personality profile: '{profile.get('name')}' (ID: {profile_id})")
                    logger.info(f"Custom profile text ({len(selected_profile)} chars): {selected_profile}")
                    profile_found = True
                    break
        
        if not profile_found:
            available_names = [p.get("name", "Unknown") for p in custom_profiles if isinstance(p, dict)]
            logger.warning(f"Personality profile '{tone}' not found in user's profiles. Available profiles: {available_names}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Personality profile '{tone}' not found. Available profiles: {available_names}"
            )
            
    except HTTPException:
        # Re-raise HTTPException
        raise
    except Exception as e:
        logger.error(f"Error accessing user's custom personality profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving personality profiles: {str(e)}"
        )
    
    if not selected_profile:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve personality profile"
        )
    
    logger.info(f"Personality profile source: {profile_source} (profile retrieved from user's database preferences)")
    
    # Build personality instruction - make it prominent and direct
    personality_instruction = f"""
=== PERSONALITY PROFILE INSTRUCTION - CRITICAL ===
YOU MUST FOLLOW THIS PERSONALITY PROFILE EXACTLY:
{selected_profile}

Apply this personality throughout the entire cover letter. This instruction takes precedence over default writing styles.
=== END PERSONALITY PROFILE INSTRUCTION ===
"""
    logger.info(f"Personality instruction prepared ({len(personality_instruction)} chars): {selected_profile[:100]}...")
    
    # Build message payload (without additional_instructions - it will be appended last to override)
    message_data = {
        "llm": llm,
        "today": f"Date: {today_date}",
        "company_name": company_name,
        "hiring_manager": hiring_manager,
        "ad_source": ad_source,
        "resume": resume_content,  # Use extracted PDF content instead of file path
        "jd": jd,
        "tone": f"Use the following tone/personality when generating the result, but do not specifically note the activities within this text: {selected_profile}"
    }
    
    # Add optional fields
    if address:
        message_data["address"] = address
    if phone_number:
        message_data["phone_number"] = phone_number
    
    message = json.dumps(message_data)
    
    # Prepare additional instructions to be appended last (so they override all other instructions)
    additional_instructions_text = ""
    if additional_instructions and additional_instructions.strip():
        # Use very explicit override language that LLMs will prioritize
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
        logger.info(f"Additional instructions provided ({len(additional_instructions)} chars) - will override ALL other instructions: {additional_instructions}")
    
    r = ""
    
    try:
        # Map model names to display names for compatibility
        if llm == "Gemini" or llm == "gemini-2.5-flash":
            # Include personality instruction prominently at the start
            msg = f"{system_message}{personality_instruction}. {message}. Hiring Manager: {hiring_manager}. Company Name: {company_name}. Ad Source: {ad_source}{additional_instructions_text}"
            logger.info("Personality instruction included in Gemini prompt")
            if additional_instructions_text:
                logger.info("Additional instructions appended to Gemini prompt as final override")
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            
            # Configure generation to ensure complete JSON response
            generation_config = {
                "temperature": 0.7,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 8192,  # Increase max tokens to prevent truncation
            }
            
            response = model.generate_content(
                contents=msg,
                generation_config=generation_config
            )
            r = response.text
            logger.info(f"Gemini response length: {len(r)} characters")
            
        elif llm == "ChatGPT" or llm == gpt_model or llm == "gpt-4.1":
            client = OpenAI(api_key=openai_api_key)
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": personality_instruction.strip()},  # Add personality instruction as separate, prominent message
                {"role": "user", "content": message},
                {"role": "user", "content": f"Hiring Manager: {hiring_manager}"},
                {"role": "user", "content": f"Company Name: {company_name}"},
                {"role": "user", "content": f"Ad Source: {ad_source}"}
            ]
            # Append additional instructions last as a separate, high-priority message
            if additional_instructions_text:
                messages.append({"role": "user", "content": additional_instructions_text.strip()})
                logger.info("Additional instructions appended to ChatGPT messages as final override")
            response = client.chat.completions.create(model=gpt_model, messages=messages)
            r = response.choices[0].message.content
            
        elif llm == "Grok" or llm == xai_model or llm == "grok-4-fast-reasoning":
            # Use HTTP API (xai SDK has different API structure)
            headers = {
                "Authorization": f"Bearer {xai_api_key}",
                "Content-Type": "application/json"
            }
            messages_list = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": personality_instruction.strip()},  # Add personality instruction as separate, prominent message
                {"role": "user", "content": message},
                {"role": "user", "content": f"Hiring Manager: {hiring_manager}"},
                {"role": "user", "content": f"Company Name: {company_name}"},
                {"role": "user", "content": f"Ad Source: {ad_source}"}
            ]
            logger.info("Personality instruction included in Grok messages")
            # Append additional instructions last so they override all previous instructions
            if additional_instructions_text:
                messages_list.append({"role": "user", "content": additional_instructions_text.strip()})
                logger.info("Additional instructions appended to Grok messages as final override")
            data = {
                "model": xai_model,
                "messages": messages_list
            }
            response = requests.post(
                "https://api.x.ai/v1/chat/completions",
                json=data,
                headers=headers,
                timeout=3600
            )
            response.raise_for_status()
            result = response.json()
            r = result["choices"][0]["message"]["content"]
                
        elif llm == "OCI" or llm == "oci-generative-ai":
            # Include personality instruction prominently at the start
            full_prompt = f"{system_message}{personality_instruction}. {message}. Hiring Manager: {hiring_manager}. Company Name: {company_name}. Ad Source: {ad_source}{additional_instructions_text}"
            r = get_oc_info(full_prompt)
            logger.info(f"OCI response received: {r[:100]}...")
            
        elif llm == "Llama" or llm == ollama_model or llm == "llama3.2":
            if not OLLAMA_AVAILABLE:
                raise ImportError("ollama library is not installed. Please install it with: pip install ollama")
            
            # Use the same message_data that includes the personality profile (tone field)
            # This ensures the personality profile description is included in Llama prompts
            message_llama = message  # Use the original message which includes the tone/personality profile
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": personality_instruction.strip()},  # Add personality instruction as separate, prominent message
                {"role": "user", "content": message_llama}
            ]
            logger.info("Personality instruction included in Llama messages")
            # Append additional instructions last so they override all previous instructions
            if additional_instructions_text:
                messages.append({"role": "user", "content": additional_instructions_text.strip()})
                logger.info("Additional instructions appended to Llama messages as final override")
            response = ollama.chat(model=ollama_model, messages=messages)
            r = response['message']['content']
            
        elif llm == "Claude" or llm == claude_model or llm == "claude-sonnet-4-20250514":
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            content_list = [
                {"type": "text", "text": personality_instruction.strip()},  # Add personality instruction as separate, prominent message
                {"type": "text", "text": message},
                {"type": "text", "text": f"Hiring Manager: {hiring_manager}"},
                {"type": "text", "text": f"Company Name: {company_name}"},
                {"type": "text", "text": f"Ad Source: {ad_source}"}
            ]
            logger.info("Personality instruction included in Claude messages")
            # Append additional instructions last so they override all previous instructions
            if additional_instructions_text:
                content_list.append({"type": "text", "text": additional_instructions_text.strip()})
                logger.info("Additional instructions appended to Claude messages as final override")
            messages = [
                {
                    "role": "user",
                    "content": content_list
                }
            ]
            response = client.messages.create(
                model=claude_model,
                system=system_message,
                messages=messages,
                max_tokens=20000,
                temperature=1
            )
            r = response.content[0].text
        else:
            raise ValueError(f"Unsupported LLM: {llm}")
        
        # Increment LLM usage count for the user (after successful LLM call)
        if user_id:
            normalized_llm = normalize_llm_name(llm)
            try:
                increment_llm_usage_count(user_id, normalized_llm)
                logger.info(f"Incremented LLM usage count for {normalized_llm} (user_id: {user_id})")
            except Exception as e:
                logger.warning(f"Failed to increment LLM usage count: {e}")
        elif user_email:
            # Try to get user_id from email
            try:
                if MONGODB_AVAILABLE:
                    user = get_user_by_email(user_email)
                    normalized_llm = normalize_llm_name(llm)
                    increment_llm_usage_count(user.id, normalized_llm)
                    logger.info(f"Incremented LLM usage count for {normalized_llm} (user_email: {user_email})")
            except Exception as e:
                logger.warning(f"Failed to increment LLM usage count from email: {e}")
        
        # Clean and parse the response
        r = r.replace("```json", "").replace("```", "").strip()
        
        # Try to extract JSON if it's embedded in text
        # Look for JSON object boundaries
        start_idx = r.find('{')
        end_idx = r.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            # Extract just the JSON portion
            json_str = r[start_idx:end_idx + 1]
        else:
            json_str = r
        
        try:
            json_r = json.loads(json_str)
        except json.JSONDecodeError as e:
            # If parsing fails, try to fix common issues
            # Remove any trailing incomplete JSON
            logger.warning(f"Initial JSON parse failed: {e}, attempting to fix...")
            
            # Try to find and extract a valid JSON object
            # Look for the last complete JSON object
            brace_count = 0
            last_valid_end = -1
            for i, char in enumerate(json_str):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        last_valid_end = i
                        break
            
            if last_valid_end > 0:
                json_str = json_str[:last_valid_end + 1]
                try:
                    json_r = json.loads(json_str)
                    logger.info("Successfully fixed truncated JSON")
                except json.JSONDecodeError:
                    raise e
            else:
                raise e
        
        # Clean up the markdown field - remove "markdown " prefix if Gemini added it
        markdown_content = json_r.get("markdown", "")
        if markdown_content.startswith("markdown "):
            markdown_content = markdown_content[9:]  # Remove "markdown " (9 characters)
            logger.info("Removed 'markdown ' prefix from Gemini response")
        
        return {
            "markdown": markdown_content,
            "html": json_r.get("html", "")
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response length: {len(r)} characters")
        logger.error(f"Response (first 1000 chars): {r[:1000]}")
        logger.error(f"Response (last 500 chars): {r[-500:]}")
        return {
            "markdown": f"Error: Failed to parse LLM response as JSON. The response may be truncated or malformed.\n\nError: {str(e)}\n\nFirst 500 chars of response:\n{r[:500]}",
            "html": f"<p>Error: Failed to parse LLM response as JSON. The response may be truncated or malformed.</p><p>Error: {str(e)}</p><pre>{r[:500]}</pre>"
        }
    except Exception as e:
        logger.error(f"Error in get_job_info: {str(e)}")
        return {
            "markdown": f"Error: {str(e)}",
            "html": f"<p>Error: {str(e)}</p>"
        }

# Define a simple root endpoint to check if the server is running
@app.get("/")
def read_root():
    return {"status": f"Simon's API is running with Hugging Face token: {hf_token[:8]}"}

# Define the main endpoint your app will call

@app.get("/api/llms")
def get_llms():
    """JSON API endpoint to get available LLMs for the mobile app"""
    llm_options = get_available_llms()
    return {"llms": llm_options}

@app.get("/api/personality-profiles")
def get_personality_profiles(user_id: Optional[str] = None, user_email: Optional[str] = None):
    """JSON API endpoint to get available personality profiles for the UI from user's preferences"""
    if not user_id and not user_email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="user_id or user_email is required"
        )
    
    try:
        from user_api import get_user_by_id, get_user_by_email
        user = None
        if user_id:
            user = get_user_by_id(user_id)
        elif user_email:
            user = get_user_by_email(user_email)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        # Get user's custom personality profiles
        user_prefs = user.preferences if user.preferences else {}
        if isinstance(user_prefs, dict):
            app_settings = user_prefs.get("appSettings", {})
            if isinstance(app_settings, dict):
                custom_profiles = app_settings.get("personalityProfiles", [])
            else:
                custom_profiles = []
        else:
            custom_profiles = []
        
        # Format profiles for the UI
        profiles = []
        for profile in custom_profiles:
            if isinstance(profile, dict):
                profiles.append({
                    "label": profile.get("name", "Unknown"),
                    "value": profile.get("name", "Unknown"),  # Use name as value for matching
                    "id": profile.get("id", ""),
                    "description": profile.get("description", "")
                })
        
        return {"profiles": profiles}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving personality profiles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error retrieving personality profiles: {str(e)}"
        )

@app.get("/api/system-prompt")
def get_system_prompt():
    """JSON API endpoint to get the current system prompt"""
    # Reload system prompt to get latest from file (useful if file is updated)
    global system_message
    system_message = load_system_prompt()
    return {"system_prompt": system_message}

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
            f'''
            <label style="display:block; margin-bottom:6px;">
                <input type="radio" name="active_model" value="{option['value']}" {'checked' if index == 0 else ''}>
                {option['label']}
            </label>
            '''
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
        
        # Check if this is a job info request (has 'llm', 'company_name', etc.)
        if 'llm' in body and 'company_name' in body:
            logger.info("Detected job info request in /chat endpoint, routing to job-info handler")
            # Check for required user identification
            if not body.get('user_id') and not body.get('user_email'):
                logger.error("Job info request missing user_id or user_email")
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "user_id or user_email is required",
                        "detail": "Please provide either 'user_id' or 'user_email' in your request to access personality profiles."
                    }
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
                user_email=job_request.user_email
            )
            return result
        else:
            # Handle as regular chat request
            chat_request = ChatRequest(**body)
            logger.info(f"Received chat request - prompt length: {len(chat_request.prompt)}, model: {chat_request.active_model}")
            response = post_to_llm(chat_request.prompt, chat_request.active_model)
            
            # Increment LLM usage count if user_id or user_email is provided
            if response:  # Only increment if LLM call was successful
                user_id_for_tracking = body.get('user_id')
                user_email_for_tracking = body.get('user_email')
                
                if user_id_for_tracking:
                    normalized_llm = normalize_llm_name(chat_request.active_model)
                    try:
                        increment_llm_usage_count(user_id_for_tracking, normalized_llm)
                        logger.info(f"Incremented LLM usage count for {normalized_llm} (user_id: {user_id_for_tracking})")
                    except Exception as e:
                        logger.warning(f"Failed to increment LLM usage count: {e}")
                elif user_email_for_tracking:
                    try:
                        if MONGODB_AVAILABLE:
                            user = get_user_by_email(user_email_for_tracking)
                            normalized_llm = normalize_llm_name(chat_request.active_model)
                            increment_llm_usage_count(user.id, normalized_llm)
                            logger.info(f"Incremented LLM usage count for {normalized_llm} (user_email: {user_email_for_tracking})")
                    except Exception as e:
                        logger.warning(f"Failed to increment LLM usage count from email: {e}")
            
            return {
                "response": response if response else f"Error: No response from LLM {chat_request.active_model}"
            }
    except HTTPException as e:
        # Re-raise HTTPException so FastAPI can handle it properly
        raise
    except Exception as e:
        logger.error(f"Error in handle_chat: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": str(e)
            }
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
        return {"error": str(e), "raw_body": body.decode('utf-8') if body else 'Empty'}

@app.post("/api/job-info")
async def handle_job_info(request: JobInfoRequest):
    """Generate cover letter based on job information"""
    logger.info(f"Received job info request for LLM: {request.llm}, Company: {request.company_name}")
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
        user_email=request.user_email
    )
    return result

# User API Endpoints
from user_api import (
    UserRegisterRequest, UserUpdateRequest, UserResponse, UserLoginRequest, UserLoginResponse,
    register_user, get_user_by_id, get_user_by_email, update_user, delete_user, login_user,
    increment_llm_usage_count
)

@app.post("/api/users/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register_user_endpoint(user_data: UserRegisterRequest):
    """Register a new user"""
    logger.info(f"User registration request: {user_data.email}")
    user_response = register_user(user_data)
    
    # Log that form fields have been cleared for new user
    logger.info(f"✓ New user registered: {user_response.email} (ID: {user_response.id})")
    logger.info(f"  Form fields initialized to empty/placeholder values")
    logger.info(f"  - Company Name: ''")
    logger.info(f"  - Hiring Manager: ''")
    logger.info(f"  - Ad Source: ''")
    logger.info(f"  - Job Description: ''")
    logger.info(f"  - Additional Instructions: ''")
    logger.info(f"  - Tone: 'Professional' (default)")
    logger.info(f"  - Address: ''")
    logger.info(f"  - Phone Number: ''")
    logger.info(f"  - Resume: ''")
    
    return user_response

@app.post("/api/users/login", response_model=UserLoginResponse)
async def login_user_endpoint(login_data: UserLoginRequest):
    """Authenticate user login"""
    logger.info(f"Login attempt: {login_data.email}")
    login_response = login_user(login_data)
    
    # After successful login, ensure user's S3 folder exists and log details
    if login_response.success and login_response.user:
        user_id = login_response.user.id
        user_name = login_response.user.name
        user_email = login_response.user.email
        
        # Log successful login
        logger.info("=" * 80)
        logger.info(f"✓ USER LOGGED IN SUCCESSFULLY")
        logger.info(f"  User ID: {user_id}")
        logger.info(f"  Name: {user_name}")
        logger.info(f"  Email: {user_email}")
        logger.info("=" * 80)
        
        # Check and ensure S3 folder exists
        logger.info(f"Checking AWS S3 folder for user_id: {user_id}")
        folder_exists = False
        file_count = 0
        
        if S3_AVAILABLE and s3_bucket_name:
            try:
                s3_client = get_s3_client()
                folder_prefix = f"{user_id}/"
                
                # Check if folder exists by listing objects
                try:
                    response = s3_client.list_objects_v2(
                        Bucket=s3_bucket_name,
                        Prefix=folder_prefix,
                        MaxKeys=1000  # Get up to 1000 files to count
                    )
                    
                    if 'Contents' in response:
                        # Count actual files (exclude placeholder)
                        files = [obj for obj in response['Contents'] 
                                if not obj['Key'].endswith('/') 
                                and not obj['Key'].endswith('.folder_initialized')]
                        file_count = len(files)
                        folder_exists = True
                        
                        logger.info(f"✓ AWS S3 folder EXISTS: {folder_prefix}")
                        logger.info(f"  Files in folder: {file_count}")
                        if file_count > 0:
                            logger.info(f"  Sample files (first 5):")
                            for i, obj in enumerate(files[:5], 1):
                                filename = obj['Key'].replace(folder_prefix, "")
                                logger.info(f"    {i}. {filename} ({obj['Size']} bytes)")
                    else:
                        # Folder might exist but be empty, or doesn't exist
                        folder_exists = False
                        logger.info(f"⚠ AWS S3 folder appears empty or doesn't exist: {folder_prefix}")
                        
                except ClientError as e:
                    error_code = e.response.get('Error', {}).get('Code', 'Unknown')
                    if error_code == 'AccessDenied':
                        logger.warning(f"⚠ Cannot check S3 folder (AccessDenied) - may need permissions")
                    else:
                        logger.warning(f"⚠ Error checking S3 folder: {error_code}")
                
                # Ensure folder exists (create if needed)
                folder_created = ensure_user_s3_folder(user_id)
                if folder_created and not folder_exists:
                    logger.info(f"✓ Created new AWS S3 folder: {folder_prefix}")
                    folder_exists = True
                elif folder_created:
                    logger.info(f"✓ AWS S3 folder verified: {folder_prefix}")
                else:
                    logger.warning(f"⚠ Could not ensure S3 folder for user_id: {user_id} (non-critical)")
                    
            except Exception as e:
                logger.error(f"✗ Error checking/creating S3 folder: {str(e)}")
        else:
            logger.warning("⚠ S3 is not available - cannot check user folder")
        
        # Final summary log
        logger.info("=" * 80)
        logger.info(f"LOGIN SUMMARY for user_id: {user_id}")
        logger.info(f"  AWS S3 Folder Exists: {'YES' if folder_exists else 'NO'}")
        logger.info(f"  Files in Folder: {file_count}")
        logger.info("=" * 80)
    
    return login_response

@app.get("/api/users/{user_id}", response_model=UserResponse)
async def get_user_by_id_endpoint(user_id: str):
    """Get user by ID"""
    logger.info(f"Get user request: {user_id}")
    return get_user_by_id(user_id)

@app.get("/api/users/email/{email}", response_model=UserResponse)
async def get_user_by_email_endpoint(email: str):
    """Get user by email"""
    logger.info(f"Get user by email request: {email}")
    return get_user_by_email(email)

@app.put("/api/users/{user_id}", response_model=UserResponse)
async def update_user_endpoint(user_id: str, updates: UserUpdateRequest):
    """Update user information"""
    logger.info(f"Update user request: {user_id}")
    return update_user(user_id, updates)

@app.delete("/api/users/{user_id}")
async def delete_user_endpoint(user_id: str):
    """Delete user"""
    logger.info(f"Delete user request: {user_id}")
    return delete_user(user_id)

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
            detail="S3 service is not available. boto3 is not installed."
        )
    
    # Require user_id or user_email to list files
    if not user_id and not user_email:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to list files"
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
                    detail="MongoDB is not available. Cannot resolve user_id from email."
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {user_email}"
            )
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id is required to list files"
        )
    
    try:
        # Ensure user's S3 folder exists before listing
        ensure_user_s3_folder(user_id)
        
        s3_client = get_s3_client()
        
        # List objects with user_id prefix
        prefix = f"{user_id}/"
        response = s3_client.list_objects_v2(
            Bucket=s3_bucket_name,
            Prefix=prefix
        )
        
        files = []
        if 'Contents' in response:
            for obj in response['Contents']:
                # Only return actual files (not folders/directories or placeholder files)
                if not obj['Key'].endswith('/') and not obj['Key'].endswith('.folder_initialized'):
                    # Extract filename from key (remove user_id/ prefix)
                    filename = obj['Key'].replace(prefix, "")
                    files.append({
                        "key": obj['Key'],
                        "name": filename,
                        "size": obj['Size'],
                        "lastModified": obj['LastModified'].isoformat()
                    })
        
        # Sort by lastModified (newest first)
        files.sort(key=lambda x: x['lastModified'], reverse=True)
        
        logger.info(f"Listed {len(files)} files for user_id: {user_id}")
        return {"files": files}
        
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
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
            detail="S3 service is not available. boto3 is not installed."
        )
    
    # Require user_id or user_email to upload files
    if not request.user_id and not request.user_email:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to upload files"
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
                    detail="MongoDB is not available. Cannot resolve user_id from email."
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}"
            )
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id is required to upload files"
        )
    
    # Ensure user's S3 folder exists before uploading
    ensure_user_s3_folder(user_id)
    
    try:
        # Decode base64 fileData
        try:
            file_bytes = base64.b64decode(request.fileData)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid base64 fileData: {str(e)}"
            )
        
        # Validate file type (only PDFs for now)
        if not request.fileName.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400,
                detail="Only PDF files are allowed"
            )
        
        # Validate file size (max 10MB)
        max_size = 10 * 1024 * 1024  # 10MB
        if len(file_bytes) > max_size:
            raise HTTPException(
                status_code=400,
                detail=f"File size exceeds maximum allowed size of {max_size / (1024 * 1024)}MB"
            )
        
        # Sanitize filename to ensure it's safe for S3 (keep original name)
        # Only replace characters that could cause issues, preserve the original structure
        safe_filename = re.sub(r'[^a-zA-Z0-9._\-\s]', '_', request.fileName)
        # Remove any leading/trailing spaces and dots
        safe_filename = safe_filename.strip('. ')
        
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
            ContentType=request.contentType
        )
        
        logger.info(f"Uploaded file to S3: {s3_key} ({len(file_bytes)} bytes)")
        logger.info(f"  Original filename: {request.fileName}")
        logger.info(f"  Stored as: {original_filename}")
        
        # Get updated file list after upload
        files = []
        try:
            prefix = f"{user_id}/"
            response = s3_client.list_objects_v2(
                Bucket=s3_bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    # Only return actual files (not folders/directories or placeholder files)
                    if not obj['Key'].endswith('/') and not obj['Key'].endswith('.folder_initialized'):
                        # Extract filename from key (remove user_id/ prefix)
                        filename = obj['Key'].replace(prefix, "")
                        files.append({
                            "key": obj['Key'],
                            "name": filename,
                            "size": obj['Size'],
                            "lastModified": obj['LastModified'].isoformat()
                        })
            
            # Sort by lastModified (newest first)
            files.sort(key=lambda x: x['lastModified'], reverse=True)
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
            "files": files  # Return updated file list
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
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
            detail="S3 service is not available. boto3 is not installed."
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
                    detail="MongoDB is not available. Cannot resolve user_id from email."
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}"
            )
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to rename files"
        )
    
    try:
        # Validate that the old key belongs to this user
        if not request.oldKey.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=403,
                detail="Cannot rename files that don't belong to this user"
            )
        
        # Sanitize new filename
        safe_filename = re.sub(r'[^a-zA-Z0-9._\-\s]', '_', request.newFileName)
        safe_filename = safe_filename.strip('. ')
        
        if not safe_filename:
            raise HTTPException(
                status_code=400,
                detail="Invalid filename"
            )
        
        # Construct new S3 key
        new_key = f"{user_id}/{safe_filename}"
        
        # If new key is same as old key, nothing to do
        if new_key == request.oldKey:
            logger.info(f"Filename unchanged: {request.oldKey}")
            return {
                "success": True,
                "key": new_key,
                "fileName": safe_filename,
                "message": "Filename unchanged"
            }
        
        # Check if new filename already exists
        s3_client = get_s3_client()
        try:
            s3_client.head_object(Bucket=s3_bucket_name, Key=new_key)
            raise HTTPException(
                status_code=409,
                detail=f"A file with the name '{safe_filename}' already exists"
            )
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') != '404':
                raise
        
        # Copy object to new key
        copy_source = {
            'Bucket': s3_bucket_name,
            'Key': request.oldKey
        }
        s3_client.copy_object(
            CopySource=copy_source,
            Bucket=s3_bucket_name,
            Key=new_key
        )
        
        # Delete old object
        s3_client.delete_object(
            Bucket=s3_bucket_name,
            Key=request.oldKey
        )
        
        logger.info(f"Renamed file from {request.oldKey} to {new_key}")
        
        # Get updated file list after rename
        files = []
        try:
            prefix = f"{user_id}/"
            response = s3_client.list_objects_v2(
                Bucket=s3_bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if not obj['Key'].endswith('/') and not obj['Key'].endswith('.folder_initialized'):
                        filename = obj['Key'].replace(prefix, "")
                        files.append({
                            "key": obj['Key'],
                            "name": filename,
                            "size": obj['Size'],
                            "lastModified": obj['LastModified'].isoformat()
                        })
            
            files.sort(key=lambda x: x['lastModified'], reverse=True)
        except Exception as e:
            logger.warning(f"Could not fetch updated file list: {e}")
        
        return {
            "success": True,
            "key": new_key,
            "oldKey": request.oldKey,
            "fileName": safe_filename,
            "message": "File renamed successfully",
            "files": files  # Return updated file list
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
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
            detail="S3 service is not available. boto3 is not installed."
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
                    detail="MongoDB is not available. Cannot resolve user_id from email."
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}"
            )
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to delete files"
        )
    
    try:
        # Validate that the key belongs to this user
        if not request.key.startswith(f"{user_id}/"):
            raise HTTPException(
                status_code=403,
                detail="Cannot delete files that don't belong to this user"
            )
        
        # Don't allow deleting the folder initialization file
        if request.key.endswith('.folder_initialized'):
            raise HTTPException(
                status_code=400,
                detail="Cannot delete system files"
            )
        
        s3_client = get_s3_client()
        
        # Delete the object
        s3_client.delete_object(
            Bucket=s3_bucket_name,
            Key=request.key
        )
        
        logger.info(f"Deleted file: {request.key}")
        
        # Get updated file list after delete
        files = []
        try:
            prefix = f"{user_id}/"
            response = s3_client.list_objects_v2(
                Bucket=s3_bucket_name,
                Prefix=prefix
            )
            
            if 'Contents' in response:
                for obj in response['Contents']:
                    if not obj['Key'].endswith('/') and not obj['Key'].endswith('.folder_initialized'):
                        filename = obj['Key'].replace(prefix, "")
                        files.append({
                            "key": obj['Key'],
                            "name": filename,
                            "size": obj['Size'],
                            "lastModified": obj['LastModified'].isoformat()
                        })
            
            files.sort(key=lambda x: x['lastModified'], reverse=True)
        except Exception as e:
            logger.warning(f"Could not fetch updated file list: {e}")
        
        return {
            "success": True,
            "key": request.key,
            "message": "File deleted successfully",
            "files": files  # Return updated file list
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
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
            detail="S3 service is not available. boto3 is not installed."
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
                    detail="MongoDB is not available. Cannot resolve user_id from email."
                )
        except Exception as e:
            logger.error(f"Failed to get user_id from email: {str(e)}")
            raise HTTPException(
                status_code=404,
                detail=f"User not found for email: {request.user_email}"
            )
    
    if not user_id:
        raise HTTPException(
            status_code=400,
            detail="user_id or user_email is required to save cover letters"
        )
    
    try:
        # Ensure the generated_cover_letters subfolder exists
        ensure_cover_letter_subfolder(user_id)
        
        # Generate filename if not provided
        if request.fileName:
            # Sanitize custom filename
            safe_filename = re.sub(r'[^a-zA-Z0-9._\-\s]', '_', request.fileName)
            safe_filename = safe_filename.strip('. ')
            if not safe_filename:
                safe_filename = "cover_letter"
        else:
            # Generate timestamped filename
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            safe_filename = f"cover_letter_{timestamp}"
        
        # Determine file extension based on content type
        if request.contentType == "text/html":
            file_extension = ".html"
        else:
            file_extension = ".md"  # Default to markdown
        
        # Construct full filename with extension
        if not safe_filename.endswith(('.md', '.html', '.txt')):
            full_filename = f"{safe_filename}{file_extension}"
        else:
            full_filename = safe_filename
        
        # Construct S3 key: user_id/generated_cover_letters/filename
        s3_key = f"{user_id}/generated_cover_letters/{full_filename}"
        
        # Convert content to bytes
        content_bytes = request.coverLetterContent.encode('utf-8')
        
        # Upload to S3
        s3_client = get_s3_client()
        s3_client.put_object(
            Bucket=s3_bucket_name,
            Key=s3_key,
            Body=content_bytes,
            ContentType=request.contentType
        )
        
        logger.info(f"Saved cover letter to S3: {s3_key} ({len(content_bytes)} bytes)")
        logger.info(f"  Filename: {full_filename}")
        logger.info(f"  Content type: {request.contentType}")
        
        return {
            "success": True,
            "key": s3_key,
            "fileName": full_filename,
            "message": "Cover letter saved successfully",
            "fileSize": len(content_bytes)
        }
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', 'Unknown')
        error_msg = f"S3 error: {error_code} - {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)
    except Exception as e:
        error_msg = f"Save cover letter failed: {str(e)}"
        logger.error(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

# --- Optional: To run this file directly ---
# You would typically use the 'uvicorn' command below,
# but this is also an option for simple testing.
if __name__ == "__main__":
    import uvicorn
    # Use PORT environment variable (Render provides this) or default to 8000
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)