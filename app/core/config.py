from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    PROJECT_NAME: str = "Wonder Scraper"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = ""  # Must be set via environment variable
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days (matches cookie expiry)

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

    model_config = SettingsConfigDict(case_sensitive=True, env_file=".env", extra="ignore")


settings = Settings()
