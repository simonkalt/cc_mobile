"""
FastAPI application entry point
"""
import warnings
import sys
import logging

# Log Python environment info at startup
logger = logging.getLogger(__name__)
logger.info(f"Python executable: {sys.executable}")
logger.info(f"Python version: {sys.version}")
logger.info(f"Python path: {sys.path[:3]}...")

# Check redis availability at startup
try:
    import redis
    logger.info(f"✓ Redis library available (version: {getattr(redis, '__version__', 'unknown')})")
except ImportError as e:
    logger.warning(f"⚠ Redis library not available: {e}")

# Suppress importlib.metadata compatibility warnings for Python 3.9
# packages_distributions was added in Python 3.10, but some dependencies try to use it
warnings.filterwarnings("ignore", message=".*importlib.metadata.*packages_distributions.*")
warnings.filterwarnings("ignore", category=FutureWarning, message=".*Python version.*")

# Patch importlib.metadata for Python 3.9 compatibility
try:
    import importlib.metadata
    if not hasattr(importlib.metadata, 'packages_distributions'):
        # Add a stub function for Python 3.9 compatibility
        def _packages_distributions_stub():
            return {}
        importlib.metadata.packages_distributions = _packages_distributions_stub
except (ImportError, AttributeError):
    pass

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse, Response, RedirectResponse
from fastapi import Request, status, HTTPException
from fastapi.staticfiles import StaticFiles
import logging
import sys
import os

from app.core.config import settings, get_cors_origins
from app.core.logging_config import setup_logging
from app.db.mongodb import connect_to_mongodb, close_mongodb_connection
from app.api.routers import users

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)

# Note: We let uvicorn handle SIGINT/SIGTERM signals natively
# The lifespan context manager below handles cleanup during shutdown


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    logger.info("Starting application...")
    connect_to_mongodb()
    logger.info("Application startup complete")
    
    
    yield
    
    # Shutdown - minimal cleanup, let uvicorn handle task cancellation
    logger.info("Shutting down application...")
    try:
        # MongoDB cleanup is already non-blocking (runs in daemon thread)
        # Just call it and return immediately - don't wait
        close_mongodb_connection()
        logger.info("Application shutdown complete")
    except Exception as e:
        logger.warning(f"Error during shutdown (non-critical): {e}")


# Create the FastAPI app instance
app = FastAPI(
    title=settings.APP_NAME,
    description="API for cover letter generation and user management",
    version=settings.APP_VERSION,
    lifespan=lifespan,
)

# Configure CORS
cors_origins = get_cors_origins()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Mount static files for website and documents BEFORE routers
# Get the project root directory - try multiple methods for compatibility
try:
    # Method 1: Relative to app/ directory (most common)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Method 2: If that doesn't work, try current working directory
    if not os.path.exists(os.path.join(project_root, "website")):
        cwd = os.getcwd()
        if os.path.exists(os.path.join(cwd, "website")):
            project_root = cwd
            logger.info(f"Using current working directory for static files: {cwd}")
    
    website_path = os.path.join(project_root, "website")
    documents_path = os.path.join(project_root, "documents")
    
    logger.info(f"Project root: {project_root}")
    logger.info(f"Website path: {website_path}")
    logger.info(f"Documents path: {documents_path}")
    logger.info(f"Website exists: {os.path.exists(website_path)}")
    logger.info(f"Documents exists: {os.path.exists(documents_path)}")
    
    if os.path.exists(website_path):
        app.mount("/website", StaticFiles(directory=website_path, html=True), name="website")
        logger.info(f"✓ Successfully mounted website static files from: {website_path}")
    else:
        logger.warning(f"✗ Website directory not found at: {website_path}")
        # List directory contents for debugging
        try:
            logger.warning(f"Contents of project root: {os.listdir(project_root)}")
        except Exception as e:
            logger.warning(f"Could not list project root: {e}")
    
    if os.path.exists(documents_path):
        app.mount("/documents", StaticFiles(directory=documents_path), name="documents")
        logger.info(f"✓ Successfully mounted documents static files from: {documents_path}")
    else:
        logger.warning(f"✗ Documents directory not found at: {documents_path}")
    
except Exception as e:
    logger.error(f"Error mounting static files: {e}", exc_info=True)

# Add exception handler for validation errors
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
            "body": body.decode("utf-8") if body else "Empty body",
        },
    )


# Include routers
try:
    app.include_router(users.router)
except Exception as e:
    logger.error(f"Failed to register users router: {e}", exc_info=True)
    raise

# Import and include other routers
try:
    from app.api.routers import (
        job_url,
        llm_config,
        personality,
        config,
        cover_letter,
        files,
        cover_letters,
        pdf,
        sms,
        email,
    )
    app.include_router(job_url.router)
    app.include_router(llm_config.router)
    app.include_router(personality.router)
    app.include_router(config.router)
    app.include_router(cover_letter.router)
    app.include_router(files.router)
    app.include_router(cover_letters.router)
    app.include_router(pdf.router)
    app.include_router(sms.router)
    app.include_router(email.router)
except ImportError as e:
    logger.error(f"❌ Some routers could not be imported: {e}", exc_info=True)
except Exception as e:
    logger.error(f"❌ Failed to register some routers: {e}", exc_info=True)

# Import and register subscriptions router separately with detailed error handling
# Note: This module may be imported multiple times (by start script check, uvicorn reloader, and server process)
# This is normal behavior - we log once per process at INFO level, detailed route info at DEBUG level
try:
    from app.api.routers import subscriptions
    logger.info(f"Imported subscriptions router: {len(subscriptions.router.routes)} routes")
    # Log individual routes at DEBUG level to reduce startup noise
    for route in subscriptions.router.routes:
        if hasattr(route, 'path'):
            path = route.path
            methods = getattr(route, 'methods', set())
            logger.debug(f"  Subscription route: {', '.join(methods):<10} {path}")
    
    app.include_router(subscriptions.router)
    logger.info("Registered subscriptions router")
except ImportError as e:
    print(f"❌ FAILED TO IMPORT SUBSCRIPTIONS ROUTER: {e}")
    logger.error(f"❌ Failed to import subscriptions router: {e}", exc_info=True)
    import traceback
    print(traceback.format_exc())
    logger.error(f"Import traceback: {traceback.format_exc()}")
except AttributeError as e:
    print(f"❌ SUBSCRIPTIONS ROUTER MISSING 'router' ATTRIBUTE: {e}")
    logger.error(f"❌ Subscriptions router missing 'router' attribute: {e}", exc_info=True)
    import traceback
    print(traceback.format_exc())
    logger.error(f"AttributeError traceback: {traceback.format_exc()}")
except Exception as e:
    print(f"❌ FAILED TO REGISTER SUBSCRIPTIONS ROUTER: {e}")
    logger.error(f"❌ Failed to register subscriptions router: {e}", exc_info=True)
    import traceback
    print(traceback.format_exc())
    logger.error(f"Exception traceback: {traceback.format_exc()}")
print("=" * 80)
logger.info("=" * 80)


# Root route - redirect to marketing website
@app.get("/")
async def root():
    """Root endpoint - redirects to marketing website"""
    return RedirectResponse(url="/website", status_code=status.HTTP_301_MOVED_PERMANENTLY)


# OAuth callback endpoint for Zoho Mail API setup
@app.get("/oauth/callback", dependencies=[])
async def oauth_callback(request: Request):
    """
    OAuth callback endpoint for Zoho Mail API authorization.
    Returns a JSON object with the authorization code or error information.
    """
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    error_description = request.query_params.get("error_description")
    
    if error:
        logger.warning(f"OAuth callback error: {error} - {error_description}")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": error,
                "error_description": error_description or "No description provided",
                "message": "OAuth authorization failed. Please try the authorization process again."
            }
        )
    
    if not code:
        logger.warning("OAuth callback received without authorization code")
        return JSONResponse(
            status_code=400,
            content={
                "success": False,
                "error": "missing_code",
                "error_description": "The authorization code was not found in the callback URL.",
                "message": "No authorization code received. Please try the authorization process again."
            }
        )
    
    # Success - return the authorization code
    logger.info(f"OAuth callback received - Authorization code: {code[:20]}...")
    return JSONResponse(
        status_code=200,
        content={
            "success": True,
            "code": code,
            "message": "Authorization code received successfully. Use this code to generate your refresh token.",
            "next_step": "Exchange this authorization code for a refresh token using the Zoho OAuth token endpoint."
        }
    )

# Public endpoint for Terms of Service - defined directly on app to ensure it's truly public
@app.get("/api/files/terms-of-service", dependencies=[])
async def get_terms_of_service():
    """
    Get the Terms of Service as markdown from S3.
    This is a public endpoint that requires no authentication.
    Returns markdown content that can be displayed or rendered by the client.
    """
    from app.utils.s3_utils import get_s3_client, S3_AVAILABLE
    from botocore.exceptions import ClientError
    
    if not S3_AVAILABLE:
        raise HTTPException(
            status_code=503,
            detail="S3 service is not available. boto3 is not installed.",
        )

    try:
        s3_path = "s3://custom-cover-user-resumes/policy/sAImon Software - Terms of Service.md"
        
        if s3_path.startswith("s3://"):
            s3_path = s3_path[5:]
        
        parts = s3_path.split("/", 1)
        if len(parts) != 2:
            raise HTTPException(
                status_code=500,
                detail=f"Invalid S3 path format: {s3_path}"
            )
        
        bucket_name = parts[0]
        object_key = parts[1]
        
        s3_client = get_s3_client()
        response = s3_client.get_object(Bucket=bucket_name, Key=object_key)
        markdown_content = response["Body"].read().decode('utf-8')
        
        if not markdown_content:
            raise HTTPException(
                status_code=404,
                detail="Terms of Service markdown file not found in S3"
            )
        
        return Response(
            content=markdown_content.encode('utf-8'),
            media_type="text/markdown; charset=utf-8",
            headers={
                "Content-Disposition": 'inline; filename="Terms of Service.md"'
            }
        )
        
    except HTTPException:
        raise
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "Unknown")
        if error_code == "NoSuchKey" or error_code == "404":
            raise HTTPException(
                status_code=404,
                detail="Terms of Service markdown file not found in S3"
            )
        raise HTTPException(status_code=500, detail=f"S3 error: {error_code}")
    except Exception as e:
        if "NoSuchKey" in str(e) or "404" in str(e) or "not found" in str(e).lower():
            raise HTTPException(status_code=404, detail="Terms of Service markdown file not found in S3")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve Terms of Service: {str(e)}")


# Debug endpoint to check static file paths
@app.get("/debug/static-paths")
async def debug_static_paths():
    """Debug endpoint to check static file paths"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cwd = os.getcwd()
    website_path1 = os.path.join(project_root, "website")
    website_path2 = os.path.join(cwd, "website")
    
    return {
        "project_root": project_root,
        "current_working_directory": cwd,
        "website_path_1": website_path1,
        "website_path_1_exists": os.path.exists(website_path1),
        "website_path_2": website_path2,
        "website_path_2_exists": os.path.exists(website_path2),
        "project_root_contents": os.listdir(project_root) if os.path.exists(project_root) else "N/A",
        "cwd_contents": os.listdir(cwd) if os.path.exists(cwd) else "N/A",
    }


# Fallback route handler for website (if mount doesn't work)
@app.get("/website", response_class=HTMLResponse)
@app.get("/website/", response_class=HTMLResponse)
@app.get("/website/index.html", response_class=HTMLResponse)
async def serve_website():
    """Fallback route to serve website index.html"""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cwd = os.getcwd()
    
    # Try multiple possible paths
    possible_paths = [
        os.path.join(project_root, "website", "index.html"),
        os.path.join(cwd, "website", "index.html"),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            return FileResponse(path)
    
    # If file not found, return error message
    return HTMLResponse(
        content=f"""
        <html>
            <body>
                <h1>Website Not Found</h1>
                <p>Could not find index.html. Checked paths:</p>
                <ul>
                    {''.join([f'<li>{path} - {"✓" if os.path.exists(path) else "✗"}</li>' for path in possible_paths])}
                </ul>
                <p>Project root: {project_root}</p>
                <p>CWD: {cwd}</p>
            </body>
        </html>
        """,
        status_code=404
    )


@app.get("/api/debug/routes")
async def debug_routes():
    """Debug endpoint to list all registered routes"""
    routes = []
    for route in app.routes:
        if hasattr(route, 'path') and hasattr(route, 'methods'):
            routes.append({
                "path": route.path,
                "methods": list(route.methods) if route.methods else [],
                "name": getattr(route, 'name', 'N/A')
            })
    return {
        "total_routes": len(routes),
        "routes": sorted(routes, key=lambda x: x['path'])
    }

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    from app.db.mongodb import is_connected, get_collection, get_database
    from app.utils.user_helpers import USERS_COLLECTION
    
    health_info = {
        "status": "healthy",
        "mongodb": "connected" if is_connected() else "disconnected"
    }
    
    # Add Stripe health check
    try:
        from app.services.subscription_service import STRIPE_AVAILABLE
        import stripe
        from app.core.config import settings
        
        health_info["stripe"] = {
            "library_available": STRIPE_AVAILABLE,
            "api_key_configured": bool(settings.STRIPE_TEST_API_KEY or settings.STRIPE_API_KEY),
            "test_key_present": bool(settings.STRIPE_TEST_API_KEY),
            "production_key_present": bool(settings.STRIPE_API_KEY),
        }
        
        # Test Stripe connection if available and configured
        if STRIPE_AVAILABLE and (settings.STRIPE_TEST_API_KEY or settings.STRIPE_API_KEY):
            try:
                # Make a simple API call to verify connection
                stripe.Account.retrieve()
                health_info["stripe"]["connection"] = "ok"
            except stripe.error.AuthenticationError:
                health_info["stripe"]["connection"] = "authentication_failed"
            except stripe.error.APIConnectionError:
                health_info["stripe"]["connection"] = "connection_error"
            except Exception as e:
                health_info["stripe"]["connection"] = f"error: {str(e)}"
        else:
            health_info["stripe"]["connection"] = "not_configured"
    except Exception as e:
        health_info["stripe"] = {"error": str(e)}
    
    # Add detailed database info if connected
    if is_connected():
        try:
            db = get_database()
            if db is not None:
                health_info["database"] = db.name
                collections = db.list_collection_names()
                health_info["collections"] = collections
                
                # Try to access users collection
                collection = get_collection(USERS_COLLECTION)
                if collection is not None:
                    user_count = collection.count_documents({})
                    health_info["users_collection"] = {
                        "name": USERS_COLLECTION,
                        "document_count": user_count
                    }
                    
                    # Try to find the specific user
                    from bson import ObjectId
                    try:
                        user_id_obj = ObjectId("693326c07fcdaab8e81cdd2f")
                        user = collection.find_one({"_id": user_id_obj})
                        health_info["test_user_found"] = user is not None
                        if user:
                            health_info["test_user_email"] = user.get("email")
                    except Exception as e:
                        health_info["test_user_error"] = str(e)
        except Exception as e:
            health_info["database_error"] = str(e)
    
    # Add route information for debugging
    try:
        routes = []
        for route in app.routes:
            if hasattr(route, 'path') and hasattr(route, 'methods'):
                routes.append({
                    "path": route.path,
                    "methods": list(route.methods) if route.methods else []
                })
        health_info["registered_routes"] = [r for r in routes if "/api/users" in r["path"]]
    except Exception as e:
        health_info["routes_error"] = str(e)
    
    return health_info


@app.get("/api/health/stripe")
async def stripe_health_check():
    """
    Dedicated Stripe health check endpoint
    Returns detailed information about Stripe configuration and connectivity
    """
    from app.services.subscription_service import STRIPE_AVAILABLE
    from app.core.config import settings
    
    health_info = {
        "stripe_library_available": STRIPE_AVAILABLE,
        "status": "unknown"
    }
    
    if not STRIPE_AVAILABLE:
        health_info["status"] = "library_not_available"
        health_info["message"] = "Stripe Python library is not installed. Install with: pip install stripe>=7.0.0"
        return health_info
    
    # Check API key configuration
    stripe_api_key = settings.STRIPE_TEST_API_KEY or settings.STRIPE_API_KEY
    if not stripe_api_key:
        health_info["status"] = "not_configured"
        health_info["message"] = "Stripe API key not found. Set STRIPE_TEST_API_KEY or STRIPE_API_KEY in environment variables."
        health_info["test_key_present"] = bool(settings.STRIPE_TEST_API_KEY)
        health_info["production_key_present"] = bool(settings.STRIPE_API_KEY)
        return health_info
    
    # Test Stripe API connection
    try:
        import stripe
        account = stripe.Account.retrieve()
        health_info["status"] = "healthy"
        health_info["message"] = "Stripe API connection successful"
        health_info["account_id"] = account.id
        health_info["account_type"] = account.type
        health_info["api_key_type"] = "test" if settings.STRIPE_TEST_API_KEY else "production"
        health_info["api_key_prefix"] = stripe_api_key[:7] + "..." if len(stripe_api_key) > 7 else "***"
    except stripe.error.AuthenticationError as e:
        health_info["status"] = "authentication_failed"
        health_info["message"] = f"Stripe authentication failed: {str(e)}"
        health_info["error_code"] = getattr(e, 'code', None)
    except stripe.error.APIConnectionError as e:
        health_info["status"] = "connection_error"
        health_info["message"] = f"Stripe API connection error: {str(e)}"
    except stripe.error.StripeError as e:
        health_info["status"] = "stripe_error"
        health_info["message"] = f"Stripe error: {str(e)}"
        health_info["error_type"] = e.__class__.__name__
        health_info["error_code"] = getattr(e, 'code', None)
    except Exception as e:
        health_info["status"] = "error"
        health_info["message"] = f"Unexpected error: {str(e)}"
        health_info["error_type"] = e.__class__.__name__
    
    return health_info

