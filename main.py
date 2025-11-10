from fastapi import FastAPI
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
import ollama
import re
import oci
# from xai.chat import user as xUser, system as xSystem  # TODO: Install xAI SDK package when needed

# Create the FastAPI app instance
app = FastAPI()

# Define the data model we expect to receive from the app
# This ensures the 'prompt' is a string
class ChatRequest(BaseModel):
    prompt: str

hf_token = ""

# Define a simple root endpoint to check if the server is running
@app.get("/")
def read_root():
    load_dotenv()

    hf_token = os.getenv('HF_TOKEN')
    # print (hf_token)
    login(hf_token, add_to_git_credential=True)

    return {"status": f"Simon's API is running with Hugging Face token: {hf_token[:8]}"}

# Define the main endpoint your app will call
@app.post("/chat")
async def handle_chat(request: ChatRequest):
    # In a real app, this is where you would call:
    # response = grok_client.chat(request.prompt)
    # response = gemini_model.generate(request.prompt)
    
    # For this example, we'll just echo the prompt back
    print(f"Received prompt: {request.prompt}")
    
    return {
        "response": f"You sent me: '{request.prompt} with Hugging Face token: {hf_token[:8]}'"
    }

# --- Optional: To run this file directly ---
# You would typically use the 'uvicorn' command below,
# but this is also an option for simple testing.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)