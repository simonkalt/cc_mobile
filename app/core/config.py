"""
Application configuration and settings
"""
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Cover Letter API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))
    
    # CORS - defaults
    _DEFAULT_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]
    
    # MongoDB
    MONGODB_URI: Optional[str] = os.getenv("MONGODB_URI")
    MONGODB_DB_NAME: str = os.getenv("MONGODB_DB_NAME", "CoverLetter")
    MONGODB_COLLECTION_NAME: str = os.getenv("MONGODB_COLLECTION_NAME", "users")
    
    # API Keys
    OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = os.getenv("ANTHROPIC_API_KEY")
    GOOGLE_API_KEY: Optional[str] = os.getenv("GOOGLE_API_KEY")
    GEMINI_API_KEY: Optional[str] = os.getenv("GEMINI_API_KEY")
    XAI_API_KEY: Optional[str] = os.getenv("XAI_API_KEY")
    HF_TOKEN: Optional[str] = os.getenv("HF_TOKEN")
    
    # AWS S3
    AWS_ACCESS_KEY_ID: Optional[str] = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    AWS_S3_BUCKET: Optional[str] = os.getenv("AWS_S3_BUCKET")
    
    # OCI Configuration
    OCI_CONFIG_FILE: Optional[str] = os.getenv("OCI_CONFIG_FILE")
    OCI_REGION: Optional[str] = os.getenv("OCI_REGION")
    OCI_COMPARTMENT_ID: Optional[str] = os.getenv("OCI_COMPARTMENT_ID")
    OCI_CONFIG_PROFILE: Optional[str] = os.getenv("OCI_CONFIG_PROFILE")
    OCI_MODEL_ID: Optional[str] = os.getenv("OCI_MODEL_ID")
    
    # LLM Configuration
    LLM_CONFIG_PATH: Path = Path(__file__).parent.parent.parent / "llms-config.json"
    
    # Google Places API
    GOOGLE_PLACES_API_KEY: Optional[str] = os.getenv("GOOGLE_PLACES_API_KEY")
    
    # Twilio Configuration
    TWILIO_ACCOUNT_SID: Optional[str] = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = os.getenv("TWILIO_PHONE_NUMBER")
    
    # Redis Configuration
    REDIS_HOST: Optional[str] = os.getenv("REDIS_HOST")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_USERNAME: Optional[str] = os.getenv("REDIS_USERNAME")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_SSL: bool = os.getenv("REDIS_SSL", "false").lower() == "true"
    REDIS_API_KEY: Optional[str] = os.getenv("REDIS_API_KEY")
    
    # SMTP Configuration
    SMTP_SERVER: Optional[str] = os.getenv("SMTP_SERVER")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"
    FROM_EMAIL: Optional[str] = os.getenv("FROM_EMAIL")
    
    # Stripe Configuration
    STRIPE_TEST_API_KEY: Optional[str] = os.getenv("STRIPE_TEST_API_KEY")
    STRIPE_API_KEY: Optional[str] = os.getenv("STRIPE_API_KEY")  # For production
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_ID_MONTHLY: Optional[str] = os.getenv("STRIPE_PRICE_ID_MONTHLY")
    STRIPE_PRICE_ID_ANNUAL: Optional[str] = os.getenv("STRIPE_PRICE_ID_ANNUAL")
    
    # File paths
    SYSTEM_PROMPT_PATH: Path = Path(__file__).parent.parent.parent / "system_prompt.json"
    PERSONALITY_PROFILES_PATH: Path = Path(__file__).parent.parent.parent / "personality_profiles.json"


# Global settings instance
settings = Settings()


def get_cors_origins() -> List[str]:
    """Get CORS origins from environment or defaults"""
    env_origins = os.getenv("CORS_ORIGINS", "")
    if env_origins:
        origins = [origin.strip() for origin in env_origins.split(",") if origin.strip()]
        # Combine with defaults and remove duplicates
        all_origins = list(set(settings._DEFAULT_CORS_ORIGINS + origins))
        return all_origins
    return settings._DEFAULT_CORS_ORIGINS

