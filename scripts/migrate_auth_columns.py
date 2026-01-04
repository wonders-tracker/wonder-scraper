"""
Migration script to add new auth columns to the user table.

Adds:
- password_reset_token_hash (replaces password_reset_token)
- refresh_token_hash

Run with: python scripts/migrate_auth_columns.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.db import engine


def migrate():
    """Add new auth columns to user table."""
    with engine.connect() as conn:
        # Check if columns already exist
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user'
            AND column_name IN ('password_reset_token_hash', 'refresh_token_hash')
        """))
        existing = {row[0] for row in result}

        # Add password_reset_token_hash if not exists
        if 'password_reset_token_hash' not in existing:
            print("Adding password_reset_token_hash column...")
            conn.execute(text("""
                ALTER TABLE "user"
                ADD COLUMN password_reset_token_hash VARCHAR NULL
            """))
            # Create index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_user_password_reset_token_hash
                ON "user" (password_reset_token_hash)
            """))
            # Migrate existing data (hash existing tokens)
            conn.execute(text("""
                UPDATE "user"
                SET password_reset_token_hash = encode(sha256(password_reset_token::bytea), 'hex')
                WHERE password_reset_token IS NOT NULL
            """))
            print("  - Created column and migrated existing data")
        else:
            print("password_reset_token_hash already exists")

        # Add refresh_token_hash if not exists
        if 'refresh_token_hash' not in existing:
            print("Adding refresh_token_hash column...")
            conn.execute(text("""
                ALTER TABLE "user"
                ADD COLUMN refresh_token_hash VARCHAR NULL
            """))
            # Create index
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS ix_user_refresh_token_hash
                ON "user" (refresh_token_hash)
            """))
            print("  - Created column and index")
        else:
            print("refresh_token_hash already exists")

        # Drop old password_reset_token column if it exists and new one is in place
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user'
            AND column_name = 'password_reset_token'
        """))
        if result.fetchone() and 'password_reset_token_hash' in existing or 'password_reset_token_hash' not in existing:
            # Keep old column for now during transition
            print("Note: Old password_reset_token column kept for backwards compatibility")
            print("  - Can be dropped later with: ALTER TABLE \"user\" DROP COLUMN password_reset_token")

        conn.commit()
        print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
