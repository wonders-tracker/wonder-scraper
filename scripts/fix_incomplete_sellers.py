#!/usr/bin/env python3
"""
Fix incomplete seller names that were truncated (like "The", "Blue", "BRM", etc.)
by re-scraping those listings.

Usage:
    python scripts/fix_incomplete_sellers.py --dry-run
    python scripts/fix_incomplete_sellers.py --execute
"""

import argparse
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional

from sqlmodel import Session
from sqlalchemy import text

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine
from scripts.backfill_seller_data import (
    extract_seller_from_html,
    extract_item_id_from_url,
    fetch_page_with_pydoll,
    create_browser,
)

# Known incomplete/truncated seller names that need to be re-scraped
INCOMPLETE_SELLERS = [
    "The",
    "Blue",
    "BRM",
    "Premier",
    "Midnight",
    "Collectors",
    "Azure",
    "Rooster",
    "Comic",
    "Dragonfly",
    "Hawkewind",  # This one might be complete, but let's verify
    "Ritchies",
    "Elkhorn",
    "Preferred",
    "GLS",
    "JDP",
]


async def fix_incomplete_sellers_async(dry_run: bool = True, limit: Optional[int] = None, batch_size: int = 5):
    """Re-scrape listings with known incomplete seller names."""
    with Session(engine) as session:
        # Build query for listings with incomplete seller names
        placeholders = ", ".join([f":seller_{i}" for i in range(len(INCOMPLETE_SELLERS))])
        params = {f"seller_{i}": seller for i, seller in enumerate(INCOMPLETE_SELLERS)}

        # Use parameterized LIMIT to prevent SQL injection
        if limit:
            query = text(f"""
                SELECT id, external_id, url, title, seller_name
                FROM marketprice
                WHERE listing_type = 'sold'
                AND platform = 'ebay'
                AND seller_name IN ({placeholders})
                AND (url IS NOT NULL OR external_id IS NOT NULL)
                ORDER BY sold_date DESC
                LIMIT :limit
            """)
            params["limit"] = limit
        else:
            query = text(f"""
                SELECT id, external_id, url, title, seller_name
                FROM marketprice
                WHERE listing_type = 'sold'
                AND platform = 'ebay'
                AND seller_name IN ({placeholders})
                AND (url IS NOT NULL OR external_id IS NOT NULL)
                ORDER BY sold_date DESC
            """)

        results = session.execute(query, params).all()
        print(f"Found {len(results)} listings with potentially incomplete seller names")

        if dry_run:
            print("\n[DRY RUN] Would re-scrape these items:")
            # Group by current seller name
            by_seller = {}
            for row in results:
                seller = row[4]
                by_seller.setdefault(seller, []).append(row)

            for seller, items in sorted(by_seller.items(), key=lambda x: -len(x[1])):
                print(f"\n  '{seller}' - {len(items)} listings")
                for row in items[:3]:
                    mp_id, external_id, url, title, _ = row
                    item_id = external_id or extract_item_id_from_url(url)
                    print(f"    ID={mp_id} | eBay={item_id} | {(title or '')[:40]}...")
                if len(items) > 3:
                    print(f"    ... and {len(items) - 3} more")
            return

        # Setup browser
        print(f"\nStarting Pydoll browser (batch_size={batch_size})...")
        browser = await create_browser()
        print("Browser started successfully")

        total_updated = 0
        total_skipped = 0
        total_failed = 0

        try:
            # Process in batches
            for i in range(0, len(results), batch_size):
                batch = results[i : i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(results) + batch_size - 1) // batch_size

                print(f"\n=== Batch {batch_num}/{total_batches} (items {i+1}-{min(i+batch_size, len(results))}) ===")

                for row in batch:
                    mp_id, external_id, url, title, old_seller = row
                    ebay_item_id = external_id or extract_item_id_from_url(url)

                    if not ebay_item_id:
                        print(f"    [{mp_id}] Skip: no item ID")
                        total_skipped += 1
                        continue

                    item_url = f"https://www.ebay.com/itm/{ebay_item_id}"
                    html = await fetch_page_with_pydoll(browser, item_url)

                    if not html:
                        print(f"    [{mp_id}] Skip: fetch failed")
                        total_skipped += 1
                        continue

                    if "Pardon Our Interruption" in html or "Security Measure" in html:
                        print(f"    [{mp_id}] Failed: blocked by eBay")
                        total_failed += 1
                        continue

                    seller_name, feedback_score, feedback_percent = extract_seller_from_html(html)

                    if not seller_name:
                        print(f"    [{mp_id}] Skip: no seller found (was '{old_seller}')")
                        total_skipped += 1
                        continue

                    # Only update if we got a different (hopefully better) name
                    if seller_name == old_seller:
                        print(f"    [{mp_id}] Skip: same seller '{seller_name}'")
                        total_skipped += 1
                        continue

                    try:
                        session.execute(
                            text("""
                            UPDATE marketprice
                            SET seller_name = :seller,
                                seller_feedback_score = :score,
                                seller_feedback_percent = :pct
                            WHERE id = :id
                        """),
                            {"seller": seller_name, "score": feedback_score, "pct": feedback_percent, "id": mp_id},
                        )
                        session.commit()
                        total_updated += 1
                        print(f"    [{mp_id}] Fixed: '{old_seller}' -> '{seller_name}'")
                    except Exception as e:
                        print(f"    [{mp_id}] DB error: {e}")
                        session.rollback()
                        total_failed += 1

                print(f"    Total so far: {total_updated} fixed, {total_skipped} skipped, {total_failed} failed")
                await asyncio.sleep(1)

            print(f"\n{'='*60}")
            print("FIX COMPLETE")
            print(f"{'='*60}")
            print(f"  Total processed: {len(results)}")
            print(f"  Fixed: {total_updated}")
            print(f"  Skipped: {total_skipped}")
            print(f"  Failed: {total_failed}")
        finally:
            print("\nClosing browser...")
            try:
                await browser.stop()
            except Exception as e:
                print(f"Error stopping browser: {e}")


def main():
    parser = argparse.ArgumentParser(description="Fix incomplete seller names")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be fixed")
    parser.add_argument("--execute", action="store_true", help="Actually execute the fix")
    parser.add_argument("--limit", type=int, help="Limit number of items")
    parser.add_argument("--batch-size", type=int, default=5, help="Batch size (default: 5)")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        return

    dry_run = not args.execute

    print(f"Fix Incomplete Sellers - {'DRY RUN' if dry_run else 'EXECUTING'}")
    print(f"Started: {datetime.now()}")
    print(f"Looking for: {INCOMPLETE_SELLERS}")
    print("=" * 60)

    asyncio.run(fix_incomplete_sellers_async(dry_run=dry_run, limit=args.limit, batch_size=args.batch_size))


if __name__ == "__main__":
    main()
