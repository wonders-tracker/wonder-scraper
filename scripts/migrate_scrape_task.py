#!/usr/bin/env python3
"""
Database migration for ScrapeTask table.

Creates the scrapetask table for persistent task queue management.
This table stores scrape jobs that survive application restarts.

Usage:
    python scripts/migrate_scrape_task.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine

load_dotenv()


MIGRATIONS = [
    # Create the scrapetask table
    """
    CREATE TABLE IF NOT EXISTS scrapetask (
        id SERIAL PRIMARY KEY,
        card_id INTEGER NOT NULL,
        source VARCHAR NOT NULL,
        status VARCHAR NOT NULL DEFAULT 'pending',
        priority INTEGER NOT NULL DEFAULT 0,
        attempts INTEGER NOT NULL DEFAULT 0,
        max_attempts INTEGER NOT NULL DEFAULT 3,
        last_error TEXT,
        created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
        started_at TIMESTAMP WITH TIME ZONE,
        completed_at TIMESTAMP WITH TIME ZONE
    );
    """,
    # Single-column indexes (card_id and status)
    """
    CREATE INDEX IF NOT EXISTS ix_scrapetask_card_id ON scrapetask(card_id);
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_scrapetask_status ON scrapetask(status);
    """,
    # Composite index: Primary queue query (status + priority DESC + created_at)
    """
    CREATE INDEX IF NOT EXISTS ix_scrapetask_queue ON scrapetask(status, priority DESC, created_at);
    """,
    # Composite index: Source-specific queue query
    """
    CREATE INDEX IF NOT EXISTS ix_scrapetask_source_status ON scrapetask(source, status);
    """,
    # Composite index: Stale task detection (in_progress + started_at)
    """
    CREATE INDEX IF NOT EXISTS ix_scrapetask_stale ON scrapetask(status, started_at);
    """,
    # Composite index: Task deduplication (card_id + source + status)
    """
    CREATE INDEX IF NOT EXISTS ix_scrapetask_dedup ON scrapetask(card_id, source, status);
    """,
]


def run_migrations():
    """Run all migrations."""
    print("Running ScrapeTask table migration...")
    print()

    with Session(engine) as session:
        for i, migration in enumerate(MIGRATIONS, 1):
            migration_name = migration.strip().split("\n")[0].strip()
            print(f"[{i}/{len(MIGRATIONS)}] {migration_name[:60]}...")

            try:
                session.exec(text(migration))
                session.commit()
                print("  OK")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print("  SKIP (already exists)")
                else:
                    print(f"  ERROR: {e}")
                    raise

    print()
    print("Migration complete!")
    print()
    print("Table created: scrapetask")
    print("Indexes created:")
    print("  - ix_scrapetask_card_id (card_id)")
    print("  - ix_scrapetask_status (status)")
    print("  - ix_scrapetask_queue (status, priority DESC, created_at)")
    print("  - ix_scrapetask_source_status (source, status)")
    print("  - ix_scrapetask_stale (status, started_at)")
    print("  - ix_scrapetask_dedup (card_id, source, status)")


if __name__ == "__main__":
    run_migrations()
