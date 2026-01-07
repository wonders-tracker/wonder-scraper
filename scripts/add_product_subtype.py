"""
Migration: Add product_subtype column to marketprice table.

This column categorizes sealed products into subtypes like:
- Collector Booster Box, Case
- Play Bundle, Blaster Box, Serialized Advantage, Starter Set
- Collector Booster Pack, Play Booster Pack, Silver Pack
- Lot, Bulk

Run: python -m scripts.add_product_subtype
"""

from sqlmodel import text, Session
from app.db import engine


def migrate():
    print("Migrating: Adding product_subtype to marketprice table...")
    with Session(engine) as session:
        try:
            # Add product_subtype column if it doesn't exist
            session.exec(
                text("""
                ALTER TABLE marketprice
                ADD COLUMN IF NOT EXISTS product_subtype VARCHAR;
            """)
            )

            # Add index on product_subtype for faster queries
            session.exec(
                text("""
                CREATE INDEX IF NOT EXISTS ix_marketprice_product_subtype
                ON marketprice (product_subtype);
            """)
            )

            session.commit()
            print("Migration successful!")
            print("  - Added column: product_subtype (VARCHAR)")
            print("  - Added index: ix_marketprice_product_subtype")
        except Exception as e:
            session.rollback()
            print(f"Migration failed: {e}")
            raise


if __name__ == "__main__":
    migrate()
