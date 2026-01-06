"""
Task Queue Service

Persistent task queue for managing scrape operations with crash resilience.
Tasks are stored in the database and survive application restarts.

Usage:
    from app.services.task_queue import (
        enqueue_task,
        claim_next_task,
        complete_task,
        fail_task,
        reset_stale_tasks,
    )

    async with AsyncSession(engine) as session:
        # Enqueue a new task
        task = await enqueue_task(session, card_id=123, source="ebay", priority=1)

        # Worker claims next task
        task = await claim_next_task(session, source="ebay")
        if task:
            try:
                # Do scrape work...
                await complete_task(session, task.id)
            except Exception as e:
                await fail_task(session, task.id, str(e))

        # On startup, reset any stale in-progress tasks
        await reset_stale_tasks(session, timeout_minutes=30)
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.typing import col
from app.models.scrape_task import ScrapeTask, TaskStatus

logger = logging.getLogger(__name__)


async def enqueue_task(
    session: AsyncSession,
    card_id: int,
    source: str,
    priority: int = 0,
    max_attempts: int = 3,
) -> ScrapeTask:
    """
    Enqueue a new scrape task.

    If a pending task for the same card/source already exists, returns the existing
    task instead of creating a duplicate.

    Args:
        session: Database session
        card_id: ID of the card to scrape
        source: Platform to scrape ("ebay", "blokpax", "opensea")
        priority: Higher values = more urgent (default 0)
        max_attempts: Maximum retry attempts before permanent failure

    Returns:
        The created or existing ScrapeTask
    """
    # Check for existing pending task to avoid duplicates
    stmt = select(ScrapeTask).where(
        col(ScrapeTask.card_id) == card_id,
        col(ScrapeTask.source) == source,
        col(ScrapeTask.status) == TaskStatus.PENDING,
    )
    result = await session.exec(stmt)
    existing = result.first()

    if existing:
        # Update priority if new task has higher priority
        if priority > existing.priority:
            existing.priority = priority
            existing.updated_at = datetime.now(timezone.utc)
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
        logger.debug(f"Task already exists for card_id={card_id}, source={source}")
        return existing

    # Create new task
    task = ScrapeTask(
        card_id=card_id,
        source=source,
        priority=priority,
        max_attempts=max_attempts,
    )
    session.add(task)
    await session.commit()
    await session.refresh(task)

    logger.info(f"Enqueued task id={task.id} for card_id={card_id}, source={source}")
    return task


async def claim_next_task(
    session: AsyncSession,
    source: Optional[str] = None,
) -> Optional[ScrapeTask]:
    """
    Claim the next pending task for processing.

    Atomically updates the task status to IN_PROGRESS and increments attempt count.
    Tasks are ordered by priority (desc) then created_at (asc).

    Args:
        session: Database session
        source: Optional filter by source platform

    Returns:
        The claimed ScrapeTask, or None if no tasks available
    """
    # Build query for next available task
    stmt = select(ScrapeTask).where(
        col(ScrapeTask.status) == TaskStatus.PENDING,
    )

    if source:
        stmt = stmt.where(col(ScrapeTask.source) == source)

    # Order by priority DESC (higher first), then created_at ASC (older first)
    stmt = stmt.order_by(
        col(ScrapeTask.priority).desc(),
        col(ScrapeTask.created_at).asc(),
    ).limit(1)

    # Use FOR UPDATE to prevent race conditions
    stmt = stmt.with_for_update(skip_locked=True)

    result = await session.exec(stmt)
    task = result.first()

    if not task:
        return None

    # Claim the task
    task.status = TaskStatus.IN_PROGRESS
    task.attempts += 1
    task.started_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)

    session.add(task)
    await session.commit()
    await session.refresh(task)

    logger.info(
        f"Claimed task id={task.id} for card_id={task.card_id}, "
        f"source={task.source}, attempt={task.attempts}/{task.max_attempts}"
    )
    return task


async def complete_task(session: AsyncSession, task_id: int) -> Optional[ScrapeTask]:
    """
    Mark a task as successfully completed.

    Args:
        session: Database session
        task_id: ID of the task to complete

    Returns:
        The updated ScrapeTask, or None if not found
    """
    stmt = select(ScrapeTask).where(col(ScrapeTask.id) == task_id)
    result = await session.exec(stmt)
    task = result.first()

    if not task:
        logger.warning(f"Task id={task_id} not found for completion")
        return None

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    task.last_error = None  # Clear any previous error

    session.add(task)
    await session.commit()
    await session.refresh(task)

    logger.info(f"Completed task id={task.id} for card_id={task.card_id}")
    return task


async def fail_task(
    session: AsyncSession,
    task_id: int,
    error: str,
) -> Optional[ScrapeTask]:
    """
    Mark a task as failed, with potential retry.

    If attempts < max_attempts, task returns to PENDING for retry.
    Otherwise, task is marked as permanently FAILED.

    Args:
        session: Database session
        task_id: ID of the task that failed
        error: Error message describing the failure

    Returns:
        The updated ScrapeTask, or None if not found
    """
    stmt = select(ScrapeTask).where(col(ScrapeTask.id) == task_id)
    result = await session.exec(stmt)
    task = result.first()

    if not task:
        logger.warning(f"Task id={task_id} not found for failure")
        return None

    task.last_error = error[:1000] if len(error) > 1000 else error  # Truncate long errors
    task.updated_at = datetime.now(timezone.utc)

    if task.attempts >= task.max_attempts:
        # Max attempts reached - permanent failure
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        logger.warning(f"Task id={task.id} permanently failed after {task.attempts} attempts: {error[:100]}")
    else:
        # Return to pending for retry
        task.status = TaskStatus.PENDING
        task.started_at = None
        logger.info(
            f"Task id={task.id} failed (attempt {task.attempts}/{task.max_attempts}), " f"will retry: {error[:100]}"
        )

    session.add(task)
    await session.commit()
    await session.refresh(task)

    return task


async def reset_stale_tasks(
    session: AsyncSession,
    timeout_minutes: int = 30,
) -> int:
    """
    Reset stale in-progress tasks to pending.

    Tasks that have been IN_PROGRESS for longer than timeout_minutes are
    considered stale (worker crashed/hung) and returned to the queue.

    This should be called on application startup to recover from crashes.

    Args:
        session: Database session
        timeout_minutes: Minutes before a task is considered stale

    Returns:
        Number of tasks reset
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    stmt = select(ScrapeTask).where(
        col(ScrapeTask.status) == TaskStatus.IN_PROGRESS,
        col(ScrapeTask.started_at) < cutoff,
    )

    result = await session.exec(stmt)
    stale_tasks = result.all()

    count = 0
    for task in stale_tasks:
        task.status = TaskStatus.PENDING
        task.started_at = None
        task.updated_at = datetime.now(timezone.utc)
        task.last_error = f"Task timed out after {timeout_minutes} minutes"
        session.add(task)
        count += 1

    if count > 0:
        await session.commit()
        logger.warning(f"Reset {count} stale tasks to pending")

    return count


async def get_queue_stats(
    session: AsyncSession,
    source: Optional[str] = None,
) -> dict[str, int]:
    """
    Get task queue statistics.

    Args:
        session: Database session
        source: Optional filter by source platform

    Returns:
        Dict with counts per status: {"pending": N, "in_progress": N, ...}
    """
    from sqlalchemy import func

    stats: dict[str, int] = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
    }

    for status in TaskStatus:
        stmt = select(func.count()).select_from(ScrapeTask).where(col(ScrapeTask.status) == status)
        if source:
            stmt = stmt.where(col(ScrapeTask.source) == source)

        result = await session.exec(stmt)
        count = result.one()
        stats[status.value] = count

    return stats


def enqueue_task_sync(
    session,  # sqlmodel.Session (sync)
    card_id: int,
    source: str,
    priority: int = 0,
    max_attempts: int = 3,
) -> ScrapeTask:
    """
    Synchronous version of enqueue_task for use with sync sessions (e.g., scheduler).

    If a pending task for the same card/source already exists, returns the existing
    task instead of creating a duplicate.

    Args:
        session: Sync database session (sqlmodel.Session)
        card_id: ID of the card to scrape
        source: Platform to scrape ("ebay", "blokpax", "opensea")
        priority: Higher values = more urgent (default 0)
        max_attempts: Maximum retry attempts before permanent failure

    Returns:
        The created or existing ScrapeTask
    """
    # Check for existing pending task to avoid duplicates
    stmt = select(ScrapeTask).where(
        col(ScrapeTask.card_id) == card_id,
        col(ScrapeTask.source) == source,
        col(ScrapeTask.status) == TaskStatus.PENDING,
    )
    existing = session.exec(stmt).first()

    if existing:
        # Update priority if new task has higher priority
        if priority > existing.priority:
            existing.priority = priority
            existing.updated_at = datetime.now(timezone.utc)
            session.add(existing)
            session.commit()
            session.refresh(existing)
        logger.debug(f"Task already exists for card_id={card_id}, source={source}")
        return existing

    # Create new task
    task = ScrapeTask(
        card_id=card_id,
        source=source,
        priority=priority,
        max_attempts=max_attempts,
    )
    session.add(task)
    session.commit()
    session.refresh(task)

    logger.info(f"Enqueued task id={task.id} for card_id={card_id}, source={source}")
    return task


def get_queue_stats_sync(
    session,  # sqlmodel.Session (sync)
    source: Optional[str] = None,
) -> dict[str, int]:
    """
    Synchronous version of get_queue_stats for use with sync sessions.

    Args:
        session: Sync database session (sqlmodel.Session)
        source: Optional filter by source platform

    Returns:
        Dict with counts per status: {"pending": N, "in_progress": N, ...}
    """
    from sqlalchemy import func

    stats: dict[str, int] = {
        "pending": 0,
        "in_progress": 0,
        "completed": 0,
        "failed": 0,
    }

    for status in TaskStatus:
        stmt = select(func.count()).select_from(ScrapeTask).where(col(ScrapeTask.status) == status)
        if source:
            stmt = stmt.where(col(ScrapeTask.source) == source)

        count = session.exec(stmt).one()
        stats[status.value] = count

    return stats


def claim_next_task_sync(
    session,  # sqlmodel.Session (sync)
    source: Optional[str] = None,
) -> Optional[ScrapeTask]:
    """
    Synchronous version of claim_next_task for worker processes.

    Atomically updates the task status to IN_PROGRESS and increments attempt count.
    Tasks are ordered by priority (desc) then created_at (asc).

    Args:
        session: Sync database session (sqlmodel.Session)
        source: Optional filter by source platform

    Returns:
        The claimed ScrapeTask, or None if no tasks available
    """
    # Build query for next available task
    stmt = select(ScrapeTask).where(
        col(ScrapeTask.status) == TaskStatus.PENDING,
    )

    if source:
        stmt = stmt.where(col(ScrapeTask.source) == source)

    # Order by priority DESC (higher first), then created_at ASC (older first)
    stmt = stmt.order_by(
        col(ScrapeTask.priority).desc(),
        col(ScrapeTask.created_at).asc(),
    ).limit(1)

    # Use FOR UPDATE to prevent race conditions
    stmt = stmt.with_for_update(skip_locked=True)

    task = session.exec(stmt).first()

    if not task:
        return None

    # Claim the task
    task.status = TaskStatus.IN_PROGRESS
    task.attempts += 1
    task.started_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)

    session.add(task)
    session.commit()
    session.refresh(task)

    logger.info(
        f"Claimed task id={task.id} for card_id={task.card_id}, "
        f"source={task.source}, attempt={task.attempts}/{task.max_attempts}"
    )
    return task


def complete_task_sync(session, task_id: int) -> Optional[ScrapeTask]:
    """
    Synchronous version of complete_task for worker processes.

    Args:
        session: Sync database session (sqlmodel.Session)
        task_id: ID of the task to complete

    Returns:
        The updated ScrapeTask, or None if not found
    """
    stmt = select(ScrapeTask).where(col(ScrapeTask.id) == task_id)
    task = session.exec(stmt).first()

    if not task:
        logger.warning(f"Task id={task_id} not found for completion")
        return None

    task.status = TaskStatus.COMPLETED
    task.completed_at = datetime.now(timezone.utc)
    task.updated_at = datetime.now(timezone.utc)
    task.last_error = None  # Clear any previous error

    session.add(task)
    session.commit()
    session.refresh(task)

    logger.info(f"Completed task id={task.id} for card_id={task.card_id}")
    return task


def fail_task_sync(
    session,  # sqlmodel.Session (sync)
    task_id: int,
    error: str,
) -> Optional[ScrapeTask]:
    """
    Synchronous version of fail_task for worker processes.

    If attempts < max_attempts, task returns to PENDING for retry.
    Otherwise, task is marked as permanently FAILED.

    Args:
        session: Sync database session (sqlmodel.Session)
        task_id: ID of the task that failed
        error: Error message describing the failure

    Returns:
        The updated ScrapeTask, or None if not found
    """
    stmt = select(ScrapeTask).where(col(ScrapeTask.id) == task_id)
    task = session.exec(stmt).first()

    if not task:
        logger.warning(f"Task id={task_id} not found for failure")
        return None

    task.last_error = error[:1000] if len(error) > 1000 else error  # Truncate long errors
    task.updated_at = datetime.now(timezone.utc)

    if task.attempts >= task.max_attempts:
        # Max attempts reached - permanent failure
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        logger.warning(f"Task id={task.id} permanently failed after {task.attempts} attempts: {error[:100]}")
    else:
        # Return to pending for retry
        task.status = TaskStatus.PENDING
        task.started_at = None
        logger.info(
            f"Task id={task.id} failed (attempt {task.attempts}/{task.max_attempts}), " f"will retry: {error[:100]}"
        )

    session.add(task)
    session.commit()
    session.refresh(task)

    return task


def reset_stale_tasks_sync(
    session,  # sqlmodel.Session (sync)
    timeout_minutes: int = 30,
) -> dict[str, int]:
    """
    Synchronous version of reset_stale_tasks for worker processes.

    Tasks that have been IN_PROGRESS for longer than timeout_minutes are
    considered stale (worker crashed/hung) and returned to the queue.

    Args:
        session: Sync database session (sqlmodel.Session)
        timeout_minutes: Minutes before a task is considered stale

    Returns:
        Dict with {"reset": N} count of reset tasks
    """
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=timeout_minutes)

    stmt = select(ScrapeTask).where(
        col(ScrapeTask.status) == TaskStatus.IN_PROGRESS,
        col(ScrapeTask.started_at) < cutoff,
    )

    stale_tasks = list(session.exec(stmt).all())

    count = 0
    for task in stale_tasks:
        task.status = TaskStatus.PENDING
        task.started_at = None
        task.updated_at = datetime.now(timezone.utc)
        task.last_error = f"Task timed out after {timeout_minutes} minutes"
        session.add(task)
        count += 1

    if count > 0:
        session.commit()
        logger.warning(f"Reset {count} stale tasks to pending")

    return {"reset": count}


def cleanup_old_tasks_sync(
    session,  # sqlmodel.Session (sync)
    days_to_keep: int = 7,
) -> dict[str, int]:
    """
    Delete completed and failed tasks older than days_to_keep.

    This should be called periodically (e.g., daily) to prevent the task
    table from growing unbounded.

    Args:
        session: Sync database session (sqlmodel.Session)
        days_to_keep: Number of days to retain completed/failed tasks

    Returns:
        Dict with {"completed_deleted": N, "failed_deleted": N}
    """
    from sqlmodel import delete

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_to_keep)

    # Delete completed tasks older than cutoff
    completed_stmt = delete(ScrapeTask).where(
        col(ScrapeTask.status) == TaskStatus.COMPLETED,
        col(ScrapeTask.completed_at) < cutoff,
    )
    completed_result = session.execute(completed_stmt)

    # Delete failed tasks (max attempts reached) older than cutoff
    failed_stmt = delete(ScrapeTask).where(
        col(ScrapeTask.status) == TaskStatus.FAILED,
        col(ScrapeTask.updated_at) < cutoff,
    )
    failed_result = session.execute(failed_stmt)

    session.commit()

    completed_deleted = completed_result.rowcount or 0
    failed_deleted = failed_result.rowcount or 0

    logger.info(
        f"Cleaned up {completed_deleted} completed and {failed_deleted} failed tasks older than {days_to_keep} days"
    )

    return {
        "completed_deleted": completed_deleted,
        "failed_deleted": failed_deleted,
    }


__all__ = [
    # Async versions (for AsyncSession)
    "enqueue_task",
    "claim_next_task",
    "complete_task",
    "fail_task",
    "reset_stale_tasks",
    "get_queue_stats",
    # Sync versions (for Session)
    "enqueue_task_sync",
    "claim_next_task_sync",
    "complete_task_sync",
    "fail_task_sync",
    "reset_stale_tasks_sync",
    "get_queue_stats_sync",
    "cleanup_old_tasks_sync",
]
