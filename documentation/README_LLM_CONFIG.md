# LLM Configuration Endpoint - Backend Integration Guide

This guide explains how to integrate the LLM configuration endpoint into your FastAPI backend.

## Quick Start

### 1. Create the Configuration File

Create `llms-config.json` in your backend directory:

```json
{
  "llms": [
    {
      "value": "gpt-5.2",
      "label": "GPT-5.2",
      "description": "Latest GPT model with enhanced capabilities"
    },
    {
      "value": "gpt-4.1",
      "label": "GPT-4.1",
      "description": "Previous generation GPT model"
    },
    {
      "value": "claude-sonnet-4-20250514",
      "label": "Claude Sonnet 4",
      "description": "Anthropic's Claude Sonnet 4 model"
    },
    {
      "value": "gemini-2.5-flash",
      "label": "Gemini 2.5 Flash",
      "description": "Google's Gemini 2.5 Flash model"
    },
    {
      "value": "grok-4-fast-reasoning",
      "label": "Grok 4 Fast Reasoning",
      "description": "xAI's Grok 4 Fast Reasoning model"
    }
  ],
  "defaultModel": "gpt-5.2",
  "internalModel": "gpt-5.2"
}
```

### 2. Integration Methods

#### Method 1: Using the Provided Module (Recommended)

If you're using the provided `llm_config_endpoint.py` module:

```python
from fastapi import FastAPI
from llm_config_endpoint import get_llms_endpoint

app = FastAPI()

# Register the LLM configuration endpoint
get_llms_endpoint(app)

# Your other routes...
@app.get("/")
async def root():
    return {"message": "Hello World"}
```

#### Method 2: Manual Integration

If you prefer to integrate manually or customize the endpoint:

```python
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
import json
from pathlib import Path

app = FastAPI()

# Path to LLM configuration file
LLM_CONFIG_PATH = Path(__file__).parent / "llms-config.json"

@app.get("/api/llms")
async def get_llms():
    try:
        with open(LLM_CONFIG_PATH, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return JSONResponse(content=config)
    except FileNotFoundError:
        raise HTTPException(
            status_code=500,
            detail=f"LLM configuration file not found at {LLM_CONFIG_PATH}"
        )
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Invalid JSON in configuration file: {e}"
        )
```

#### Method 3: Using APIRouter

If you're using APIRouter for modular routing:

```python
from fastapi import FastAPI, APIRouter
from llm_config_endpoint import load_llm_config
from fastapi.responses import JSONResponse
from fastapi import HTTPException

app = FastAPI()
api_router = APIRouter()

@api_router.get("/llms")
async def get_llms():
    try:
        config = load_llm_config()
        return JSONResponse(content=config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

app.include_router(api_router, prefix="/api")
```

### 3. Environment Variable Configuration

You can configure the config file path using an environment variable:

```bash
export LLM_CONFIG_PATH=/path/to/your/llms-config.json
```

Or in your `.env` file:
```
LLM_CONFIG_PATH=/path/to/your/llms-config.json
```

The code will use this path if set, otherwise defaults to `backend/llms-config.json`.

### 4. Testing the Endpoint

Start your FastAPI server and test the endpoint:

```bash
# Start server
uvicorn main:app --reload

# Test endpoint
curl http://localhost:8000/api/llms
```

Expected response:
```json
{
  "llms": [
    {
      "value": "gpt-5.2",
      "label": "GPT-5.2",
      "description": "Latest GPT model with enhanced capabilities"
    }
  ],
  "defaultModel": "gpt-5.2",
  "internalModel": "gpt-5.2"
}
```

## Configuration File Structure

### Required Fields

- **`llms`** (array): List of available LLM models
  - Each entry must have:
    - `value` (string): Model identifier used in API calls
    - `label` (string): Display name for the UI
    - `description` (string, optional): Description of the model

### Optional Fields

- **`defaultModel`** (string): The default model to use when no model is selected
  - Must match a `value` in the `llms` array
- **`internalModel`** (string): The model to use for internal API calls
  - Must match a `value` in the `llms` array

## Validation

The endpoint validates:
1. Configuration file exists and is readable
2. JSON is valid
3. `llms` is an array
4. Each LLM entry has required fields (`value`, `label`)
5. `defaultModel` value exists in `llms` array (if specified)
6. `internalModel` value exists in `llms` array (if specified)

## Error Handling

The endpoint returns appropriate HTTP status codes:

- **200 OK**: Configuration loaded successfully
- **500 Internal Server Error**: 
  - Configuration file not found
  - Invalid JSON
  - Missing required fields
  - Invalid model references

## Caching (Optional)

The provided `llm_config_endpoint.py` includes basic caching. For production, consider:

1. **File Watching**: Reload config when file changes
2. **Cache TTL**: Implement time-based cache expiration
3. **Redis Cache**: For distributed systems

Example with file watching:

```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ConfigFileHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == str(LLM_CONFIG_PATH):
            global _llm_config_cache
            _llm_config_cache = None  # Invalidate cache
            logger.info("LLM config file changed, cache invalidated")

observer = Observer()
observer.schedule(ConfigFileHandler(), path=str(LLM_CONFIG_PATH.parent), recursive=False)
observer.start()
```

## Security Considerations

1. **File Path Validation**: Ensure the config file path cannot be manipulated
2. **Rate Limiting**: Consider rate limiting if needed
3. **CORS**: Configure CORS appropriately for your frontend domain
4. **Authentication**: This is typically a public endpoint, but add auth if needed

## Troubleshooting

### Configuration file not found
- Check that `llms-config.json` exists in the expected location
- Verify file permissions
- Check `LLM_CONFIG_PATH` environment variable if set

### Invalid JSON
- Validate JSON syntax using a JSON validator
- Check for trailing commas or syntax errors

### Model not found errors
- Ensure `defaultModel` and `internalModel` values match `value` fields in `llms` array
- Check for typos in model identifiers

## Example Integration

See `backend/llm_config_endpoint.py` for a complete implementation example.

For a full FastAPI app example:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from llm_config_endpoint import get_llms_endpoint

app = FastAPI(title="Cover Letter API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register LLM configuration endpoint
get_llms_endpoint(app)

# Other endpoints...
@app.get("/api/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

