#!/usr/bin/env python3
"""
Clean up marketprice listing data quality issues.

Issues addressed:
1. Card mismatches - listings matched to wrong card (title doesn't contain card name)
2. Graded cards - PSA/BGS/CGC/TAG slabs not marked in grading field
3. Lots/multiples - X2, X3, lot of, etc. not marked in quantity field

Usage:
    python scripts/cleanup_listing_data.py --dry-run        # Preview changes
    python scripts/cleanup_listing_data.py --execute        # Apply changes
    python scripts/cleanup_listing_data.py --execute --fix-grades   # Only fix grading
    python scripts/cleanup_listing_data.py --execute --fix-quantity # Only fix quantity
    python scripts/cleanup_listing_data.py --execute --fix-mismatches # Only fix mismatches
"""

import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

from sqlmodel import Session
from sqlalchemy import text

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine


def extract_grading_from_title(title: str) -> Optional[str]:
    """Extract grading info from listing title."""
    title_lower = title.lower()

    # PSA grades
    psa_match = re.search(r'psa\s*(\d+(?:\.\d+)?)', title_lower)
    if psa_match:
        return f"PSA {psa_match.group(1)}"

    # BGS grades
    bgs_match = re.search(r'bgs\s*(\d+(?:\.\d+)?)', title_lower)
    if bgs_match:
        return f"BGS {bgs_match.group(1)}"

    # CGC grades
    cgc_match = re.search(r'cgc\s*(\d+(?:\.\d+)?)', title_lower)
    if cgc_match:
        return f"CGC {cgc_match.group(1)}"

    # TAG SLAB (common for WOTF)
    if 'tag' in title_lower and 'slab' in title_lower:
        tag_match = re.search(r'tag\s*(?:slab)?\s*(\d+(?:\.\d+)?)', title_lower)
        if tag_match:
            return f"TAG {tag_match.group(1)}"
        return "TAG SLAB"

    # Generic slab/graded mentions
    if 'slab' in title_lower or 'graded' in title_lower:
        return "GRADED"

    return None


def extract_quantity_from_title(title: str) -> Optional[int]:
    """Extract quantity from listing title for lots/multiples."""
    title_lower = title.lower()

    # Skip if title contains known card names with X in them
    # (Carbon-X7, X7v1, etc. are card names, not quantities)
    skip_patterns = [
        r'carbon-x\d',  # Carbon-X7 card name
        r'x\d+v\d',     # X7v1 variant naming
        r'experiment\s*x',  # Experiment X series
    ]
    for pattern in skip_patterns:
        if re.search(pattern, title_lower):
            return None

    # Patterns like "X3", "x2", "X 3" at START of title or after separator
    # Must have space/separator before to avoid matching card names like "Carbon-X7"
    x_match = re.search(r'(?:^|[\s\-])x\s*(\d+)(?:\s|$|-)', title_lower)
    if x_match:
        qty = int(x_match.group(1))
        if qty > 1 and qty <= 20:  # Reasonable lot size
            return qty

    # Patterns like "3x", "2x " at START of title or after separator
    num_x_match = re.search(r'(?:^|[\s\-])(\d+)\s*x(?:\s|$|-)', title_lower)
    if num_x_match:
        qty = int(num_x_match.group(1))
        if qty > 1 and qty <= 20:
            return qty

    # "lot of X"
    lot_match = re.search(r'lot\s+of\s+(\d+)', title_lower)
    if lot_match:
        qty = int(lot_match.group(1))
        if qty > 1 and qty <= 50:
            return qty

    # "Xct" like "3ct"
    ct_match = re.search(r'\b(\d+)\s*ct\b', title_lower)
    if ct_match:
        qty = int(ct_match.group(1))
        if qty > 1 and qty <= 20:
            return qty

    return None


def normalize_card_name(name: str) -> str:
    """Normalize card name for fuzzy matching.

    Handles common variations between DB names and eBay listing titles:
    - Apostrophe styles: ' vs ' vs '
    - Quote styles: " vs " vs "
    - Commas in names: "Autumn, Essence" vs "Autumn Essence"
    - Hyphens: "Cave-Dwelling" vs "Cave Dwelling"
    - Articles: "of the" vs "of", "The Great" vs "Great"
    - Common typos/misspellings
    """
    normalized = name.lower()

    # Normalize apostrophes and quotes
    normalized = normalized.replace("'", "'").replace("'", "'")
    normalized = normalized.replace('"', '"').replace('"', '"')

    # Remove commas (card names often have commas, titles often don't)
    normalized = normalized.replace(',', '')

    # Normalize hyphens to spaces (Cave-Dwelling -> Cave Dwelling)
    normalized = normalized.replace('-', ' ')

    # Normalize spaces
    normalized = re.sub(r'\s+', ' ', normalized)

    # Handle "of the" vs "of" variations
    normalized = re.sub(r'\bof the\b', 'of', normalized)

    # Handle "the" at start (sometimes dropped in titles)
    normalized = re.sub(r'^the\s+', '', normalized)

    return normalized.strip()


# Common spelling variations/typos found in eBay titles
SPELLING_CORRECTIONS = {
    'issac': 'isaac',
    'mutaded': 'mutated',
    'deathsworm': 'deathsworn',
    'rooting': 'rootling',
    'ceacean': 'cetacean',
    'cetaccean': 'cetacean',
    'lyonnaisa': 'lyonnisia',
    'volris': 'voluris',
    "bath'al": "bathr'al",  # Missing 'r'
    'bathal': "bathr'al",  # Missing apostrophe and r
    'chieftan': 'chieftain',  # Common misspelling
    'flok': 'floki',  # Truncated name
    'cave dwelling': 'cave-dwelling',  # Missing hyphen
    'drogothar destroyer': 'drogothar the destroyer',  # Missing 'the'
    'aether valkyr': 'aether valkyre',  # Check card name
}


def apply_spelling_corrections(text: str) -> str:
    """Apply known spelling corrections to text."""
    result = text.lower()
    for wrong, right in SPELLING_CORRECTIONS.items():
        result = result.replace(wrong, right)
    return result


def strip_punctuation(text: str) -> str:
    """Remove all punctuation for fuzzy matching."""
    return re.sub(r'[^\w\s]', '', text.lower())


def find_best_card_match(title: str, session, current_card_id: Optional[int] = None) -> Optional[Tuple[int, str, float]]:
    """
    Find the best matching card for a listing title.
    Returns (card_id, card_name, confidence) or None.

    Uses normalized matching to handle variations like "of the" vs "of".
    Will not suggest a shorter match if a longer card name is already assigned.
    """
    # Get all single cards
    cards = session.execute(text("""
        SELECT id, name FROM card WHERE product_type = 'Single'
    """)).all()

    title_lower = title.lower()
    title_normalized = normalize_card_name(title)
    title_corrected = apply_spelling_corrections(title_normalized)
    title_stripped = strip_punctuation(title)
    title_stripped_corrected = apply_spelling_corrections(title_stripped)
    best_match = None
    best_score = 0
    current_card_len = 0

    # If we have a current card, get its length for comparison
    if current_card_id:
        for card_id, card_name in cards:
            if card_id == current_card_id:
                current_card_len = len(card_name)
                break

    for card_id, card_name in cards:
        name_lower = card_name.lower()
        name_normalized = normalize_card_name(card_name)
        name_stripped = strip_punctuation(card_name)

        # Check exact, normalized, spelling-corrected, and punctuation-stripped matches
        exact_match = name_lower in title_lower
        normalized_match = name_normalized in title_normalized
        corrected_match = name_normalized in title_corrected
        stripped_match = name_stripped in title_stripped
        stripped_corrected_match = name_stripped in title_stripped_corrected

        if exact_match or normalized_match or corrected_match or stripped_match or stripped_corrected_match:
            # Score based on name length (longer = more specific = better)
            score = len(card_name)

            # Bonus for exact match (no normalization needed)
            if exact_match:
                score += 10

            # Add bonus for names that appear at the START of the title (after "Wonders of...")
            # This helps prioritize the actual card name over incidental matches
            wonders_prefix = re.search(r'wonders of the first\s*', title_lower)
            if wonders_prefix:
                title_after_prefix = title_lower[wonders_prefix.end():]
                title_after_norm = normalize_card_name(title_after_prefix)
                title_after_corr = apply_spelling_corrections(title_after_norm)
                if (title_after_prefix.startswith(name_lower) or
                    title_after_norm.startswith(name_normalized) or
                    title_after_corr.startswith(name_normalized)):
                    score += 100  # Strong bonus for title-start matches

            if score > best_score:
                best_score = score
                best_match = (card_id, card_name, 1.0)

    # Don't suggest a shorter/worse match than what's currently assigned
    if best_match and current_card_len > 0:
        if len(best_match[1]) < current_card_len:
            # Current assignment is to a longer/more specific card, keep it
            return None

    return best_match


def cleanup_grading(session, dry_run: bool = True) -> dict:
    """Fix grading field for slabbed cards."""
    results = {"updated": 0, "skipped": 0}

    # Find listings with grading keywords but no grading field
    listings = session.execute(text("""
        SELECT mp.id, mp.title, mp.grading
        FROM marketprice mp
        JOIN card c ON mp.card_id = c.id
        WHERE c.product_type = 'Single'
        AND mp.platform = 'ebay'
        AND mp.grading IS NULL
        AND (
            LOWER(mp.title) LIKE '%psa%'
            OR LOWER(mp.title) LIKE '%bgs%'
            OR LOWER(mp.title) LIKE '%cgc%'
            OR (LOWER(mp.title) LIKE '%tag%' AND LOWER(mp.title) LIKE '%slab%')
            OR LOWER(mp.title) LIKE '%graded%'
        )
    """)).all()

    print(f"\nFound {len(listings)} listings with grading keywords but no grading field")

    for listing_id, title, current_grading in listings:
        grading = extract_grading_from_title(title)

        if grading:
            print(f"  [{listing_id}] {title[:50]}...")
            print(f"         -> Grading: {grading}")

            if not dry_run:
                session.execute(text("""
                    UPDATE marketprice SET grading = :grading WHERE id = :id
                """), {"grading": grading, "id": listing_id})
                results["updated"] += 1
            else:
                results["updated"] += 1
        else:
            results["skipped"] += 1

    if not dry_run:
        session.commit()

    return results


def cleanup_quantity(session, dry_run: bool = True) -> dict:
    """Fix quantity field for lots/multiples."""
    results = {"updated": 0, "skipped": 0}

    # Find listings with quantity keywords but quantity = 1
    listings = session.execute(text("""
        SELECT mp.id, mp.title, mp.quantity
        FROM marketprice mp
        JOIN card c ON mp.card_id = c.id
        WHERE c.product_type = 'Single'
        AND mp.platform = 'ebay'
        AND (mp.quantity IS NULL OR mp.quantity = 1)
        AND (
            LOWER(mp.title) ~ 'x[2-9]'
            OR LOWER(mp.title) ~ '[2-9]x\\s'
            OR LOWER(mp.title) LIKE '%lot of%'
            OR LOWER(mp.title) LIKE '% lot %'
            OR LOWER(mp.title) ~ '[2-9]ct'
        )
    """)).all()

    print(f"\nFound {len(listings)} listings with quantity keywords but quantity=1")

    for listing_id, title, current_qty in listings:
        quantity = extract_quantity_from_title(title)

        if quantity and quantity > 1:
            print(f"  [{listing_id}] {title[:50]}...")
            print(f"         -> Quantity: {quantity}")

            if not dry_run:
                session.execute(text("""
                    UPDATE marketprice SET quantity = :qty WHERE id = :id
                """), {"qty": quantity, "id": listing_id})
                results["updated"] += 1
            else:
                results["updated"] += 1
        else:
            results["skipped"] += 1

    if not dry_run:
        session.commit()

    return results


def cleanup_mismatches(session, dry_run: bool = True) -> dict:
    """Fix card mismatches where title doesn't contain card name."""
    results = {"updated": 0, "skipped": 0, "unmatched": 0, "kept_current": 0}

    # Find mismatched listings - but use normalized comparison to catch "of the" vs "of"
    # We'll do the exact check in Python to be more flexible
    listings = session.execute(text("""
        SELECT mp.id, mp.card_id, c.name as current_card, mp.title
        FROM marketprice mp
        JOIN card c ON mp.card_id = c.id
        WHERE c.product_type = 'Single'
        AND mp.platform = 'ebay'
        AND LOWER(mp.title) NOT LIKE '%' || LOWER(c.name) || '%'
        ORDER BY mp.price DESC
    """)).all()

    print(f"\nFound {len(listings)} listings where title doesn't contain exact card name")

    # Filter further - exclude listings where ANY normalized matching method succeeds
    # This catches apostrophe variations, spelling errors, punctuation differences, etc.
    filtered_listings = []
    for listing_id, current_card_id, current_card_name, title in listings:
        title_normalized = normalize_card_name(title)
        title_corrected = apply_spelling_corrections(title_normalized)
        title_stripped = strip_punctuation(title)
        title_stripped_corrected = apply_spelling_corrections(title_stripped)

        card_normalized = normalize_card_name(current_card_name)
        card_stripped = strip_punctuation(current_card_name)

        # Check if current card matches via any normalization method
        matches = (
            card_normalized in title_normalized or
            card_normalized in title_corrected or
            card_stripped in title_stripped or
            card_stripped in title_stripped_corrected
        )

        if not matches:
            filtered_listings.append((listing_id, current_card_id, current_card_name, title))
        else:
            results["kept_current"] += 1

    print(f"After normalized matching: {len(filtered_listings)} truly mismatched ({results['kept_current']} were actually correct)")

    for listing_id, current_card_id, current_card_name, title in filtered_listings:
        best_match = find_best_card_match(title, session, current_card_id)

        if best_match:
            new_card_id, new_card_name, confidence = best_match
            if new_card_id != current_card_id:
                print(f"  [{listing_id}] {title[:50]}...")
                print(f"         Current: {current_card_name}")
                print(f"         -> New: {new_card_name} (confidence: {confidence})")

                if not dry_run:
                    try:
                        session.execute(text("""
                            UPDATE marketprice SET card_id = :card_id WHERE id = :id
                        """), {"card_id": new_card_id, "id": listing_id})
                        session.commit()
                        results["updated"] += 1
                    except Exception as e:
                        session.rollback()
                        if "duplicate key" in str(e).lower() or "unique" in str(e).lower():
                            print(f"         DUPLICATE: Deleting duplicate listing")
                            # Delete the duplicate instead of updating
                            session.execute(text("""
                                DELETE FROM marketprice WHERE id = :id
                            """), {"id": listing_id})
                            session.commit()
                            results["updated"] += 1
                        else:
                            print(f"         ERROR: {e}")
                            results["skipped"] += 1
                else:
                    results["updated"] += 1
            else:
                results["skipped"] += 1
        else:
            print(f"  [{listing_id}] NO MATCH FOUND: {title[:60]}...")
            results["unmatched"] += 1

    return results


def main():
    parser = argparse.ArgumentParser(description="Clean up marketprice listing data")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without applying")
    parser.add_argument("--execute", action="store_true", help="Apply changes to database")
    parser.add_argument("--fix-grades", action="store_true", help="Only fix grading field")
    parser.add_argument("--fix-quantity", action="store_true", help="Only fix quantity field")
    parser.add_argument("--fix-mismatches", action="store_true", help="Only fix card mismatches")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        return

    dry_run = not args.execute
    fix_all = not (args.fix_grades or args.fix_quantity or args.fix_mismatches)

    print(f"Listing Data Cleanup - {'DRY RUN' if dry_run else 'EXECUTING'}")
    print(f"Started: {datetime.now()}")
    print("=" * 60)

    with Session(engine) as session:
        total_results = {"grading": {}, "quantity": {}, "mismatches": {}}

        if fix_all or args.fix_grades:
            print("\n" + "=" * 60)
            print("FIXING GRADING FIELDS")
            print("=" * 60)
            total_results["grading"] = cleanup_grading(session, dry_run)

        if fix_all or args.fix_quantity:
            print("\n" + "=" * 60)
            print("FIXING QUANTITY FIELDS")
            print("=" * 60)
            total_results["quantity"] = cleanup_quantity(session, dry_run)

        if fix_all or args.fix_mismatches:
            print("\n" + "=" * 60)
            print("FIXING CARD MISMATCHES")
            print("=" * 60)
            total_results["mismatches"] = cleanup_mismatches(session, dry_run)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    for category, results in total_results.items():
        if results:
            print(f"  {category.upper()}:")
            for key, value in results.items():
                print(f"    {key}: {value}")


if __name__ == "__main__":
    main()
