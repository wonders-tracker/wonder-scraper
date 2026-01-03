from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Wonder Scraper"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = ""  # Must be set via environment variable
    ALGORITHM: str = "HS256"

    def model_post_init(self, __context) -> None:
        """Validate critical settings after initialization."""
        if not self.SECRET_KEY:
            raise ValueError(
                "SECRET_KEY environment variable is required. "
                "Generate one with: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )

    # Discord OAuth
    DISCORD_CLIENT_ID: str = ""  # Required in production, optional for tests
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/discord/callback"

    # Frontend URL for redirects
    FRONTEND_URL: str = "http://localhost:3000"

    # Cookie security (False for local dev without HTTPS)
    COOKIE_SECURE: bool = True

    # Resend Email
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "WondersTracker <noreply@wonderstracker.com>"
    ADMIN_EMAIL: str = "digitalcody@gmail.com"  # Admin notification email

    # Polar Billing
    POLAR_ACCESS_TOKEN: str = ""
    POLAR_WEBHOOK_SECRET: str = ""
    POLAR_PRO_PRODUCT_ID: str = ""  # Product ID for Pro subscription ($49.95/mo)
    POLAR_API_PRODUCT_ID: str = ""  # Product ID for API Access (pay-per-request)
    POLAR_SUCCESS_URL: str = ""  # Redirect URL after successful checkout
    POLAR_ENVIRONMENT: str = "production"  # "sandbox" or "production"

    # Infrastructure
    THREADPOOL_MAX_WORKERS: int = 40  # Cap AnyIO worker threads to avoid OS limits
    RUN_SCHEDULER: bool = True  # Allow API dyno to turn scheduler off
    MEMORY_LOG_INTERVAL_SECONDS: int = 0  # Disabled by default

    # Anti-scraping
    ANTI_SCRAPING_STATE_TTL_SECONDS: int = 900
    ANTI_SCRAPING_MAX_TRACKED_IPS: int = 5000

    # Database pool
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 5

    # Auth tokens
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15  # Short-lived access token
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7  # Refresh token in httpOnly cookie

    # CSRF Protection
    CSRF_SECRET: str = ""  # Falls back to SECRET_KEY if not set

    # Cards API tuning
    CARDS_CACHE_MAXSIZE: int = 250
    CARDS_CACHE_TTL_SECONDS: int = 300
    CARDS_DEFAULT_LIMIT: int = 200
    CARDS_MAX_LIMIT: int = 300

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


settings = Settings()
