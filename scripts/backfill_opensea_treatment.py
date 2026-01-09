#!/usr/bin/env python3
"""
Backfill treatment data for OpenSea listings in marketprice table.

Categorizes OpenSea NFT listings by product type based on title patterns:
- Dragon Boxes: "Dragon 619/2699" → "Dragon Box"
- First Forms: "First Form: Solfera 77/99" → "First Form: Solfera"

Run with: python scripts/backfill_opensea_treatment.py
"""

import sys
sys.path.insert(0, '.')

import re
from sqlalchemy import text
from app.db import engine


def parse_treatment_from_title(title: str) -> str | None:
    """
    Parse treatment/category from OpenSea NFT title.

    Patterns:
    - "Dragon 619/2699" → "Dragon Box"
    - "First Form: Solfera 77/99" → "First Form: Solfera"
    - "First Form: Umbrathene 80/99" → "First Form: Umbrathene"
    """
    name = title.strip()

    # Pattern 1: Dragon Box - "Dragon 715/2699" or "Dragon 1234/2699"
    box_match = re.match(r'^(Dragon)\s+\d+/\d+$', name)
    if box_match:
        return "Dragon Box"

    # Pattern 2: First Form boxes - "First Form: Umbrathene 80/99"
    first_form_match = re.match(r'^(First Form:\s*\w+)\s+\d+/\d+$', name)
    if first_form_match:
        return first_form_match.group(1).strip()

    # Pattern 3: Art Proof with serial - "Highlord Voluris Crestwing 91/93"
    # Card name followed by small serial number (x/93, x/99, etc.)
    art_proof_match = re.match(r'^(.+?)\s+\d+/\d{2,3}$', name)
    if art_proof_match:
        return "Art Proof"

    return None


def backfill():
    """Backfill treatment for OpenSea listings in marketprice table."""

    # Get OpenSea listings without treatment
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, title, listing_type, price
            FROM marketprice
            WHERE platform = 'opensea' AND treatment IS NULL
            ORDER BY id
        """))
        listings = result.fetchall()

    if not listings:
        print("No OpenSea listings need backfilling!")
        return

    print(f"Found {len(listings)} OpenSea listings to backfill...")

    # Group by treatment for summary
    treatment_counts: dict[str, int] = {}
    updated = 0
    unknown = []

    with engine.connect() as conn:
        for i, (listing_id, title, listing_type, price) in enumerate(listings):
            treatment = parse_treatment_from_title(title)

            if treatment:
                conn.execute(
                    text("UPDATE marketprice SET treatment = :treatment WHERE id = :id"),
                    {"treatment": treatment, "id": listing_id}
                )
                updated += 1
                treatment_counts[treatment] = treatment_counts.get(treatment, 0) + 1
                print(f"  [{i+1}/{len(listings)}] {title[:45]}: {treatment}")
            else:
                unknown.append((listing_id, title, listing_type, price))
                print(f"  [{i+1}/{len(listings)}] {title[:45]}: (unknown pattern)")

        conn.commit()

    print(f"\nBackfill complete! Updated {updated}/{len(listings)} listings.")
    print("\nTreatment breakdown:")
    for treatment, count in sorted(treatment_counts.items(), key=lambda x: -x[1]):
        print(f"  {treatment}: {count}")

    if unknown:
        print(f"\nUnknown patterns ({len(unknown)}):")
        for listing_id, title, listing_type, price in unknown[:10]:
            print(f"  [{listing_type}] ${price:.2f} - {title}")


if __name__ == "__main__":
    backfill()
