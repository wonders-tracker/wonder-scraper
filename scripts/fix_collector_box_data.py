"""
Fix Collector Booster Box data structure.

The current data has:
- NFT box "rarity tiers" (Rare, First Form, Legendary) incorrectly stored as treatment
- Dragon boxes identified by title but wrong treatment
- Generic product_subtype="Box" that loses variant info

The correct structure:
- NFT boxes: treatment=null, product_subtype reflects the box variant
- eBay sealed: treatment="Sealed", product_subtype="Collector Booster Box"/"Case"

Usage:
    python scripts/fix_collector_box_data.py              # Dry run
    python scripts/fix_collector_box_data.py --execute    # Apply changes
"""

import argparse
import re
from sqlmodel import Session, select
from app.db import engine
from app.models.market import MarketPrice
from app.models.card import Card


def extract_box_variant_from_title(title: str) -> str:
    """
    Extract box variant from NFT token title.

    Examples:
    - "Dragon 733/2699" -> "Dragon Box"
    - "First Form: Solfera 77/99" -> "First Form"
    - "Highlord Voluris Crestwing 91/93" -> "Legendary" (named legendary boxes)
    - "Rare 1234/3393" -> "Rare"
    """
    if not title:
        return "Unknown"

    title_lower = title.lower()

    # Dragon boxes: "Dragon 733/2699"
    if title_lower.startswith("dragon "):
        return "Dragon Box"

    # First Form variants: "First Form: Solfera 77/99"
    # Store as just "First Form" for aggregation purposes
    if title_lower.startswith("first form:"):
        return "First Form"

    # Legendary boxes have character names (not starting with common prefixes)
    # They have format like "Highlord Voluris Crestwing 91/93" with /93 or /99 suffix
    # Legendary boxes are numbered out of small totals (93, 99, etc)
    legendary_match = re.match(r"^([A-Z][a-zA-Z\s]+)\s+\d+/(?:93|99)\s*$", title)
    if legendary_match:
        return "Legendary"

    # Rare boxes (default NFT tier) - numbered out of 3393
    if re.match(r"^\d+/3393", title_lower) or title_lower.startswith("rare "):
        return "Rare"

    # Fallback - if numbered out of small total, likely Legendary
    if re.match(r"^[A-Z].*\s+\d+/\d{2,3}\s*$", title):
        return "Legendary"

    return "Unknown"


def extract_box_variant_from_traits(traits: list) -> str | None:
    """
    Extract box variant from NFT traits.

    Traits like: [{"trait_type": "Box Art", "value": "Dragon"}, ...]

    Returns normalized category:
    - "Dragon Box" for Dragon boxes
    - "First Form" for any First Form variant
    - "Legendary" for legendary character boxes
    - "Rare" for standard boxes
    """
    if not traits:
        return None

    for trait in traits:
        if not isinstance(trait, dict):
            continue
        trait_type = (trait.get("trait_type") or "").lower()
        trait_value = trait.get("value") or ""

        if trait_type == "box art" and trait_value:
            value_lower = trait_value.lower()

            # Dragon boxes
            if value_lower == "dragon":
                return "Dragon Box"

            # First Form boxes - normalize to just "First Form"
            if value_lower.startswith("first form"):
                return "First Form"

            # Legendary boxes - character names like "Highlord Voluris Crestwing"
            # These don't start with common prefixes
            if not any(value_lower.startswith(p) for p in ["dragon", "first form", "rare"]):
                return "Legendary"

        # Also check rarity trait for standard boxes
        if trait_type == "rarity" and trait_value:
            if trait_value.lower() in ["rare", "legendary"]:
                return trait_value.title()

    return None


def fix_collector_box_data(execute: bool = False):
    """Fix collector box data structure."""

    print("=" * 70)
    print("COLLECTOR BOOSTER BOX DATA FIX")
    print("=" * 70)
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN (use --execute to apply)'}")
    print()

    with Session(engine) as session:
        # Find the Collector Booster Box cards
        nft_box = session.exec(select(Card).where(Card.name == "Collector Booster Box (NFT)")).first()

        physical_box = session.exec(select(Card).where(Card.name == "Collector Booster Box")).first()

        if not nft_box and not physical_box:
            print("ERROR: No Collector Booster Box cards found in database")
            return

        # Track stats
        stats = {
            "nft_fixed": 0,
            "ebay_fixed": 0,
            "skipped": 0,
            "errors": 0,
        }

        # Fix NFT Collector Boxes
        if nft_box:
            print(f"\n--- NFT Collector Boxes (card_id={nft_box.id}) ---\n")

            nft_records = session.exec(
                select(MarketPrice).where(MarketPrice.card_id == nft_box.id, MarketPrice.platform == "opensea")
            ).all()

            print(f"Found {len(nft_records)} NFT box records")

            for record in nft_records:
                old_treatment = record.treatment
                old_subtype = record.product_subtype

                # Determine the correct variant from title or traits
                variant = extract_box_variant_from_traits(record.traits)
                if not variant:
                    variant = extract_box_variant_from_title(record.title)

                # For NFT boxes:
                # - treatment should be null (no card treatment concept)
                # - product_subtype should be the box variant
                new_treatment = None
                new_subtype = variant

                if old_treatment != new_treatment or old_subtype != new_subtype:
                    print(f'  ID {record.id}: "{record.title[:40]}..."')
                    print(f'    treatment: "{old_treatment}" -> {new_treatment}')
                    print(f'    subtype: "{old_subtype}" -> "{new_subtype}"')

                    if execute:
                        record.treatment = new_treatment
                        record.product_subtype = new_subtype
                        session.add(record)

                    stats["nft_fixed"] += 1
                else:
                    stats["skipped"] += 1

        # Fix Physical (eBay) Collector Boxes
        if physical_box:
            print(f"\n--- Physical Collector Boxes (card_id={physical_box.id}) ---\n")

            ebay_records = session.exec(
                select(MarketPrice).where(MarketPrice.card_id == physical_box.id, MarketPrice.platform == "ebay")
            ).all()

            print(f"Found {len(ebay_records)} eBay box records")

            for record in ebay_records:
                old_treatment = record.treatment
                old_subtype = record.product_subtype

                # For eBay sealed products:
                # - treatment should be "Sealed" (uniform for all sealed products)
                # - product_subtype should be specific (Collector Booster Box, Case, Bundle)

                # Normalize treatment to "Sealed"
                new_treatment = "Sealed"

                # Ensure product_subtype is set correctly
                title_lower = (record.title or "").lower()
                if "case" in title_lower or "6-box" in title_lower or "6 box" in title_lower:
                    new_subtype = "Case"
                elif old_subtype == "Case":
                    new_subtype = "Case"
                elif "bundle" in title_lower and "booster box" not in title_lower:
                    # Only mark as Bundle if it says bundle but NOT booster box
                    new_subtype = "Bundle"
                else:
                    # Default: Collector Booster Box
                    new_subtype = "Collector Booster Box"

                if old_treatment != new_treatment or old_subtype != new_subtype:
                    print(f'  ID {record.id}: "{record.title[:50]}..."')
                    print(f'    treatment: "{old_treatment}" -> "{new_treatment}"')
                    print(f'    subtype: "{old_subtype}" -> "{new_subtype}"')

                    if execute:
                        record.treatment = new_treatment
                        record.product_subtype = new_subtype
                        session.add(record)

                    stats["ebay_fixed"] += 1
                else:
                    stats["skipped"] += 1

        if execute:
            session.commit()
            print("\nChanges committed to database.")

        print("\n" + "=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"NFT boxes fixed: {stats['nft_fixed']}")
        print(f"eBay boxes fixed: {stats['ebay_fixed']}")
        print(f"Skipped (already correct): {stats['skipped']}")
        print(f"Errors: {stats['errors']}")

        if not execute:
            print("\nThis was a DRY RUN. Use --execute to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fix Collector Booster Box data structure")
    parser.add_argument("--execute", action="store_true", help="Actually update records (default is dry run)")
    args = parser.parse_args()

    fix_collector_box_data(execute=args.execute)
