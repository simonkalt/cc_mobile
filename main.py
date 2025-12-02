from fastapi import FastAPI, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, ValidationError
from contextlib import asynccontextmanager

import os
import json
import datetime
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
import google.generativeai as genai
from huggingface_hub import login
import requests
import oci
import logging
import sys

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
    # Shutdown (if needed in the future)

# Create the FastAPI app instance
app = FastAPI(lifespan=lifespan)

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

# System message for cover letter generation
system_message = """You are an expert cover letter writer. Generate a professional cover letter based on the provided information. 
Return your response as a JSON object with two fields:
- "markdown": The cover letter in markdown format
- "html": The cover letter in HTML format

The cover letter should be well-structured, professional, and tailored to the specific job and company."""

# Personality profiles for different tones
personality_profiles = {
    "Professional": "Professional, formal, and polished tone. Use standard business language and maintain a respectful, courteous demeanor.",
    "Friendly": "Warm, approachable, and personable tone. Use conversational language while remaining professional.",
    "Confident": "Assertive, self-assured, and impactful tone. Highlight achievements and capabilities with conviction.",
    "Enthusiastic": "Energetic, passionate, and excited tone. Show genuine interest and enthusiasm for the role and company.",
    "Casual": "Relaxed, informal, and conversational tone. Use a more laid-back approach while still being respectful.",
    "Formal": "Very formal, traditional, and conservative tone. Use formal business language and traditional structure."
}

# Model names mapping
gpt_model = os.getenv('GPT_MODEL', 'gpt-4.1')
claude_model = os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514')
ollama_model = os.getenv('OLLAMA_MODEL', 'llama3.2')
xai_model = os.getenv('XAI_MODEL', 'grok-4-fast-reasoning')

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

def get_job_info(llm: str, date_input: str, company_name: str, hiring_manager: str, 
                 ad_source: str, resume: str, jd: str, additional_instructions: str, 
                 tone: str, address: str = "", phone_number: str = ""):
    """
    Generate cover letter based on job information using specified LLM.
    Returns a dictionary with 'markdown' and 'html' fields.
    """
    # Get today's date if not provided
    today_date = date_input if date_input else datetime.datetime.now().strftime("%Y-%m-%d")
    
    # Build message payload
    message_data = {
        "llm": llm,
        "today": f"Date: {today_date}",
        "company_name": company_name,
        "hiring_manager": hiring_manager,
        "ad_source": ad_source,
        "resume": resume,
        "jd": jd,
        "additional_instructions": additional_instructions,
        "tone": f"Use the following tone/personality when generating the result, but do not specifically note the activities within this text: {personality_profiles.get(tone, personality_profiles['Professional'])}"
    }
    
    # Add optional fields
    if address:
        message_data["address"] = address
    if phone_number:
        message_data["phone_number"] = phone_number
    
    message = json.dumps(message_data)
    r = ""
    
    try:
        if llm == "Gemini":
            msg = f"{system_message}. {message}. Hiring Manager: {hiring_manager}. Company Name: {company_name}. Ad Source: {ad_source}"
            genai.configure(api_key=gemini_api_key)
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(contents=msg)
            r = response.text
            
        elif llm == "ChatGPT":
            client = OpenAI(api_key=openai_api_key)
            messages = [
                {"role": "user", "content": system_message},
                {"role": "user", "content": message},
                {"role": "user", "content": f"Hiring Manager: {hiring_manager}"},
                {"role": "user", "content": f"Company Name: {company_name}"},
                {"role": "user", "content": f"Ad Source: {ad_source}"}
            ]
            response = client.chat.completions.create(model=gpt_model, messages=messages)
            r = response.choices[0].message.content
            
        elif llm == "Grok":
            # Use HTTP API (xai SDK has different API structure)
            headers = {
                "Authorization": f"Bearer {xai_api_key}",
                "Content-Type": "application/json"
            }
            data = {
                "model": xai_model,
                "messages": [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": message},
                    {"role": "user", "content": f"Hiring Manager: {hiring_manager}"},
                    {"role": "user", "content": f"Company Name: {company_name}"},
                    {"role": "user", "content": f"Ad Source: {ad_source}"}
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
            r = result["choices"][0]["message"]["content"]
                
        elif llm == "OCI":
            full_prompt = f"{system_message}. {message}. Hiring Manager: {hiring_manager}. Company Name: {company_name}. Ad Source: {ad_source}"
            r = get_oc_info(full_prompt)
            logger.info(f"OCI response received: {r[:100]}...")
            
        elif llm == "Llama":
            if not OLLAMA_AVAILABLE:
                raise ImportError("ollama library is not installed. Please install it with: pip install ollama")
            
            message_data_llama = {
                "Company Name": company_name,
                "Hiring Manager": hiring_manager,
                "Resume": resume,
                "Ad Source": ad_source,
                "Job Description": jd,
                "Additional Instructions": additional_instructions
            }
            if address:
                message_data_llama["Address"] = address
            if phone_number:
                message_data_llama["Phone Number"] = phone_number
                
            message_llama = json.dumps(message_data_llama)
            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": message_llama}
            ]
            response = ollama.chat(model=ollama_model, messages=messages)
            r = response['message']['content']
            
        elif llm == "Claude":
            client = anthropic.Anthropic(api_key=anthropic_api_key)
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": message},
                        {"type": "text", "text": f"Hiring Manager: {hiring_manager}"},
                        {"type": "text", "text": f"Company Name: {company_name}"},
                        {"type": "text", "text": f"Ad Source: {ad_source}"}
                    ]
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
        
        # Clean and parse the response
        r = r.replace("```json", "").replace("```", "").strip()
        json_r = json.loads(r)
        
        return {
            "markdown": json_r.get("markdown", ""),
            "html": json_r.get("html", "")
        }
        
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON response: {e}")
        logger.error(f"Response was: {r[:500]}")
        return {
            "markdown": f"Error: Failed to parse LLM response as JSON. Raw response: {r[:500]}",
            "html": f"<p>Error: Failed to parse LLM response as JSON.</p><pre>{r[:500]}</pre>"
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
async def handle_chat(request: ChatRequest):
    logger.info(f"Received chat request - prompt length: {len(request.prompt)}, model: {request.active_model}")
    try:
        response = post_to_llm(request.prompt, request.active_model)
        return {
            "response": response if response else f"Error: No response from LLM {request.active_model}"
        }
    except Exception as e:
        logger.error(f"Error in handle_chat: {str(e)}")
        return {
            "response": f"Error processing request: {str(e)}"
        }

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
        phone_number=request.phone_number
    )
    return result

# --- Optional: To run this file directly ---
# You would typically use the 'uvicorn' command below,
# but this is also an option for simple testing.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)