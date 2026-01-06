"""
Add missing database indexes for performance optimization.

Run: PYTHONPATH=. poetry run python scripts/add_performance_indexes.py

Expected improvements:
- /market/listings: 10-50x faster
- /market/overview: 4-5x faster
- Deals tab: 2-5x faster
"""

from sqlalchemy import text
from app.db import engine


def add_performance_indexes():
    """Add missing indexes to optimize slow queries."""

    indexes = [
        # 1. Listings query optimization (listing_type + platform + dates)
        # Speeds up: GET /market/listings endpoint
        (
            "idx_marketprice_listings_query",
            """
            CREATE INDEX IF NOT EXISTS idx_marketprice_listings_query
            ON marketprice (listing_type, platform, listed_at DESC NULLS LAST, sold_date DESC NULLS LAST)
            WHERE listing_type IS NOT NULL
            """,
        ),
        # 2. Scraped_at index for freshness filtering
        # Speeds up: Deals tab, recent listings queries
        (
            "idx_marketprice_scraped_at",
            """
            CREATE INDEX IF NOT EXISTS idx_marketprice_scraped_at
            ON marketprice (scraped_at DESC)
            """,
        ),
        # 3. COALESCE(sold_date, scraped_at) for sold listings
        # Speeds up: Floor price, VWAP calculations
        (
            "idx_marketprice_sold_date_fallback",
            """
            CREATE INDEX IF NOT EXISTS idx_marketprice_sold_date_fallback
            ON marketprice (card_id, listing_type, COALESCE(sold_date, scraped_at) DESC)
            WHERE listing_type = 'sold'
            """,
        ),
        # 4. Platform + listing_type composite for platform filtering
        # Speeds up: eBay vs Blokpax filtering
        (
            "idx_marketprice_platform_type",
            """
            CREATE INDEX IF NOT EXISTS idx_marketprice_platform_type
            ON marketprice (platform, listing_type, card_id)
            """,
        ),
        # 5. Active listings by card for deals detection
        # Speeds up: Deals tab, active inventory queries
        (
            "idx_marketprice_active_by_card",
            """
            CREATE INDEX IF NOT EXISTS idx_marketprice_active_by_card
            ON marketprice (card_id, price, scraped_at DESC)
            WHERE listing_type = 'active'
            """,
        ),
    ]

    print("Adding performance indexes to marketprice table...")
    print("=" * 60)

    with engine.begin() as conn:
        for name, sql in indexes:
            try:
                print(f"\n Creating: {name}")
                conn.execute(text(sql))
                print(f" ✓ {name} created successfully")
            except Exception as e:
                if "already exists" in str(e).lower():
                    print(f" - {name} already exists (skipping)")
                else:
                    print(f" ✗ Error creating {name}: {e}")

    print("\n" + "=" * 60)
    print("Index creation complete!")
    print("\nRun EXPLAIN ANALYZE on slow queries to verify improvements.")


if __name__ == "__main__":
    add_performance_indexes()
