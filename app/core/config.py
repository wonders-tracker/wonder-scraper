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
                'Generate one with: python -c "import secrets; print(secrets.token_urlsafe(32))"'
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
    CARDS_MAX_LIMIT: int = 500  # Allow fetching all ~355 cards at once

    # ===== Browser Scraper Settings =====
    # Concurrent browser tab operations (4 tabs balances speed vs memory)
    BROWSER_SEMAPHORE_LIMIT: int = 2  # Reduced from 4 to avoid eBay rate limits
    # Maximum browser restart attempts before extended cooldown
    BROWSER_MAX_RESTARTS: int = 3
    # Seconds to wait for browser to start
    BROWSER_STARTUP_TIMEOUT: int = 60
    # Restart browser after this many page fetches to prevent memory leaks
    BROWSER_MAX_PAGES_BEFORE_RESTART: int = 50
    # Extended cooldown (seconds) after hitting max restarts
    BROWSER_EXTENDED_COOLDOWN: int = 10
    # Delay (seconds) between browser restarts
    BROWSER_RESTART_DELAY: int = 2
    # Default retry count for page fetches
    BROWSER_PAGE_RETRIES: int = 3
    # Random delay range (seconds) before navigation for human-like behavior
    BROWSER_PRE_NAV_DELAY_MIN: float = 1.0
    BROWSER_PRE_NAV_DELAY_MAX: float = 3.0
    # Random delay range (seconds) after navigation for content load
    BROWSER_CONTENT_LOAD_DELAY_MIN: float = 2.0
    BROWSER_CONTENT_LOAD_DELAY_MAX: float = 4.0
    # Minimum valid page content length (bytes)
    BROWSER_MIN_CONTENT_LENGTH: int = 100
    # Extended cooldown range (seconds) when eBay blocking detected
    BROWSER_BLOCKING_COOLDOWN_MIN: float = 5.0
    BROWSER_BLOCKING_COOLDOWN_MAX: float = 10.0
    # Timeout (seconds) for Chrome binary search command
    BROWSER_CHROME_SEARCH_TIMEOUT: int = 10
    # Timeout (seconds) for pkill command
    BROWSER_PKILL_TIMEOUT: int = 10

    # ===== Blokpax API Settings =====
    # Maximum retry attempts for Blokpax API calls
    BLOKPAX_MAX_RETRIES: int = 3
    # Base delay (seconds) for exponential backoff
    BLOKPAX_RETRY_BASE_DELAY: float = 1.0
    # Maximum delay (seconds) between retries
    BLOKPAX_RETRY_MAX_DELAY: float = 10.0
    # BPX price cache TTL (seconds)
    BLOKPAX_BPX_CACHE_TTL: int = 300
    # Fallback BPX price (USD) when API fails
    BLOKPAX_BPX_FALLBACK_PRICE: float = 0.002
    # Concurrent requests for storefront scraping
    BLOKPAX_SCRAPER_CONCURRENCY: int = 20
    # Multiplier for effective max pages in small page mode
    BLOKPAX_SMALL_PAGE_MULTIPLIER: int = 20
    # Exit after this many consecutive pages without listings
    BLOKPAX_MAX_EMPTY_PAGES: int = 10
    # Delay (seconds) between paginated requests
    BLOKPAX_PAGE_DELAY: float = 0.05
    # Delay (seconds) between asset detail requests
    BLOKPAX_ASSET_DELAY: float = 0.1
    # Delay (seconds) between activity/sales requests
    BLOKPAX_ACTIVITY_DELAY: float = 0.5
    # Delay (seconds) between storefront scans
    BLOKPAX_STOREFRONT_DELAY: float = 0.3
    # HTTP request timeout (seconds)
    BLOKPAX_REQUEST_TIMEOUT: float = 15.0

    # ===== Scheduler Settings =====
    # Batch size for concurrent card scraping (matches 2x browser semaphore)
    SCHEDULER_CARD_BATCH_SIZE: int = 8
    # Number of cards between DB connection health checks
    SCHEDULER_CONNECTION_CHECK_INTERVAL: int = 40
    # Random sample size when no stale cards need update
    SCHEDULER_RANDOM_SAMPLE_SIZE: int = 10
    # Maximum consecutive DB failures before aborting job
    SCHEDULER_MAX_DB_FAILURES: int = 5
    # Maximum consecutive scrape failures (circuit breaker)
    SCHEDULER_MAX_SCRAPE_FAILURES: int = 3
    # Maximum browser startup attempts
    SCHEDULER_MAX_BROWSER_RETRIES: int = 3
    # Base delay (seconds) for browser startup retries (multiplied by attempt)
    SCHEDULER_BROWSER_RETRY_BASE_DELAY: int = 10
    # Delay (seconds) between card batches
    SCHEDULER_BATCH_DELAY: int = 2
    # DB connection check retry settings
    SCHEDULER_DB_CHECK_MAX_RETRIES: int = 5
    SCHEDULER_DB_CHECK_BASE_DELAY: float = 2.0
    # Threshold for high DB error rate warning (50% of failures)
    SCHEDULER_DB_ERROR_RATE_THRESHOLD: float = 0.5
    # Minimum DB errors to trigger warning
    SCHEDULER_DB_ERROR_MIN_COUNT: int = 5

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


settings = Settings()
