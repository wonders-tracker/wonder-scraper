"""
Enhanced metrics with database persistence.

Extends the existing MetricsStore to add:
- Job log persistence (start/complete)
- Periodic snapshot flushing to database
- Historical query methods

This enables metrics to survive restarts and supports historical analysis.

Usage:
    # Use as drop-in replacement for scraper_metrics
    from app.core.metrics_persistent import persistent_metrics

    persistent_metrics.record_start("ebay_market_update")
    # ... job runs ...
    persistent_metrics.record_complete("ebay_market_update", ...)

    # Metrics are automatically persisted to database
"""

from datetime import datetime, timezone
from typing import Optional, Dict, Any
import structlog

from sqlmodel import Session, select
from app.db import engine
from app.core.metrics import MetricsStore
from app.models.observability import ScraperJobLog, MetricsSnapshot
from app.core.errors import capture_exception

logger = structlog.get_logger(__name__)

__all__ = ["PersistentMetricsStore", "persistent_metrics"]


class PersistentMetricsStore(MetricsStore):
    """
    Enhanced metrics store with database persistence.

    Inherits from MetricsStore and adds:
    - Job log persistence (start/complete)
    - Periodic snapshot flushing
    - Historical query methods

    Thread-safe: Uses parent's lock for in-memory operations,
    database operations are transactional.
    """

    def __init__(self):
        super().__init__()
        # Track job log IDs for updating completion
        self._job_log_ids: Dict[str, int] = {}

    def record_start(  # type: ignore[override]
        self,
        job_name: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[int]:
        """
        Record job start to database and return job log ID.

        Args:
            job_name: Name of the job (e.g., "ebay_market_update")
            metadata: Optional additional context

        Returns:
            Job log ID for updating completion, or None if persistence failed
        """
        # Record to in-memory store
        super().record_start(job_name)

        # Persist to database
        try:
            with Session(engine) as session:
                log_entry = ScraperJobLog(
                    job_name=job_name,
                    started_at=datetime.now(timezone.utc),
                    status="running",
                    job_metadata=metadata,
                )
                session.add(log_entry)
                session.commit()
                session.refresh(log_entry)

                # Track for completion update
                if log_entry.id is not None:
                    self._job_log_ids[job_name] = log_entry.id

                logger.debug(
                    "Job start logged",
                    job_name=job_name,
                    job_log_id=log_entry.id,
                )
                return log_entry.id

        except Exception as e:
            logger.warning(
                "Failed to persist job start",
                job_name=job_name,
                error=str(e),
            )
            capture_exception(e, context={"job_name": job_name, "action": "record_start"})
            return None

    def record_complete(
        self,
        job_name: str,
        cards_processed: int,
        successful: int,
        failed: int,
        db_errors: int = 0,
        error: Optional[Exception] = None,
        job_log_id: Optional[int] = None,
    ) -> None:
        """
        Record job completion to database.

        Args:
            job_name: Name of the job
            cards_processed: Total cards attempted
            successful: Successfully processed count
            failed: Failed count
            db_errors: Database error count
            error: Exception if job failed
            job_log_id: Optional ID from record_start (auto-looked up if not provided)
        """
        # Record to in-memory store
        super().record_complete(job_name, cards_processed, successful, failed, db_errors)

        # Get job log ID
        log_id = job_log_id or self._job_log_ids.get(job_name)

        # Persist completion to database
        try:
            with Session(engine) as session:
                # Get the in-memory metrics for duration
                metrics = self.get_last_run(job_name)

                if log_id:
                    # Update existing log entry
                    log_entry = session.get(ScraperJobLog, log_id)
                else:
                    # Find the most recent running entry
                    log_entry = session.exec(
                        select(ScraperJobLog)
                        .where(ScraperJobLog.job_name == job_name)
                        .where(ScraperJobLog.status == "running")
                        .order_by(ScraperJobLog.started_at.desc())
                    ).first()

                if log_entry:
                    log_entry.completed_at = datetime.now(timezone.utc)
                    log_entry.status = "failed" if failed > successful else "completed"
                    log_entry.cards_processed = cards_processed
                    log_entry.successful = successful
                    log_entry.failed = failed
                    log_entry.db_errors = db_errors

                    if metrics:
                        log_entry.duration_seconds = metrics.duration_seconds

                    if error:
                        log_entry.error_type = type(error).__name__
                        log_entry.error_message = str(error)[:1000]

                    session.add(log_entry)
                    session.commit()

                    logger.debug(
                        "Job completion logged",
                        job_name=job_name,
                        job_log_id=log_entry.id,
                        status=log_entry.status,
                    )
                else:
                    # No running entry found, create a completed record
                    log_entry = ScraperJobLog(
                        job_name=job_name,
                        started_at=datetime.now(timezone.utc),
                        completed_at=datetime.now(timezone.utc),
                        status="failed" if failed > successful else "completed",
                        cards_processed=cards_processed,
                        successful=successful,
                        failed=failed,
                        db_errors=db_errors,
                        duration_seconds=metrics.duration_seconds if metrics else 0,
                        error_type=type(error).__name__ if error else None,
                        error_message=str(error)[:1000] if error else None,
                    )
                    session.add(log_entry)
                    session.commit()

                # Clean up tracked ID
                self._job_log_ids.pop(job_name, None)

        except Exception as e:
            logger.warning(
                "Failed to persist job completion",
                job_name=job_name,
                error=str(e),
            )
            capture_exception(e, context={"job_name": job_name, "action": "record_complete"})

    def snapshot_all(self) -> int:
        """
        Save snapshot of all current metrics to database.

        Called periodically by scheduler to capture metrics before restart.

        Returns:
            Number of snapshots saved
        """
        try:
            with Session(engine) as session:
                snapshot_time = datetime.now(timezone.utc)
                count = 0

                # Snapshot scraper metrics
                all_metrics = self.get_all_metrics()
                for job_name, metrics in all_metrics.items():
                    snapshot = MetricsSnapshot(
                        snapshot_at=snapshot_time,
                        metric_type="scraper",
                        metric_name=job_name,
                        metric_value=metrics,
                    )
                    session.add(snapshot)
                    count += 1

                # Snapshot summary
                summary = self.get_summary()
                summary_snapshot = MetricsSnapshot(
                    snapshot_at=snapshot_time,
                    metric_type="scraper",
                    metric_name="_summary",
                    metric_value=summary,
                )
                session.add(summary_snapshot)
                count += 1

                session.commit()
                logger.debug("Metrics snapshot saved", snapshot_count=count)
                return count

        except Exception as e:
            logger.warning("Failed to save metrics snapshot", error=str(e))
            capture_exception(e, context={"action": "snapshot_all"})
            return 0

    def get_historical_job_runs(
        self,
        job_name: str,
        limit: int = 100,
    ) -> list[dict]:
        """
        Get historical job runs from database.

        Args:
            job_name: Name of the job
            limit: Maximum number of runs to return

        Returns:
            List of job run dicts, most recent first
        """
        try:
            with Session(engine) as session:
                logs = session.exec(
                    select(ScraperJobLog)
                    .where(ScraperJobLog.job_name == job_name)
                    .order_by(ScraperJobLog.started_at.desc())
                    .limit(limit)
                ).all()

                return [
                    {
                        "id": log.id,
                        "started_at": log.started_at.isoformat(),
                        "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                        "status": log.status,
                        "cards_processed": log.cards_processed,
                        "successful": log.successful,
                        "failed": log.failed,
                        "db_errors": log.db_errors,
                        "duration_seconds": log.duration_seconds,
                        "error_type": log.error_type,
                        "error_message": log.error_message,
                    }
                    for log in logs
                ]

        except Exception as e:
            logger.warning(
                "Failed to get historical job runs",
                job_name=job_name,
                error=str(e),
            )
            return []

    def get_job_success_rate(
        self,
        job_name: str,
        hours: int = 24,
    ) -> Optional[float]:
        """
        Calculate success rate for a job over a time period.

        Args:
            job_name: Name of the job
            hours: Number of hours to look back

        Returns:
            Success rate as decimal (0.0-1.0) or None if no data
        """
        try:
            from sqlalchemy import text

            with Session(engine) as session:
                result = session.execute(
                    text(
                        """
                    SELECT
                        COALESCE(SUM(successful), 0) as total_successful,
                        COALESCE(SUM(cards_processed), 0) as total_processed
                    FROM scraper_job_log
                    WHERE job_name = :job_name
                    AND started_at >= NOW() - (:hours * INTERVAL '1 hour')
                    AND status IN ('completed', 'failed')
                """
                    ),
                    {"job_name": job_name, "hours": hours},
                ).first()

                if result and result[1] > 0:
                    return result[0] / result[1]
                return None

        except Exception as e:
            logger.warning(
                "Failed to calculate job success rate",
                job_name=job_name,
                error=str(e),
            )
            return None


# Global persistent metrics store (drop-in replacement for scraper_metrics)
persistent_metrics = PersistentMetricsStore()
