"""
Application configuration and settings
"""
import os
from pathlib import Path
from typing import List, Optional
from app.core.env_loader import PROJECT_ROOT, load_project_env

# Project root: .env then secrets (.secrets locally or /etc/secrets/.secrets on Render)
_ROOT = PROJECT_ROOT
load_project_env(_ROOT)


def _strip_env_value(raw: str) -> str:
    """Strip whitespace and trailing inline comments.

    Docker ``--env-file`` passes values verbatim (unlike python-dotenv), so
    ``KEY=value  # note`` can reach os.getenv with the comment included.
    """
    s = (raw or "").strip()
    if not s:
        return s
    if " #" in s:
        s = s.split(" #", 1)[0].strip()
    return s


def _env_int(name: str, default: str) -> int:
    return int(_strip_env_value(os.getenv(name) or default))


def _env_int_optional(name: str) -> Optional[int]:
    raw = _strip_env_value(os.getenv(name) or "")
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def _env_first(*names: str) -> Optional[str]:
    """Return the first non-empty env value among *names*."""
    for name in names:
        raw = _strip_env_value(os.getenv(name) or "")
        if raw:
            return raw
    return None

def _default_docx_service_base_url(debug_enabled: bool) -> str:
    deploy_env = (
        os.getenv("DEPLOYMENT_ENV")
        or os.getenv("ENVIRONMENT")
        or os.getenv("APP_ENV")
        or os.getenv("EXPO_PUBLIC_BUILD_TYPE")
        or ("development" if debug_enabled else "production")
    ).strip().lower()

    if deploy_env in {"production", "prod", "live"}:
        return "https://api.saimonsoft.com"
    if deploy_env in {"uat", "staging", "stage", "preview"}:
        return "https://syncfusion-uat.onrender.com"
    return "http://192.168.0.8:5000"


class Settings:
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "Cover Letter API"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"
    # When true, store verification codes even if outbound email fails (UAT / local testing).
    VERIFICATION_EMAIL_FAIL_OPEN: bool = (
        os.getenv("VERIFICATION_EMAIL_FAIL_OPEN", "False").lower() == "true"
    )

    # Google Analytics (GA4) — injected into website/index.html when serving /
    GOOGLE_ANALYTICS_TAG: Optional[str] = os.getenv("GOOGLE_ANALYTICS_TAG")

    # Marketing site (/) — app store badge links, injected into website/index.html
    PLAY_STORE_URL: Optional[str] = os.getenv("PLAY_STORE_URL")
    IOS_APP_STORE_URL: Optional[str] = os.getenv("IOS_APP_STORE_URL")

    # Public legal pages (HTML on marketing site). Used by client-settings for registration links, etc.
    PUBLIC_PRIVACY_POLICY_URL: str = (
        (os.getenv("PUBLIC_PRIVACY_POLICY_URL") or "").strip()
        or "https://www.saimonsoft.com/website/docs/privacy-policy.html"
    )
    PUBLIC_TERMS_OF_SERVICE_URL: str = (
        (os.getenv("PUBLIC_TERMS_OF_SERVICE_URL") or "").strip()
        or "https://www.saimonsoft.com/website/docs/terms-of-service.html"
    )
    DOCX_SERVICE_BASE_URL: str = (
        (os.getenv("DOCX_SERVICE_BASE_URL") or "").strip()
        or _default_docx_service_base_url(DEBUG)
    )

    # Registration: Data Use & Sharing Notice copy (editable JSON in repo root by default)
    REGISTRATION_DATA_USE_NOTICE_PATH: Path = Path(
        os.getenv(
            "REGISTRATION_DATA_USE_NOTICE_PATH",
            str(_ROOT / "registration_data_use_notice.json"),
        )
    )

    # Third-party / server-to-server integration (set in .secrets, not committed)
    SERVICE_AUTH_KEY: Optional[str] = os.getenv("SERVICE_AUTH_KEY")
    INTEGRATION_AUTH_ENDPOINTS_FILE: str = os.getenv(
        "INTEGRATION_AUTH_ENDPOINTS_FILE",
        str(_ROOT / "integration_auth_endpoints.json"),
    )
    
    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = _env_int("PORT", "8000")
    
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

    # Mobile app version / update policy doc (see documentation/API_APP_UPDATE_AND_VERSION.md).
    # Default DB: same as the active connection (URI/MONGODB_DB_NAME). Override if policy lives elsewhere.
    APP_UPDATE_POLICY_DB_NAME: Optional[str] = (
        (os.getenv("APP_UPDATE_POLICY_DB_NAME") or "").strip() or None
    )
    APP_UPDATE_POLICY_COLLECTION: str = (
        (os.getenv("APP_UPDATE_POLICY_COLLECTION") or "").strip() or "version"
    )
    APP_UPDATE_POLICY_DOC_ID: Optional[str] = (
        (os.getenv("APP_UPDATE_POLICY_DOC_ID") or "").strip() or None
    )
    APP_UPDATE_POLICY_DOC_FILTER_JSON: Optional[str] = (
        (os.getenv("APP_UPDATE_POLICY_DOC_FILTER_JSON") or "").strip() or None
    )
    APP_UPDATE_POLICY_CACHE_TTL_SECONDS: int = int(
        os.getenv("APP_UPDATE_POLICY_CACHE_TTL_SECONDS", "60")
    )
    
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
    
    # LLM Configuration
    LLM_CONFIG_PATH: Path = Path(__file__).parent.parent.parent / "llms-config.json"
    # Canonical model list + default for new users (see llm-models-registry.json; override via LLM_MODELS_REGISTRY_PATH)
    LLM_MODELS_REGISTRY_PATH: Path = Path(__file__).parent.parent.parent / "llm-models-registry.json"
    
    # Google Places API
    GOOGLE_PLACES_API_KEY: Optional[str] = os.getenv("GOOGLE_PLACES_API_KEY")

    # Google OAuth (mobile/web login — Authorization Code + PKCE)
    GOOGLE_CLIENT_ID: Optional[str] = os.getenv("GOOGLE_CLIENT_ID")
    GOOGLE_CLIENT_SECRET: Optional[str] = os.getenv("GOOGLE_CLIENT_SECRET")
    # Deep link after HTTPS OAuth callback (default ccmobile://)
    OAUTH_NATIVE_APP_SCHEME: str = _strip_env_value(
        os.getenv("OAUTH_NATIVE_APP_SCHEME") or "ccmobile"
    )
    # False = 200 on HTTPS callback (Expo dev client / openAuthSessionAsync on https).
    # True = 302 to {OAUTH_NATIVE_APP_SCHEME}://oauth/... (release / TestFlight builds).
    OAUTH_CALLBACK_DEEP_LINK: bool = os.getenv(
        "OAUTH_CALLBACK_DEEP_LINK", "true"
    ).lower() in ("1", "true", "yes")

    # LinkedIn API (3-legged OAuth + jobLibrary integration; OIDC login reuses these)
    # Falls back to EXPO_PUBLIC_* when LINKEDIN_* are unset (shared .env with mobile app).
    LINKEDIN_CLIENT_ID: Optional[str] = _env_first(
        "LINKEDIN_CLIENT_ID",
        "EXPO_PUBLIC_LINKEDIN_CLIENT_ID",
    )
    LINKEDIN_CLIENT_SECRET: Optional[str] = _env_first(
        "LINKEDIN_CLIENT_SECRET",
        "EXPO_PUBLIC_LINKEDIN_CLIENT_SECRET",
    )
    LINKEDIN_REDIRECT_URI: Optional[str] = os.getenv("LINKEDIN_REDIRECT_URI")
    LINKEDIN_SCOPE: Optional[str] = os.getenv("LINKEDIN_SCOPE")
    LINKEDIN_SUCCESS_REDIRECT: Optional[str] = os.getenv("LINKEDIN_SUCCESS_REDIRECT")

    # Sign in with Apple (native iOS login). The identity token's `aud` is the app
    # bundle id; defaults to the production bundle id and falls back to APP_STORE_BUNDLE_ID.
    APPLE_OAUTH_CLIENT_ID: Optional[str] = (
        _env_first("APPLE_OAUTH_CLIENT_ID", "APP_STORE_BUNDLE_ID")
        or "com.saimonsoft.customcoverlettermobile.app"
    )
    
    # Telnyx SMS Configuration
    TELNYX_API_KEY: Optional[str] = os.getenv("TELNYX_API_KEY")
    TELNYX_PHONE_NUMBER: Optional[str] = os.getenv("TELNYX_PHONE_NUMBER")

    # Redis Configuration
    REDIS_HOST: Optional[str] = _strip_env_value(os.getenv("REDIS_HOST") or "") or None
    REDIS_PORT: int = _env_int("REDIS_PORT", "6379")
    REDIS_USERNAME: Optional[str] = _strip_env_value(os.getenv("REDIS_USERNAME") or "") or None
    REDIS_PASSWORD: Optional[str] = _strip_env_value(os.getenv("REDIS_PASSWORD") or "") or None
    REDIS_DB: int = _env_int("REDIS_DB", "0")
    REDIS_SSL: bool = os.getenv("REDIS_SSL", "false").lower() == "true"
    REDIS_API_KEY: Optional[str] = os.getenv("REDIS_API_KEY")

    # Zoho Mail API (legacy Render names ZOHO_SIMON_* are fallbacks only)
    ZOHO_CLIENT_ID: Optional[str] = _env_first("ZOHO_CLIENT_ID", "ZOHO_SIMON_CLIENT_ID")
    ZOHO_CLIENT_SECRET: Optional[str] = _env_first(
        "ZOHO_CLIENT_SECRET", "ZOHO_SIMON_CLIENT_SECRET"
    )
    ZOHO_REFRESH_TOKEN: Optional[str] = _env_first(
        "ZOHO_REFRESH_TOKEN", "ZOHO_SIMON_REFRESH_TOKEN"
    )
    ZOHO_ACCOUNT_ID: Optional[str] = _env_first("ZOHO_ACCOUNT_ID", "ZOHO_SIMON_ACCOUNT_ID")
    # EU: https://accounts.zoho.eu  IN: https://accounts.zoho.in  (default US)
    ZOHO_ACCOUNTS_BASE: str = (
        _env_first("ZOHO_ACCOUNTS_BASE", "ZOHO_ACCOUNTS_URL")
        or "https://accounts.zoho.com"
    )
    FROM_EMAIL: Optional[str] = os.getenv("FROM_EMAIL", "no-reply@saimonsoft.com")

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

    # App Store Server API (StoreKit 2 / in-app purchase verification)
    # Root certs: download Apple Root CA – G3 (and intermediates per Apple docs) into a directory,
    # then set APP_STORE_ROOT_CERTIFICATES_DIR to that path.
    APP_STORE_ISSUER_ID: Optional[str] = (os.getenv("APP_STORE_ISSUER_ID") or "").strip() or None
    APP_STORE_KEY_ID: Optional[str] = (os.getenv("APP_STORE_KEY_ID") or "").strip() or None
    APP_STORE_PRIVATE_KEY: Optional[str] = os.getenv("APP_STORE_PRIVATE_KEY")  # PEM, optional if PATH set
    APP_STORE_PRIVATE_KEY_PATH: Optional[str] = (
        (os.getenv("APP_STORE_PRIVATE_KEY_PATH") or "").strip() or None
    )
    APP_STORE_BUNDLE_ID: Optional[str] = (os.getenv("APP_STORE_BUNDLE_ID") or "").strip() or None
    # Numeric App Store Connect app id; required for Production JWS verification (SignedDataVerifier).
    APP_APPLE_ID: Optional[int] = _env_int_optional("APP_APPLE_ID")
    APP_STORE_USE_SANDBOX: bool = os.getenv("APP_STORE_USE_SANDBOX", "true").lower() == "true"
    # If the transaction is not found in the primary environment, try the other (sandbox ↔ production).
    APP_STORE_RETRY_ALTERNATE_ENVIRONMENT: bool = (
        os.getenv("APP_STORE_RETRY_ALTERNATE_ENVIRONMENT", "true").lower() == "true"
    )
    APP_STORE_ROOT_CERTIFICATES_DIR: Optional[str] = (
        (os.getenv("APP_STORE_ROOT_CERTIFICATES_DIR") or "").strip() or None
    )
    # JSON object: { "com.myapp.sub.premium": "premium" }; values become subscriptionPlan in DB.
    APP_STORE_PRODUCT_PLAN_MAP_JSON: Optional[str] = os.getenv("APP_STORE_PRODUCT_PLAN_MAP_JSON")
    # JSON object: { "price_1Abc...": "monthly" }; maps Stripe price IDs to logical plan keys.
    STRIPE_PRICE_PLAN_MAP_JSON: Optional[str] = os.getenv("STRIPE_PRICE_PLAN_MAP_JSON")
    # Comma-separated product ids; if set, rejects verify for unknown products.
    APP_STORE_ALLOWED_PRODUCT_IDS: Optional[str] = os.getenv("APP_STORE_ALLOWED_PRODUCT_IDS")
    # Dedup collection for App Store Server Notifications V2 (same DB as MONGODB_URI).
    MONGODB_APPLE_NOTIFICATIONS_COLLECTION: str = os.getenv(
        "MONGODB_APPLE_NOTIFICATIONS_COLLECTION", "apple_store_notifications"
    )
    # Remote config: iOS/Android subscription product ids, planKey, rank (see BILLING_MONGODB_SCHEMA.md).
    MONGODB_SUBSCRIPTION_PRODUCT_CATALOG_COLLECTION: str = os.getenv(
        "MONGODB_SUBSCRIPTION_PRODUCT_CATALOG_COLLECTION",
        "subscription_product_catalog",
    )

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
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = _env_int("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "1440")
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = _env_int("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30")

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
    
    # Shipped mobile app semver (version.json); see documentation/API_APP_UPDATE_AND_VERSION.md
    VERSION_JSON_PATH: Path = Path(
        os.getenv("VERSION_JSON_PATH", str(_ROOT / "version.json"))
    )
    APP_UPDATE_MIN_REQUIRED_VERSION: Optional[str] = os.getenv("APP_UPDATE_MIN_REQUIRED_VERSION")
    APP_UPDATE_LATEST_VERSION: Optional[str] = os.getenv("APP_UPDATE_LATEST_VERSION")
    APP_UPDATE_MESSAGE: Optional[str] = os.getenv("APP_UPDATE_MESSAGE")
    APP_UPDATE_STORE_ANDROID_URL: Optional[str] = os.getenv("APP_UPDATE_STORE_ANDROID_URL")
    APP_UPDATE_STORE_IOS_URL: Optional[str] = os.getenv("APP_UPDATE_STORE_IOS_URL")

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
    LLM_MAX_OUTPUT_TOKENS: int = _env_int("LLM_MAX_OUTPUT_TOKENS", "8124")
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

