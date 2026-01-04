#!/usr/bin/env python3
"""
Migration: Add is_meta column to card table.

This adds a boolean flag to identify cards currently played in competitive
tournament decks (meta cards).

Usage:
    python scripts/migrate_add_is_meta.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import text, Session
from app.db import engine


def migrate():
    """Add is_meta column to card table."""
    with Session(engine) as session:
        print("Adding is_meta column to card table...")

        try:
            # Add the column with default False
            session.exec(
                text(
                    """
                    ALTER TABLE card
                    ADD COLUMN IF NOT EXISTS is_meta BOOLEAN NOT NULL DEFAULT FALSE
                    """
                )
            )
            print("  Added is_meta column")

            # Create index for efficient filtering
            session.exec(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS ix_card_is_meta
                    ON card (is_meta)
                    """
                )
            )
            print("  Created index ix_card_is_meta")

            session.commit()
            print("\nMigration complete!")

        except Exception as e:
            print(f"Error during migration: {e}")
            session.rollback()
            raise


if __name__ == "__main__":
    migrate()
