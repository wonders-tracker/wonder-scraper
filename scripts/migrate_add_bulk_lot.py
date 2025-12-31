#!/usr/bin/env python3
"""
Migration: Add is_bulk_lot column to marketprice table.

This adds a boolean flag to identify bulk lot listings that should be
excluded from Fair Market Price (FMP) calculations.

Usage:
    python scripts/migrate_add_bulk_lot.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import text, Session
from app.db import engine


def migrate():
    """Add is_bulk_lot column to marketprice table."""
    with Session(engine) as session:
        print("Adding is_bulk_lot column to marketprice table...")

        try:
            # Add the column with default False
            session.exec(
                text(
                    """
                    ALTER TABLE marketprice
                    ADD COLUMN IF NOT EXISTS is_bulk_lot BOOLEAN NOT NULL DEFAULT FALSE
                    """
                )
            )
            print("  Added is_bulk_lot column")

            # Create index for efficient filtering
            session.exec(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_marketprice_is_bulk_lot
                    ON marketprice (is_bulk_lot)
                    """
                )
            )
            print("  Created index ix_marketprice_is_bulk_lot")

            session.commit()
            print("\nMigration complete!")

        except Exception as e:
            print(f"Error during migration: {e}")
            session.rollback()
            raise


if __name__ == "__main__":
    migrate()
