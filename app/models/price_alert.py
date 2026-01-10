"""
PriceAlert Model - User-defined price alerts for cards

When a card's price crosses the user's target threshold,
an email notification is sent.
"""

from datetime import datetime, timezone
from typing import Optional
from sqlmodel import SQLModel, Field
from enum import Enum


def _utc_now() -> datetime:
    """Get current UTC time (timezone-aware)."""
    return datetime.now(timezone.utc)


class AlertType(str, Enum):
    """Type of price alert"""

    BELOW = "below"  # Alert when price drops below target
    ABOVE = "above"  # Alert when price rises above target


class AlertStatus(str, Enum):
    """Status of a price alert"""

    ACTIVE = "active"  # Actively monitoring
    TRIGGERED = "triggered"  # Alert was triggered
    EXPIRED = "expired"  # Alert expired without triggering
    CANCELLED = "cancelled"  # User cancelled the alert


class PriceAlert(SQLModel, table=True):
    """
    Price alert for a specific card.

    When the card's floor price crosses the target_price in the
    specified direction (alert_type), trigger a notification.
    """

    id: Optional[int] = Field(default=None, primary_key=True)

    # User who created the alert
    user_id: int = Field(index=True, foreign_key="user.id")

    # Card being monitored
    card_id: int = Field(index=True, foreign_key="card.id")

    # Alert configuration
    target_price: float = Field(description="Price threshold to trigger alert")
    alert_type: AlertType = Field(default=AlertType.BELOW, description="Trigger when price goes above or below target")

    # Optional: specific treatment to monitor (None = any treatment)
    treatment: Optional[str] = Field(default=None, description="Specific treatment to monitor, or None for all")

    # Status tracking
    status: AlertStatus = Field(default=AlertStatus.ACTIVE, index=True)

    # Price when alert was created (for reference)
    price_at_creation: Optional[float] = Field(default=None, description="Card price when alert was created")

    # Triggered info
    triggered_at: Optional[datetime] = Field(default=None, description="When the alert was triggered")
    triggered_price: Optional[float] = Field(default=None, description="Price that triggered the alert")

    # Timestamps
    created_at: datetime = Field(default_factory=_utc_now)
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiration date")

    # Email notification tracking
    notification_sent: bool = Field(default=False)
    notification_sent_at: Optional[datetime] = Field(default=None)


class PriceAlertCreate(SQLModel):
    """Schema for creating a new price alert"""

    card_id: int
    target_price: float
    alert_type: AlertType = AlertType.BELOW
    treatment: Optional[str] = None
    expires_at: Optional[datetime] = None


class PriceAlertRead(SQLModel):
    """Schema for reading a price alert"""

    id: int
    user_id: int
    card_id: int
    target_price: float
    alert_type: AlertType
    treatment: Optional[str]
    status: AlertStatus
    price_at_creation: Optional[float]
    triggered_at: Optional[datetime]
    triggered_price: Optional[float]
    created_at: datetime
    expires_at: Optional[datetime]
    notification_sent: bool


class PriceAlertUpdate(SQLModel):
    """Schema for updating a price alert"""

    target_price: Optional[float] = None
    alert_type: Optional[AlertType] = None
    treatment: Optional[str] = None
    status: Optional[AlertStatus] = None
    expires_at: Optional[datetime] = None
