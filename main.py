from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
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
    logger.info(f"oci_config_file: {oci_config_file}")
    logger.info(f"oci_region: {oci_region}")
    logger.info(f"oci_compartment_id: {oci_compartment_id}")
    logger.info(f"oci_config_profile: {oci_config_profile}")
    logger.info(f"oci_model_id: {oci_model_id}")
    
    # Send OCI configuration via ntfy
    config_summary = f"""OCI Configuration:
- Config file: {oci_config_file}
- Region: {oci_region}
- Compartment ID: {oci_compartment_id}
- Config profile: {oci_config_profile}
- Model ID: {oci_model_id}
- Config exists: {os.path.exists(oci_config_file)}
- Compartment ID set: {bool(oci_compartment_id)}"""
    send_ntfy_notification(config_summary, "OCI Config")

    yield
    # Shutdown (if needed in the future)

# Create the FastAPI app instance
app = FastAPI(lifespan=lifespan)

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

LLM_ENVIRONMENT_MAPPING = [
    ("ChatGPT", "gpt-4.1", openai_api_key),
    ("Claude", "claude-sonnet-4-20250514", anthropic_api_key),
    ("Gemini", "gemini-2.5-flash", gemini_api_key),
    ("Grok", "grok-4-fast-reasoning", xai_api_key),
    ("OCI", "oci-generative-ai", oci_compartment_id),
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
            inference_request = oci.generative_ai_inference.models.CohereGenerateRequest(
                prompt=full_prompt,
                max_tokens=2048,
                temperature=0.7,
                num_generations=1
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
    print(f"Received prompt: {request.prompt} with model: {request.active_model}")
    response = post_to_llm(request.prompt, request.active_model)
    return {
        "response": response if response else f"Error: No response from LLM {request.active_model}"
    }

# --- Optional: To run this file directly ---
# You would typically use the 'uvicorn' command below,
# but this is also an option for simple testing.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)