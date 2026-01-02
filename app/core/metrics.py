"""Simple in-memory metrics for scraper monitoring.

These metrics are process-local and reset on restart.
For persistent metrics, use the database health check queries.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import Lock
from typing import Optional


@dataclass
class ScrapeMetrics:
    """Metrics for a single scrape job run."""

    job_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    cards_processed: int = 0
    successful: int = 0
    failed: int = 0
    db_errors: int = 0
    duration_seconds: float = 0.0


@dataclass
class MetricsStore:
    """Thread-safe store for scraper metrics."""

    _lock: Lock = field(default_factory=Lock)
    _last_runs: dict = field(default_factory=dict)  # job_name -> ScrapeMetrics
    _total_runs: dict = field(default_factory=lambda: {})  # job_name -> count
    _total_failures: dict = field(default_factory=lambda: {})  # job_name -> count

    def record_start(self, job_name: str) -> None:
        """Record the start of a scrape job."""
        with self._lock:
            self._last_runs[job_name] = ScrapeMetrics(
                job_name=job_name,
                started_at=datetime.now(timezone.utc),
            )

    def record_complete(
        self,
        job_name: str,
        cards_processed: int,
        successful: int,
        failed: int,
        db_errors: int = 0,
    ) -> None:
        """Record the completion of a scrape job."""
        with self._lock:
            now = datetime.now(timezone.utc)

            if job_name in self._last_runs:
                metrics = self._last_runs[job_name]
                metrics.completed_at = now
                metrics.cards_processed = cards_processed
                metrics.successful = successful
                metrics.failed = failed
                metrics.db_errors = db_errors
                metrics.duration_seconds = (now - metrics.started_at).total_seconds()
            else:
                # Job wasn't recorded starting, create a completed record
                self._last_runs[job_name] = ScrapeMetrics(
                    job_name=job_name,
                    started_at=now,
                    completed_at=now,
                    cards_processed=cards_processed,
                    successful=successful,
                    failed=failed,
                    db_errors=db_errors,
                )

            # Update totals
            self._total_runs[job_name] = self._total_runs.get(job_name, 0) + 1
            if failed > successful:
                self._total_failures[job_name] = self._total_failures.get(job_name, 0) + 1

    def get_last_run(self, job_name: str) -> Optional[ScrapeMetrics]:
        """Get metrics for the last run of a job."""
        with self._lock:
            return self._last_runs.get(job_name)

    def get_all_metrics(self) -> dict:
        """Get all metrics as a dictionary."""
        with self._lock:
            result = {}
            for job_name, metrics in self._last_runs.items():
                result[job_name] = {
                    "last_run": {
                        "started_at": metrics.started_at.isoformat(),
                        "completed_at": metrics.completed_at.isoformat() if metrics.completed_at else None,
                        "cards_processed": metrics.cards_processed,
                        "successful": metrics.successful,
                        "failed": metrics.failed,
                        "db_errors": metrics.db_errors,
                        "duration_seconds": round(metrics.duration_seconds, 1),
                        "success_rate": round(metrics.successful / metrics.cards_processed * 100, 1)
                        if metrics.cards_processed > 0
                        else 0,
                    },
                    "total_runs": self._total_runs.get(job_name, 0),
                    "total_failures": self._total_failures.get(job_name, 0),
                }
            return result

    def get_summary(self) -> dict:
        """Get a summary of all metrics."""
        with self._lock:
            total_jobs = len(self._last_runs)
            healthy_jobs = 0
            degraded_jobs = 0

            for job_name, metrics in self._last_runs.items():
                if metrics.cards_processed > 0:
                    success_rate = metrics.successful / metrics.cards_processed
                    if success_rate >= 0.9:
                        healthy_jobs += 1
                    elif success_rate >= 0.5:
                        degraded_jobs += 1

            return {
                "total_jobs": total_jobs,
                "healthy_jobs": healthy_jobs,
                "degraded_jobs": degraded_jobs,
                "unhealthy_jobs": total_jobs - healthy_jobs - degraded_jobs,
            }


# Global metrics store
scraper_metrics = MetricsStore()
