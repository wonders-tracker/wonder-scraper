#!/usr/bin/env python3
"""
Backfill treatment data for existing BlokpaxSale records.

Categorizes Blokpax sales by product type based on asset name patterns:
- Collector Boxes: "Dragon 715/2699" → "Dragon Box"
- First Forms: "First Form: Umbrathene 80/99" → "First Form: Umbrathene"
- Art Proofs: Card names → "Art Proof"
- Preslabs: Graded cards → "Preslab TAG X"

Run with: python scripts/backfill_blokpax_treatment.py
"""

import sys
sys.path.insert(0, '.')

import re
from sqlalchemy import text
from app.db import engine


def parse_treatment_from_name(asset_name: str) -> str | None:
    """
    Parse treatment/category from Blokpax asset name.

    Patterns:
    - "Dragon 715/2699" → "Dragon Box"
    - "First Form: Umbrathene 80/99" → "First Form: Umbrathene"
    - "Card Name '24 9 MINT 123 (Cert: #X)" → "Preslab TAG 9"
    - "Card Name '24 8.5 NM MT+ 123 (Cert: #X)" → "Preslab TAG 8.5"
    - "Card Name 70/93" (art proof with serial) → "Art Proof"
    - "Card Name" (art proof) → "Art Proof"
    """
    name = asset_name.strip()

    # Pattern 1: Collector Box - "Dragon 715/2699" or "Dragon 1234/2699"
    box_match = re.match(r'^(Dragon)\s+\d+/\d+$', name)
    if box_match:
        return "Dragon Box"

    # Pattern 2: First Form boxes - "First Form: Umbrathene 80/99"
    first_form_match = re.match(r'^(First Form:\s*\w+)\s+\d+/\d+$', name)
    if first_form_match:
        return first_form_match.group(1).strip()

    # Pattern 3: Preslab - has '24 and grade info (integer or decimal like 8.5)
    # "Card Name '24 9 MINT 123" or "Card Name '24 8.5 NM MT+ 123"
    preslab_match = re.search(r"'24\s+(\d+(?:\.\d+)?)\s+(MINT|NM MT\+?|GEM MINT|NM)", name, re.IGNORECASE)
    if preslab_match:
        grade = preslab_match.group(1)
        return f"Preslab TAG {grade}"

    # Pattern 4: Preslab with serial number in parens format (card specific serial)
    # "Card Name '24 9 (928) MINT 003" - serial in parens before grade
    preslab_paren_serial = re.search(r"'24\s+(\d+(?:\.\d+)?)\s+\(\d+\)\s+(MINT|NM)", name, re.IGNORECASE)
    if preslab_paren_serial:
        grade = preslab_paren_serial.group(1)
        return f"Preslab TAG {grade}"

    # Pattern 5: Preslab without grade - just has '24 and serial
    # "Card Name '24 123 (Cert: #X)"
    preslab_no_grade = re.search(r"'24\s+\d+\s*\(Cert:", name)
    if preslab_no_grade:
        return "Preslab TAG"

    # Pattern 6: Art Proof with serial - "Card Name 70/93" (small serial like x/99 or x/93)
    # These are limited edition art proofs
    art_proof_serial = re.match(r'^(.+?)\s+\d+/\d{2,3}$', name)
    if art_proof_serial and "'24" not in name:
        return "Art Proof"

    # Pattern 7: Art Proof - just a card name (no serial, no grade)
    if not re.search(r'\d+/\d+', name) and "'24" not in name:
        return "Art Proof"

    return None


def backfill():
    """Backfill treatment for existing BlokpaxSale records."""

    # Get sales without treatment
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT id, asset_id, asset_name
            FROM blokpaxsale
            WHERE treatment IS NULL
            ORDER BY id
        """))
        sales = result.fetchall()

    if not sales:
        print("No sales need backfilling!")
        return

    print(f"Found {len(sales)} sales to backfill...")

    # Group by treatment for summary
    treatment_counts: dict[str, int] = {}
    updated = 0

    with engine.connect() as conn:
        for i, (sale_id, asset_id, asset_name) in enumerate(sales):
            treatment = parse_treatment_from_name(asset_name)

            if treatment:
                conn.execute(
                    text("UPDATE blokpaxsale SET treatment = :treatment WHERE id = :id"),
                    {"treatment": treatment, "id": sale_id}
                )
                updated += 1
                treatment_counts[treatment] = treatment_counts.get(treatment, 0) + 1
                print(f"  [{i+1}/{len(sales)}] {asset_name[:45]}: {treatment}")
            else:
                print(f"  [{i+1}/{len(sales)}] {asset_name[:45]}: (unknown pattern)")

        conn.commit()

    print(f"\nBackfill complete! Updated {updated}/{len(sales)} sales.")
    print("\nTreatment breakdown:")
    for treatment, count in sorted(treatment_counts.items(), key=lambda x: -x[1]):
        print(f"  {treatment}: {count}")


if __name__ == "__main__":
    backfill()
