from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

import os
import json
import datetime
from dotenv import load_dotenv
from openai import OpenAI
import anthropic
# import google.generativeai as genai
# from google import genai
import google.generativeai as genai
from huggingface_hub import login
import requests
import sys
import re
import oci
try:
    from xai_sdk import Client as xClient
    from xai import user as xUser, system as xSystem
    XAI_SDK_AVAILABLE = True
except ImportError:
    XAI_SDK_AVAILABLE = False
    # Install with: pip install xai-sdk (requires Python 3.10+)
    # Or use direct HTTP requests (already implemented as fallback)

# Create the FastAPI app instance
app = FastAPI()

# Hugging Face token
hf_token = os.getenv('HF_TOKEN')
google_api_key = os.getenv("GOOGLE_API_KEY")
openai_api_key = os.getenv('OPENAI_API_KEY')
anthropic_api_key = os.getenv('ANTHROPIC_API_KEY')
oci_compartment_id=os.getenv("OCI_COMPARTMENT_ID")
gemini_api_key = os.getenv('GEMINI_API_KEY')
xai_api_key = os.getenv('XAI_API_KEY')

LLM_ENVIRONMENT_MAPPING = [
    ("ChatGPT", "gpt-4.1", openai_api_key),
    ("Claude", "claude-sonnet-4-20250514", anthropic_api_key),
    ("Gemini", "gemini-2.5-flash", gemini_api_key),
    ("Grok", "grok-4-fast-reasoning", xai_api_key),
]


def get_available_llms():
    return [
        {"label": display_name, "value": model_name}
        for display_name, model_name, api_key in LLM_ENVIRONMENT_MAPPING
        if api_key
    ]

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
        client = genai.Client(api_key=gemini_api_key)
        response = client.models.generate_content(
            model=model,
            contents=prompt
        )
        return_response = response.text
    elif model == "grok-4-fast-reasoning":
        if XAI_SDK_AVAILABLE:
            # Use SDK if available
            xai_client = xClient(
                api_key=xai_api_key,
                timeout=3600  # Override default timeout with longer timeout for reasoning models
            )
            response = xai_client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant."},
                    {"role": "user", "content": prompt}
                ]
            )
            return_response = response.choices[0].message.content
        else:
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