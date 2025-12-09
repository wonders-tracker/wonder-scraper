#!/usr/bin/env python3
"""
Backfill seller data for sold eBay listings using Pydoll (undetected Chrome).

Uses batch processing with multiple concurrent tabs for speed.

Usage:
    python scripts/backfill_seller_data.py --dry-run        # Preview what would be updated
    python scripts/backfill_seller_data.py --execute        # Actually run the backfill
    python scripts/backfill_seller_data.py --execute --limit 100  # Limit to 100 items
    python scripts/backfill_seller_data.py --execute --batch-size 5  # 5 concurrent tabs
"""

import argparse
import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, List

from bs4 import BeautifulSoup
from sqlmodel import Session
from sqlalchemy import text

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine


def extract_item_id_from_url(url: str) -> Optional[str]:
    """Extract eBay item ID from URL."""
    if not url:
        return None
    match = re.search(r'/itm/(?:[^/]+/)?(\d+)', url)
    if match:
        return match.group(1)
    return None


def extract_seller_from_html(html: str) -> Tuple[Optional[str], Optional[int], Optional[float]]:
    """
    Extract seller info from eBay item page HTML.
    Returns: (seller_name, feedback_score, feedback_percent)
    """
    soup = BeautifulSoup(html, 'html.parser')

    seller_name = None
    feedback_score = None
    feedback_percent = None

    # Method 1: Look for sid= parameter in seller store links (most reliable for ended listings)
    # Pattern: sid=seller_username or _ssn=Seller Name
    sid_match = re.search(r'[?&]sid=([a-zA-Z0-9_\-\.]+)', html)
    if sid_match:
        seller_name = sid_match.group(1).strip()

    # Method 2: Look for _ssn in JSON metadata (seller store name)
    if not seller_name:
        ssn_match = re.search(r'"_ssn":\s*"([^"]+)"', html)
        if ssn_match:
            # This gives display name like "BRM Collectibles", extract username from sid if possible
            # Otherwise use the display name
            display_name = ssn_match.group(1).strip()
            # Don't use display name directly - it might have spaces
            # Try to find the sid nearby or use Method 1's result
            pass

    # Method 3: Look for /usr/ link in href
    if not seller_name:
        for link in soup.find_all('a', href=True):
            href = link.get('href', '')
            if '/usr/' in href:
                match = re.search(r'/usr/([^/?]+)', href)
                if match and match.group(1) != '@@':  # Skip placeholder
                    seller_name = match.group(1).strip()
                    break

    # Method 4: Look in JSON data embedded in page
    if not seller_name:
        # Look for seller in various JSON patterns
        patterns = [
            r'"seller":\s*\{\s*"username":\s*"([^"]+)"',
            r'"sellerName":\s*"([^"]+)"',
            r'"seller_name":\s*"([^"]+)"',
            r'sellerInfo.*?"username":\s*"([^"]+)"',
            r'"userId":\s*"([^"]+)".*?"sellerLevel"',  # userId near sellerLevel context
        ]
        for pattern in patterns:
            match = re.search(pattern, html)
            if match:
                seller_name = match.group(1).strip()
                break

    # Method 5: Look for seller card/section links
    if not seller_name:
        seller_selectors = [
            '.x-sellercard-atf__info__about-seller a',
            '.ux-seller-section__item--seller a',
            '[data-testid="ux-seller-section"] a',
            '.seller-persona a',
            '.mbg-nw',
        ]
        for selector in seller_selectors:
            elem = soup.select_one(selector)
            if elem:
                href = elem.get('href', '')
                if '/usr/' in href:
                    match = re.search(r'/usr/([^/?]+)', href)
                    if match and match.group(1) != '@@':
                        seller_name = match.group(1).strip()
                        break
                # Also check for sid= in the href
                if 'sid=' in href:
                    match = re.search(r'sid=([a-zA-Z0-9_\-\.]+)', href)
                    if match:
                        seller_name = match.group(1).strip()
                        break

    # Extract feedback if we found seller
    if seller_name:
        # Look for feedback percentage
        feedback_match = re.search(r'([\d.]+)%\s*positive', html, re.IGNORECASE)
        if feedback_match:
            feedback_percent = float(feedback_match.group(1))

        # Look for feedback score
        score_match = re.search(r'\((\d[\d,]*)\)', html)
        if score_match:
            feedback_score = int(score_match.group(1).replace(',', ''))

    return seller_name, feedback_score, feedback_percent


async def fetch_page_with_pydoll(browser, url: str, timeout: int = 30) -> Optional[str]:
    """Fetch a page using Pydoll browser."""
    tab = None
    try:
        tab = await browser.new_tab()
        await tab.go_to(url, timeout=timeout)
        await asyncio.sleep(2)  # Let page settle
        # Use execute_script to get page HTML since Pydoll doesn't have get_page_source
        result = await tab.execute_script(
            "return document.documentElement.outerHTML;",
            return_by_value=True
        )
        # Extract the value from the response - it's a dict with nested structure
        if isinstance(result, dict):
            # Dict path: result['result']['result']['value']
            inner = result.get('result', {})
            if isinstance(inner, dict):
                value = inner.get('result', {}).get('value')
                if value:
                    return value
        # Object path (fallback)
        if hasattr(result, 'result') and hasattr(result.result, 'value'):
            return result.result.value
        return None
    except Exception as e:
        print(f"    Error fetching {url}: {e}")
        return None
    finally:
        if tab:
            try:
                await tab.close()
            except:
                pass


async def process_batch(browser, batch: List[tuple], session) -> dict:
    """Process a batch of items concurrently."""
    results = {"updated": 0, "skipped": 0, "failed": 0}

    async def process_item(item):
        mp_id, external_id, url, title = item
        ebay_item_id = external_id or extract_item_id_from_url(url)

        if not ebay_item_id:
            return ("skip", mp_id, "no item ID")

        item_url = f"https://www.ebay.com/itm/{ebay_item_id}"
        html = await fetch_page_with_pydoll(browser, item_url)

        if not html:
            return ("skip", mp_id, "fetch failed")

        # Check for CAPTCHA/block
        if "Pardon Our Interruption" in html or "Security Measure" in html:
            return ("fail", mp_id, "blocked by eBay")

        seller_name, feedback_score, feedback_percent = extract_seller_from_html(html)

        if not seller_name:
            return ("skip", mp_id, "no seller found")

        return ("success", mp_id, seller_name, feedback_score, feedback_percent)

    # Process batch concurrently
    tasks = [process_item(item) for item in batch]
    batch_results = await asyncio.gather(*tasks, return_exceptions=True)

    # Update database with results
    for result in batch_results:
        if isinstance(result, Exception):
            results["failed"] += 1
            continue

        status = result[0]
        mp_id = result[1]

        if status == "success":
            seller_name, feedback_score, feedback_percent = result[2], result[3], result[4]
            try:
                session.execute(text("""
                    UPDATE marketprice
                    SET seller_name = :seller,
                        seller_feedback_score = :score,
                        seller_feedback_percent = :pct
                    WHERE id = :id
                """), {
                    "seller": seller_name,
                    "score": feedback_score,
                    "pct": feedback_percent,
                    "id": mp_id
                })
                session.commit()
                results["updated"] += 1
                print(f"    [{mp_id}] Updated: {seller_name}")
            except Exception as e:
                print(f"    [{mp_id}] DB error: {e}")
                session.rollback()
                results["failed"] += 1
        elif status == "skip":
            results["skipped"] += 1
            print(f"    [{mp_id}] Skip: {result[2]}")
        else:
            results["failed"] += 1
            print(f"    [{mp_id}] Failed: {result[2]}")

    return results


async def create_browser():
    """Create and start a new Pydoll browser."""
    from pydoll.browser import Chrome
    from pydoll.browser.options import ChromiumOptions

    options = ChromiumOptions()
    options.headless = True
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    browser = Chrome(options=options)
    await browser.start()
    return browser


async def backfill_seller_data_async(dry_run: bool = True, limit: Optional[int] = None, batch_size: int = 3):
    """Backfill seller data using Pydoll."""
    with Session(engine) as session:
        # Find sold listings with NULL seller_name
        query = text("""
            SELECT id, external_id, url, title
            FROM marketprice
            WHERE listing_type = 'sold'
            AND seller_name IS NULL
            AND platform = 'ebay'
            AND (url IS NOT NULL OR external_id IS NOT NULL)
            ORDER BY sold_date DESC
        """ + (f" LIMIT {limit}" if limit else ""))

        results = session.execute(query).all()
        print(f"Found {len(results)} sold listings missing seller data")

        if dry_run:
            print("\n[DRY RUN] Would process these items:")
            for i, row in enumerate(results[:20]):
                mp_id, external_id, url, title = row
                item_id = external_id or extract_item_id_from_url(url)
                print(f"  {i+1}. ID={mp_id} | eBay={item_id} | {(title or '')[:50]}...")
            if len(results) > 20:
                print(f"  ... and {len(results) - 20} more")
            return

        # Setup browser
        print(f"\nStarting Pydoll browser (batch_size={batch_size})...")
        browser = await create_browser()
        print("Browser started successfully")

        total_updated = 0
        total_skipped = 0
        total_failed = 0
        consecutive_failures = 0
        max_consecutive_failures = 2  # Restart browser after 2 failed batches

        try:
            # Process in batches
            for i in range(0, len(results), batch_size):
                batch = results[i:i + batch_size]
                batch_num = i // batch_size + 1
                total_batches = (len(results) + batch_size - 1) // batch_size

                print(f"\n=== Batch {batch_num}/{total_batches} (items {i+1}-{min(i+batch_size, len(results))}) ===")

                batch_results = await process_batch(browser, batch, session)

                total_updated += batch_results["updated"]
                total_skipped += batch_results["skipped"]
                total_failed += batch_results["failed"]

                # Track consecutive failures to detect stuck browser
                if batch_results["updated"] == 0 and batch_results["skipped"] == batch_size:
                    consecutive_failures += 1
                    print(f"    WARNING: All items failed/skipped ({consecutive_failures}/{max_consecutive_failures})")
                else:
                    consecutive_failures = 0

                print(f"    Batch: +{batch_results['updated']} updated, {batch_results['skipped']} skipped, {batch_results['failed']} failed")
                print(f"    Total: {total_updated} updated, {total_skipped} skipped, {total_failed} failed")

                # Restart browser if it seems stuck
                if consecutive_failures >= max_consecutive_failures:
                    print("\n    >>> Browser appears stuck, restarting...")
                    try:
                        await browser.stop()
                    except:
                        pass
                    await asyncio.sleep(3)
                    browser = await create_browser()
                    print("    >>> Browser restarted successfully")
                    consecutive_failures = 0

                # Small delay between batches to be nice
                await asyncio.sleep(1)

            print(f"\n{'='*60}")
            print("BACKFILL COMPLETE")
            print(f"{'='*60}")
            print(f"  Total processed: {len(results)}")
            print(f"  Updated: {total_updated}")
            print(f"  Skipped: {total_skipped}")
            print(f"  Failed: {total_failed}")
        finally:
            print("\nClosing browser...")
            try:
                await browser.stop()
            except Exception as e:
                print(f"Error stopping browser: {e}")


def backfill_seller_data(dry_run: bool = True, limit: Optional[int] = None, batch_size: int = 3):
    """Wrapper to run async backfill."""
    asyncio.run(backfill_seller_data_async(dry_run, limit, batch_size))


def main():
    parser = argparse.ArgumentParser(description="Backfill seller data for eBay sold listings")
    parser.add_argument("--dry-run", action="store_true", help="Preview what would be updated")
    parser.add_argument("--execute", action="store_true", help="Actually execute the backfill")
    parser.add_argument("--limit", type=int, help="Limit number of items to process")
    parser.add_argument("--batch-size", type=int, default=3, help="Number of concurrent tabs (default: 3)")

    args = parser.parse_args()

    if not args.dry_run and not args.execute:
        print("Please specify --dry-run or --execute")
        print("  --dry-run: Preview what would be updated")
        print("  --execute: Actually run the backfill")
        print("  --batch-size N: Process N items concurrently (default: 3)")
        return

    dry_run = not args.execute

    print(f"Seller Data Backfill - {'DRY RUN' if dry_run else 'EXECUTING'}")
    print(f"Started: {datetime.now()}")
    print(f"Batch size: {args.batch_size}")
    print("=" * 60)

    backfill_seller_data(dry_run=dry_run, limit=args.limit, batch_size=args.batch_size)


if __name__ == "__main__":
    main()
