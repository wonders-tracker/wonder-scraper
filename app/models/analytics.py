"""
Analytics models for tracking page views and user activity.
"""

from datetime import datetime
from typing import Optional
from sqlmodel import SQLModel, Field


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
