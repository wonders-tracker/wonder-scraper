#!/usr/bin/env python3
"""
Add onboarding_completed column to user table.

Usage:
    python scripts/add_onboarding_column.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import text
from app.db import engine


def add_onboarding_column():
    """Add onboarding_completed column to user table."""
    with engine.connect() as conn:
        # Check if column exists
        result = conn.execute(
            text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user' AND column_name = 'onboarding_completed'
        """)
        )

        if result.fetchone():
            print("Column 'onboarding_completed' already exists")
            return

        # Add column with default false
        conn.execute(
            text("""
            ALTER TABLE "user"
            ADD COLUMN onboarding_completed BOOLEAN DEFAULT FALSE
        """)
        )
        conn.commit()
        print("Added 'onboarding_completed' column to user table")

        # Mark existing users as having completed onboarding (they're already users)
        result = conn.execute(
            text("""
            UPDATE "user" SET onboarding_completed = TRUE
        """)
        )
        conn.commit()
        print(f"Marked {result.rowcount} existing users as onboarding completed")


if __name__ == "__main__":
    add_onboarding_column()
