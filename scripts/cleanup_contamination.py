"""
Cleanup script for removing non-WOTF contaminated data from the database.

Identifies and removes:
- Yu-Gi-Oh cards (MP22-EN, MGED-EN, etc.)
- Dragon Ball Z cards
- Pokemon cards
- Other TCG products that were incorrectly scraped

Usage:
    python scripts/cleanup_contamination.py --dry-run  # Preview what will be deleted
    python scripts/cleanup_contamination.py            # Actually delete contaminated records
"""

import argparse
from sqlmodel import Session, select, delete
from app.db import engine
from app.models.card import Card
from app.models.market import MarketPrice
from app.services.ai_extractor import get_ai_extractor


# WOTF indicators - if present, listing is definitely WOTF (even if PSA graded)
WOTF_INDICATORS = [
    "wonders of the first",
    "wotf",
    "wonders first",
    "existence set",
    "existence booster",
    "existence collector",
    "existence 1st",
    "existence formless",
    "existence classic",
    "genesis set",
    "genesis booster",
    "formless foil",
    "stonefoil",
    "stone foil",
    "classic paper",
    "classic foil",
    "/401",  # Card number format
]

# Non-WOTF indicators that should trigger deletion
# NOTE: PSA/CGC grading is NOT included here - handled separately
NON_WOTF_INDICATORS = {
    "Yu-Gi-Oh": [
        "mp22-en",
        "mp23-en",
        "mp24-en",
        "mp25-en",
        "mged-en",
        "mago-en",
        "maze-en",
        "tin of the",
        "pharaoh's gods",
        "pharaohs gods",
        "konami",
        "yugioh",
        "yu-gi-oh",
        "ruddy rose dragon",
        "roxrose dragon",
        "albion the branded",
        "trishula",
        "ice barrier",
        "red-eyes black dragon",
        "dark magician",
        "exodia",
        "slifer",
        "obelisk",
        "1st edition gold rare",
        "gold rare lp",
        "gold rare nm",
        "duelist",
        "lcyw-en",
        "lckc-en",
    ],
    "Dragon Ball Z": [
        "dragonball",
        "dragon ball",
        "dbz ccg",
        "android 20",
        "android 17",
        "android 18",
        "hercule",
        "goku",
        "vegeta",
        "frieza",
        "gohan",
        "piccolo",
        "wa-066",
        "wa-079",
        "gold stamp",
    ],
    "Pokemon": [
        "pokemon",
        "pokémon",
        "pikachu",
        "charizard",
        "mewtwo",
        "eevee",
        "scarlet violet",
        "evolving skies",
        "shining fates",
        # NOT including PSA/CGC - WOTF cards can be graded too
    ],
    "One Piece": [
        "one piece tcg",
        "one piece card",
        "luffy",
        "zoro",
        "straw hat",
        "op01",
        "op02",
        "op03",
        "op04",
        "op05",
    ],
    "MTG": [
        "magic the gathering",
        "mtg ",
        "planeswalker",
        "wizards of the coast",
    ],
    "Sports": [
        "topps",
        "panini",
        "upper deck",
        "bowman",
        "prizm",
        "nba",
        "nfl",
        "mlb",
        "nhl",
    ],
}


def is_wotf_listing(title_lower: str) -> bool:
    """Check if a listing has strong WOTF indicators."""
    for indicator in WOTF_INDICATORS:
        if indicator in title_lower:
            return True
    return False


def find_contaminated_listings(session: Session, use_ai: bool = False) -> list:
    """Find all listings that appear to be non-WOTF products."""
    contaminated = []

    # Get all sold listings
    listings = session.exec(select(MarketPrice).where(MarketPrice.listing_type == "sold")).all()

    ai_extractor = get_ai_extractor() if use_ai else None

    for listing in listings:
        title_lower = (listing.title or "").lower()

        # FIRST: Check if listing has WOTF indicators - if so, skip it
        if is_wotf_listing(title_lower):
            continue

        detected_tcg = None
        indicator_found = None

        # Check against all non-WOTF indicator patterns
        for tcg, indicators in NON_WOTF_INDICATORS.items():
            for indicator in indicators:
                if indicator in title_lower:
                    detected_tcg = tcg
                    indicator_found = indicator
                    break
            if detected_tcg:
                break

        if detected_tcg:
            # Get card name for context
            card = session.exec(select(Card).where(Card.id == listing.card_id)).first()
            card_name = card.name if card else "Unknown"

            contaminated.append(
                {
                    "id": listing.id,
                    "card_id": listing.card_id,
                    "card_name": card_name,
                    "title": listing.title,
                    "price": listing.price,
                    "detected_tcg": detected_tcg,
                    "indicator": indicator_found,
                }
            )

    return contaminated


def cleanup_contamination(dry_run: bool = True, use_ai: bool = False):
    """Remove contaminated listings from the database."""
    with Session(engine) as session:
        contaminated = find_contaminated_listings(session, use_ai)

        if not contaminated:
            print("✅ No contaminated listings found!")
            return

        # Group by detected TCG
        by_tcg = {}
        for item in contaminated:
            tcg = item["detected_tcg"]
            if tcg not in by_tcg:
                by_tcg[tcg] = []
            by_tcg[tcg].append(item)

        print(f"\n{'='*60}")
        print("CONTAMINATION REPORT")
        print(f"{'='*60}")
        print(f"Total contaminated listings: {len(contaminated)}")
        print("\nBreakdown by TCG:")
        for tcg, items in sorted(by_tcg.items(), key=lambda x: -len(x[1])):
            print(f"  - {tcg}: {len(items)} listings")

        print(f"\n{'-'*60}")
        print("Sample listings to be removed:")
        print(f"{'-'*60}")

        # Show samples from each TCG
        for tcg, items in sorted(by_tcg.items(), key=lambda x: -len(x[1])):
            print(f"\n{tcg}:")
            for item in items[:3]:  # Show up to 3 samples
                print(f"  ID {item['id']}: {item['title'][:60]}...")
                print(f"    → Card: {item['card_name']}, Price: ${item['price']:.2f}")
                print(f"    → Matched: '{item['indicator']}'")

        if dry_run:
            print(f"\n{'='*60}")
            print("🔍 DRY RUN - No changes made")
            print("Run without --dry-run to delete these listings")
            print(f"{'='*60}")
        else:
            # Confirm before deleting
            print(f"\n{'='*60}")
            print(f"⚠️  About to DELETE {len(contaminated)} listings!")
            print(f"{'='*60}")

            confirm = input("Type 'DELETE' to confirm: ")
            if confirm != "DELETE":
                print("Aborted.")
                return

            # Delete contaminated listings
            ids_to_delete = [item["id"] for item in contaminated]

            session.exec(delete(MarketPrice).where(MarketPrice.id.in_(ids_to_delete)))
            session.commit()

            print(f"\n✅ Deleted {len(ids_to_delete)} contaminated listings")

            # Show summary of what was removed
            print("\nRemoved by TCG:")
            for tcg, items in sorted(by_tcg.items(), key=lambda x: -len(x[1])):
                print(f"  - {tcg}: {len(items)} listings")


def find_duplicate_ebay_items(session: Session) -> list:
    """Find duplicate eBay listings by external_id."""
    from sqlalchemy import func as sa_func

    duplicates = session.exec(
        select(MarketPrice.external_id, sa_func.count(MarketPrice.id).label("count"))
        .where(MarketPrice.platform == "ebay", MarketPrice.external_id.isnot(None), MarketPrice.external_id != "")
        .group_by(MarketPrice.external_id)
        .having(sa_func.count(MarketPrice.id) > 1)
    ).all()

    return duplicates


def cleanup_duplicates(dry_run: bool = True):
    """Remove duplicate eBay listings, keeping the first occurrence."""
    with Session(engine) as session:
        duplicates = find_duplicate_ebay_items(session)

        if not duplicates:
            print("✅ No duplicate eBay listings found!")
            return

        print(f"\n{'='*60}")
        print("DUPLICATE LISTINGS REPORT")
        print(f"{'='*60}")
        print(f"Found {len(duplicates)} external_ids with duplicates")

        total_to_remove = 0
        ids_to_delete = []

        for external_id, count in duplicates:
            # Get all listings with this external_id
            listings = session.exec(
                select(MarketPrice)
                .where(MarketPrice.external_id == external_id)
                .order_by(MarketPrice.id)  # Keep oldest (lowest ID)
            ).all()

            # Mark all but the first for deletion
            for listing in listings[1:]:
                ids_to_delete.append(listing.id)
                total_to_remove += 1

        print(f"Total duplicate records to remove: {total_to_remove}")

        if dry_run:
            print("\n🔍 DRY RUN - No changes made")
            print("Run without --dry-run to delete duplicates")
        else:
            confirm = input(f"\nDelete {total_to_remove} duplicate records? (yes/no): ")
            if confirm.lower() != "yes":
                print("Aborted.")
                return

            session.exec(delete(MarketPrice).where(MarketPrice.id.in_(ids_to_delete)))
            session.commit()

            print(f"✅ Deleted {total_to_remove} duplicate listings")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Clean up contaminated data in the database")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without deleting")
    parser.add_argument("--use-ai", action="store_true", help="Use AI for additional validation")
    parser.add_argument("--duplicates", action="store_true", help="Also clean up duplicate eBay listings")

    args = parser.parse_args()

    print("🧹 WOTF Database Cleanup Tool")
    print("=" * 60)

    # Run contamination cleanup
    cleanup_contamination(dry_run=args.dry_run, use_ai=args.use_ai)

    # Optionally clean up duplicates
    if args.duplicates:
        print("\n")
        cleanup_duplicates(dry_run=args.dry_run)
