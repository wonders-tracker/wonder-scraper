#!/usr/bin/env python3
"""
Enrich card database with Carde.io data.

This script:
1. Matches Carde.io cards to our existing cards by name
2. Updates card_type, orbital, orbital_color, card_number fields
3. Downloads official card images and uploads to Vercel Blob
4. Supports --dry-run to preview changes without modifying anything

Usage:
    # Dry run - preview what would change
    python scripts/enrich_cards_from_cardeio.py --dry-run

    # Actually run the migration
    python scripts/enrich_cards_from_cardeio.py

    # Skip image upload (just update fields)
    python scripts/enrich_cards_from_cardeio.py --skip-images

    # Only process specific cards
    python scripts/enrich_cards_from_cardeio.py --card-name "Dragonmaster Cai"
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.services.blob_storage import BlobStorageService


# Load environment variables
load_dotenv()

DATA_DIR = Path(__file__).parent.parent / "data" / "cardeio"
CARDEIO_CARDS_FILE = DATA_DIR / "cards_basic.json"


def load_cardeio_data() -> list[dict]:
    """Load Carde.io card data from JSON file."""
    if not CARDEIO_CARDS_FILE.exists():
        print(f"Error: {CARDEIO_CARDS_FILE} not found.")
        print("Run 'python scripts/datamine_cardeio.py' first to fetch card data.")
        sys.exit(1)

    with open(CARDEIO_CARDS_FILE) as f:
        data = json.load(f)
        return data.get("cards", [])


# Manual name aliases for cards with typos in our DB (from eBay title parsing)
# Maps: our DB name -> Carde.io name
NAME_ALIASES = {
    "cave-dwelling toebiter": "cave-dwelling canthropid",
    "ethosrelic fr-39": "ethosrelic fr-38",
    "astrox a-10": "astrox a-9",
    "hex hunter hx-11": "hex hunter hx-12",
}


def normalize_name(name: str) -> str:
    """Normalize card name for matching."""
    normalized = name.lower().strip()
    # Normalize quotes
    normalized = normalized.replace("'", "'").replace("'", "'")
    # Remove double quotes entirely (DB has "Fixem" but Carde.io has Fixem)
    normalized = normalized.replace('"', "")
    # Apply manual aliases for known typos
    normalized = NAME_ALIASES.get(normalized, normalized)
    return normalized


def build_cardeio_lookup(cards: list[dict]) -> dict[str, dict]:
    """Build a lookup dict by normalized card name."""
    lookup = {}
    for card in cards:
        normalized = normalize_name(card["name"])
        lookup[normalized] = card
    return lookup


def parse_card_number(slug: str) -> Optional[str]:
    """Extract card number from slug like 'Existence_143' -> '143'."""
    if "_" in slug:
        parts = slug.split("_")
        if len(parts) >= 2:
            return parts[-1]  # e.g., "143", "T-033", "P-043"
    return None


async def download_image(url: str) -> Optional[bytes]:
    """Download image from URL."""
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, follow_redirects=True)
            response.raise_for_status()
            return response.content
    except Exception as e:
        print(f"  Error downloading {url}: {e}")
        return None


async def upload_to_blob(
    blob_service: BlobStorageService,
    card_id: int,
    image_url: str,
    card_name: str,
) -> Optional[str]:
    """Download image and upload to Vercel Blob."""
    return await blob_service.upload_card_image(
        card_id=card_id,
        source_url=image_url,
        card_name=card_name,
    )


def get_db_cards(session: Session, card_name: Optional[str] = None) -> list[Card]:
    """Get cards from database, optionally filtered by name."""
    query = select(Card)
    if card_name:
        query = query.where(Card.name == card_name)
    return list(session.exec(query).all())


async def enrich_cards(
    dry_run: bool = True,
    skip_images: bool = False,
    card_name: Optional[str] = None,
    verbose: bool = True,
):
    """Main enrichment function."""
    # Load Carde.io data
    cardeio_cards = load_cardeio_data()
    cardeio_lookup = build_cardeio_lookup(cardeio_cards)

    print(f"Loaded {len(cardeio_cards)} cards from Carde.io")
    print(f"Mode: {'DRY RUN' if dry_run else 'LIVE'}")
    print(f"Images: {'SKIP' if skip_images else 'UPLOAD'}")
    print()

    # Initialize blob service
    blob_service = BlobStorageService()
    if not skip_images and not blob_service.is_configured():
        print("Warning: BLOB_READ_WRITE_TOKEN not set. Images will be skipped.")
        skip_images = True

    # Stats
    stats = {
        "matched": 0,
        "not_found": 0,
        "updated_fields": 0,
        "updated_images": 0,
        "skipped_images": 0,
        "errors": 0,
    }
    not_found_cards = []

    with Session(engine) as session:
        db_cards = get_db_cards(session, card_name)
        print(f"Processing {len(db_cards)} cards from database...\n")

        for card in db_cards:
            normalized = normalize_name(card.name)
            cardeio_card = cardeio_lookup.get(normalized)

            if not cardeio_card:
                stats["not_found"] += 1
                not_found_cards.append(card.name)
                if verbose:
                    print(f"[NOT FOUND] {card.name}")
                continue

            stats["matched"] += 1

            # Extract data from Carde.io
            card_type = cardeio_card.get("cardType", {}).get("name")
            orbital = cardeio_card.get("orbital", {}).get("name")
            orbital_color = cardeio_card.get("orbital", {}).get("hexColor")
            card_number = parse_card_number(cardeio_card.get("slug", ""))
            cardeio_image_url = cardeio_card.get("imageUrl")

            # Check what would change
            changes = []
            if card_type and getattr(card, "card_type", None) != card_type:
                changes.append(f"card_type: {getattr(card, 'card_type', None)} -> {card_type}")
            if orbital and getattr(card, "orbital", None) != orbital:
                changes.append(f"orbital: {getattr(card, 'orbital', None)} -> {orbital}")
            if orbital_color and getattr(card, "orbital_color", None) != orbital_color:
                changes.append(f"orbital_color: {getattr(card, 'orbital_color', None)} -> {orbital_color}")
            if card_number and getattr(card, "card_number", None) != card_number:
                changes.append(f"card_number: {getattr(card, 'card_number', None)} -> {card_number}")

            # Print changes
            if changes or verbose:
                print(f"[MATCH] {card.name} (ID: {card.id})")
                for change in changes:
                    print(f"  {change}")

            # Apply field updates
            if changes and not dry_run:
                try:
                    if card_type:
                        card.card_type = card_type
                    if orbital:
                        card.orbital = orbital
                    if orbital_color:
                        card.orbital_color = orbital_color
                    if card_number:
                        card.card_number = card_number
                    session.add(card)
                    session.commit()  # Commit each card to avoid idle timeout
                    stats["updated_fields"] += 1
                except AttributeError as e:
                    print("  Error: Card model missing fields. Run migration first.")
                    print(f"  Details: {e}")
                    stats["errors"] += 1
                    continue

            # Handle image upload
            if not skip_images and cardeio_image_url:
                current_image = getattr(card, "cardeio_image_url", None)

                if current_image:
                    if verbose:
                        print("  Image: Already has image")
                    stats["skipped_images"] += 1
                else:
                    print(f"  Image: {cardeio_image_url}")
                    if not dry_run:
                        blob_url = await upload_to_blob(
                            blob_service,
                            card.id,
                            cardeio_image_url,
                            card.name,
                        )
                        if blob_url:
                            try:
                                card.cardeio_image_url = blob_url
                                session.add(card)
                                session.commit()  # Commit immediately to avoid idle timeout
                                stats["updated_images"] += 1
                                print(f"  -> Uploaded: {blob_url}")
                            except AttributeError:
                                # Field doesn't exist yet
                                card.image_url = blob_url
                                session.add(card)
                                session.commit()  # Commit immediately to avoid idle timeout
                                stats["updated_images"] += 1
                                print(f"  -> Uploaded to image_url: {blob_url}")
                        else:
                            stats["errors"] += 1
                    else:
                        print("  -> Would upload to Vercel Blob")

            if changes or (not skip_images and cardeio_image_url):
                print()

        # Commit changes
        if not dry_run:
            session.commit()
            print("Changes committed to database.")

    # Print summary
    print("\n" + "=" * 50)
    print("SUMMARY")
    print("=" * 50)
    print(f"Matched:         {stats['matched']}")
    print(f"Not found:       {stats['not_found']}")
    if not dry_run:
        print(f"Fields updated:  {stats['updated_fields']}")
        print(f"Images uploaded: {stats['updated_images']}")
    print(f"Images skipped:  {stats['skipped_images']}")
    print(f"Errors:          {stats['errors']}")

    if not_found_cards and verbose:
        print(f"\nCards not found in Carde.io ({len(not_found_cards)}):")
        for name in not_found_cards[:20]:
            print(f"  - {name}")
        if len(not_found_cards) > 20:
            print(f"  ... and {len(not_found_cards) - 20} more")

    if dry_run:
        print("\n[DRY RUN] No changes were made. Run without --dry-run to apply.")


def main():
    parser = argparse.ArgumentParser(description="Enrich cards with Carde.io data")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview changes without modifying database",
    )
    parser.add_argument(
        "--skip-images",
        action="store_true",
        help="Skip image download and upload",
    )
    parser.add_argument(
        "--card-name",
        type=str,
        help="Only process a specific card by name",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Only show summary, not individual card updates",
    )

    args = parser.parse_args()

    asyncio.run(
        enrich_cards(
            dry_run=args.dry_run,
            skip_images=args.skip_images,
            card_name=args.card_name,
            verbose=not args.quiet,
        )
    )


if __name__ == "__main__":
    main()
