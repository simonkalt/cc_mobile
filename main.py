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
# from xai.chat import user as xUser, system as xSystem  # TODO: Install xAI SDK package when needed

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
    ("ChatGPT", "gpt-4o-mini", openai_api_key),
    ("Claude", "claude-3-5-sonnet-20241022", anthropic_api_key),
    ("Gemini", "gemini-2.5-flash", gemini_api_key),
    ("Grok", "grok-1", xai_api_key),
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
    active_model: str = "gpt-4o-mini"  # Default model

def post_to_llm(prompt: str, model: str = "gpt-4o-mini"):
    return_response = None
    if model == "gpt-4o-mini":
        client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        response = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return_response = response.choices[0].message.content
    elif model == "claude-3-5-sonnet-20241022":
        client = anthropic.Anthropic(api_key=os.getenv('ANTHROPIC_API_KEY'))
        response = client.messages.create(
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": prompt}
            ]
        )
        return_response = response.choices[0].message.content
    elif model == "gemini-2.5-flash":
        client = genai.Client(api_key=os.getenv('GEMINI_API_KEY'))
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[prompt]
        )
        return_response = response.text

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
    # In a real app, this is where you would call:
    # response = grok_client.chat(request.prompt)
    # response = gemini_model.generate(request.prompt)
    
    # For this example, we'll just echo the prompt back
    print(f"Received prompt: {request.prompt} with model: {request.active_model}")
    response = post_to_llm(request.prompt, request.active_model)
    return {
        "response": response if response else "Error: No response from LLM"
    }

# --- Optional: To run this file directly ---
# You would typically use the 'uvicorn' command below,
# but this is also an option for simple testing.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)