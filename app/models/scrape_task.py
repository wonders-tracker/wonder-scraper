"""
Scrape Task Model

Persistent task queue for managing scrape jobs that survive application restarts.
Tasks represent pending, in-progress, or completed scrape operations for cards
across different platforms (eBay, Blokpax, etc.).

Usage:
    from app.models.scrape_task import ScrapeTask, TaskStatus

    # Create a task
    task = ScrapeTask(card_id=123, source="ebay", priority=1)

    # Check status
    if task.status == TaskStatus.PENDING:
        task.status = TaskStatus.IN_PROGRESS
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlmodel import Field, SQLModel
from sqlalchemy import Index


class TaskStatus(str, Enum):
    """Status of a scrape task."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class ScrapeTask(SQLModel, table=True):
    """
    Persistent scrape task for crash-resilient job management.

    Tasks are created when scrape jobs are queued and persist until
    completed or max attempts exceeded. This allows recovery from
    crashes/restarts without losing pending work.

    Attributes:
        id: Primary key
        card_id: ID of the card to scrape
        source: Platform to scrape ("ebay", "blokpax", "opensea")
        status: Current task status
        priority: Higher values = more urgent (default 0)
        attempts: Number of execution attempts
        max_attempts: Maximum retries before permanent failure
        last_error: Error message from most recent failure
        created_at: When the task was created
        updated_at: When the task was last modified
        started_at: When execution began
        completed_at: When execution finished (success or failure)
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(index=True)
    source: str  # "ebay", "blokpax", "opensea"
    status: TaskStatus = Field(default=TaskStatus.PENDING, index=True)
    priority: int = Field(default=0)  # Higher = more urgent
    attempts: int = Field(default=0)
    max_attempts: int = Field(default=3)
    last_error: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Composite indexes for efficient queue queries
    __table_args__ = (
        # Primary queue query: status + priority + created_at
        Index("ix_scrapetask_queue", "status", "priority", "created_at"),
        # Source-specific queue query
        Index("ix_scrapetask_source_status", "source", "status"),
        # Stale task detection (in_progress + started_at)
        Index("ix_scrapetask_stale", "status", "started_at"),
        # Task deduplication: card_id + source + status
        Index("ix_scrapetask_dedup", "card_id", "source", "status"),
    )


__all__ = ["ScrapeTask", "TaskStatus"]
