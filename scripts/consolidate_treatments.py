#!/usr/bin/env python3
"""
Consolidate treatment values in marketprice table.

Maps inconsistent treatment values to standard treatments:
- Classic Paper, Classic Foil, Formless Foil, OCM Serialized, Stonefoil
- Alt Art variants: Classic Paper Alt Art, Formless Foil Alt Art, etc.
- Graded: Preslab TAG, Preslab TAG 8, Preslab TAG 9, Preslab TAG 10
- Sealed products: Sealed, Factory Sealed
- Special: Promo, Prerelease, Error/Errata, Character Proof, Proof/Sample

Run with: python scripts/consolidate_treatments.py
"""

import sys
sys.path.insert(0, '.')

from sqlalchemy import text
from app.db import engine


# Consolidation mapping: old_value -> new_value
TREATMENT_MAP = {
    # Generic/ambiguous foil → Classic Foil
    "Foil": "Classic Foil",
    "Holo Foil": "Classic Foil",
    "Red Foil": "Classic Foil",
    "Full Art Foil": "Classic Foil",

    # Rarity-mixed treatments → Classic Paper (rarity is not a treatment)
    "Epic Rare": "Classic Paper",
    "Rare": "Classic Paper",
    "Classic Rare": "Classic Paper",
    "Mythic Rare": "Classic Paper",
    "Mythic": "Classic Paper",
    "Epic": "Classic Paper",
    "1st Edition Rare": "Classic Paper",

    # Existence set foils → Classic Foil (Existence is the set name)
    "Existence Foil": "Classic Foil",
    "Epic Foil": "Classic Foil",
    "Rare Foil": "Classic Foil",
    "Mythic Foil": "Classic Foil",
    "Existence EPIC FOIL": "Classic Foil",
    "Secret Rare Mythic Foil": "Classic Foil",

    # Existence set rarity descriptions → Classic Paper
    "Rare Existence": "Classic Paper",
    "Existence Mythic": "Classic Paper",

    # Formless variants
    "Formless Mythic": "Formless Foil",
    "Alternate Art Formless": "Formless Foil Alt Art",

    # OCM shorthand
    "OCM": "OCM Serialized",

    # Generic alternate art → depends on context, default to Classic Paper Alt Art
    "Alternate Art": "Classic Paper Alt Art",

    # Sealed products
    "New": "Sealed",
    "Unopened": "Sealed",
    "Open Box": "Sealed",  # Opened but still sealed product

    # Paper variants
    "Paper": "Classic Paper",
    "Classic Regular": "Classic Paper",
}


def consolidate():
    """Consolidate treatment values to standard names."""

    with engine.connect() as conn:
        # First, show current state
        result = conn.execute(text("""
            SELECT treatment, COUNT(*) as cnt
            FROM marketprice
            WHERE treatment IN :treatments
            GROUP BY treatment
            ORDER BY cnt DESC
        """), {"treatments": tuple(TREATMENT_MAP.keys())})

        rows = result.fetchall()
        if not rows:
            print("No treatments need consolidation!")
            return

        print(f"Found {len(rows)} treatment values to consolidate:")
        total = 0
        for row in rows:
            new_val = TREATMENT_MAP[row[0]]
            print(f"  {row[0]} ({row[1]}) → {new_val}")
            total += row[1]

        print(f"\nTotal records to update: {total}")

        # Apply consolidation
        updated = 0
        for old_val, new_val in TREATMENT_MAP.items():
            result = conn.execute(
                text("UPDATE marketprice SET treatment = :new_val WHERE treatment = :old_val"),
                {"old_val": old_val, "new_val": new_val}
            )
            if result.rowcount > 0:
                print(f"  Updated {result.rowcount}: {old_val} → {new_val}")
                updated += result.rowcount

        conn.commit()
        print(f"\nConsolidation complete! Updated {updated} records.")

        # Show final state
        result = conn.execute(text("""
            SELECT treatment, COUNT(*) as cnt
            FROM marketprice
            WHERE treatment IS NOT NULL
            GROUP BY treatment
            ORDER BY cnt DESC
            LIMIT 20
        """))
        print("\nTop treatments after consolidation:")
        for row in result:
            print(f"  {row[0]}: {row[1]}")


if __name__ == "__main__":
    consolidate()
