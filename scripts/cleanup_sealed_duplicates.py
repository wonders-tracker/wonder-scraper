#!/usr/bin/env python3
"""
Cleanup duplicate sealed product listings using smart matching scoring.

This script finds listings that exist under multiple cards (same external_id)
and keeps only the best match based on score_sealed_match().

Usage:
    python scripts/cleanup_sealed_duplicates.py --dry-run        # Preview what would be cleaned
    python scripts/cleanup_sealed_duplicates.py --execute        # Actually delete duplicates
"""

import argparse
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from sqlmodel import Session, select
from sqlalchemy import text

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine
from app.models.market import MarketPrice
from app.models.card import Card
from app.scraper.ebay import score_sealed_match


def find_duplicates(session: Session) -> dict:
    """
    Find all external_ids that exist under multiple card_ids.
    Returns: {external_id: [(mp_id, card_id, title, card_name, product_type), ...]}
    """
    # Query to find duplicated external_ids
    dupes_query = text("""
        SELECT mp.external_id, mp.id, mp.card_id, mp.title, c.name, c.product_type
        FROM marketprice mp
        JOIN card c ON mp.card_id = c.id
        WHERE mp.external_id IN (
            SELECT external_id
            FROM marketprice
            WHERE external_id IS NOT NULL
            GROUP BY external_id
            HAVING COUNT(DISTINCT card_id) > 1
        )
        ORDER BY mp.external_id, mp.id
    """)

    results = session.execute(dupes_query).all()

    # Group by external_id
    duplicates = defaultdict(list)
    for ext_id, mp_id, card_id, title, card_name, product_type in results:
        duplicates[ext_id].append({
            "mp_id": mp_id,
            "card_id": card_id,
            "title": title,
            "card_name": card_name,
            "product_type": product_type
        })

    return duplicates


def cleanup_duplicates(dry_run: bool = True):
    """
    Find and clean up duplicate listings using smart matching.
    """
    with Session(engine) as session:
        duplicates = find_duplicates(session)

        print(f"\n{'#'*80}")
        print(f"  SEALED PRODUCT DUPLICATE CLEANUP - {'DRY RUN' if dry_run else 'EXECUTING'}")
        print(f"  Started: {datetime.now()}")
        print(f"{'#'*80}")
        print(f"\n  Found {len(duplicates)} external_ids with duplicates across cards\n")

        stats = {
            "kept": 0,
            "deleted": 0,
            "errors": 0
        }

        for ext_id, entries in duplicates.items():
            title = entries[0]["title"]
            print(f"\n{'='*80}")
            print(f"  external_id: {ext_id}")
            print(f"  Title: {title[:70]}...")
            print(f"  Entries: {len(entries)}")
            print("-" * 80)

            # Score each entry
            scored = []
            for entry in entries:
                score = score_sealed_match(title, entry["card_name"], entry["product_type"])
                scored.append({**entry, "score": score})
                print(f"    [{entry['product_type']:8}] {entry['card_name'][:40]:40} -> Score: {score:4}")

            # Find the best match (highest score)
            scored.sort(key=lambda x: x["score"], reverse=True)
            best = scored[0]
            to_delete = scored[1:]

            print()
            print(f"  KEEP: ID {best['mp_id']} -> {best['card_name']} (score: {best['score']})")

            for entry in to_delete:
                mp_id = entry["mp_id"]
                if dry_run:
                    print(f"  [DRY RUN] DELETE ID {mp_id} -> {entry['card_name']} (score: {entry['score']})")
                    stats["deleted"] += 1
                else:
                    try:
                        session.execute(
                            text("DELETE FROM marketprice WHERE id = :id"),
                            {"id": mp_id}
                        )
                        session.commit()
                        print(f"  [DELETED] ID {mp_id} -> {entry['card_name']}")
                        stats["deleted"] += 1
                    except Exception as e:
                        session.rollback()
                        print(f"  [ERROR] ID {mp_id}: {e}")
                        stats["errors"] += 1

            stats["kept"] += 1

        # Summary
        print(f"\n{'='*80}")
        print("  SUMMARY")
        print(f"{'='*80}")
        print(f"  Duplicate groups processed: {len(duplicates)}")
        print(f"  Records kept (best match): {stats['kept']}")
        print(f"  {'Would delete' if dry_run else 'Deleted'}: {stats['deleted']}")
        print(f"  Errors: {stats['errors']}")

        if dry_run:
            print(f"\n  Run with --execute to apply these changes")


def main():
    parser = argparse.ArgumentParser(description="Cleanup duplicate sealed product listings")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be deleted")
    parser.add_argument("--execute", action="store_true", help="Actually delete duplicates")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        return

    dry_run = not args.execute
    cleanup_duplicates(dry_run=dry_run)


if __name__ == "__main__":
    main()
