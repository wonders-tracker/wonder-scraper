"""
Circuit breaker state persistence model.

Stores circuit breaker states to survive deploys/restarts.
This prevents immediately retrying a failing service after restart.
"""

from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

from app.core.typing import utc_now


class CircuitBreakerState(SQLModel, table=True):
    """Persisted circuit breaker state."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)  # Circuit name (e.g., "ebay", "blokpax")
    state: str = Field(default="closed")  # "closed", "open", "half_open"
    failure_count: int = Field(default=0)
    last_failure_at: Optional[datetime] = Field(default=None)
    updated_at: datetime = Field(default_factory=utc_now)
