"""
Migration script to add marketing_emails_enabled column to the user table.

This allows users to unsubscribe from marketing/digest emails while still
receiving transactional emails (password reset, security alerts, etc.).

Run with: python scripts/migrate_marketing_emails.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db import engine


def migrate():
    """Add marketing_emails_enabled column to user table."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(
            text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user'
            AND column_name = 'marketing_emails_enabled'
        """)
        )
        existing = result.fetchone()

        if existing:
            print("marketing_emails_enabled column already exists")
        else:
            print("Adding marketing_emails_enabled column...")
            conn.execute(
                text("""
                ALTER TABLE "user"
                ADD COLUMN marketing_emails_enabled BOOLEAN DEFAULT TRUE NOT NULL
            """)
            )
            print("  - Created column with default TRUE")

        conn.commit()
        print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
