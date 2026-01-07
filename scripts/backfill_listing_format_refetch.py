"""
Backfill listing_format by re-fetching listings from eBay using Pydoll.

This script fetches each active listing's eBay page and extracts the actual
listing format (auction, buy_it_now, best_offer) from the HTML.

Uses Pydoll (undetected Chrome) to bypass eBay's bot protection.
"""

import asyncio
import time
from typing import Optional

from bs4 import BeautifulSoup
from sqlmodel import Session, select, col
from app.db import engine
from app.models.market import MarketPrice
from app.scraper.browser import get_page_content
from app.scraper.ebay import _extract_bid_count, _extract_listing_format


async def fetch_and_extract(url: str) -> tuple[Optional[str], int]:
    """
    Fetch a listing page using Pydoll and extract listing format.
    Returns (listing_format, bid_count)
    """
    try:
        html = await get_page_content(url)
        soup = BeautifulSoup(html, "lxml")

        # Use the scraper's extraction functions
        bid_count = _extract_bid_count(soup)
        listing_format = _extract_listing_format(soup, bid_count)

        return listing_format, bid_count
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return None, 0


async def backfill_batch(listings: list[MarketPrice], dry_run: bool = False) -> dict:
    """Process a batch of listings sequentially (Pydoll doesn't support concurrent tabs well)."""
    stats = {"auction": 0, "buy_it_now": 0, "best_offer": 0, "unknown": 0, "failed": 0}
    updates = []

    for listing in listings:
        url = None
        if listing.url:
            url = listing.url
        elif listing.external_id:
            url = f"https://www.ebay.com/itm/{listing.external_id}"

        if not url:
            stats["failed"] += 1
            continue

        listing_format, bid_count = await fetch_and_extract(url)

        if listing_format:
            stats[listing_format] += 1
            updates.append((listing.id, listing_format, bid_count))
        else:
            stats["unknown"] += 1

    # Batch update database
    if not dry_run and updates:
        with Session(engine) as session:
            for listing_id, listing_format, bid_count in updates:
                listing = session.get(MarketPrice, listing_id)
                if listing:
                    listing.listing_format = listing_format
                    listing.bid_count = bid_count
                    session.add(listing)
            session.commit()

    return stats


def backfill_listing_format_refetch(
    listing_type: str = "active", limit: Optional[int] = None, batch_size: int = 20, dry_run: bool = False
):
    """
    Backfill listing_format by re-fetching from eBay.

    Args:
        listing_type: 'active' or 'sold' or 'all'
        limit: Max listings to process (None = all)
        batch_size: Concurrent requests per batch
        dry_run: Preview without saving
    """
    with Session(engine) as session:
        # Get listings without listing_format
        stmt = select(MarketPrice).where(col(MarketPrice.listing_format).is_(None))

        if listing_type != "all":
            stmt = stmt.where(MarketPrice.listing_type == listing_type)

        # Need URL or external_id to fetch
        stmt = stmt.where((col(MarketPrice.url).is_not(None)) | (col(MarketPrice.external_id).is_not(None)))

        if limit:
            stmt = stmt.limit(limit)

        listings = session.exec(stmt).all()
        print(f"Found {len(listings)} listings to process")

        if not listings:
            print("Nothing to backfill!")
            return

    # Process in batches
    total_stats = {"auction": 0, "buy_it_now": 0, "best_offer": 0, "unknown": 0, "failed": 0}

    for i in range(0, len(listings), batch_size):
        batch = listings[i : i + batch_size]
        print(
            f"Processing batch {i // batch_size + 1} ({i + 1}-{min(i + batch_size, len(listings))} of {len(listings)})..."
        )

        stats = asyncio.run(backfill_batch(batch, dry_run))

        for key in total_stats:
            total_stats[key] += stats[key]

        # Rate limit - wait between batches
        if i + batch_size < len(listings):
            time.sleep(2)

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Results:")
    print(f"  Auction:    {total_stats['auction']}")
    print(f"  Buy It Now: {total_stats['buy_it_now']}")
    print(f"  Best Offer: {total_stats['best_offer']}")
    print(f"  Unknown:    {total_stats['unknown']}")
    print(f"  Failed:     {total_stats['failed']}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Backfill listing_format by re-fetching from eBay")
    parser.add_argument("--type", choices=["active", "sold", "all"], default="active", help="Which listings to process")
    parser.add_argument("--limit", type=int, default=None, help="Max listings to process")
    parser.add_argument("--batch-size", type=int, default=20, help="Concurrent requests per batch")
    parser.add_argument("--dry-run", action="store_true", help="Preview without saving")
    args = parser.parse_args()

    backfill_listing_format_refetch(
        listing_type=args.type, limit=args.limit, batch_size=args.batch_size, dry_run=args.dry_run
    )
