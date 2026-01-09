#!/usr/bin/env python3
"""
Migration script for observability tables.

Creates:
- scraper_job_log: Track scraper job executions
- metrics_snapshot: Periodic metric snapshots
- request_trace: Sample slow/error requests

Run: python scripts/migrate_observability.py

Tables are idempotent (IF NOT EXISTS).
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from sqlmodel import Session
from app.db import engine


def migrate() -> None:
    """Create observability tables with indexes."""
    with Session(engine) as session:
        print("Creating observability tables...")

        # Scraper job log - detailed per-job tracking
        session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS scraper_job_log (
                id SERIAL PRIMARY KEY,
                job_name VARCHAR(100) NOT NULL,
                started_at TIMESTAMP WITH TIME ZONE NOT NULL,
                completed_at TIMESTAMP WITH TIME ZONE,
                status VARCHAR(20) NOT NULL,
                cards_processed INT DEFAULT 0,
                successful INT DEFAULT 0,
                failed INT DEFAULT 0,
                db_errors INT DEFAULT 0,
                duration_seconds FLOAT,
                error_message VARCHAR(1000),
                error_type VARCHAR(100),
                job_metadata JSONB,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """
            )
        )
        print("  - scraper_job_log table created")

        # Indexes for scraper_job_log
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_scraper_job_name
            ON scraper_job_log(job_name);
        """
            )
        )
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_scraper_started_at
            ON scraper_job_log(started_at DESC);
        """
            )
        )
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_scraper_status
            ON scraper_job_log(status);
        """
            )
        )
        print("  - scraper_job_log indexes created")

        # Metrics snapshot - periodic dumps of in-memory metrics
        session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS metrics_snapshot (
                id SERIAL PRIMARY KEY,
                snapshot_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
                metric_type VARCHAR(50) NOT NULL,
                metric_name VARCHAR(100) NOT NULL,
                metric_value JSONB NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """
            )
        )
        print("  - metrics_snapshot table created")

        # Indexes for metrics_snapshot
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_metrics_snapshot_at
            ON metrics_snapshot(snapshot_at DESC);
        """
            )
        )
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_metrics_type
            ON metrics_snapshot(metric_type);
        """
            )
        )
        print("  - metrics_snapshot indexes created")

        # Request trace - sample of slow/failed requests
        session.execute(
            text(
                """
            CREATE TABLE IF NOT EXISTS request_trace (
                id SERIAL PRIMARY KEY,
                request_id VARCHAR(50) UNIQUE NOT NULL,
                correlation_id VARCHAR(50),
                method VARCHAR(10) NOT NULL,
                path VARCHAR(500) NOT NULL,
                status_code INT,
                duration_ms FLOAT,
                user_id INT,
                error_type VARCHAR(100),
                error_message VARCHAR(1000),
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
        """
            )
        )
        print("  - request_trace table created")

        # Indexes for request_trace
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_request_trace_created_at
            ON request_trace(created_at DESC);
        """
            )
        )
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_request_trace_duration
            ON request_trace(duration_ms DESC);
        """
            )
        )
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_request_trace_error
            ON request_trace(error_type);
        """
            )
        )
        session.execute(
            text(
                """
            CREATE INDEX IF NOT EXISTS idx_request_trace_user
            ON request_trace(user_id);
        """
            )
        )
        print("  - request_trace indexes created")

        session.commit()
        print("\nObservability tables created successfully!")


def cleanup_old_data(days: int = 30) -> int:
    """
    Clean up old observability data.

    Args:
        days: Keep data for this many days (default: 30)

    Returns:
        Number of rows deleted
    """
    with Session(engine) as session:
        # Use parameterized query to prevent SQL injection
        result = session.execute(
            text(
                """
            WITH deleted_jobs AS (
                DELETE FROM scraper_job_log
                WHERE created_at < NOW() - (:days * INTERVAL '1 day')
                RETURNING id
            ),
            deleted_snapshots AS (
                DELETE FROM metrics_snapshot
                WHERE created_at < NOW() - (:days * INTERVAL '1 day')
                RETURNING id
            ),
            deleted_traces AS (
                DELETE FROM request_trace
                WHERE created_at < NOW() - (:days * INTERVAL '1 day')
                RETURNING id
            )
            SELECT
                (SELECT COUNT(*) FROM deleted_jobs) +
                (SELECT COUNT(*) FROM deleted_snapshots) +
                (SELECT COUNT(*) FROM deleted_traces) as total
        """
            ),
            {"days": days},
        )
        total = result.scalar() or 0
        session.commit()
        return total


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage observability tables")
    parser.add_argument(
        "--cleanup",
        type=int,
        metavar="DAYS",
        help="Clean up data older than DAYS",
    )
    args = parser.parse_args()

    if args.cleanup:
        deleted = cleanup_old_data(args.cleanup)
        print(f"Deleted {deleted} old observability records")
    else:
        migrate()
