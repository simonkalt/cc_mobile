"""
FastAPI application entry point
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi import Request, status
import logging
import sys

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
    logger.info("Application startup")
    
    # Connect to MongoDB Atlas
    logger.info("Attempting to connect to MongoDB Atlas...")
    if connect_to_mongodb():
        logger.info("MongoDB Atlas connection established")
    else:
        logger.warning("MongoDB Atlas connection failed. Continuing without database.")
    
    yield
    
    # Shutdown
    logger.info("Application shutdown")
    close_mongodb_connection()
    logger.info("MongoDB Atlas connection closed")


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
logger.info(f"CORS configured for origins: {cors_origins}")

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
app.include_router(users.router)

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
    )
    app.include_router(job_url.router)
    app.include_router(llm_config.router)
    app.include_router(personality.router)
    app.include_router(config.router)
    app.include_router(cover_letter.router)
    app.include_router(files.router)
    app.include_router(cover_letters.router)
    app.include_router(pdf.router)
    logger.info("All API routers registered successfully")
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
            if db:
                health_info["database"] = db.name
                collections = db.list_collection_names()
                health_info["collections"] = collections
                
                # Try to access users collection
                collection = get_collection(USERS_COLLECTION)
                if collection:
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
    
    return health_info

