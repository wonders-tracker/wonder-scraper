#!/usr/bin/env python3
"""
Migration: Create circuit_breaker_state table for state persistence.

This table stores circuit breaker states to survive deploys/restarts,
preventing immediate retry of failing services after restart.

Usage:
    python scripts/migrate_circuit_breaker_state.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import text, Session, SQLModel
from app.db import engine


def migrate():
    """Create circuit_breaker_state table."""
    with Session(engine) as session:
        print("Creating circuit_breaker_state table...")

        try:
            session.exec(
                text(
                    """
                    CREATE TABLE IF NOT EXISTS circuitbreakerstate (
                        id SERIAL PRIMARY KEY,
                        name VARCHAR NOT NULL UNIQUE,
                        state VARCHAR NOT NULL DEFAULT 'closed',
                        failure_count INTEGER NOT NULL DEFAULT 0,
                        last_failure_at TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                    )
                    """
                )
            )
            session.exec(
                text("CREATE INDEX IF NOT EXISTS ix_circuitbreakerstate_name ON circuitbreakerstate (name)")
            )
            session.commit()
            print("  Created table: circuitbreakerstate")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("  Table already exists, skipping")
            else:
                raise

        print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
