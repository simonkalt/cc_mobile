# CORS Setup Explanation

## What is CORS?

**CORS (Cross-Origin Resource Sharing)** is a browser security feature that controls which websites can make requests to your API.

### The Problem

When your React app (running on `http://localhost:3000` or `https://myapp.com`) tries to make a request to your API (running on `https://api.onrender.com`), the browser blocks it because they're on **different origins** (different domains/ports).

**Example:**
- React app: `http://localhost:3000` 
- API: `https://cover-letter-api.onrender.com`
- ❌ Browser blocks the request (different origins)

### The Solution

CORS headers tell the browser: *"It's okay, this API allows requests from these specific websites."*

## How It Works in Your Code

In `main.py`, the CORS middleware is configured like this:

```python
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
    allow_origins=all_origins,  # List of allowed websites
    allow_credentials=True,      # Allow cookies/auth headers
    allow_methods=["*"],         # Allow all HTTP methods
    allow_headers=["*"],         # Allow all headers
)
```

## Configuration Scenarios

### Scenario 1: Local Development

**React app:** `http://localhost:3000`  
**API:** `http://localhost:8000`

**Configuration:** No action needed! The default localhost origins are already included.

```python
# Already configured in code:
default_origins = [
    "http://localhost:3000",  # ✅ Your React app
    "http://localhost:3001",
    ...
]
```

### Scenario 2: React App on Render, API on Render

**React app:** `https://my-react-app.onrender.com`  
**API:** `https://cover-letter-api.onrender.com`

**Configuration:** Add React app URL to environment variable in Render dashboard:

```env
CORS_ORIGINS=https://my-react-app.onrender.com
```

**In Render Dashboard:**
1. Go to your API service
2. Click **"Environment"** tab
3. Add new variable:
   - **Key:** `CORS_ORIGINS`
   - **Value:** `https://my-react-app.onrender.com`
4. Save and redeploy

### Scenario 3: Multiple React Apps

**React apps:**
- `https://my-app.onrender.com`
- `https://my-app.com` (custom domain)
- `http://localhost:3000` (local dev)

**Configuration:** Separate with commas (no spaces):

```env
CORS_ORIGINS=https://my-app.onrender.com,https://my-app.com,http://localhost:3000
```

### Scenario 4: Custom Domain

**React app:** `https://myapp.com`  
**API:** `https://api.myapp.com`

**Configuration:**

```env
CORS_ORIGINS=https://myapp.com
```

**Important:** Include the protocol (`https://`) and no trailing slash.

## Step-by-Step Setup for Render

### 1. Find Your React App URL

After deploying your React app to Render, you'll get a URL like:
```
https://my-react-app.onrender.com
```

### 2. Add to Render Environment Variables

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click on your **API service** (not React app)
3. Go to **"Environment"** tab
4. Click **"Add Environment Variable"**
5. Enter:
   - **Key:** `CORS_ORIGINS`
   - **Value:** `https://my-react-app.onrender.com`
6. Click **"Save Changes"**
7. Render will automatically redeploy

### 3. Verify It Works

After redeployment, check the logs. You should see:
```
CORS configured for origins: ['https://my-react-app.onrender.com', 'http://localhost:3000', ...]
```

### 4. Test from React App

In your React app, make a request:

```javascript
const API_URL = 'https://cover-letter-api.onrender.com';

fetch(`${API_URL}/api/users/register`, {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ name: 'Test', email: 'test@example.com', password: 'test123' })
})
  .then(res => res.json())
  .then(data => console.log('Success:', data))
  .catch(err => console.error('CORS Error:', err));
```

If CORS is configured correctly, the request will succeed. If not, you'll see an error in the browser console.

## Common CORS Errors

### Error: "Access to fetch at '...' from origin '...' has been blocked by CORS policy"

**Cause:** The React app URL is not in the `allow_origins` list.

**Solution:** 
1. Check the exact URL of your React app (including `https://`)
2. Add it to `CORS_ORIGINS` environment variable
3. Make sure there are no typos
4. Redeploy the API

### Error: "Credentials flag is true, but Access-Control-Allow-Credentials is not 'true'"

**Cause:** This shouldn't happen with current config (we set `allow_credentials=True`).

**Solution:** If you see this, check that CORS middleware is properly configured.

### Error: "Method PUT is not allowed by Access-Control-Allow-Methods"

**Cause:** This shouldn't happen (we allow all methods with `["*"]`).

**Solution:** Verify CORS middleware configuration.

## Testing CORS Configuration

### Method 1: Browser Console

1. Open your React app in browser
2. Open Developer Tools (F12)
3. Go to Console tab
4. Run:
```javascript
fetch('https://your-api.onrender.com/')
  .then(r => r.json())
  .then(console.log)
  .catch(console.error)
```

If it works, CORS is configured correctly!

### Method 2: curl (from terminal)

```bash
curl -H "Origin: https://my-react-app.onrender.com" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: Content-Type" \
     -X OPTIONS \
     https://your-api.onrender.com/api/users/register \
     -v
```

Look for `Access-Control-Allow-Origin: https://my-react-app.onrender.com` in the response.

### Method 3: Check API Logs

After making a request, check Render logs. You should see the request come through without CORS errors.

## Quick Reference

| React App URL | CORS_ORIGINS Value |
|--------------|-------------------|
| `http://localhost:3000` | Already included (no config needed) |
| `https://myapp.onrender.com` | `https://myapp.onrender.com` |
| `https://myapp.com` | `https://myapp.com` |
| Multiple apps | `https://app1.com,https://app2.com` |

## Important Notes

1. **Exact Match Required:** The URL must match exactly (including `https://`, no trailing slash)
2. **No Wildcards:** You can't use `*.onrender.com` - list each URL explicitly
3. **Localhost Included:** Localhost origins are always included for development
4. **Redeploy Required:** After changing `CORS_ORIGINS`, you must redeploy the API
5. **Case Sensitive:** URLs are case-sensitive

## Troubleshooting Checklist

- [ ] React app URL is exactly correct (check for typos)
- [ ] `CORS_ORIGINS` environment variable is set in Render
- [ ] No spaces in the `CORS_ORIGINS` value (use commas only)
- [ ] API has been redeployed after setting environment variable
- [ ] Check browser console for exact error message
- [ ] Verify the URL includes `https://` (not `http://` for production)
- [ ] Check Render logs for CORS configuration message

## Still Having Issues?

1. **Check Render Logs:** Look for the CORS configuration message on startup
2. **Test with curl:** Use the curl command above to test CORS headers
3. **Browser DevTools:** Check Network tab → Headers → Response Headers for CORS headers
4. **Verify Environment Variable:** Double-check it's set correctly in Render dashboard

