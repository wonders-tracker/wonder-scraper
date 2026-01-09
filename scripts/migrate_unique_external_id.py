#!/usr/bin/env python3
"""
Migration: Add unique constraint on (external_id, platform) to MarketPrice.

This prevents duplicate listings from being scraped. The constraint allows
NULL external_ids (PostgreSQL treats NULLs as distinct).

Steps:
1. Find and remove duplicate entries (keep most recent)
2. Add unique constraint

Usage:
    python scripts/migrate_unique_external_id.py
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import text, Session
from app.db import engine


def migrate():
    """Add unique constraint on (external_id, platform)."""
    with Session(engine) as session:
        # Step 1: Find and count duplicates
        print("Checking for duplicate external_ids...")
        result = session.exec(
            text(
                """
                SELECT external_id, platform, COUNT(*) as cnt
                FROM marketprice
                WHERE external_id IS NOT NULL
                GROUP BY external_id, platform
                HAVING COUNT(*) > 1
                """
            )
        )
        duplicates = list(result)

        if duplicates:
            print(f"  Found {len(duplicates)} duplicate (external_id, platform) combinations")

            # Step 2: Delete duplicates, keeping the most recent (highest id)
            print("  Removing duplicates (keeping most recent)...")
            deleted = session.exec(
                text(
                    """
                    DELETE FROM marketprice
                    WHERE id IN (
                        SELECT id FROM (
                            SELECT id,
                                   ROW_NUMBER() OVER (
                                       PARTITION BY external_id, platform
                                       ORDER BY scraped_at DESC, id DESC
                                   ) as rn
                            FROM marketprice
                            WHERE external_id IS NOT NULL
                        ) ranked
                        WHERE rn > 1
                    )
                    """
                )
            )
            session.commit()
            print(f"  Removed duplicate rows")
        else:
            print("  No duplicates found")

        # Step 3: Add unique constraint
        print("\nAdding unique constraint...")
        try:
            session.exec(
                text(
                    """
                    ALTER TABLE marketprice
                    ADD CONSTRAINT uq_marketprice_external_platform
                    UNIQUE (external_id, platform)
                    """
                )
            )
            session.commit()
            print("  Created unique constraint: uq_marketprice_external_platform")
        except Exception as e:
            if "already exists" in str(e).lower():
                print("  Constraint already exists, skipping")
            else:
                raise

        print("\nMigration complete!")


if __name__ == "__main__":
    migrate()
