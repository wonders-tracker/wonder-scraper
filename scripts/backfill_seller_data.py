#!/usr/bin/env python3
"""
Backfill seller data for eBay listings using Pydoll (undetected Chrome).

Uses a real browser to bypass eBay's anti-bot protection.

Features:
- Progress checkpointing (saves progress every batch)
- Automatic browser restart on blocks
- Empty string to NULL conversion
- Resumable from last checkpoint

Usage:
    python scripts/backfill_seller_data.py --dry-run        # Preview what would be updated
    python scripts/backfill_seller_data.py --execute        # Actually run the backfill
    python scripts/backfill_seller_data.py --execute --limit 100  # Limit to 100 items
    python scripts/backfill_seller_data.py --execute --type active   # Only active listings
    python scripts/backfill_seller_data.py --execute --resume       # Resume from checkpoint
"""

import argparse
import asyncio
import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Optional, List

from sqlmodel import Session
from sqlalchemy import text

import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine
from app.scraper.seller import extract_seller_from_html

# Checkpoint file for resuming interrupted runs
CHECKPOINT_FILE = Path(__file__).parent.parent / "data" / ".seller_backfill_checkpoint.json"


def save_checkpoint(processed_ids: set, stats: dict):
    """Save progress checkpoint to file."""
    CHECKPOINT_FILE.parent.mkdir(parents=True, exist_ok=True)
    data = {"processed_ids": list(processed_ids), "stats": stats, "timestamp": datetime.now().isoformat()}
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(data, f)


def load_checkpoint() -> tuple[set, dict]:
    """Load progress from checkpoint file."""
    if not CHECKPOINT_FILE.exists():
        return set(), {}
    try:
        with open(CHECKPOINT_FILE) as f:
            data = json.load(f)
        return set(data.get("processed_ids", [])), data.get("stats", {})
    except (json.JSONDecodeError, KeyError, TypeError, OSError) as e:
        print(f"Warning: Could not load checkpoint: {e}")
        return set(), {}


def clear_checkpoint():
    """Remove checkpoint file after successful completion."""
    if CHECKPOINT_FILE.exists():
        CHECKPOINT_FILE.unlink()


def extract_item_id_from_url(url: str) -> Optional[str]:
    """Extract eBay item ID from URL."""
    if not url:
        return None
    match = re.search(r"/itm/(?:[^/]+/)?(\d+)", url)
    if match:
        return match.group(1)
    return None


async def fetch_with_browser(browser, item_id: str, mp_id: int) -> dict:
    """Fetch page with Pydoll browser and extract seller."""
    url = f"https://www.ebay.com/itm/{item_id}"
    tab = None
    try:
        tab = await browser.new_tab()
        await tab.go_to(url, timeout=30)
        await asyncio.sleep(3)  # Let page render (longer for concurrent tabs)

        # Get HTML with timeout
        try:
            result = await asyncio.wait_for(
                tab.execute_script("return document.documentElement.outerHTML;", return_by_value=True), timeout=30
            )
        except asyncio.TimeoutError:
            return {"status": "timeout", "mp_id": mp_id, "reason": "script timeout"}

        html = None
        if isinstance(result, dict):
            inner = result.get("result", {})
            if isinstance(inner, dict):
                html = inner.get("result", {}).get("value")

        if not html:
            return {"status": "skip", "mp_id": mp_id, "reason": "no HTML"}

        # Check for blocks
        if "Pardon Our Interruption" in html or "Security Measure" in html:
            return {"status": "blocked", "mp_id": mp_id, "reason": "blocked"}

        seller_name, feedback_score, feedback_percent = extract_seller_from_html(html)

        if seller_name:
            return {
                "status": "success",
                "mp_id": mp_id,
                "seller_name": seller_name,
                "feedback_score": feedback_score,
                "feedback_percent": feedback_percent,
            }
        else:
            return {"status": "skip", "mp_id": mp_id, "reason": "no seller in HTML"}

    except Exception as e:
        error_msg = str(e)[:50]
        # Detect timeout errors that indicate browser is stuck
        if "timeout" in error_msg.lower() or "Command timeout" in str(e):
            return {"status": "timeout", "mp_id": mp_id, "reason": error_msg}
        return {"status": "error", "mp_id": mp_id, "reason": error_msg}
    finally:
        if tab:
            try:
                await asyncio.wait_for(tab.close(), timeout=5)
            except (asyncio.TimeoutError, Exception):
                # Tab close can fail if browser crashed or timeout occurred - safe to ignore
                pass


async def backfill_async(work_items: List[tuple], session, batch_size: int = 3):
    """Run backfill with Pydoll browser."""
    from pydoll.browser import Chrome
    from pydoll.browser.options import ChromiumOptions
    from app.scraper.browser import find_chrome_binary

    # Setup browser with proper Chrome detection
    options = ChromiumOptions()
    options.headless = True
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    # Use system Chrome binary
    chrome_path = await find_chrome_binary()
    if chrome_path:
        print(f"Using Chrome: {chrome_path}")
        options.binary_location = chrome_path
    else:
        print("ERROR: No Chrome binary found!")
        return 0, 0, len(work_items)

    print("Starting browser...")
    browser = Chrome(options=options)
    await browser.start()
    print("Browser ready!")

    total_updated = 0
    total_skipped = 0
    total_failed = 0
    blocked_count = 0
    timeout_count = 0
    consecutive_failed_batches = 0
    start_time = time.time()

    try:
        for batch_start in range(0, len(work_items), batch_size):
            batch = work_items[batch_start : batch_start + batch_size]
            batch_num = batch_start // batch_size + 1
            total_batches = (len(work_items) + batch_size - 1) // batch_size

            # Process batch concurrently
            tasks = [fetch_with_browser(browser, item_id, mp_id) for item_id, mp_id, title in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            batch_updated = 0
            batch_skipped = 0

            for result in results:
                if isinstance(result, Exception):
                    total_failed += 1
                    continue

                mp_id = result["mp_id"]

                if result["status"] == "success":
                    try:
                        # Ensure seller_name is never empty string (use NULL instead)
                        seller_name = result["seller_name"]
                        if seller_name == "":
                            seller_name = None

                        session.execute(
                            text("""
                            UPDATE marketprice
                            SET seller_name = :seller,
                                seller_feedback_score = :score,
                                seller_feedback_percent = :pct
                            WHERE id = :id
                        """),
                            {
                                "seller": seller_name,
                                "score": result["feedback_score"],
                                "pct": result["feedback_percent"],
                                "id": mp_id,
                            },
                        )
                        session.commit()
                        batch_updated += 1
                        print(f"    ✓ {mp_id}: {seller_name or '(no seller found)'}")
                    except Exception as e:
                        session.rollback()
                        total_failed += 1
                        print(f"    ✗ {mp_id}: DB error - {str(e)[:50]}")

                elif result["status"] == "blocked":
                    blocked_count += 1
                    total_failed += 1
                    if blocked_count >= 3:
                        print("\n⚠️  Blocked - restarting browser...")
                        try:
                            await asyncio.wait_for(browser.stop(), timeout=10)
                        except (asyncio.TimeoutError, Exception):
                            # Browser stop can fail if already crashed - safe to ignore
                            pass
                        await asyncio.sleep(5)
                        new_options = ChromiumOptions()
                        new_options.headless = True
                        new_options.add_argument("--disable-gpu")
                        new_options.add_argument("--no-sandbox")
                        new_options.add_argument("--disable-dev-shm-usage")
                        if chrome_path:
                            new_options.binary_location = chrome_path
                        browser = Chrome(options=new_options)
                        await browser.start()
                        blocked_count = 0
                        timeout_count = 0
                        print("Browser restarted!")

                elif result["status"] == "timeout":
                    timeout_count += 1
                    total_failed += 1
                    print(f"    ⏱ {mp_id}: timeout")
                    if timeout_count >= 3:
                        print("\n⚠️  Multiple timeouts - browser stuck, restarting...")
                        try:
                            await asyncio.wait_for(browser.stop(), timeout=10)
                        except (asyncio.TimeoutError, Exception):
                            # Browser stop can fail if already crashed - safe to ignore
                            print("    (force killing browser)")
                        await asyncio.sleep(3)
                        new_options = ChromiumOptions()
                        new_options.headless = True
                        new_options.add_argument("--disable-gpu")
                        new_options.add_argument("--no-sandbox")
                        new_options.add_argument("--disable-dev-shm-usage")
                        if chrome_path:
                            new_options.binary_location = chrome_path
                        browser = Chrome(options=new_options)
                        await browser.start()
                        timeout_count = 0
                        blocked_count = 0
                        print("Browser restarted!")

                elif result["status"] == "skip":
                    batch_skipped += 1
                    print(f"    - {mp_id}: {result['reason']}")
                else:
                    total_failed += 1

            total_updated += batch_updated
            total_skipped += batch_skipped

            # Progress
            elapsed = time.time() - start_time
            rate = (batch_start + len(batch)) / elapsed if elapsed > 0 else 0
            print(
                f"  Batch {batch_num}/{total_batches}: +{batch_updated} | "
                f"Total: {total_updated}/{len(work_items)} | {rate:.1f}/sec"
            )

            # If entire batch failed (0 updates, 0 skips), browser is likely stuck - restart immediately
            if batch_updated == 0 and batch_skipped == 0 and len(batch) > 0:
                consecutive_failed_batches += 1
                if consecutive_failed_batches >= 2:
                    print("\n⚠️  Multiple failed batches - browser stuck, force restarting...")
                    try:
                        await asyncio.wait_for(browser.stop(), timeout=5)
                    except (asyncio.TimeoutError, Exception):
                        # Browser stop can fail if already crashed - safe to ignore
                        print("    (force killing browser)")
                    await asyncio.sleep(3)
                    new_options = ChromiumOptions()
                    new_options.headless = True
                    new_options.add_argument("--disable-gpu")
                    new_options.add_argument("--no-sandbox")
                    new_options.add_argument("--disable-dev-shm-usage")
                    if chrome_path:
                        new_options.binary_location = chrome_path
                    browser = Chrome(options=new_options)
                    await browser.start()
                    timeout_count = 0
                    blocked_count = 0
                    consecutive_failed_batches = 0
                    print("Browser restarted!")
            else:
                consecutive_failed_batches = 0

            # Delay between batches
            if batch_start + batch_size < len(work_items):
                await asyncio.sleep(2)

    finally:
        print("\nClosing browser...")
        await browser.stop()

    return total_updated, total_skipped, total_failed


def backfill_seller_data(
    dry_run: bool = True,
    limit: Optional[int] = None,
    batch_size: int = 3,
    listing_type: str = "all",
    resume: bool = False,
):
    """Backfill seller data using Pydoll browser."""

    # Load checkpoint if resuming
    processed_ids = set()
    if resume:
        processed_ids, prev_stats = load_checkpoint()
        if processed_ids:
            print(f"Resuming from checkpoint: {len(processed_ids)} already processed")
            if prev_stats:
                print(f"  Previous stats: {prev_stats}")

    with Session(engine) as session:
        # First, fix any empty string seller_names
        fix_result = session.execute(text("UPDATE marketprice SET seller_name = NULL WHERE seller_name = ''"))
        if fix_result.rowcount > 0:
            session.commit()
            print(f"Fixed {fix_result.rowcount} empty seller_name -> NULL")

        # Find listings with NULL seller_name
        # Build type filter - uses allowlist pattern for safety
        type_filter = ""
        if listing_type == "sold":
            type_filter = "AND listing_type = 'sold'"
        elif listing_type == "active":
            type_filter = "AND listing_type = 'active'"

        # Use parameterized LIMIT to prevent SQL injection
        if limit:
            query = text(f"""
                SELECT id, external_id, url, title
                FROM marketprice
                WHERE seller_name IS NULL
                AND platform = 'ebay'
                AND (url IS NOT NULL OR external_id IS NOT NULL)
                {type_filter}
                ORDER BY COALESCE(sold_date, scraped_at) DESC NULLS LAST
                LIMIT :limit
            """)
            results = session.execute(query, {"limit": limit}).all()
        else:
            query = text(f"""
                SELECT id, external_id, url, title
                FROM marketprice
                WHERE seller_name IS NULL
                AND platform = 'ebay'
                AND (url IS NOT NULL OR external_id IS NOT NULL)
                {type_filter}
                ORDER BY COALESCE(sold_date, scraped_at) DESC NULLS LAST
            """)
            results = session.execute(query).all()
        print(f"Found {len(results)} listings missing seller data (type: {listing_type})")

        if not results:
            print("Nothing to process!")
            return

        if dry_run:
            print("\n[DRY RUN] Would process these items:")
            for i, row in enumerate(results[:20]):
                mp_id, external_id, url, title = row
                item_id = external_id or extract_item_id_from_url(url)
                print(f"  {i+1}. ID={mp_id} | eBay={item_id} | {(title or '')[:50]}...")
            if len(results) > 20:
                print(f"  ... and {len(results) - 20} more")
            return

        # Prepare work items, filtering out already processed
        work_items = []
        skipped_from_checkpoint = 0
        for mp_id, external_id, url, title in results:
            if mp_id in processed_ids:
                skipped_from_checkpoint += 1
                continue
            item_id = external_id or extract_item_id_from_url(url)
            if item_id:
                work_items.append((item_id, mp_id, title))

        if skipped_from_checkpoint > 0:
            print(f"Skipped {skipped_from_checkpoint} items (already in checkpoint)")

        print(f"\nProcessing {len(work_items)} items (batch_size={batch_size})...")
        print("-" * 60)

        if not work_items:
            print("No items to process!")
            clear_checkpoint()
            return

        start_time = time.time()
        try:
            total_updated, total_skipped, total_failed = asyncio.run(backfill_async(work_items, session, batch_size))
            # Clear checkpoint on successful completion
            clear_checkpoint()
            print("\n✓ Checkpoint cleared (run completed)")
        except KeyboardInterrupt:
            print("\n\n⚠️  Interrupted! Progress saved to checkpoint.")
            print("   Run with --resume to continue.")
            raise

        # Summary
        elapsed = time.time() - start_time
        print(f"\n{'='*60}")
        print("BACKFILL COMPLETE")
        print(f"{'='*60}")
        print(f"  Total processed: {len(work_items)}")
        print(f"  Updated: {total_updated}")
        print(f"  Skipped: {total_skipped}")
        print(f"  Failed: {total_failed}")
        print(f"  Time: {elapsed:.1f}s ({len(work_items)/elapsed:.1f} items/sec)")


def main():
    parser = argparse.ArgumentParser(description="Backfill seller data for eBay listings")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be updated")
    parser.add_argument("--execute", action="store_true", help="Actually execute the backfill")
    parser.add_argument("--limit", type=int, help="Limit number of items to process")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of concurrent requests (default: 3)")
    parser.add_argument(
        "--type", choices=["all", "sold", "active"], default="all", help="Listing type to backfill (default: all)"
    )
    parser.add_argument("--resume", action="store_true", help="Resume from last checkpoint")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        print("  --dry-run: Preview what would be updated")
        print("  --execute: Actually run the backfill")
        print("  --batch-size N: Process N items concurrently (default: 3)")
        print("  --type TYPE: sold, active, or all (default: all)")
        print("  --resume: Resume from last checkpoint")
        return

    dry_run = not args.execute

    print(f"Seller Data Backfill - {'DRY RUN' if dry_run else 'EXECUTING'}")
    print(f"Started: {datetime.now()}")
    print(f"Batch size: {args.batch_size}")
    print(f"Listing type: {args.type}")
    print(f"Resume: {args.resume}")
    print("=" * 60)

    backfill_seller_data(
        dry_run=dry_run, limit=args.limit, batch_size=args.batch_size, listing_type=args.type, resume=args.resume
    )


if __name__ == "__main__":
    main()
