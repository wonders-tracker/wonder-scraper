"""
Backfill product_subtype for existing sealed product listings.

Usage:
    python scripts/backfill_product_subtype.py           # Dry run - show what would be updated
    python scripts/backfill_product_subtype.py --commit  # Actually update the database
"""
import argparse
from sqlmodel import Session, select
from app.db import engine
from app.models.market import MarketPrice
from app.models.card import Card
from app.scraper.ebay import _detect_product_subtype


def backfill_product_subtypes(commit: bool = False):
    """Backfill product_subtype for sealed products that don't have one."""

    with Session(engine) as session:
        # Get all sealed product listings without a subtype
        # Join with card to get product_type
        stmt = (
            select(MarketPrice, Card.product_type)
            .join(Card, MarketPrice.card_id == Card.id)
            .where(MarketPrice.product_subtype.is_(None))
            .where(Card.product_type != "Single")  # Only sealed products
        )

        results = session.exec(stmt).all()

        print(f"Found {len(results)} sealed product listings without product_subtype")

        updated = 0
        updates_by_subtype = {}

        for listing, product_type in results:
            subtype = _detect_product_subtype(listing.title, product_type)

            if subtype:
                updated += 1
                updates_by_subtype[subtype] = updates_by_subtype.get(subtype, 0) + 1

                if commit:
                    listing.product_subtype = subtype
                    session.add(listing)
                else:
                    # Show sample updates in dry run
                    if updated <= 10:
                        print(f"  [{subtype}] {listing.title[:60]}...")

        if commit:
            session.commit()
            print(f"\n✅ Updated {updated} listings")
        else:
            print(f"\n📋 Would update {updated} listings (dry run)")

        print("\nBreakdown by subtype:")
        for subtype, count in sorted(updates_by_subtype.items(), key=lambda x: -x[1]):
            print(f"  {subtype}: {count}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill product_subtype for sealed products")
    parser.add_argument("--commit", action="store_true", help="Actually update the database")
    args = parser.parse_args()

    backfill_product_subtypes(commit=args.commit)
