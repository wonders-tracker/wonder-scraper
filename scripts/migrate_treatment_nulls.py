#!/usr/bin/env python3
"""
Migration script to fix historical treatment data.

Problem:
- Previously, treatment defaulted to "Classic Paper" when not detected
- This mixed "actually Classic Paper" with "unknown treatment" sales
- Floor price calculations became inaccurate

Solution:
- Identify records where treatment is "Classic Paper"
- Check if the title actually contains Classic Paper indicators
- If not, set treatment to NULL (unknown)

Indicators that confirm Classic Paper:
- "classic paper" in title
- "paper" in title (without "stonefoil", "formless", etc.)
- "non-foil" or "non foil" in title

Run with: python scripts/migrate_treatment_nulls.py [--dry-run] [--batch-size N]
"""

import argparse
import logging
import re
import sys
from datetime import datetime, timezone

from sqlalchemy import text

# Add project root to path
sys.path.insert(0, str(__file__.rsplit("/", 2)[0]))

from app.db import engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def is_classic_paper_in_title(title: str) -> bool:
    """
    Check if title contains Classic Paper indicators.

    Returns True if we're confident this is actually Classic Paper.
    """
    if not title:
        return False

    title_lower = title.lower()

    # Explicit Classic Paper mentions
    if "classic paper" in title_lower:
        return True

    # "paper" mention (but not in "stonefoil", "formless", etc.)
    if "paper" in title_lower:
        # Make sure it's not part of another word
        if re.search(r"\bpaper\b", title_lower):
            return True

    # Non-foil indicators
    if "non-foil" in title_lower or "non foil" in title_lower:
        return True

    return False


def has_other_treatment_indicator(title: str) -> bool:
    """
    Check if title contains OTHER treatment indicators.

    If title mentions Foil, Serialized, etc., it shouldn't be Classic Paper.
    """
    if not title:
        return False

    title_lower = title.lower()

    # Foil variants (these should NOT be Classic Paper)
    if "foil" in title_lower or "holo" in title_lower or "refractor" in title_lower:
        return True

    # Serialized
    if "serialized" in title_lower or re.search(r"/\d{2,3}\b", title_lower):
        return True

    # Special variants
    if any(kw in title_lower for kw in [
        "stonefoil", "stone foil", "formless", "prerelease", "promo",
        "proof", "sample", "error", "errata", "ocm"
    ]):
        return True

    return False


def migrate_classic_paper_to_null(dry_run: bool = True, batch_size: int = 1000) -> dict:
    """
    Migrate Classic Paper records to NULL where appropriate.

    Returns stats dict with counts.
    """
    stats = {
        "total_classic_paper": 0,
        "kept_classic_paper": 0,
        "converted_to_null": 0,
        "had_other_treatment": 0,
        "skipped_sealed": 0,
        "errors": 0,
    }

    with engine.connect() as conn:
        # Get total count first
        count_query = text("""
            SELECT COUNT(*) FROM marketprice
            WHERE treatment = 'Classic Paper'
        """)
        result = conn.execute(count_query)
        stats["total_classic_paper"] = result.scalar() or 0
        logger.info(f"Found {stats['total_classic_paper']} records with treatment='Classic Paper'")

        if stats["total_classic_paper"] == 0:
            logger.info("No records to migrate")
            return stats

        # Process in batches
        offset = 0

        while True:
            # Fetch batch of Classic Paper records
            batch_query = text("""
                SELECT id, title, product_subtype
                FROM marketprice
                WHERE treatment = 'Classic Paper'
                ORDER BY id
                LIMIT :limit OFFSET :offset
            """)
            result = conn.execute(batch_query, {"limit": batch_size, "offset": offset})
            rows = result.fetchall()

            if not rows:
                break

            ids_to_nullify = []

            for row in rows:
                id_, title, product_subtype = row[0], row[1], row[2]

                # Skip sealed products (Box, Pack, Bundle, Lot)
                if product_subtype and product_subtype.lower() in ["sealed", "open box"]:
                    stats["skipped_sealed"] += 1
                    continue

                # Check if this really should be Classic Paper
                if is_classic_paper_in_title(title):
                    stats["kept_classic_paper"] += 1
                elif has_other_treatment_indicator(title):
                    # Title mentions another treatment - this is clearly wrong
                    stats["had_other_treatment"] += 1
                    ids_to_nullify.append(id_)
                else:
                    # No treatment indicator found - set to NULL
                    ids_to_nullify.append(id_)

            # Update batch
            if ids_to_nullify and not dry_run:
                try:
                    update_query = text("""
                        UPDATE marketprice
                        SET treatment = NULL
                        WHERE id = ANY(:ids)
                    """)
                    conn.execute(update_query, {"ids": ids_to_nullify})
                    conn.commit()
                    stats["converted_to_null"] += len(ids_to_nullify)
                except Exception as e:
                    logger.error(f"Error updating batch: {e}")
                    stats["errors"] += 1
                    conn.rollback()
            elif ids_to_nullify and dry_run:
                stats["converted_to_null"] += len(ids_to_nullify)

            offset += batch_size
            logger.info(f"Processed {min(offset, stats['total_classic_paper'])}/{stats['total_classic_paper']} records...")

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate Classic Paper treatments to NULL where appropriate")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without modifying database")
    parser.add_argument("--batch-size", type=int, default=1000, help="Batch size for processing (default: 1000)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("Treatment NULL Migration")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("DRY RUN MODE - No changes will be made")

    start_time = datetime.now(timezone.utc)
    stats = migrate_classic_paper_to_null(dry_run=args.dry_run, batch_size=args.batch_size)
    duration = (datetime.now(timezone.utc) - start_time).total_seconds()

    logger.info("=" * 60)
    logger.info("Migration Results")
    logger.info("=" * 60)
    logger.info(f"Total Classic Paper records: {stats['total_classic_paper']}")
    logger.info(f"Kept as Classic Paper (detected): {stats['kept_classic_paper']}")
    logger.info(f"Converted to NULL (unknown): {stats['converted_to_null']}")
    logger.info(f"Had other treatment indicator: {stats['had_other_treatment']}")
    logger.info(f"Skipped (sealed products): {stats['skipped_sealed']}")
    logger.info(f"Errors: {stats['errors']}")
    logger.info(f"Duration: {duration:.1f}s")

    if args.dry_run:
        logger.info("\nThis was a DRY RUN. Run without --dry-run to apply changes.")

    return 0 if stats["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
