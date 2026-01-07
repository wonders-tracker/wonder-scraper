#!/usr/bin/env python3
"""
Backfill is_bulk_lot flags for existing MarketPrice listings.

This script analyzes existing listing titles and sets the is_bulk_lot flag
for listings that match bulk lot patterns (e.g., "3X - Wonders...", "LOT OF 5").

Usage:
    # Preview changes (dry run)
    python scripts/backfill_bulk_lot_flags.py --dry-run

    # Apply changes
    python scripts/backfill_bulk_lot_flags.py

    # Show verbose output
    python scripts/backfill_bulk_lot_flags.py --verbose
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.models.market import MarketPrice
from app.models.card import Card
from app.scraper.utils import is_bulk_lot
from app.db import engine


def backfill_bulk_lot_flags(dry_run: bool = True, verbose: bool = False) -> dict:
    """
    Backfills is_bulk_lot flag for existing MarketPrice listings.

    Args:
        dry_run: If True, preview changes without committing
        verbose: If True, print each detected bulk lot

    Returns:
        Dict with statistics about the backfill operation
    """
    stats = {
        "total_processed": 0,
        "bulk_lots_found": 0,
        "already_flagged": 0,
        "updated": 0,
        "errors": 0,
    }

    # Cache card product types for efficiency
    card_types: dict[int, str] = {}

    with Session(engine) as session:
        # Pre-fetch all card product types
        cards = session.exec(select(Card)).all()
        for card in cards:
            card_types[card.id] = card.product_type or "Single"

        # Query all listings
        listings = session.exec(select(MarketPrice)).all()
        stats["total_processed"] = len(listings)
        print(f"Processing {len(listings)} listings...")

        for listing in listings:
            try:
                product_type = card_types.get(listing.card_id, "Single")
                detected = is_bulk_lot(listing.title, product_type)

                if detected:
                    stats["bulk_lots_found"] += 1

                    if listing.is_bulk_lot:
                        stats["already_flagged"] += 1
                        continue

                    if verbose or dry_run:
                        prefix = "[DRY RUN] " if dry_run else ""
                        print(f"{prefix}Bulk lot: ${listing.price:.2f} | {listing.title[:70]}...")

                    if not dry_run:
                        listing.is_bulk_lot = True
                        session.add(listing)
                        stats["updated"] += 1

            except Exception as e:
                stats["errors"] += 1
                if verbose:
                    print(f"Error processing listing {listing.id}: {e}")

        if not dry_run:
            session.commit()
            print("\nBackfill complete!")
        else:
            print("\n[DRY RUN] No changes made.")

    return stats


def print_stats(stats: dict, dry_run: bool):
    """Print summary statistics."""
    print("\n" + "=" * 50)
    print("BACKFILL SUMMARY")
    print("=" * 50)
    print(f"Total listings processed: {stats['total_processed']:,}")
    print(f"Bulk lots detected:       {stats['bulk_lots_found']:,}")
    print(f"Already flagged:          {stats['already_flagged']:,}")

    if dry_run:
        print(f"Would update:             {stats['bulk_lots_found'] - stats['already_flagged']:,}")
    else:
        print(f"Updated:                  {stats['updated']:,}")

    if stats["errors"] > 0:
        print(f"Errors:                   {stats['errors']:,}")

    # Calculate percentage
    if stats["total_processed"] > 0:
        pct = (stats["bulk_lots_found"] / stats["total_processed"]) * 100
        print(f"\nBulk lot rate: {pct:.1f}%")


def main():
    parser = argparse.ArgumentParser(description="Backfill is_bulk_lot flags for MarketPrice listings")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without committing to database",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Show each detected bulk lot",
    )
    args = parser.parse_args()

    print("Bulk Lot Backfill Script")
    print("-" * 30)

    if args.dry_run:
        print("Mode: DRY RUN (no changes will be made)\n")
    else:
        print("Mode: LIVE (changes will be committed)\n")
        response = input("Are you sure you want to proceed? (y/N): ")
        if response.lower() != "y":
            print("Aborted.")
            sys.exit(0)

    stats = backfill_bulk_lot_flags(dry_run=args.dry_run, verbose=args.verbose)
    print_stats(stats, args.dry_run)


if __name__ == "__main__":
    main()
