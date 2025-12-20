"""
API Key model for tracking and rate limiting API access.
"""

from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime
import secrets

from app.core.typing import utc_now


class APIKey(SQLModel, table=True):
    """API keys for authenticated API access."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)

    # Key details
    key_hash: str = Field(index=True, unique=True)  # SHA256 hash of key (we don't store raw)
    key_prefix: str = Field(index=True)  # First 8 chars for identification (e.g., "wt_abc123")
    name: str = Field(default="Default")  # User-friendly name

    # Permissions
    is_active: bool = Field(default=True)

    # Rate limiting
    rate_limit_per_minute: int = Field(default=60)  # Requests per minute
    rate_limit_per_day: int = Field(default=10000)  # Requests per day

    # Usage tracking
    requests_today: int = Field(default=0)
    requests_total: int = Field(default=0)
    last_used_at: Optional[datetime] = Field(default=None)
    last_reset_date: Optional[datetime] = Field(default=None)  # For daily reset

    # Metadata
    created_at: datetime = Field(default_factory=utc_now)
    expires_at: Optional[datetime] = Field(default=None)  # Optional expiration

    @staticmethod
    def generate_key() -> str:
        """Generate a new API key with prefix."""
        return f"wt_{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_key(key: str) -> str:
        """Hash an API key for storage."""
        import hashlib

        return hashlib.sha256(key.encode()).hexdigest()

    @staticmethod
    def get_prefix(key: str) -> str:
        """Get the prefix from a key for identification."""
        return key[:11] if key.startswith("wt_") else key[:8]
