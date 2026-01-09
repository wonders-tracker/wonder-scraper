#!/usr/bin/env python3
"""
Migration: Drop legacy 'variant' column from marketprice table.

The 'variant' column was always set to 'Classic Paper' and is not used.
The 'treatment' column contains the actual variant/treatment information.

Run with: python scripts/migrate_drop_variant.py
"""

import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.db import engine


def migrate():
    """Drop the legacy variant column from marketprice table."""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'marketprice' AND column_name = 'variant'
        """))

        if not result.fetchone():
            print("Column 'variant' does not exist in marketprice table.")
            return

        # Verify all values are 'Classic Paper' (safety check)
        result = conn.execute(text("""
            SELECT DISTINCT variant FROM marketprice WHERE variant != 'Classic Paper'
        """))
        non_classic = result.fetchall()
        if non_classic:
            print(f"Warning: Found non-'Classic Paper' values: {non_classic}")
            print("Aborting migration. Please review these values first.")
            return

        # Drop the column
        print("Dropping 'variant' column from marketprice table...")
        conn.execute(text("ALTER TABLE marketprice DROP COLUMN variant"))
        conn.commit()
        print("Migration complete! 'variant' column removed.")


if __name__ == "__main__":
    migrate()
