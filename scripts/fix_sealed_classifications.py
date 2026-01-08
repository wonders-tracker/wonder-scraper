#!/usr/bin/env python3
"""
Fix sealed product classifications in marketprice table.

Issues found:
1. "Prerelease" treatment applied to graded singles (should be Preslab TAG X)
2. Sealed products missing product_subtype
3. Some singles miscategorized as sealed

Run with: python scripts/fix_sealed_classifications.py
"""

import sys
sys.path.insert(0, '.')

import re
from sqlalchemy import text
from app.db import engine


def classify_listing(title: str, treatment: str) -> tuple[str, str | None]:
    """
    Classify a listing and return (new_treatment, new_product_subtype).

    Returns the correct treatment and product_subtype based on title analysis.
    """
    title_lower = title.lower()

    # Check for graded cards (TAG/Preslab) - these are singles, not sealed
    tag_match = re.search(r'tag\s*(?:graded\s*)?(\d+(?:\.\d+)?)', title_lower)
    preslab_match = re.search(r'preslab\s*tag\s*(\d+(?:\.\d+)?)', title_lower)
    slab_match = re.search(r'slab\s*tag\s*(\d+(?:\.\d+)?)', title_lower)

    if preslab_match or slab_match or tag_match:
        # This is a graded card
        match = preslab_match or slab_match or tag_match
        grade = match.group(1)

        # Check if it's a prerelease graded card
        if 'prerelease' in title_lower or 'pre-release' in title_lower:
            # Prerelease Preslab - keep prerelease info in treatment
            return f"Prerelease Preslab TAG {grade}", None
        else:
            return f"Preslab TAG {grade}", None

    # Check for proof cards (Character Proof, Foil Proof, etc.) - singles
    if 'proof' in title_lower and 'tag' in title_lower:
        tag_match = re.search(r'tag\s*(\d+(?:\.\d+)?)', title_lower)
        if tag_match:
            grade = tag_match.group(1)
            return f"Proof Preslab TAG {grade}", None

    # Check for sealed products
    if treatment in ('Sealed', 'Factory Sealed'):
        # Case
        if 'case' in title_lower:
            return treatment, "Case"

        # Collector Booster Box
        if 'collector' in title_lower and 'box' in title_lower:
            return treatment, "Collector Booster Box"

        # Collector Bundle
        if 'collector' in title_lower and 'bundle' in title_lower:
            return treatment, "Collector Bundle"

        # Play Bundle
        if 'play' in title_lower and 'bundle' in title_lower:
            return treatment, "Play Bundle"
        if 'play booster bundle' in title_lower:
            return treatment, "Play Bundle"

        # Collector Booster Pack
        if 'collector' in title_lower and ('pack' in title_lower or 'booster' in title_lower):
            return treatment, "Collector Booster Pack"

        # Play Booster Pack
        if 'play' in title_lower and 'pack' in title_lower:
            return treatment, "Play Booster Pack"

        # Silver Pack
        if 'silver' in title_lower and 'pack' in title_lower:
            return treatment, "Silver Pack"

        # Generic booster pack (default to Collector)
        if 'booster pack' in title_lower or ('booster' in title_lower and 'pack' in title_lower):
            return treatment, "Collector Booster Pack"

        # Generic pack
        if 'pack' in title_lower:
            return treatment, "Pack"

        # Generic bundle
        if 'bundle' in title_lower:
            return treatment, "Bundle"

        # Playtest deck
        if 'playtest' in title_lower:
            return treatment, "Playtest Deck"

        # Generic box
        if 'box' in title_lower:
            return treatment, "Box"

    # Prerelease items that are NOT graded - likely raw prerelease cards
    if treatment == 'Prerelease':
        # Check if it's a sealed prerelease kit/bundle
        if 'kit' in title_lower or 'bundle' in title_lower or 'set' in title_lower:
            return "Sealed", "Prerelease Kit"

        # Otherwise it's a raw prerelease card (single)
        # Keep as Prerelease treatment, no product_subtype
        return "Prerelease", None

    # No changes needed
    return treatment, None


def fix_classifications():
    """Fix sealed product classifications."""

    with engine.connect() as conn:
        # Get all items that need review
        result = conn.execute(text("""
            SELECT id, title, treatment, product_subtype, listing_type, price
            FROM marketprice
            WHERE treatment IN ('Sealed', 'Factory Sealed', 'Prerelease')
              AND product_subtype IS NULL
            ORDER BY treatment, title
        """))
        records = result.fetchall()

    if not records:
        print("No records need fixing!")
        return

    print(f"Analyzing {len(records)} records...\n")

    # Categorize changes
    changes = {
        'treatment_only': [],      # Treatment changed, no subtype
        'subtype_only': [],        # Subtype added, treatment unchanged
        'both_changed': [],        # Both changed
        'no_change': [],           # No changes needed
    }

    for record in records:
        record_id, title, old_treatment, old_subtype, listing_type, price = record
        new_treatment, new_subtype = classify_listing(title, old_treatment)

        treatment_changed = new_treatment != old_treatment
        subtype_changed = new_subtype != old_subtype

        if treatment_changed and subtype_changed:
            changes['both_changed'].append((record_id, title, old_treatment, new_treatment, old_subtype, new_subtype))
        elif treatment_changed:
            changes['treatment_only'].append((record_id, title, old_treatment, new_treatment))
        elif subtype_changed:
            changes['subtype_only'].append((record_id, title, old_treatment, old_subtype, new_subtype))
        else:
            changes['no_change'].append((record_id, title, old_treatment))

    # Report changes
    print("=== TREATMENT CHANGES (graded cards misclassified as sealed) ===")
    for item in changes['treatment_only'][:20]:
        print(f"  {item[2]} → {item[3]}: {item[1][:55]}")
    if len(changes['treatment_only']) > 20:
        print(f"  ... and {len(changes['treatment_only']) - 20} more")
    print(f"Total: {len(changes['treatment_only'])}\n")

    print("=== SUBTYPE ADDITIONS (sealed products needing subtype) ===")
    for item in changes['subtype_only'][:20]:
        print(f"  +{item[4]}: {item[1][:55]}")
    if len(changes['subtype_only']) > 20:
        print(f"  ... and {len(changes['subtype_only']) - 20} more")
    print(f"Total: {len(changes['subtype_only'])}\n")

    print("=== BOTH TREATMENT AND SUBTYPE CHANGED ===")
    for item in changes['both_changed'][:10]:
        print(f"  {item[2]} → {item[3]}, +{item[5]}: {item[1][:50]}")
    print(f"Total: {len(changes['both_changed'])}\n")

    print("=== NO CHANGES (raw prerelease singles) ===")
    for item in changes['no_change'][:10]:
        print(f"  [{item[2]}] {item[1][:60]}")
    print(f"Total: {len(changes['no_change'])}\n")

    # Apply changes
    total_updated = 0
    with engine.connect() as conn:
        # Treatment only changes
        for item in changes['treatment_only']:
            conn.execute(
                text("UPDATE marketprice SET treatment = :treatment WHERE id = :id"),
                {"treatment": item[3], "id": item[0]}
            )
            total_updated += 1

        # Subtype only changes
        for item in changes['subtype_only']:
            conn.execute(
                text("UPDATE marketprice SET product_subtype = :subtype WHERE id = :id"),
                {"subtype": item[4], "id": item[0]}
            )
            total_updated += 1

        # Both changed
        for item in changes['both_changed']:
            conn.execute(
                text("UPDATE marketprice SET treatment = :treatment, product_subtype = :subtype WHERE id = :id"),
                {"treatment": item[3], "subtype": item[5], "id": item[0]}
            )
            total_updated += 1

        conn.commit()

    print(f"=== COMPLETE ===")
    print(f"Updated {total_updated} records")


if __name__ == "__main__":
    fix_classifications()
