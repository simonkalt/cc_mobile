from fastapi import FastAPI
from pydantic import BaseModel

# Create the FastAPI app instance
app = FastAPI()

# Define the data model we expect to receive from the app
# This ensures the 'prompt' is a string
class ChatRequest(BaseModel):
    prompt: str

# Define a simple root endpoint to check if the server is running
@app.get("/")
def read_root():
    return {"status": "API is running"}

# Define the main endpoint your app will call
@app.post("/chat")
async def handle_chat(request: ChatRequest):
    # In a real app, this is where you would call:
    # response = grok_client.chat(request.prompt)
    # response = gemini_model.generate(request.prompt)
    
    # For this example, we'll just echo the prompt back
    print(f"Received prompt: {request.prompt}")
    
    return {
        "response": f"You sent me: '{request.prompt}'"
    }

# --- Optional: To run this file directly ---
# You would typically use the 'uvicorn' command below,
# but this is also an option for simple testing.
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)