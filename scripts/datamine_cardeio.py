#!/usr/bin/env python3
"""
Datamine card data from Carde.io API (compete.wondersccg.com).

This script fetches all card data from the official game API and outputs it
in a format we can use to enhance our card pages with additional content.
"""

import json
import time
from pathlib import Path

import httpx


BASE_URL = "https://play-api.carde.io/v1"
GAME_ID = "907f6223-9f5a-429b-97f8-bba1fe663983"
CARD_DB_ID = "6627fabd6b6038576e986833"

HEADERS = {
    "content-type": "application/json",
    "game-id": GAME_ID,
    "Origin": "https://compete.wondersccg.com",
    "Referer": "https://compete.wondersccg.com/",
}

OUTPUT_DIR = Path(__file__).parent.parent / "data" / "cardeio"


def fetch_cards_page(page: int = 1) -> dict:
    """Fetch a single page of cards from the API."""
    url = f"{BASE_URL}/cards/{CARD_DB_ID}"
    params = {"page": page}

    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        return response.json()


def fetch_card_detail(card_id: str) -> dict | None:
    """Fetch detailed card data including abilities and stats."""
    url = f"{BASE_URL}/card/{card_id}"

    with httpx.Client(timeout=30) as client:
        try:
            response = client.get(url, headers=HEADERS)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise


def fetch_all_cards() -> list[dict]:
    """Fetch all cards from all pages."""
    all_cards = []

    # First request to get pagination info
    first_page = fetch_cards_page(1)
    pagination = first_page.get("pagination", {})
    total_pages = pagination.get("totalPages", 1)
    total_results = pagination.get("totalResults", 0)

    print(f"Found {total_results} cards across {total_pages} pages")

    all_cards.extend(first_page.get("data", []))

    # Fetch remaining pages
    for page in range(2, total_pages + 1):
        print(f"Fetching page {page}/{total_pages}...")
        page_data = fetch_cards_page(page)
        all_cards.extend(page_data.get("data", []))
        time.sleep(0.5)  # Be respectful

    return all_cards


def fetch_filters() -> dict:
    """Fetch filter options (orbitals, card types, classes, factions, etc.)."""
    url = f"{BASE_URL}/cards/{CARD_DB_ID}/filters"

    with httpx.Client(timeout=30) as client:
        response = client.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()


def enrich_with_details(cards: list[dict], max_cards: int | None = None) -> list[dict]:
    """Fetch detailed data for each card."""
    enriched = []

    cards_to_process = cards[:max_cards] if max_cards else cards
    total = len(cards_to_process)

    for i, card in enumerate(cards_to_process, 1):
        card_id = card.get("id")
        print(f"[{i}/{total}] Fetching details for {card.get('name')}...")

        detail = fetch_card_detail(card_id)
        if detail:
            enriched.append({**card, "detail": detail})
        else:
            enriched.append(card)

        time.sleep(0.3)  # Be respectful

    return enriched


def save_data(data: dict, filename: str):
    """Save data to JSON file."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    filepath = OUTPUT_DIR / filename

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

    print(f"Saved to {filepath}")


def main():
    print("=== Carde.io Card Data Mining ===\n")

    # Fetch filter metadata
    print("Fetching filter metadata...")
    filters = fetch_filters()
    save_data(filters, "filters.json")

    # Extract orbital data for later use
    orbitals = {}
    for filter_item in filters:
        if filter_item.get("searchField") == "orbital":
            for option in filter_item.get("options", []):
                orbitals[option["searchTerm"]] = {
                    "name": option["displayText"],
                    "icon": option.get("displayIcon", ""),
                }
    save_data(orbitals, "orbitals.json")

    # Fetch all cards
    print("\nFetching all cards...")
    cards = fetch_all_cards()
    save_data({"total": len(cards), "cards": cards}, "cards_basic.json")

    # Sample a few cards with full details to understand the schema
    print("\nFetching sample card details...")
    sample_cards = enrich_with_details(cards[:5])
    save_data({"sample": sample_cards}, "cards_sample_detailed.json")

    print(f"\n=== Complete ===")
    print(f"Total cards fetched: {len(cards)}")
    print(f"Output directory: {OUTPUT_DIR}")

    # Print summary
    card_types = {}
    orbitals_count = {}
    for card in cards:
        ct = card.get("cardType", {}).get("name", "Unknown")
        card_types[ct] = card_types.get(ct, 0) + 1

        orb = card.get("orbital", {}).get("name", "Unknown")
        orbitals_count[orb] = orbitals_count.get(orb, 0) + 1

    print("\nCard Types:")
    for ct, count in sorted(card_types.items(), key=lambda x: -x[1]):
        print(f"  {ct}: {count}")

    print("\nOrbitals:")
    for orb, count in sorted(orbitals_count.items(), key=lambda x: -x[1]):
        print(f"  {orb}: {count}")


if __name__ == "__main__":
    main()
