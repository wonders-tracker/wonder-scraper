"""
Worker health monitoring.

Provides health checks and alerting for the scheduler worker service.

Usage:
    # In worker startup
    from app.core.worker_health import worker_heartbeat_loop
    await worker_heartbeat_loop(interval_seconds=300)

    # Check worker health (from API)
    from app.core.worker_health import check_worker_health
    health = await check_worker_health()
"""

from datetime import datetime, timezone, timedelta
from typing import Dict, Any
import asyncio
import structlog

from sqlmodel import Session, select
from app.db import engine
from app.models.observability import ScraperJobLog
from app.core.health_thresholds import HealthThresholds, check_threshold
from app.core.errors import capture_message

logger = structlog.get_logger(__name__)

__all__ = ["check_worker_health", "worker_heartbeat_loop"]


async def check_worker_health() -> Dict[str, Any]:
    """
    Check worker health status.

    Checks:
    - Recent job activity (last 2 hours)
    - Stuck jobs (running > 30 minutes)
    - Failure rate (recent completed jobs)

    Returns:
        Dict with status and details
    """
    try:
        with Session(engine) as session:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(hours=2)

            # Check for recent job activity
            recent_jobs = session.exec(
                select(ScraperJobLog)
                .where(ScraperJobLog.started_at >= cutoff)
                .order_by(ScraperJobLog.started_at.desc())
            ).all()

            if not recent_jobs:
                # No recent jobs - check if worker is running
                hours_since_last = None

                # Find the most recent job ever
                last_job = session.exec(select(ScraperJobLog).order_by(ScraperJobLog.started_at.desc())).first()

                if last_job:
                    hours_since_last = (now - last_job.started_at).total_seconds() / 3600

                status = check_threshold(
                    hours_since_last or 999,
                    HealthThresholds.WORKER_JOB_GAP_HOURS,
                )

                return {
                    "status": status,
                    "reason": "No jobs in last 2 hours",
                    "last_job_at": last_job.started_at.isoformat() if last_job else None,
                    "hours_since_last_job": round(hours_since_last, 1) if hours_since_last else None,
                }

            # Check for stuck jobs (running > 30 minutes)
            stuck_jobs = session.exec(
                select(ScraperJobLog)
                .where(ScraperJobLog.status == "running")
                .where(ScraperJobLog.started_at < now - timedelta(minutes=30))
            ).all()

            if stuck_jobs:
                return {
                    "status": "warning",
                    "reason": f"{len(stuck_jobs)} jobs stuck (running > 30 min)",
                    "stuck_jobs": [
                        {
                            "job_name": j.job_name,
                            "started_at": j.started_at.isoformat(),
                            "minutes_running": int((now - j.started_at).total_seconds() / 60),
                        }
                        for j in stuck_jobs
                    ],
                }

            # Check failure rate
            completed_jobs = [j for j in recent_jobs if j.status in ["completed", "failed"]]

            if completed_jobs:
                failed_count = len([j for j in completed_jobs if j.status == "failed"])
                failure_rate = failed_count / len(completed_jobs)

                status = check_threshold(failure_rate, HealthThresholds.WORKER_JOB_FAILURE_RATE)

                if status != "ok":
                    return {
                        "status": status,
                        "reason": f"High failure rate: {failure_rate:.1%}",
                        "failed_count": failed_count,
                        "total_count": len(completed_jobs),
                        "failure_rate": round(failure_rate, 3),
                    }

            # All checks passed
            return {
                "status": "ok",
                "recent_jobs": len(recent_jobs),
                "last_job_at": recent_jobs[0].started_at.isoformat(),
                "completed_jobs": len(completed_jobs),
            }

    except Exception as e:
        logger.error("Worker health check failed", error=str(e))
        return {
            "status": "warning",
            "reason": f"Health check error: {str(e)}",
        }


async def worker_heartbeat_loop(
    interval_seconds: int = 300,
    alert_on_unhealthy: bool = True,
) -> None:
    """
    Periodic heartbeat that checks worker health and logs.

    This runs in the worker process and:
    - Checks health every interval
    - Logs status (INFO for healthy, WARNING/ERROR for degraded/unhealthy)
    - Optionally sends Discord alerts on unhealthy status

    Args:
        interval_seconds: Heartbeat interval (default 5 minutes)
        alert_on_unhealthy: Whether to send Discord alerts (default True)
    """
    logger.info(
        "Worker heartbeat started",
        interval_seconds=interval_seconds,
        alert_on_unhealthy=alert_on_unhealthy,
    )

    while True:
        try:
            health = await check_worker_health()
            status = health.get("status", "unknown")

            if status == "critical":
                logger.error("Worker health CRITICAL", **health)

                if alert_on_unhealthy:
                    try:
                        from app.discord_bot.logger import log_error

                        log_error(
                            "Worker Unhealthy",
                            f"Reason: {health.get('reason', 'Unknown')}\n"
                            f"Last job: {health.get('last_job_at', 'Never')}",
                        )
                    except Exception:
                        pass  # Discord alert is best-effort

                # Capture in Sentry
                capture_message(
                    "Worker health critical",
                    level="error",
                    context=health,
                )

            elif status == "warning":
                logger.warning("Worker health DEGRADED", **health)

                # Capture in Sentry (warning level)
                capture_message(
                    "Worker health degraded",
                    level="warning",
                    context=health,
                )

            else:
                logger.info("Worker heartbeat", **health)

            await asyncio.sleep(interval_seconds)

        except asyncio.CancelledError:
            logger.info("Worker heartbeat cancelled")
            break
        except Exception as e:
            logger.error("Worker heartbeat error", error=str(e))
            # Continue running, retry after shorter interval
            await asyncio.sleep(60)
