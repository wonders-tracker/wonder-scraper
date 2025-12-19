"""
Analytics models for tracking page views, events, and user activity.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON


class PageView(SQLModel, table=True):
    """Track page views for analytics."""

    id: Optional[int] = Field(default=None, primary_key=True)
    path: str = Field(index=True)
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    session_id: Optional[str] = Field(default=None, index=True)
    referrer: Optional[str] = Field(default=None)
    user_agent: Optional[str] = Field(default=None)
    ip_hash: Optional[str] = Field(default=None)  # Hashed for privacy
    country: Optional[str] = Field(default=None)
    device_type: Optional[str] = Field(default=None)  # desktop, mobile, tablet
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)


class AnalyticsEvent(SQLModel, table=True):
    """Track custom analytics events."""

    __tablename__ = "analytics_event"

    id: Optional[int] = Field(default=None, primary_key=True)
    event_name: str = Field(index=True)  # e.g., "sign_up", "card_view", "external_link_click"
    user_id: Optional[int] = Field(default=None, foreign_key="user.id", index=True)
    session_id: Optional[str] = Field(default=None, index=True)
    ip_hash: Optional[str] = Field(default=None)

    # Event properties stored as JSON
    properties: Optional[dict] = Field(default=None, sa_column=Column(JSON))

    # Common properties extracted for easy querying
    card_id: Optional[int] = Field(default=None, index=True)
    card_name: Optional[str] = Field(default=None)
    platform: Optional[str] = Field(default=None)  # ebay, blokpax, etc.

    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
