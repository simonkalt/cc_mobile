# Render.com Deployment Guide

Complete guide for deploying your FastAPI application to Render.com.

## Prerequisites

- Render.com account (free tier available)
- MongoDB Atlas cluster set up
- GitHub repository (or connect directly)

## Step 1: Prepare Your Repository

Make sure your repository has:

- ✅ `main.py` (FastAPI app)
- ✅ `requirements.txt` (all dependencies)
- ✅ `.gitignore` (excludes `.env` and sensitive files)

## Step 2: Create a New Web Service on Render

1. Go to [Render Dashboard](https://dashboard.render.com)
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select your repository

## Step 3: Configure Build Settings

**Name:** `cover-letter-api` (or your preferred name)

**Environment:** `Python 3`

**Build Command:**

```bash
pip install -r requirements.txt
```

**Start Command:**

```bash
uvicorn main:app --host 0.0.0.0 --port $PORT
```

**Note:** Render automatically sets the `$PORT` environment variable, so use that instead of a hardcoded port.

### Alternative: Deploy with Docker (required for docx→PDF)

If you use **POST /api/files/docx-to-pdf** (LibreOffice), deploy as **Docker** so LibreOffice is available:

1. In Render, set **Environment** to **Docker** (not "Python 3").
2. Use the repo **Dockerfile** (root); Render will build it. No build/start commands needed.
3. See [LIBREOFFICE_SETUP.md](./LIBREOFFICE_SETUP.md) for details.

## Step 4: Set Environment Variables

In the Render dashboard, go to **"Environment"** tab and add:

### Required Variables

```env
# MongoDB Configuration
MONGODB_URI=mongodb+srv://username:password@cluster0.xxxxx.mongodb.net/CoverLetter?retryWrites=true&w=majority
MONGODB_DB_NAME=CoverLetter
MONGODB_COLLECTION_NAME=users

# CORS - Add your React app URL(s)
CORS_ORIGINS=https://your-react-app.onrender.com,https://your-custom-domain.com

# API Keys (if using)
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=...
GEMINI_API_KEY=...
XAI_API_KEY=...
```

### Optional Variables

```env
# OCI Configuration (if using)
OCI_COMPARTMENT_ID=ocid1...
OCI_REGION=us-phoenix-1
OCI_MODEL_ID=ocid1...

# AWS S3 (if using)
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
AWS_REGION=us-east-1
```

**Important:**

- Never commit these to your repository
- Use Render's environment variables section
- Use strong, unique passwords

## Step 5: Configure CORS for Your React App

The API automatically reads `CORS_ORIGINS` from environment variables. Add your React app URL(s):

```env
CORS_ORIGINS=https://your-react-app.onrender.com,https://your-custom-domain.com
```

**Multiple origins:** Separate with commas (no spaces)

**Example:**

```env
CORS_ORIGINS=https://myapp.onrender.com,https://myapp.com,http://localhost:3000
```

## Step 6: MongoDB Atlas Configuration

### Whitelist IP Addresses

Since Render uses dynamic IPs:

1. Go to MongoDB Atlas → **Security** → **Network Access**
2. Click **"Add IP Address"**
3. Click **"Allow Access from Anywhere"** (adds `0.0.0.0/0`)
4. Click **"Confirm"**

See `RENDER_DEPLOYMENT.md` for detailed MongoDB setup.

## Step 7: Deploy

1. Click **"Create Web Service"**
2. Render will:
   - Clone your repository
   - Install dependencies
   - Start your application
3. Watch the logs for any errors

## Step 8: Get Your API URL

After deployment, Render provides a URL like:

```
https://cover-letter-api.onrender.com
```

**Note:** Free tier services spin down after 15 minutes of inactivity and take ~30 seconds to wake up.

## Step 9: Update Your React App

Update your React app to use the Render URL:

```javascript
// Production
const API_BASE_URL = "https://cover-letter-api.onrender.com";

// Or use environment variable
const API_BASE_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";
```

## Step 10: Test Your Deployment

### Health Check

```bash
curl https://your-api.onrender.com/
```

### Test User Registration

```bash
curl -X POST https://your-api.onrender.com/api/users/register \
  -H "Content-Type: application/json" \
  -d '{"name":"Test User","email":"test@example.com","password":"test123"}'
```

### Access API Docs

Visit: `https://your-api.onrender.com/docs`

## Render-Specific Considerations

### Free Tier Limitations

- **Spins down after 15 min inactivity** - First request after spin-down takes ~30 seconds
- **Limited resources** - May be slower than paid tiers
- **No custom domains on free tier** - Must use `.onrender.com` subdomain

### Upgrading to Paid Tier

Benefits:

- Always-on service (no spin-down)
- Custom domains
- More resources
- Better performance

### Environment Variables

- Set all variables in Render dashboard
- Never commit `.env` files
- Use Render's **"Environment"** tab for all secrets

### Logs

- View logs in Render dashboard
- Logs are available in real-time
- Use `logger.info()` for important messages

### Auto-Deploy

Render automatically deploys when you push to:

- `main` branch (production)
- Or configure specific branches

## Troubleshooting

### Service Won't Start

**Check logs in Render dashboard:**

- Look for import errors
- Check if all dependencies are in `requirements.txt`
- Verify Python version compatibility

**Common issues:**

- Missing dependencies in `requirements.txt`
- Port not using `$PORT` variable
- Environment variables not set

### CORS Errors

**Symptoms:** React app can't connect to API

**Solutions:**

1. Add React app URL to `CORS_ORIGINS` environment variable
2. Check that URL matches exactly (http vs https, trailing slashes)
3. Verify CORS middleware is configured correctly

### MongoDB Connection Errors

**Check:**

1. `MONGODB_URI` is set correctly
2. IP whitelist includes `0.0.0.0/0` in MongoDB Atlas
3. Username/password are correct
4. Database name matches (`CoverLetter`)

### Slow First Request

**Normal on free tier:** Services spin down after 15 minutes. First request after spin-down takes ~30 seconds to wake up.

**Solution:** Upgrade to paid tier for always-on service.

## Production Checklist

- [ ] All environment variables set in Render
- [ ] MongoDB Atlas IP whitelist configured (`0.0.0.0/0`)
- [ ] CORS origins set for React app
- [ ] API tested and working
- [ ] React app updated with production API URL
- [ ] Logs monitored for errors
- [ ] Health check endpoint working

## Next Steps

1. Set up custom domain (paid tier)
2. Configure monitoring/alerts
3. Set up CI/CD pipeline
4. Add rate limiting (if needed)
5. Set up backup strategy for MongoDB

## Support

- Render Docs: https://render.com/docs
- Render Community: https://community.render.com
- MongoDB Atlas Docs: https://docs.atlas.mongodb.com
