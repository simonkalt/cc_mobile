"""
Application configuration and settings
"""
import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

# Project root (repo root): load .env then .secrets so local overrides stay out of git
_ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(_ROOT / ".env")
load_dotenv(_ROOT / ".secrets", override=True)


class Settings:
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Cover Letter API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

    # Google Analytics (GA4) — injected into website/index.html when serving /
    GOOGLE_ANALYTICS_TAG: Optional[str] = os.getenv("GOOGLE_ANALYTICS_TAG")

    # Marketing site (/) — app store badge links, injected into website/index.html
    PLAY_STORE_URL: Optional[str] = os.getenv("PLAY_STORE_URL")
    IOS_APP_STORE_URL: Optional[str] = os.getenv("IOS_APP_STORE_URL")

    # Third-party / server-to-server integration (set in .secrets, not committed)
    SERVICE_AUTH_KEY: Optional[str] = os.getenv("SERVICE_AUTH_KEY")
    INTEGRATION_AUTH_ENDPOINTS_FILE: str = os.getenv(
        "INTEGRATION_AUTH_ENDPOINTS_FILE",
        str(_ROOT / "integration_auth_endpoints.json"),
    )
    
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

    # LinkedIn API (3-legged OAuth + jobLibrary integration)
    LINKEDIN_CLIENT_ID: Optional[str] = os.getenv("LINKEDIN_CLIENT_ID")
    LINKEDIN_CLIENT_SECRET: Optional[str] = os.getenv("LINKEDIN_CLIENT_SECRET")
    LINKEDIN_REDIRECT_URI: Optional[str] = os.getenv("LINKEDIN_REDIRECT_URI")
    LINKEDIN_SCOPE: Optional[str] = os.getenv("LINKEDIN_SCOPE")
    LINKEDIN_SUCCESS_REDIRECT: Optional[str] = os.getenv("LINKEDIN_SUCCESS_REDIRECT")
    
    # Telnyx SMS Configuration
    TELNYX_API_KEY: Optional[str] = os.getenv("TELNYX_API_KEY")
    TELNYX_PHONE_NUMBER: Optional[str] = os.getenv("TELNYX_PHONE_NUMBER")

    # Redis Configuration
    REDIS_HOST: Optional[str] = os.getenv("REDIS_HOST")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_USERNAME: Optional[str] = os.getenv("REDIS_USERNAME")
    REDIS_PASSWORD: Optional[str] = os.getenv("REDIS_PASSWORD")
    REDIS_DB: int = int(os.getenv("REDIS_DB", "0"))
    REDIS_SSL: bool = os.getenv("REDIS_SSL", "false").lower() == "true"
    REDIS_API_KEY: Optional[str] = os.getenv("REDIS_API_KEY")

    # Zoho Mail API + legacy SMTP
    ZOHO_CLIENT_ID: Optional[str] = os.getenv("ZOHO_CLIENT_ID")
    ZOHO_CLIENT_SECRET: Optional[str] = os.getenv("ZOHO_CLIENT_SECRET")
    ZOHO_REFRESH_TOKEN: Optional[str] = os.getenv("ZOHO_REFRESH_TOKEN")
    ZOHO_ACCOUNT_ID: Optional[str] = os.getenv("ZOHO_ACCOUNT_ID")
    FROM_EMAIL: Optional[str] = os.getenv("FROM_EMAIL", "no-reply@saimonsoft.com")

    SMTP_SERVER: Optional[str] = os.getenv("SMTP_SERVER")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME: Optional[str] = os.getenv("SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = os.getenv("SMTP_PASSWORD")
    SMTP_USE_TLS: bool = os.getenv("SMTP_USE_TLS", "true").lower() == "true"
    SMTP_USE_SSL: bool = os.getenv("SMTP_USE_SSL", "false").lower() == "true"

    # Stripe Configuration (supports both legacy and newer env names)
    STRIPE_LIVE: bool = os.getenv("STRIPE_LIVE", "false").lower() == "true"
    STRIPE_TEST_SECRET_KEY: Optional[str] = os.getenv("STRIPE_TEST_SECRET_KEY")
    STRIPE_LIVE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_LIVE_SECRET_KEY")
    # Backward-compatible aliases used by older subscription modules
    STRIPE_TEST_API_KEY: Optional[str] = os.getenv("STRIPE_TEST_API_KEY") or STRIPE_TEST_SECRET_KEY
    STRIPE_API_KEY: Optional[str] = os.getenv("STRIPE_API_KEY")
    STRIPE_SECRET_KEY: Optional[str] = os.getenv("STRIPE_SECRET_KEY")
    STRIPE_TEST_PUBLIC_KEY: Optional[str] = os.getenv("STRIPE_TEST_PUBLIC_KEY")
    STRIPE_LIVE_PUBLIC_KEY: Optional[str] = os.getenv("STRIPE_LIVE_PUBLIC_KEY")
    STRIPE_WEBHOOK_SECRET: Optional[str] = os.getenv("STRIPE_WEBHOOK_SECRET")
    STRIPE_PRICE_ID_MONTHLY: Optional[str] = os.getenv("STRIPE_PRICE_ID_MONTHLY")
    STRIPE_PRICE_ID_ANNUAL: Optional[str] = os.getenv("STRIPE_PRICE_ID_ANNUAL")
    STRIPE_PRODUCT_CAMPAIGN: Optional[str] = os.getenv("STRIPE_PRODUCT_CAMPAIGN")

    # JWT Configuration
    JWT_ENABLED: bool = os.getenv("JWT_ENABLED", "true").lower() == "true"
    JWT_SECRET: str = os.getenv(
        "JWT_SECRET",
        os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production"),
    )
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    JWT_ISSUER: Optional[str] = os.getenv("JWT_ISSUER")
    JWT_AUDIENCE: Optional[str] = os.getenv("JWT_AUDIENCE")
    JWT_VALIDATE_ISSUER: bool = os.getenv("JWT_VALIDATE_ISSUER", "false").lower() == "true"
    JWT_VALIDATE_AUDIENCE: bool = os.getenv("JWT_VALIDATE_AUDIENCE", "false").lower() == "true"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))

    # Print-preview/PDF behavior flags
    NUTRIENT_API_KEY: Optional[str] = os.getenv("NUTRIENT_API_KEY")
    PRINT_PREVIEW_USE_NUTRIENT: bool = (
        os.getenv("PRINT_PREVIEW_USE_NUTRIENT", "false").lower() == "true"
    )
    PRINT_PREVIEW_USE_WEASYPRINT_ONLY: bool = (
        os.getenv("PRINT_PREVIEW_USE_WEASYPRINT_ONLY", "false").lower() == "true"
    )
    PRINT_PREVIEW_RAW_HTML: bool = (
        os.getenv("PRINT_PREVIEW_RAW_HTML", "false").lower() == "true"
    )
    
    # File paths
    SYSTEM_PROMPT_PATH: Path = Path(__file__).parent.parent.parent / "system_prompt.json"
    USE_SYSTEM_PROMPT_FILE: bool = (
        os.getenv("USE_SYSTEM_PROMPT_FILE", "true").lower() == "true"
    )
    PERSONALITY_PROFILES_PATH: Path = Path(__file__).parent.parent.parent / "personality_profiles.json"
    DEFAULT_PERSONALITY_PROFILES_PATH: Path = Path(__file__).parent.parent.parent / "default_personality_profiles.json"
    TEMPLATES_DIR: Path = Path(__file__).parent.parent.parent / "templates"

    # Cover-letter generation feature flags (Word-integration compatibility)
    USE_TEMPLATE_IN_PROMPT: bool = os.getenv("USE_TEMPLATE_IN_PROMPT", "false").lower() == "true"
    USE_DOCX_COMPONENTS: bool = os.getenv("USE_DOCX_COMPONENTS", "false").lower() == "true"
    LLM_MAX_OUTPUT_TOKENS: int = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "8124"))
    ENFORCE_STRONG_PASSWORDS: bool = os.getenv("ENFORCE_STRONG_PASSWORDS", "false").lower() == "true"
    # ASCII timing chart in logs for cover-letter routes. Default off.
    # Only LOG_TIMING is honored (ENABLE_GENERATION_TIMING_CHART is ignored to avoid stale env turning logs on).
    _LOG_TIMING_ENV = (os.getenv("LOG_TIMING") or "").strip().lower()
    LOG_TIMING: bool = _LOG_TIMING_ENV in ("1", "true", "yes")

    # When true: skip Redis/local caches for cover-letter generation (result, resume text, user profile)
    # and skip on-disk PDF cache used by generate-pdf / print-preview (avoids stale formatting while testing).
    DISABLE_COVER_LETTER_CACHING: bool = (
        os.getenv("DISABLE_COVER_LETTER_CACHING", "false").lower() == "true"
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

