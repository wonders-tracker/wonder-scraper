"""
Centralized health threshold configuration.

Defines thresholds for alerting on system degradation.
All thresholds are tunable via environment variables.

Usage:
    from app.core.health_thresholds import HealthThresholds, check_threshold

    status = check_threshold(
        value=hours_since_scrape,
        threshold=HealthThresholds.SCRAPER_STALE_HOURS,
    )
    # Returns: "ok", "warning", or "critical"
"""

from dataclasses import dataclass
from typing import Literal
import os

__all__ = [
    "Threshold",
    "HealthThresholds",
    "check_threshold",
    "ThresholdStatus",
]

ThresholdStatus = Literal["ok", "warning", "critical"]


@dataclass(frozen=True)
class Threshold:
    """
    Health threshold with warning and critical levels.

    Attributes:
        warning: Value at which to warn (degraded)
        critical: Value at which to alert (unhealthy)
        unit: Human-readable unit for display
        name: Optional name for logging
    """

    warning: float
    critical: float
    unit: str = ""
    name: str = ""

    def __str__(self) -> str:
        return f"{self.name or 'threshold'}: warn={self.warning}{self.unit}, crit={self.critical}{self.unit}"


def check_threshold(value: float, threshold: Threshold) -> ThresholdStatus:
    """
    Check if value exceeds threshold.

    Args:
        value: Current metric value
        threshold: Threshold to check against

    Returns:
        "ok" if below warning
        "warning" if at/above warning but below critical
        "critical" if at/above critical
    """
    if value >= threshold.critical:
        return "critical"
    elif value >= threshold.warning:
        return "warning"
    return "ok"


def _env_float(key: str, default: float) -> float:
    """Get float from environment or return default."""
    try:
        return float(os.environ.get(key, default))
    except (TypeError, ValueError):
        return default


class HealthThresholds:
    """
    Centralized health thresholds for all monitoring checks.

    All thresholds can be overridden via environment variables:
        THRESHOLD_SCRAPER_STALE_WARN=2.0
        THRESHOLD_SCRAPER_STALE_CRIT=6.0

    Categories:
        - Scraper: Data freshness, error rates
        - Performance: API response times
        - Database: Connection and query times
        - Circuit: Circuit breaker states
        - Worker: Job execution health
        - Queue: Task queue depth (if enabled)
    """

    # ==========================================================================
    # Scraper Thresholds
    # ==========================================================================

    SCRAPER_ERROR_RATE = Threshold(
        warning=_env_float("THRESHOLD_SCRAPER_ERROR_WARN", 0.3),
        critical=_env_float("THRESHOLD_SCRAPER_ERROR_CRIT", 0.5),
        unit="ratio",
        name="scraper_error_rate",
    )
    """Error rate: 30% warn, 50% critical"""

    SCRAPER_DB_ERROR_RATE = Threshold(
        warning=_env_float("THRESHOLD_SCRAPER_DB_ERROR_WARN", 0.2),
        critical=_env_float("THRESHOLD_SCRAPER_DB_ERROR_CRIT", 0.4),
        unit="ratio",
        name="scraper_db_error_rate",
    )
    """DB error rate: 20% warn, 40% critical"""

    SCRAPER_STALE_HOURS = Threshold(
        warning=_env_float("THRESHOLD_SCRAPER_STALE_WARN", 1.0),  # Changed from 2.0
        critical=_env_float("THRESHOLD_SCRAPER_STALE_CRIT", 3.0),  # Changed from 6.0
        unit="hours",
        name="scraper_stale_hours",
    )
    """Hours since last scrape: 1h warn, 3h critical (tightened from 2/6)"""

    # ==========================================================================
    # Performance Thresholds
    # ==========================================================================

    API_P95_RESPONSE_MS = Threshold(
        warning=_env_float("THRESHOLD_API_P95_WARN", 1000.0),
        critical=_env_float("THRESHOLD_API_P95_CRIT", 3000.0),
        unit="ms",
        name="api_p95_response",
    )
    """API p95 latency: 1s warn, 3s critical"""

    API_P99_RESPONSE_MS = Threshold(
        warning=_env_float("THRESHOLD_API_P99_WARN", 3000.0),
        critical=_env_float("THRESHOLD_API_P99_CRIT", 10000.0),
        unit="ms",
        name="api_p99_response",
    )
    """API p99 latency: 3s warn, 10s critical"""

    API_SLOW_REQUEST_RATE = Threshold(
        warning=_env_float("THRESHOLD_API_SLOW_WARN", 0.1),
        critical=_env_float("THRESHOLD_API_SLOW_CRIT", 0.3),
        unit="ratio",
        name="api_slow_request_rate",
    )
    """Slow request rate (>500ms): 10% warn, 30% critical"""

    # ==========================================================================
    # Database Thresholds
    # ==========================================================================

    DB_CONNECTION_TIME_MS = Threshold(
        warning=_env_float("THRESHOLD_DB_CONN_WARN", 100.0),
        critical=_env_float("THRESHOLD_DB_CONN_CRIT", 500.0),
        unit="ms",
        name="db_connection_time",
    )
    """DB connection time: 100ms warn, 500ms critical"""

    DB_QUERY_TIME_MS = Threshold(
        warning=_env_float("THRESHOLD_DB_QUERY_WARN", 500.0),
        critical=_env_float("THRESHOLD_DB_QUERY_CRIT", 2000.0),
        unit="ms",
        name="db_query_time",
    )
    """DB query time: 500ms warn, 2s critical"""

    # ==========================================================================
    # Circuit Breaker Thresholds
    # ==========================================================================

    CIRCUIT_OPEN_DURATION_MIN = Threshold(
        warning=_env_float("THRESHOLD_CIRCUIT_OPEN_WARN", 5.0),
        critical=_env_float("THRESHOLD_CIRCUIT_OPEN_CRIT", 30.0),
        unit="minutes",
        name="circuit_open_duration",
    )
    """Circuit open duration: 5m warn, 30m critical"""

    # ==========================================================================
    # Worker Thresholds
    # ==========================================================================

    WORKER_JOB_GAP_HOURS = Threshold(
        warning=_env_float("THRESHOLD_WORKER_GAP_WARN", 1.0),  # Tightened from 2.0
        critical=_env_float("THRESHOLD_WORKER_GAP_CRIT", 3.0),  # Tightened from 6.0
        unit="hours",
        name="worker_job_gap",
    )
    """Hours since last job: 1h warn, 3h critical"""

    WORKER_JOB_FAILURE_RATE = Threshold(
        warning=_env_float("THRESHOLD_WORKER_FAIL_WARN", 0.3),
        critical=_env_float("THRESHOLD_WORKER_FAIL_CRIT", 0.5),
        unit="ratio",
        name="worker_job_failure_rate",
    )
    """Job failure rate: 30% warn, 50% critical"""

    # ==========================================================================
    # Queue Thresholds (if enabled)
    # ==========================================================================

    QUEUE_DEPTH = Threshold(
        warning=_env_float("THRESHOLD_QUEUE_DEPTH_WARN", 500),
        critical=_env_float("THRESHOLD_QUEUE_DEPTH_CRIT", 1000),
        unit="tasks",
        name="queue_depth",
    )
    """Pending task count: 500 warn, 1000 critical"""

    QUEUE_DEAD_LETTER = Threshold(
        warning=_env_float("THRESHOLD_QUEUE_DL_WARN", 10),
        critical=_env_float("THRESHOLD_QUEUE_DL_CRIT", 50),
        unit="tasks",
        name="queue_dead_letter",
    )
    """Dead letter queue count: 10 warn, 50 critical"""

    @classmethod
    def get_all(cls) -> dict[str, Threshold]:
        """Get all thresholds as dict."""
        return {
            name: value
            for name, value in vars(cls).items()
            if isinstance(value, Threshold)
        }
