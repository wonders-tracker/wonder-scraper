"""
Add subscription_product_type column to user table.

This column tracks whether the user subscribed to 'pro' or 'api' product.
"""
import sys
sys.path.insert(0, ".")

from sqlmodel import text
from app.db import engine

def migrate():
    """Add subscription_product_type column to user table."""
    with engine.connect() as conn:
        # Check if column already exists
        result = conn.execute(text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'user'
            AND column_name = 'subscription_product_type'
        """))

        if result.fetchone():
            print("Column subscription_product_type already exists, skipping...")
            return

        # Add the column
        conn.execute(text("""
            ALTER TABLE "user"
            ADD COLUMN subscription_product_type VARCHAR NULL
        """))
        conn.commit()
        print("Added subscription_product_type column to user table")

if __name__ == "__main__":
    migrate()
