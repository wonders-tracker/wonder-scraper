"""
Backfill listing_format for existing MarketPrice records.

Since we don't have the original HTML, we infer from available data:
1. bid_count > 0 → 'auction' (definite)
2. Title contains "or best offer" → 'best_offer'
3. Title contains "buy it now" → 'buy_it_now'
4. Active listings with 0 bids → 'buy_it_now' (most likely)
5. Sold listings with 0 bids → NULL (could be BIN or no-bid auction)
"""

import re
from sqlmodel import Session, select, col
from app.db import engine
from app.models.market import MarketPrice


def infer_listing_format(price: MarketPrice) -> str | None:
    """Infer listing format from available data."""
    title_lower = (price.title or "").lower()

    # Definite: has bids = auction
    if (price.bid_count or 0) > 0:
        return "auction"

    # Check title for clues
    # "or best offer" / "obo" → best_offer
    if re.search(r"\bor best offer\b|\bobo\b", title_lower):
        return "best_offer"

    # "buy it now" / "bin" in title → buy_it_now
    if re.search(r"\bbuy it now\b|\bbin\b", title_lower):
        return "buy_it_now"

    # Active listings with 0 bids are most likely BIN
    # (auctions usually have time indicators we'd have captured)
    if price.listing_type == "active" and (price.bid_count or 0) == 0:
        return "buy_it_now"

    # Sold listings with 0 bids - default to buy_it_now
    # Rationale: BIN is the most common format, and if it sold with 0 bids,
    # someone likely just clicked Buy It Now (not won a no-bid auction)
    if price.listing_type == "sold" and (price.bid_count or 0) == 0:
        return "buy_it_now"

    return None


BATCH_SIZE = 1000  # Process in batches to avoid memory issues


def backfill_listing_format(dry_run: bool = False):
    """Backfill listing_format for records that don't have it set."""
    from sqlalchemy import func

    with Session(engine) as session:
        # Get count first
        total_count = session.exec(
            select(func.count(MarketPrice.id)).where(col(MarketPrice.listing_format).is_(None))
        ).one()
        print(f"Found {total_count} prices to process (batches of {BATCH_SIZE}).")

        if total_count == 0:
            print("Nothing to backfill!")
            return

        # Track stats
        stats = {
            "auction": 0,
            "buy_it_now": 0,
            "best_offer": 0,
            "unknown": 0,
        }

        updated_count = 0
        processed = 0

        while True:
            # Fetch batch (use ID ordering for consistent pagination)
            batch = session.exec(
                select(MarketPrice)
                .where(col(MarketPrice.listing_format).is_(None))
                .order_by(MarketPrice.id)
                .limit(BATCH_SIZE)
            ).all()

            if not batch:
                break

            batch_updates = 0
            for price in batch:
                listing_format = infer_listing_format(price)

                if listing_format:
                    stats[listing_format] += 1
                    if not dry_run:
                        price.listing_format = listing_format
                        session.add(price)
                    batch_updates += 1
                else:
                    stats["unknown"] += 1

            # Commit after each batch
            if not dry_run and batch_updates > 0:
                session.commit()

            updated_count += batch_updates
            processed += len(batch)
            print(f"  Processed {processed}/{total_count} ({updated_count} updated)")

        print(f"\n{'[DRY RUN] ' if dry_run else ''}Results:")
        print(f"  Auction:    {stats['auction']:,}")
        print(f"  Buy It Now: {stats['buy_it_now']:,}")
        print(f"  Best Offer: {stats['best_offer']:,}")
        print(f"  Unknown:    {stats['unknown']:,}")
        print(f"\n{'Would update' if dry_run else 'Updated'} {updated_count:,} records.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill listing_format field")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    backfill_listing_format(dry_run=args.dry_run)
