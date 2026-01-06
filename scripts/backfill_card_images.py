#!/usr/bin/env python3
"""
Backfill card images from eBay listings to Vercel Blob storage.

This script:
1. Finds all cards without an image_url
2. For each card, finds the best listing image from recent sales
3. Downloads the image and uploads it to Vercel Blob
4. Updates the card record with the new blob URL

Usage:
    # Dry run (no changes)
    python scripts/backfill_card_images.py --dry-run

    # Process all cards without images
    python scripts/backfill_card_images.py

    # Limit to N cards
    python scripts/backfill_card_images.py --limit 50

    # Force re-upload for specific card
    python scripts/backfill_card_images.py --card-id 123 --force

Environment:
    BLOB_READ_WRITE_TOKEN: Required for Vercel Blob uploads
    DATABASE_URL: Database connection string
"""

import asyncio
import argparse
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select
from sqlalchemy import text

from app.db import engine
from app.models.card import Card
from app.services.blob_storage import get_blob_service


async def get_best_image_for_card(session: Session, card_id: int) -> str | None:
    """
    Find the best image URL for a card from its listings.

    Priority:
    1. Most recent sold listing with image
    2. Most recent active listing with image

    Args:
        session: Database session
        card_id: Card ID to find image for

    Returns:
        Best image URL or None if no images found
    """
    # Query for sold listings with images first
    query = text("""
        SELECT image_url
        FROM marketprice
        WHERE card_id = :card_id
        AND image_url IS NOT NULL
        AND image_url != ''
        ORDER BY
            CASE WHEN listing_type = 'sold' THEN 0 ELSE 1 END,
            COALESCE(sold_date, scraped_at) DESC
        LIMIT 1
    """)

    result = session.execute(query, {"card_id": card_id}).first()
    return result[0] if result else None


async def process_card(
    session: Session,
    card: Card,
    blob_service,
    dry_run: bool = False,
) -> bool:
    """
    Process a single card - find image, upload to blob, update card.

    Returns:
        True if successful, False otherwise
    """
    # Find best image
    image_url = await get_best_image_for_card(session, card.id)

    if not image_url:
        print(f"  [{card.id}] {card.name}: No listing images found")
        return False

    print(f"  [{card.id}] {card.name}: Found image {image_url[:60]}...")

    if dry_run:
        print(f"  [{card.id}] DRY RUN - would upload to Vercel Blob")
        return True

    # Upload to Vercel Blob
    blob_url = await blob_service.upload_card_image(
        card_id=card.id,
        source_url=image_url,
        card_name=card.name,
    )

    if not blob_url:
        print(f"  [{card.id}] Failed to upload image")
        return False

    # Update card record
    card.image_url = blob_url
    session.add(card)
    session.commit()

    print(f"  [{card.id}] Uploaded: {blob_url}")
    return True


async def main():
    parser = argparse.ArgumentParser(description="Backfill card images to Vercel Blob")
    parser.add_argument("--dry-run", action="store_true", help="Don't make any changes")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of cards to process")
    parser.add_argument("--card-id", type=int, default=None, help="Process specific card ID")
    parser.add_argument("--force", action="store_true", help="Re-upload even if image exists")
    parser.add_argument("--product-type", type=str, default=None, help="Filter by product type (Single, Box, etc)")
    args = parser.parse_args()

    blob_service = get_blob_service()

    if not blob_service.is_configured():
        print("ERROR: BLOB_READ_WRITE_TOKEN environment variable not set")
        print("Get your token from Vercel Dashboard -> Storage -> Blob")
        sys.exit(1)

    print("=== Card Image Backfill ===")
    print(f"Dry run: {args.dry_run}")
    print(f"Limit: {args.limit or 'none'}")
    print()

    with Session(engine) as session:
        # Build query
        query = select(Card)

        if args.card_id:
            query = query.where(Card.id == args.card_id)
        elif not args.force:
            # Only cards without images
            query = query.where(Card.image_url.is_(None))

        if args.product_type:
            query = query.where(Card.product_type == args.product_type)

        # Order by ID for consistent processing
        query = query.order_by(Card.id)

        if args.limit:
            query = query.limit(args.limit)

        cards = session.exec(query).all()

        print(f"Found {len(cards)} cards to process")
        print()

        success_count = 0
        fail_count = 0

        for card in cards:
            try:
                success = await process_card(
                    session=session,
                    card=card,
                    blob_service=blob_service,
                    dry_run=args.dry_run,
                )
                if success:
                    success_count += 1
                else:
                    fail_count += 1
            except Exception as e:
                print(f"  [{card.id}] Error: {e}")
                fail_count += 1

            # Small delay to avoid rate limiting
            await asyncio.sleep(0.1)

        print()
        print("=== Summary ===")
        print(f"Processed: {len(cards)}")
        print(f"Success: {success_count}")
        print(f"Failed: {fail_count}")


if __name__ == "__main__":
    asyncio.run(main())
