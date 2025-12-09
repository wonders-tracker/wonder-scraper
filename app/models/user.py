from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime, timezone

def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    has_api_access: bool = Field(default=False)  # Granted via subscription or admin
    created_at: datetime = Field(default_factory=_utc_now)

    # Profile Fields
    username: Optional[str] = Field(default=None, nullable=True)
    discord_handle: Optional[str] = Field(default=None, nullable=True)
    discord_id: Optional[str] = Field(default=None, nullable=True, sa_column_kwargs={"unique": True})
    bio: Optional[str] = Field(default=None, nullable=True)
    onboarding_completed: bool = Field(default=False)  # Track if user finished onboarding flow
    last_login: Optional[datetime] = Field(default=None, nullable=True)  # Track last successful login

    # Password Reset
    password_reset_token: Optional[str] = Field(default=None, nullable=True, index=True)
    password_reset_expires: Optional[datetime] = Field(default=None, nullable=True)

    # API Access Request
    api_access_requested: bool = Field(default=False)  # User requested API access
    api_access_requested_at: Optional[datetime] = Field(default=None, nullable=True)
    api_access_approved: bool = Field(default=False)  # Admin approved
    api_access_approved_at: Optional[datetime] = Field(default=None, nullable=True)

    # Subscription Fields (Polar)
    subscription_tier: str = Field(default="free")  # "free", "pro", "api"
    subscription_status: Optional[str] = Field(default=None, nullable=True)  # "active", "canceled", "past_due"
    subscription_id: Optional[str] = Field(default=None, nullable=True, index=True)  # Polar subscription ID
    polar_customer_id: Optional[str] = Field(default=None, nullable=True, index=True)  # Polar customer ID
    subscription_current_period_end: Optional[datetime] = Field(default=None, nullable=True)
    subscription_product_type: Optional[str] = Field(default=None, nullable=True)  # "pro" or "api"

    @property
    def is_pro(self) -> bool:
        """Check if user has active Pro subscription."""
        return self.subscription_tier == "pro" and self.subscription_status == "active"

    @property
    def is_api_subscriber(self) -> bool:
        """Check if user has active API-only subscription."""
        return self.subscription_tier == "api" and self.subscription_status == "active"
