#!/usr/bin/env python3
"""
Standalone scheduler worker process.

Run this as a separate Railway service for reliable scheduled job execution.
This keeps the scheduler running independently of the web server, preventing
gaps like the Dec 19-30 incident where the scheduler stopped with the web process.

Usage:
    python scripts/run_scheduler_worker.py

Railway Deployment:
    1. Create a new service in Railway pointing to this repo
    2. Set start command: python scripts/run_scheduler_worker.py
    3. Set RUN_SCHEDULER=False on the web service to avoid duplicate jobs
"""

import asyncio
import logging
import signal
import sys
from datetime import datetime, timezone

from app.core.scheduler import scheduler, start_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def handle_shutdown(signum, frame):
    """Graceful shutdown handler."""
    logger.info("Received shutdown signal, stopping scheduler...")
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped.")
    sys.exit(0)


async def main():
    """Main entry point for scheduler worker."""
    logger.info("=" * 50)
    logger.info("SCHEDULER WORKER STARTING")
    logger.info("=" * 50)

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Start the scheduler
    start_scheduler()

    # Try to send Discord notification
    try:
        from app.discord_bot.logger import log_warning

        log_warning(
            "🟢 Scheduler Worker Started",
            f"Worker started at {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        )
    except Exception as e:
        logger.warning(f"Could not send Discord notification: {e}")

    logger.info("Scheduler running. Heartbeat every 5 minutes.")

    # Keep the process alive with periodic heartbeat
    try:
        while True:
            await asyncio.sleep(300)  # 5 minute heartbeat
            if scheduler.running:
                jobs = scheduler.get_jobs()
                logger.info(f"Heartbeat: {len(jobs)} jobs scheduled, scheduler running")
            else:
                logger.error("Scheduler stopped unexpectedly!")
    except asyncio.CancelledError:
        logger.info("Scheduler worker shutting down.")


if __name__ == "__main__":
    asyncio.run(main())
