#!/usr/bin/env python3
"""
Migration: Add treatment column to blokpaxsale table.

This allows tracking which card treatment (e.g., "Hologram Foil", "Classic Foil")
was sold, enabling better price analysis by variant.

Run with: python scripts/migrate_blokpax_treatment.py
"""

import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.db import engine


def migrate():
    """Add treatment column to blokpaxsale table."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'blokpaxsale' AND column_name = 'treatment'
        """))

        if result.fetchone():
            print("Column 'treatment' already exists in blokpaxsale table.")
            return

        # Add the treatment column
        print("Adding 'treatment' column to blokpaxsale table...")
        conn.execute(text("""
            ALTER TABLE blokpaxsale
            ADD COLUMN treatment VARCHAR(100) DEFAULT NULL
        """))

        # Add index for efficient filtering by treatment
        print("Adding index on treatment column...")
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS ix_blokpaxsale_treatment
            ON blokpaxsale (treatment)
        """))

        conn.commit()
        print("Migration complete!")

        # Show sample of existing sales that could be backfilled
        result = conn.execute(text("""
            SELECT COUNT(*) as total,
                   COUNT(*) FILTER (WHERE treatment IS NOT NULL) as with_treatment
            FROM blokpaxsale
        """))
        row = result.fetchone()
        print(f"\nBlokpaxSale records: {row[0]} total, {row[1]} with treatment")
        print("Note: Existing sales will have treatment=NULL until next scrape.")


if __name__ == "__main__":
    migrate()
