import os
from pydantic import ConfigDict
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Wonder Scraper"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # Discord OAuth
    DISCORD_CLIENT_ID: str
    DISCORD_CLIENT_SECRET: str = ""
    DISCORD_REDIRECT_URI: str = "http://localhost:8000/api/v1/auth/discord/callback"

    # Frontend URL for redirects
    FRONTEND_URL: str = "http://localhost:3000"

    # Resend Email
    RESEND_API_KEY: str = ""
    FROM_EMAIL: str = "WondersTracker <noreply@wonderstrader.com>"
    ADMIN_EMAIL: str = ""  # Admin notification email (falls back to FROM_EMAIL)
    
    model_config = ConfigDict(case_sensitive=True, env_file=".env", extra="ignore")

settings = Settings()

