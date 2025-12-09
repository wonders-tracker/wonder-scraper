"""
Watchlist / Price Alert Model

Users can track cards and set price alerts. Used for:
- Price alert emails when target price is hit
- Daily/weekly digest emails based on watched cards
- "Tracking" indicator on card pages
"""

from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime


class Watchlist(SQLModel, table=True):
    """User's watchlist entry for a card."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)

    # Alert settings
    alert_enabled: bool = Field(default=True)
    alert_type: str = Field(default="below")  # 'above', 'below', 'any'
    target_price: Optional[float] = Field(default=None)  # Price threshold
    treatment: Optional[str] = Field(default=None)  # Specific treatment or None for any

    # Notification preferences
    notify_email: bool = Field(default=True)
    notify_push: bool = Field(default=False)  # Future: push notifications

    # Tracking
    last_alerted_at: Optional[datetime] = Field(default=None)  # Prevent spam
    last_alerted_price: Optional[float] = Field(default=None)  # Price when last alerted

    # Metadata
    notes: Optional[str] = Field(default=None)  # User's notes
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        # Unique constraint: one entry per user+card
        table_args = {"sqlite_autoincrement": True}


class EmailPreferences(SQLModel, table=True):
    """User's email notification preferences."""

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", unique=True, index=True)

    # Digest preferences
    daily_digest: bool = Field(default=False)
    weekly_report: bool = Field(default=True)
    portfolio_summary: bool = Field(default=True)

    # Alert preferences
    price_alerts: bool = Field(default=True)
    new_listings: bool = Field(default=False)  # Notify on new listings for watched cards

    # Timing
    digest_hour: int = Field(default=9)  # Hour (UTC) to send daily digest
    digest_day: int = Field(default=0)  # Day of week for weekly (0=Monday)

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
