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

    # LinkedIn API (job extraction: 3-legged OAuth + jobLibrary FINDER)
    LINKEDIN_CLIENT_ID: Optional[str] = os.getenv("LINKEDIN_CLIENT_ID")
    LINKEDIN_CLIENT_SECRET: Optional[str] = os.getenv("LINKEDIN_CLIENT_SECRET")
    # Callback URL registered in LinkedIn Developer Portal (Auth tab). E.g. https://yourapi.com/api/linkedin/callback
    LINKEDIN_REDIRECT_URI: Optional[str] = os.getenv("LINKEDIN_REDIRECT_URI")
    # Scope for 3-legged OAuth. MUST be the exact string shown in Developer Portal → Your app → Auth tab.
    # Scopes are product-specific (e.g. jobLibrary has its own scope). invalid_scope_error = wrong value here.
    LINKEDIN_SCOPE: Optional[str] = os.getenv("LINKEDIN_SCOPE")
    # Optional: where to send user after successful LinkedIn connect (e.g. myapp://linkedin/connected)
    LINKEDIN_SUCCESS_REDIRECT: Optional[str] = os.getenv("LINKEDIN_SUCCESS_REDIRECT")

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

    # Zoho Mail API Configuration
    ZOHO_CLIENT_ID: Optional[str] = os.getenv("ZOHO_CLIENT_ID")
    ZOHO_CLIENT_SECRET: Optional[str] = os.getenv("ZOHO_CLIENT_SECRET")
    ZOHO_REFRESH_TOKEN: Optional[str] = os.getenv("ZOHO_REFRESH_TOKEN")
    ZOHO_ACCOUNT_ID: Optional[str] = os.getenv("ZOHO_ACCOUNT_ID")
    FROM_EMAIL: Optional[str] = os.getenv("FROM_EMAIL", "no-reply@saimonsoft.com")

    # Legacy SMTP Configuration (deprecated - kept for backward compatibility)
    SMTP_SERVER: Optional[str] = os.getenv("SMTP_SERVER")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    # Stripe Configuration
    STRIPE_TEST_API_KEY: Optional[str] = os.getenv("STRIPE_TEST_API_KEY")
    STRIPE_API_KEY: Optional[str] = os.getenv("STRIPE_API_KEY")  # For production
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_ID_MONTHLY: Optional[str] = os.getenv("STRIPE_PRICE_ID_MONTHLY")  # Fallback only
    STRIPE_PRICE_ID_ANNUAL: Optional[str] = os.getenv("STRIPE_PRICE_ID_ANNUAL")  # Fallback only
    STRIPE_PRODUCT_CAMPAIGN: Optional[str] = os.getenv(
        "STRIPE_PRODUCT_CAMPAIGN"
    )  # Optional filter for products by metadata

    # JWT Configuration
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    )  # 24 hours default
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(
        os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30")
    )  # 30 days default

    # Nutrient.io PDF: when True and NUTRIENT_API_KEY is set, use Nutrient.io for print-preview PDF.
    # Set to "true" to try Nutrient first; falls back to Playwright/WeasyPrint on failure.
    NUTRIENT_API_KEY: Optional[str] = os.getenv("NUTRIENT_API_KEY")
    PRINT_PREVIEW_USE_NUTRIENT: bool = (
        os.getenv("PRINT_PREVIEW_USE_NUTRIENT", "false").lower() == "true"
    )

    # Print Preview PDF: use only WeasyPrint (skip Playwright) when True.
    # Set to "true" if Playwright margins are wrong at page breaks.
    PRINT_PREVIEW_USE_WEASYPRINT_ONLY: bool = (
        os.getenv("PRINT_PREVIEW_USE_WEASYPRINT_ONLY", "false").lower() == "true"
    )

    # Print Preview PDF: when True, do not alter incoming HTML (minimal wrapper only).
    # Use to see what the raw htmlContent produces with no server-side CSS or .print-content.
    PRINT_PREVIEW_RAW_HTML: bool = os.getenv("PRINT_PREVIEW_RAW_HTML", "false").lower() == "true"

    # File paths
    SYSTEM_PROMPT_PATH: Path = Path(__file__).parent.parent.parent / "system_prompt.json"
    # Set USE_SYSTEM_PROMPT_FILE=true to load prompt from system_prompt.json (default); when false, use built-in default
    USE_SYSTEM_PROMPT_FILE: bool = (
        os.getenv("USE_SYSTEM_PROMPT_FILE", "true").lower() == "true"
    )
    PERSONALITY_PROFILES_PATH: Path = (
        Path(__file__).parent.parent.parent / "personality_profiles.json"
    )
    TEMPLATES_DIR: Path = Path(__file__).parent.parent.parent / "templates"
    # Include template structure in LLM prompt for consistent line breaks. Set to "false" to revert.
    USE_TEMPLATE_IN_PROMPT: bool = (
        os.getenv("USE_TEMPLATE_IN_PROMPT", "true").lower() == "true"
    )


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
