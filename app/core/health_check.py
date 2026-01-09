"""
Unified health check system.

Aggregates health from all subsystems with threshold-based alerting.

Usage:
    from app.core.health_check import HealthCheck

    # Full health check
    health = HealthCheck.check_overall_health()
    # Returns: {"status": "healthy", "components": {...}}

    # Component-specific checks
    scraper = HealthCheck.check_scraper_health()
    circuits = HealthCheck.check_circuit_health()
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import structlog

from sqlmodel import Session, select, func
from app.db import engine
from app.models.market import MarketPrice
from app.core.health_thresholds import HealthThresholds, check_threshold, ThresholdStatus
from app.core.circuit_breaker import CircuitBreakerRegistry
from app.core.perf_metrics import perf_metrics

logger = structlog.get_logger(__name__)

__all__ = ["HealthCheck", "ThresholdStatus"]


class HealthCheck:
    """
    Unified health check system.

    Aggregates health from:
    - Scrapers (data freshness, error rates)
    - Performance (API latency)
    - Circuit breakers (service availability)
    - Database (connectivity)

    Each check returns:
    - status: "ok", "warning", or "critical"
    - Additional context for debugging
    """

    @staticmethod
    def check_scraper_health() -> Dict[str, Any]:
        """
        Check scraper subsystem health.

        Checks:
        - Time since last scrape (sold listings)
        - Job metrics from persistent store
        """
        try:
            with Session(engine) as session:
                now = datetime.now(timezone.utc)

                # Check last scrape time for sold listings
                last_sold = session.execute(
                    select(func.max(MarketPrice.scraped_at)).where(
                        MarketPrice.listing_type == "sold"
                    )
                ).scalar()

                # Check last scrape time for active listings
                last_active = session.execute(
                    select(func.max(MarketPrice.scraped_at)).where(
                        MarketPrice.listing_type == "active"
                    )
                ).scalar()

                if not last_sold:
                    return {
                        "status": "critical",
                        "reason": "No sold listings found",
                        "last_sold_hours_ago": None,
                        "last_active_hours_ago": None,
                    }

                sold_hours_ago = (now - last_sold).total_seconds() / 3600
                active_hours_ago = (
                    (now - last_active).total_seconds() / 3600 if last_active else None
                )

                # Check against thresholds
                status = check_threshold(sold_hours_ago, HealthThresholds.SCRAPER_STALE_HOURS)

                # Get job metrics
                try:
                    from app.core.metrics_persistent import persistent_metrics

                    metrics_summary = persistent_metrics.get_summary()
                except ImportError:
                    from app.core.metrics import scraper_metrics

                    metrics_summary = scraper_metrics.get_summary()

                return {
                    "status": status,
                    "last_sold_hours_ago": round(sold_hours_ago, 1),
                    "last_active_hours_ago": round(active_hours_ago, 1)
                    if active_hours_ago
                    else None,
                    "threshold_warn_hours": HealthThresholds.SCRAPER_STALE_HOURS.warning,
                    "threshold_crit_hours": HealthThresholds.SCRAPER_STALE_HOURS.critical,
                    **metrics_summary,
                }

        except Exception as e:
            logger.error("Scraper health check failed", error=str(e))
            return {
                "status": "critical",
                "reason": f"Health check error: {str(e)}",
            }

    @staticmethod
    def check_performance_health() -> Dict[str, Any]:
        """
        Check API performance health.

        Checks:
        - Request latency (p95)
        - Slow request rate
        """
        try:
            summary = perf_metrics.get_summary()
            slowest = perf_metrics.get_slowest_endpoints(n=5, by="p95")

            slow_pct = summary.get("slow_request_pct", 0)
            slow_rate = slow_pct / 100  # Convert to ratio

            status = check_threshold(slow_rate, HealthThresholds.API_SLOW_REQUEST_RATE)

            return {
                "status": status,
                "total_requests": summary.get("total_requests", 0),
                "slow_request_pct": slow_pct,
                "threshold_warn_pct": HealthThresholds.API_SLOW_REQUEST_RATE.warning * 100,
                "threshold_crit_pct": HealthThresholds.API_SLOW_REQUEST_RATE.critical * 100,
                "slowest_endpoints": [
                    {"endpoint": e["endpoint"], "p95_ms": e["p95_ms"]} for e in slowest
                ],
            }

        except Exception as e:
            logger.error("Performance health check failed", error=str(e))
            return {
                "status": "warning",
                "reason": f"Health check error: {str(e)}",
            }

    @staticmethod
    def check_circuit_health() -> Dict[str, Any]:
        """
        Check circuit breaker health.

        Checks:
        - Circuit states (open = critical)
        """
        try:
            states = CircuitBreakerRegistry.get_all_states()

            open_circuits = [name for name, state in states.items() if state == "open"]
            half_open_circuits = [
                name for name, state in states.items() if state == "half_open"
            ]
            closed_circuits = [
                name for name, state in states.items() if state == "closed"
            ]

            status: ThresholdStatus = "ok"
            if open_circuits:
                status = "critical"
            elif half_open_circuits:
                status = "warning"

            return {
                "status": status,
                "open_circuits": open_circuits,
                "half_open_circuits": half_open_circuits,
                "closed_circuits": closed_circuits,
                "total_circuits": len(states),
            }

        except Exception as e:
            logger.error("Circuit health check failed", error=str(e))
            return {
                "status": "warning",
                "reason": f"Health check error: {str(e)}",
            }

    @staticmethod
    def check_database_health() -> Dict[str, Any]:
        """
        Check database connectivity.

        Simple SELECT 1 to verify connection.
        """
        import time

        try:
            from sqlalchemy import text

            start = time.perf_counter()
            with Session(engine) as session:
                session.execute(text("SELECT 1"))
            duration_ms = (time.perf_counter() - start) * 1000

            status = check_threshold(duration_ms, HealthThresholds.DB_CONNECTION_TIME_MS)

            return {
                "status": status,
                "connection_time_ms": round(duration_ms, 1),
                "threshold_warn_ms": HealthThresholds.DB_CONNECTION_TIME_MS.warning,
                "threshold_crit_ms": HealthThresholds.DB_CONNECTION_TIME_MS.critical,
            }

        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return {
                "status": "critical",
                "reason": f"Database error: {str(e)}",
            }

    @staticmethod
    def check_queue_health() -> Dict[str, Any]:
        """
        Check task queue health (if enabled).

        Checks:
        - Queue depth
        - Dead letter count
        """
        from app.core.config import settings

        if not settings.USE_TASK_QUEUE:
            return {"enabled": False}

        try:
            from sqlalchemy import text

            with Session(engine) as session:
                # Get queue depth by status
                result = session.execute(
                    text(
                        """
                    SELECT status, COUNT(*) as count
                    FROM scrapetask
                    GROUP BY status
                """
                    )
                ).all()

                depth = {row[0]: row[1] for row in result}
                pending = depth.get("PENDING", 0)
                dead_letter = depth.get("FAILED", 0)  # Failed after max retries

                # Check thresholds
                depth_status = check_threshold(pending, HealthThresholds.QUEUE_DEPTH)
                dl_status = check_threshold(dead_letter, HealthThresholds.QUEUE_DEAD_LETTER)

                # Overall status is worst of both
                if depth_status == "critical" or dl_status == "critical":
                    status = "critical"
                elif depth_status == "warning" or dl_status == "warning":
                    status = "warning"
                else:
                    status = "ok"

                return {
                    "enabled": True,
                    "status": status,
                    "pending": pending,
                    "in_progress": depth.get("IN_PROGRESS", 0),
                    "completed": depth.get("COMPLETED", 0),
                    "failed": dead_letter,
                    "threshold_depth_warn": int(HealthThresholds.QUEUE_DEPTH.warning),
                    "threshold_dl_warn": int(HealthThresholds.QUEUE_DEAD_LETTER.warning),
                }

        except Exception as e:
            logger.error("Queue health check failed", error=str(e))
            return {
                "enabled": True,
                "status": "warning",
                "reason": f"Health check error: {str(e)}",
            }

    @staticmethod
    def check_overall_health() -> Dict[str, Any]:
        """
        Aggregate health check across all subsystems.

        Returns unified health status with component details.
        HTTP status should be:
        - 200 for "ok" and "warning"
        - 503 for "critical"
        """
        scraper = HealthCheck.check_scraper_health()
        performance = HealthCheck.check_performance_health()
        circuits = HealthCheck.check_circuit_health()
        database = HealthCheck.check_database_health()
        queue = HealthCheck.check_queue_health()

        # Determine overall status (worst of all components)
        all_statuses = [
            scraper["status"],
            performance["status"],
            circuits["status"],
            database["status"],
        ]

        # Only include queue if enabled
        if queue.get("enabled"):
            all_statuses.append(queue["status"])

        if "critical" in all_statuses:
            overall_status = "critical"
        elif "warning" in all_statuses:
            overall_status = "warning"
        else:
            overall_status = "ok"

        return {
            "status": overall_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "components": {
                "scraper": scraper,
                "performance": performance,
                "circuits": circuits,
                "database": database,
                "queue": queue,
            },
        }
