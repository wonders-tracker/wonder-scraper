"""
SQLModel models for observability tables.

Tables:
- scraper_job_log: Detailed log of each scraper job execution
- metrics_snapshot: Periodic snapshots of in-memory metrics
- request_trace: Sample of slow/failed requests for debugging

These tables enable:
- Historical metrics analysis (survive restarts)
- Performance trending
- Error pattern detection
- Debugging production issues
"""

from datetime import datetime, timezone
from typing import Optional, Any
from sqlmodel import Field, SQLModel, Column
from sqlalchemy import JSON

__all__ = [
    "ScraperJobLog",
    "MetricsSnapshot",
    "RequestTrace",
]


class ScraperJobLog(SQLModel, table=True):
    """
    Log entry for a scraper job execution.

    Tracks start/completion, success/failure counts, and errors
    for historical analysis and alerting.

    Example:
        job = ScraperJobLog(
            job_name="ebay_market_update",
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        # ... job runs ...
        job.completed_at = datetime.now(timezone.utc)
        job.status = "completed"
        job.successful = 350
    """

    __tablename__ = "scraper_job_log"

    id: Optional[int] = Field(default=None, primary_key=True)
    job_name: str = Field(max_length=100, index=True)
    started_at: datetime = Field(index=True)
    completed_at: Optional[datetime] = None
    status: str = Field(
        max_length=20,
        index=True,
        description="pending, running, completed, failed",
    )
    cards_processed: int = Field(default=0)
    successful: int = Field(default=0)
    failed: int = Field(default=0)
    db_errors: int = Field(default=0)
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = Field(default=None, max_length=1000)
    error_type: Optional[str] = Field(default=None, max_length=100)
    job_metadata: Optional[dict[str, Any]] = Field(
        default=None,
        sa_column=Column(JSON),
        description="Additional context (circuit state, browser tabs, etc.)",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class MetricsSnapshot(SQLModel, table=True):
    """
    Periodic snapshot of in-memory metrics.

    Captured every 5 minutes by scheduler to enable:
    - Historical trending
    - Post-restart analysis
    - Dashboard queries

    Example:
        snapshot = MetricsSnapshot(
            metric_type="scraper",
            metric_name="ebay_market_update",
            metric_value={"success_rate": 98.5, "avg_duration": 22.5},
        )
    """

    __tablename__ = "metrics_snapshot"

    id: Optional[int] = Field(default=None, primary_key=True)
    snapshot_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
    )
    metric_type: str = Field(
        max_length=50,
        index=True,
        description="scraper, performance, circuit, queue",
    )
    metric_name: str = Field(max_length=100)
    metric_value: dict[str, Any] = Field(sa_column=Column(JSON))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        nullable=False,
    )


class RequestTrace(SQLModel, table=True):
    """
    Trace of individual requests for debugging.

    Only samples slow (>500ms) or error requests to avoid storage bloat.
    Enables debugging production issues by request_id.

    Example:
        trace = RequestTrace(
            request_id="req_abc123",
            method="GET",
            path="/api/v1/cards/123",
            status_code=500,
            duration_ms=1523.4,
            error_type="DatabaseError",
        )
    """

    __tablename__ = "request_trace"

    id: Optional[int] = Field(default=None, primary_key=True)
    request_id: str = Field(max_length=50, unique=True, index=True)
    correlation_id: Optional[str] = Field(default=None, max_length=50)
    method: str = Field(max_length=10)
    path: str = Field(max_length=500)
    status_code: Optional[int] = None
    duration_ms: Optional[float] = Field(default=None, index=True)
    user_id: Optional[int] = Field(default=None, index=True)
    error_type: Optional[str] = Field(default=None, max_length=100, index=True)
    error_message: Optional[str] = Field(default=None, max_length=1000)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )
