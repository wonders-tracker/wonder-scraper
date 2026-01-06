#!/usr/bin/env python3
"""
Dry run script to test preslab parsing and card matching.
Does NOT write to the database - only prints what would happen.
"""

import re
import httpx
from typing import Optional
from dataclasses import dataclass


@dataclass
class PreslabInfo:
    """Parsed preslab information."""

    card_name: str
    grade: Optional[str]  # e.g., "9 MINT", "8 NM MT"
    grade_number: Optional[int]  # Just the number: 9, 8, etc.
    serial: Optional[str]
    cert_id: Optional[str]
    treatment: str  # Computed: "Preslab TAG 9" or "Preslab TAG"
    raw_name: str  # Original asset name


def parse_preslab_name(asset_name: str) -> Optional[PreslabInfo]:
    """
    Parse a preslab asset name into components.

    Examples:
        "Kishral Vivasynth, ChronoTitan '24 9 MINT 109 (Cert: #C8498411)"
        "Sylira Shadowstalker '24 210 (Cert: #T4614216)"
        "Mold Warrior '24 8 NM MT 353 (Cert: #X4074354)"

    Pattern: [Card Name] '24 [Optional: Grade] [Serial] (Cert: #[ID])
    """
    # Extract cert ID first
    cert_match = re.search(r"\(Cert:\s*#([A-Z0-9]+)\)", asset_name)
    cert_id = cert_match.group(1) if cert_match else None

    # Remove cert portion for easier parsing
    name_without_cert = re.sub(r"\s*\(Cert:\s*#[A-Z0-9]+\)", "", asset_name).strip()

    # Pattern: [Card Name] '24 [stuff]
    # The '24 marks the year/set indicator
    year_match = re.search(r"^(.+?)\s+'24\s+(.*)$", name_without_cert)

    if not year_match:
        return None

    card_name = year_match.group(1).strip()
    remainder = year_match.group(2).strip()

    # Parse remainder: could be "[grade] [serial]" or just "[serial]"
    # Grades look like: "9 MINT", "8 NM MT", "10 GEM MINT", etc.
    # Serial is usually just a number at the end

    grade = None
    grade_number = None
    serial = None

    # Try to match grade pattern: number followed by grade text
    grade_match = re.match(
        r"^(\d+)\s+(MINT|NM MT|GEM MINT|NM|MT|EX|VG|GOOD|POOR)(?:\s+(.+))?$", remainder, re.IGNORECASE
    )

    if grade_match:
        grade_number = int(grade_match.group(1))
        grade_text = grade_match.group(2).upper()
        grade = f"{grade_number} {grade_text}"
        serial = grade_match.group(3).strip() if grade_match.group(3) else None
    else:
        # No grade, remainder is just serial
        serial = remainder if remainder else None

    # Compute treatment name
    if grade_number:
        treatment = f"Preslab TAG {grade_number}"
    else:
        treatment = "Preslab TAG"

    return PreslabInfo(
        card_name=card_name,
        grade=grade,
        grade_number=grade_number,
        serial=serial,
        cert_id=cert_id,
        treatment=treatment,
        raw_name=asset_name,
    )


def normalize_card_name(name: str) -> str:
    """Normalize card name for matching."""
    # Lowercase, remove extra spaces, handle common variations
    normalized = name.lower().strip()
    normalized = re.sub(r"\s+", " ", normalized)  # Collapse whitespace
    # Remove trailing commas and articles that might differ
    normalized = re.sub(r",\s*$", "", normalized)
    return normalized


def fetch_preslabs_from_api() -> list:
    """Fetch preslab assets from Blokpax API."""
    url = "https://api.blokpax.com/api/storefront/wotf-existence-preslabs/assets"
    all_assets = []
    page = 1
    per_page = 100

    print("Fetching preslabs from Blokpax API...")

    while True:
        response = httpx.get(url, params={"page": page, "perPage": per_page}, timeout=30)
        data = response.json()

        assets = data.get("data", [])
        if not assets:
            break

        all_assets.extend(assets)
        print(f"  Page {page}: {len(assets)} assets (total: {len(all_assets)})")

        # Check if there are more pages
        meta = data.get("meta", {})
        total = meta.get("total", 0)
        if len(all_assets) >= total:
            break

        page += 1

    return all_assets


def fetch_cards_from_db() -> dict:
    """Fetch card names from database for matching."""
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    from sqlmodel import Session, select
    from app.db import engine
    from app.models.card import Card, Rarity

    cards_by_name = {}

    with Session(engine) as session:
        # Get all non-sealed cards (singles)
        stmt = select(Card, Rarity.name).join(Rarity, Card.rarity_id == Rarity.id).where(Rarity.name != "SEALED")
        results = session.exec(stmt).all()

        for card, rarity_name in results:
            normalized = normalize_card_name(card.name)
            cards_by_name[normalized] = {
                "id": card.id,
                "name": card.name,
                "set_name": card.set_name,
                "rarity": rarity_name,
            }

    return cards_by_name


def find_matching_card(preslab_name: str, cards_by_name: dict) -> Optional[dict]:
    """Find a matching card for a preslab name."""
    normalized = normalize_card_name(preslab_name)

    # Direct match
    if normalized in cards_by_name:
        return cards_by_name[normalized]

    # Try without trailing parts (some cards have subtitles)
    # e.g., "Kishral Vivasynth, ChronoTitan" might match "Kishral Vivasynth"
    parts = normalized.split(",")
    if len(parts) > 1:
        base_name = parts[0].strip()
        if base_name in cards_by_name:
            return cards_by_name[base_name]

    # Fuzzy match: check if preslab name contains or is contained by card name
    for card_normalized, card_info in cards_by_name.items():
        if card_normalized in normalized or normalized in card_normalized:
            return card_info

    return None


def fetch_preslab_sales_from_api() -> list:
    """Fetch preslab sales activity from Blokpax API."""
    url = "https://api.blokpax.com/api/storefront/wotf-existence-preslabs/activity"
    all_sales = []
    page = 1
    per_page = 100

    print("Fetching preslab sales from Blokpax API...")

    while True:
        response = httpx.get(url, params={"page": page, "perPage": per_page}, timeout=30)
        data = response.json()

        activities = data.get("data", [])
        if not activities:
            break

        # Filter to only sales
        sales = [a for a in activities if a.get("type") == "sale"]
        all_sales.extend(sales)
        print(f"  Page {page}: {len(sales)} sales (total: {len(all_sales)})")

        # Check if there are more pages
        meta = data.get("meta", {})
        total = meta.get("total", 0)
        if page * per_page >= total:
            break

        page += 1
        if page > 20:  # Limit for dry run
            print("  (stopping at 20 pages for dry run)")
            break

    return all_sales


def main():
    print("=" * 60)
    print("PRESLAB DRY RUN - Testing parser and card matching")
    print("=" * 60)
    print()

    # Fetch data
    preslabs = fetch_preslabs_from_api()
    print(f"\nTotal preslabs fetched: {len(preslabs)}")
    print()

    cards_by_name = fetch_cards_from_db()
    print(f"Total cards in database: {len(cards_by_name)}")
    print()

    # Parse and match
    print("=" * 60)
    print("PARSING AND MATCHING RESULTS")
    print("=" * 60)
    print()

    parsed_count = 0
    matched_count = 0
    unmatched = []
    parse_failures = []

    # Track unique card names we find
    unique_preslab_cards = set()
    matched_cards = {}

    for asset in preslabs:
        asset_name = asset.get("name", "")

        parsed = parse_preslab_name(asset_name)

        if not parsed:
            parse_failures.append(asset_name)
            continue

        parsed_count += 1
        unique_preslab_cards.add(parsed.card_name)

        match = find_matching_card(parsed.card_name, cards_by_name)

        if match:
            matched_count += 1
            if parsed.card_name not in matched_cards:
                matched_cards[parsed.card_name] = match
        else:
            if parsed.card_name not in [u[0] for u in unmatched]:
                unmatched.append((parsed.card_name, asset_name))

    # Summary
    print(f"Parsed successfully: {parsed_count}/{len(preslabs)}")
    print(f"Unique card names in preslabs: {len(unique_preslab_cards)}")
    print(f"Matched to DB cards: {matched_count}/{parsed_count} ({100*matched_count/parsed_count:.1f}%)")
    print(f"Unique cards matched: {len(matched_cards)}")
    print()

    # Show some examples of successful matches
    print("-" * 60)
    print("SAMPLE SUCCESSFUL MATCHES (first 10)")
    print("-" * 60)
    for i, (preslab_name, card_info) in enumerate(list(matched_cards.items())[:10]):
        print(f"  '{preslab_name}' -> Card #{card_info['id']}: {card_info['name']} ({card_info['rarity']})")
    print()

    # Show parse failures
    if parse_failures:
        print("-" * 60)
        print(f"PARSE FAILURES ({len(parse_failures)})")
        print("-" * 60)
        for name in parse_failures[:10]:
            print(f"  {name}")
        if len(parse_failures) > 10:
            print(f"  ... and {len(parse_failures) - 10} more")
        print()

    # Show unmatched
    if unmatched:
        print("-" * 60)
        print(f"UNMATCHED CARDS ({len(unmatched)} unique)")
        print("-" * 60)
        for preslab_name, example in unmatched[:20]:
            print(f"  '{preslab_name}'")
            print(f"    Example: {example}")
        if len(unmatched) > 20:
            print(f"  ... and {len(unmatched) - 20} more")
        print()

    # Show treatment distribution
    print("-" * 60)
    print("TREATMENT DISTRIBUTION")
    print("-" * 60)
    treatments = {}
    for asset in preslabs:
        parsed = parse_preslab_name(asset.get("name", ""))
        if parsed:
            treatments[parsed.treatment] = treatments.get(parsed.treatment, 0) + 1

    for treatment, count in sorted(treatments.items(), key=lambda x: -x[1]):
        print(f"  {treatment}: {count}")
    print()

    # Show sample parsed data
    print("-" * 60)
    print("SAMPLE PARSED DATA (first 5)")
    print("-" * 60)
    for asset in preslabs[:5]:
        parsed = parse_preslab_name(asset.get("name", ""))
        if parsed:
            print(f"  Raw: {parsed.raw_name}")
            print(f"  Card: {parsed.card_name}")
            print(f"  Grade: {parsed.grade}")
            print(f"  Serial: {parsed.serial}")
            print(f"  Cert: {parsed.cert_id}")
            print(f"  Treatment: {parsed.treatment}")
            print()

    # Test sales parsing
    print("=" * 60)
    print("SALES DATA TEST")
    print("=" * 60)
    print()

    sales = fetch_preslab_sales_from_api()
    print(f"\nTotal sales fetched: {len(sales)}")
    print()

    if sales:
        sales_parsed = 0
        sales_matched = 0

        print("-" * 60)
        print("SAMPLE SALES (first 10)")
        print("-" * 60)
        for sale in sales[:10]:
            asset_name = sale.get("asset", {}).get("name", "")
            price_bpx = sale.get("price", 0)
            price_usd = sale.get("price_in_usd", 0)
            created_at = sale.get("created_at", "")

            parsed = parse_preslab_name(asset_name)
            if parsed:
                sales_parsed += 1
                match = find_matching_card(parsed.card_name, cards_by_name)
                if match:
                    sales_matched += 1
                    print(f"  {parsed.card_name} ({parsed.treatment})")
                    print(f"    -> Card #{match['id']}: {match['name']}")
                    print(f"    Price: ${price_usd:.2f} ({price_bpx/1e9:.2f} BPX)")
                    print(f"    Date: {created_at}")
                    print()

        print(f"\nSales parsed: {sales_parsed}/{len(sales)}")
        print(f"Sales matched: {sales_matched}/{sales_parsed}")


if __name__ == "__main__":
    main()
