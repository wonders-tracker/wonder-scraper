"""
Model for tracking processed webhook events to ensure idempotency.
"""
from typing import Optional
from datetime import datetime, timezone
from sqlmodel import Field, SQLModel


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class WebhookEvent(SQLModel, table=True):
    """
    Tracks processed webhook events to prevent duplicate processing.

    Polar (and most webhook providers) may retry failed webhooks,
    so we need to ensure each event is only processed once.
    """
    __tablename__ = "webhook_event"

    id: Optional[int] = Field(default=None, primary_key=True)

    # Event identification
    event_id: str = Field(unique=True, index=True)  # Polar event ID or generated ID
    event_type: str = Field(index=True)  # e.g., "subscription.active", "checkout.updated"
    source: str = Field(default="polar")  # "polar", etc.

    # Processing status
    processed_at: datetime = Field(default_factory=_utc_now)
    status: str = Field(default="processed")  # "processed", "failed", "skipped"

    # Optional: store relevant data for debugging
    user_id: Optional[int] = Field(default=None, nullable=True, index=True)
    subscription_id: Optional[str] = Field(default=None, nullable=True)
    error_message: Optional[str] = Field(default=None, nullable=True)
