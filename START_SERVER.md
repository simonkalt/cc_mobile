# FastAPI Server Setup and Startup Guide

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Make sure your `.env` file has:

```env
MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/CoverLetter?retryWrites=true&w=majority
MONGODB_DB_NAME=CoverLetter
MONGODB_COLLECTION_NAME=users
```

### 3. Start the Server

**Development (with auto-reload):**

```bash
# Option 1: Direct command (if uvicorn is in PATH)
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Option 2: Using Python module (works if uvicorn is installed)
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Production:**

```bash
# Option 1: Direct command
uvicorn main:app --host 0.0.0.0 --port 8000

# Option 2: Using Python module
python -m uvicorn main:app --host 0.0.0.0 --port 8000
```

### 4. Access the API

- **API Base URL:** `http://localhost:8000`
- **Interactive API Docs:** `http://localhost:8000/docs` (Swagger UI)
- **Alternative Docs:** `http://localhost:8000/redoc` (ReDoc)
- **Health Check:** `http://localhost:8000/`

## CORS Configuration

The server is configured to allow requests from:

- `http://localhost:3000` (React default)
- `http://localhost:3001`
- `http://127.0.0.1:3000`
- `http://127.0.0.1:3001`

To add your production React app URL, edit `main.py` and add it to the `allow_origins` list:

```python
allow_origins=[
    "http://localhost:3000",
    "https://your-production-app.com",  # Add your production URL here
],
```

## API Endpoints

### User Management

- `POST /api/users/register` - Register new user
- `POST /api/users/login` - User login
- `GET /api/users/{user_id}` - Get user by ID
- `GET /api/users/email/{email}` - Get user by email
- `PUT /api/users/{user_id}` - Update user
- `DELETE /api/users/{user_id}` - Delete user

### Cover Letter Generation

- `POST /api/job-info` - Generate cover letter
- `POST /chat` - Chat endpoint

### Configuration

- `GET /api/llms` - Get available LLMs
- `GET /api/personality-profiles` - Get personality profiles
- `GET /api/system-prompt` - Get system prompt

## Testing the Server

### Using the Interactive Docs

1. Start the server
2. Go to `http://localhost:8000/docs`
3. Try the endpoints directly in the browser

### Using curl

```bash
# Health check
curl http://localhost:8000/

# Register user
curl -X POST http://localhost:8000/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"test123"}'
```

### Using Python

```python
import requests

response = requests.post(
    "http://localhost:8000/api/users/register",
    json={
        "name": "Test User",
        "email": "test@example.com",
        "password": "test123"
    }
)
print(response.json())
```

## React Integration

In your React app, use the API base URL:

```javascript
const API_BASE_URL = "http://localhost:8000";

// Example: Register user
const registerUser = async (userData) => {
  const response = await fetch(`${API_BASE_URL}/api/users/register`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(userData),
  });
  return response.json();
};
```

## Production Deployment

### For Render.com

1. Set environment variables in Render dashboard
2. Build command: `pip install -r requirements.txt`
3. Start command: `uvicorn main:app --host 0.0.0.0 --port $PORT`

### Environment Variables for Production

Make sure to set:

- `MONGODB_URI`
- `MONGODB_DB_NAME`
- `MONGODB_COLLECTION_NAME`
- Any API keys you're using (OpenAI, Anthropic, etc.)

## Troubleshooting

### Port Already in Use

```bash
# Find process using port 8000
lsof -i :8000  # Mac/Linux
netstat -ano | findstr :8000  # Windows

# Use a different port
uvicorn main:app --reload --port 8001
```

### CORS Errors

- Make sure your React app URL is in the `allow_origins` list
- Check that you're using the correct protocol (http vs https)

### MongoDB Connection Issues

- Verify `MONGODB_URI` is set correctly
- Check IP whitelist in MongoDB Atlas
- Test connection with: `python test_mongodb.py`

## Server Logs

The server logs will show:

- Startup messages
- API requests
- Database connections
- Errors and warnings

Watch the console output for debugging information.
