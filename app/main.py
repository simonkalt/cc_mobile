"""
FastAPI application entry point
"""
import warnings
import sys

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
from fastapi.responses import JSONResponse
from fastapi import Request, status
import logging

from app.core.config import settings, get_cors_origins
from app.core.logging_config import setup_logging
from app.db.mongodb import connect_to_mongodb, close_mongodb_connection
from app.api.routers import users

# Setup logging
setup_logging()

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for startup and shutdown"""
    # Startup
    connect_to_mongodb()
    
    yield
    
    # Shutdown
    close_mongodb_connection()


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
    logger.warning(f"Some routers could not be imported: {e}")


# Health check endpoints
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "Cover Letter API",
        "version": settings.APP_VERSION,
        "status": "running"
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

