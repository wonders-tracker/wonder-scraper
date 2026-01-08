#!/usr/bin/env python3
"""
Migration: Add performance indexes to marketprice and blokpaxsale tables.

Addresses performance issues identified in API endpoints:
1. (card_id, platform) - for platform-filtered floor price queries
2. (card_id, listed_at) - for time-filtered active listings
3. (filled_at) on blokpaxsale - for sales count/volume aggregations

Usage:
    python scripts/migrate_add_performance_indexes.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import text, Session
from app.db import engine


def migrate():
    """Add performance indexes for common query patterns."""
    with Session(engine) as session:
        print("Adding performance indexes...")

        indexes = [
            # MarketPrice indexes
            (
                "ix_marketprice_card_platform",
                "marketprice",
                "(card_id, platform)",
                "Platform-filtered floor prices",
            ),
            (
                "ix_marketprice_card_listed_at",
                "marketprice",
                "(card_id, listed_at DESC NULLS LAST)",
                "Time-filtered active listings",
            ),
            (
                "ix_marketprice_card_sold_date",
                "marketprice",
                "(card_id, sold_date DESC NULLS LAST)",
                "Time-filtered sold listings",
            ),
            # BlokpaxSale index
            (
                "ix_blokpaxsale_filled_at",
                "blokpaxsale",
                "(filled_at DESC)",
                "Sales count/volume aggregations",
            ),
        ]

        for index_name, table, columns, description in indexes:
            try:
                session.exec(
                    text(
                        f"""
                        CREATE INDEX IF NOT EXISTS {index_name}
                        ON {table} {columns}
                        """
                    )
                )
                print(f"  Created {index_name} ({description})")
            except Exception as e:
                print(f"  Warning: Could not create {index_name}: {e}")

        session.commit()
        print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
