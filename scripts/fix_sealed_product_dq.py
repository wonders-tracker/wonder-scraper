#!/usr/bin/env python3
"""
Fix Data Quality issues for sealed products (Packs, Bundles, Lots, Boxes).

Issues addressed:
1. Card Mismatch: Play Bundle listings assigned to Pack cards instead of Bundle card
2. Quantity Detection: qty=1 but title indicates multiple items
3. Price Normalization: When fixing quantity, divide price to get unit price

Usage:
    python scripts/fix_sealed_product_dq.py --dry-run        # Preview all fixes
    python scripts/fix_sealed_product_dq.py --execute        # Apply all fixes
    python scripts/fix_sealed_product_dq.py --execute --fix card-mismatch  # Only fix card mismatches
    python scripts/fix_sealed_product_dq.py --execute --fix quantity       # Only fix quantities
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Tuple

from sqlmodel import Session, select
from sqlalchemy import text

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine
from app.models.market import MarketPrice
from app.models.card import Card


# Quantity detection patterns for sealed products
QUANTITY_PATTERNS = [
    (r'^(\d+)\s*x\s+', 'start Nx'),           # "2x Bundle" at start
    (r'^x\s*(\d+)\s+', 'start xN'),           # "X3 Bundle" at start
    (r'\bx\s*(\d+)\s*$', 'end xN'),           # "Bundle x4" at end
    (r'\b(\d+)\s*x\s*$', 'end Nx'),           # "Bundle 2x" at end (less common)
    (r'\blot\s+of\s+(\d+)\b', 'lot of N'),    # "lot of 4"
    (r'\bset\s+of\s+(\d+)\b', 'set of N'),    # "set of 2"
    (r'^(\d+)\s+wonders\b', 'N Wonders'),     # "2 Wonders of..." at start
    (r'\b(\d+)\s*ct\b', 'Nct'),               # "5ct"
    (r'\(x(\d+)\)', 'parentheses (xN)'),      # "(x2)"
]


def detect_quantity_from_title(title: str) -> Tuple[int, str]:
    """
    Detect quantity from title using patterns.
    Returns (quantity, pattern_matched) or (1, None) if no match.
    """
    title_lower = title.lower()

    for pattern, name in QUANTITY_PATTERNS:
        match = re.search(pattern, title_lower)
        if match:
            qty = int(match.group(1))
            # Sanity check - skip if qty looks like a year or unreasonable
            if 2 <= qty <= 50 and not (2020 <= qty <= 2030):
                return qty, name

    return 1, None


def get_bundle_card_id(session: Session) -> Optional[int]:
    """Get the card_id for Existence Play Booster Bundle."""
    card = session.exec(
        select(Card).where(Card.name == "Existence Play Booster Bundle")
    ).first()
    return card.id if card else None


def fix_card_mismatches(session: Session, dry_run: bool = True) -> dict:
    """
    Fix listings where Play Bundle is assigned to Pack card instead of Bundle card.
    Also handles duplicates - keeps the Bundle copy, deletes Pack copies.
    """
    results = {"fixed": 0, "skipped": 0, "errors": 0, "deleted": 0}

    bundle_card_id = get_bundle_card_id(session)
    if not bundle_card_id:
        print("ERROR: Could not find 'Existence Play Booster Bundle' card")
        return results

    print(f"\n{'='*80}")
    print("  FIX 1: CARD MISMATCH (Play Bundle -> Pack)")
    print(f"{'='*80}")
    print(f"  Target card_id: {bundle_card_id} (Existence Play Booster Bundle)")
    print()

    # Find Pack listings that mention "play bundle" or "blaster box"
    pack_cards = session.exec(select(Card.id).where(Card.product_type == "Pack")).all()
    pack_card_ids = [c for c in pack_cards]

    mismatched = session.exec(
        select(MarketPrice)
        .where(MarketPrice.platform == "ebay")
        .where(MarketPrice.card_id.in_(pack_card_ids))
        .where(
            (MarketPrice.title.ilike("%play bundle%")) |
            (MarketPrice.title.ilike("%blaster box%"))
        )
    ).all()

    print(f"  Found {len(mismatched)} listings to process")
    print("-" * 80)

    for mp in mismatched:
        # Check it's actually a bundle listing (not just mentioning packs from a bundle)
        title_lower = mp.title.lower()

        # Skip if it's clearly about individual packs
        if "booster pack" in title_lower and "bundle" not in title_lower:
            results["skipped"] += 1
            continue

        # Check if a copy already exists with the correct card_id (Bundle)
        existing = session.exec(
            select(MarketPrice)
            .where(MarketPrice.external_id == mp.external_id)
            .where(MarketPrice.card_id == bundle_card_id)
        ).first()

        if existing:
            # Duplicate - delete this one, keep the Bundle copy
            mp_id = mp.id
            mp_title = mp.title[:55]
            existing_id = existing.id
            if dry_run:
                print(f"  [DRY RUN] DELETE ID {mp_id}: duplicate of ID {existing_id} (Bundle copy exists)")
                print(f"            Title: {mp_title}...")
                results["deleted"] += 1
            else:
                try:
                    session.execute(
                        text("DELETE FROM marketprice WHERE id = :id"),
                        {"id": mp_id}
                    )
                    session.commit()
                    print(f"  [DELETED] ID {mp_id}: duplicate (kept ID {existing_id})")
                    results["deleted"] += 1
                except Exception as e:
                    session.rollback()
                    print(f"  [ERROR] ID {mp_id}: {e}")
                    results["errors"] += 1
        else:
            # No Bundle copy exists - update this one
            if dry_run:
                print(f"  [DRY RUN] ID {mp.id}: card_id {mp.card_id} -> {bundle_card_id}")
                print(f"            Title: {mp.title[:55]}...")
                results["fixed"] += 1
            else:
                try:
                    session.execute(
                        text("UPDATE marketprice SET card_id = :card_id WHERE id = :id"),
                        {"card_id": bundle_card_id, "id": mp.id}
                    )
                    session.commit()
                    print(f"  [FIXED] ID {mp.id}: card_id -> {bundle_card_id}")
                    results["fixed"] += 1
                except Exception as e:
                    session.rollback()
                    print(f"  [ERROR] ID {mp.id}: {e}")
                    results["errors"] += 1

    return results


def fix_quantities(session: Session, dry_run: bool = True) -> dict:
    """
    Fix quantity detection failures and normalize prices.
    When qty changes from 1 to N, divide price by N.
    """
    results = {"fixed": 0, "skipped": 0, "errors": 0, "deleted": 0}

    print(f"\n{'='*80}")
    print("  FIX 2: QUANTITY DETECTION (with price normalization)")
    print(f"{'='*80}")
    print("  Note: price = total_price / quantity (per-unit price)")
    print()

    # Get all sealed product listings with qty=1
    sealed_types = ['Pack', 'Bundle', 'Box', 'Lot']

    listings = session.exec(
        select(MarketPrice, Card.product_type)
        .join(Card, MarketPrice.card_id == Card.id)
        .where(MarketPrice.platform == "ebay")
        .where(Card.product_type.in_(sealed_types))
        .where(MarketPrice.quantity == 1)
    ).all()

    print(f"  Checking {len(listings)} listings with qty=1...")
    print("-" * 80)

    fixes_by_pattern = {}

    for mp, product_type in listings:
        detected_qty, pattern = detect_quantity_from_title(mp.title)

        if detected_qty > 1:
            # Calculate new unit price
            old_price = mp.price
            new_price = round(old_price / detected_qty, 2)

            if pattern not in fixes_by_pattern:
                fixes_by_pattern[pattern] = []
            fixes_by_pattern[pattern].append((mp.id, mp.title, detected_qty, old_price, new_price))

            if dry_run:
                print(f"  [DRY RUN] ID {mp.id} ({pattern}):")
                print(f"            qty: 1 -> {detected_qty}")
                print(f"            price: ${old_price:.2f} -> ${new_price:.2f} (per unit)")
                print(f"            Title: {mp.title[:55]}...")
                print()
                results["fixed"] += 1
            else:
                try:
                    session.execute(
                        text("""
                            UPDATE marketprice
                            SET quantity = :qty, price = :price
                            WHERE id = :id
                        """),
                        {"qty": detected_qty, "price": new_price, "id": mp.id}
                    )
                    session.commit()
                    print(f"  [FIXED] ID {mp.id}: qty=1->{detected_qty}, price=${old_price:.2f}->${new_price:.2f}")
                    results["fixed"] += 1
                except Exception as e:
                    session.rollback()
                    print(f"  [ERROR] ID {mp.id}: {e}")
                    results["errors"] += 1

    # Summary by pattern
    print()
    print("  Summary by pattern:")
    for pattern, items in sorted(fixes_by_pattern.items(), key=lambda x: -len(x[1])):
        print(f"    {pattern}: {len(items)} fixes")

    return results


def main():
    parser = argparse.ArgumentParser(description="Fix sealed product DQ issues")
    parser.add_argument("--dry-run", action="store_true", help="Preview fixes without applying")
    parser.add_argument("--execute", action="store_true", help="Apply fixes")
    parser.add_argument("--fix", choices=["card-mismatch", "quantity", "all"],
                        default="all", help="Which fix to apply")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        return

    dry_run = not args.execute

    print(f"\n{'#'*80}")
    print(f"  SEALED PRODUCT DQ FIX - {'DRY RUN' if dry_run else 'EXECUTING'}")
    print(f"  Started: {datetime.now()}")
    print(f"{'#'*80}")

    total_results = {"fixed": 0, "skipped": 0, "errors": 0, "deleted": 0}

    with Session(engine) as session:
        # Fix 1: Card mismatches
        if args.fix in ["card-mismatch", "all"]:
            r = fix_card_mismatches(session, dry_run)
            for k in total_results:
                total_results[k] += r[k]

        # Fix 2: Quantity detection
        if args.fix in ["quantity", "all"]:
            r = fix_quantities(session, dry_run)
            for k in total_results:
                total_results[k] += r[k]

    # Final summary
    print(f"\n{'='*80}")
    print("  SUMMARY")
    print(f"{'='*80}")
    print(f"  {'Would fix' if dry_run else 'Fixed'}: {total_results['fixed']}")
    print(f"  {'Would delete' if dry_run else 'Deleted'}: {total_results['deleted']}")
    print(f"  Skipped: {total_results['skipped']}")
    print(f"  Errors: {total_results['errors']}")

    if dry_run:
        print(f"\n  Run with --execute to apply these fixes")


if __name__ == "__main__":
    main()
