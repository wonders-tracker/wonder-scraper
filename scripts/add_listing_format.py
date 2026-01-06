"""
Migration: Add listing_format column to marketprice table.

This column stores the eBay listing format:
- 'auction' - Auction listing (has bids or shows auction indicators)
- 'buy_it_now' - Fixed price Buy It Now listing
- 'best_offer' - Buy It Now with Best Offer option
- NULL - Unknown format

Run: PYTHONPATH=. poetry run python scripts/add_listing_format.py
"""

from sqlmodel import text, Session
from app.db import engine


def migrate():
    print("Migrating: Adding listing_format to marketprice table...")
    with Session(engine) as session:
        try:
            # Add listing_format column if it doesn't exist
            session.exec(
                text("""
                ALTER TABLE marketprice
                ADD COLUMN IF NOT EXISTS listing_format VARCHAR;
            """)
            )

            session.commit()
            print("Migration successful!")
            print("  - Added column: listing_format (VARCHAR)")
        except Exception as e:
            session.rollback()
            print(f"Migration failed: {e}")
            raise


if __name__ == "__main__":
    migrate()
