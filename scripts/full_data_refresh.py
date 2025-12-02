"""
Complete data refresh: eBay cards + boxes/packs + OpenSea collections using distributed workers
"""
import asyncio
import multiprocessing as mp
from datetime import datetime
from typing import List
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager
from app.scraper.opensea import scrape_opensea_collection
import sys
import os

# Global browser lock for the process
_process_browser = None

async def get_process_browser():
    """Get or create a persistent browser for this process."""
    global _process_browser
    if _process_browser is None:
        _process_browser = await BrowserManager.get_browser()
    return _process_browser

async def process_card_batch(cards_data: List[dict], is_backfill: bool = True):
    """Process a batch of cards using a single browser instance."""
    results = []
    try:
        # Ensure browser is ready
        await get_process_browser()

        for i, card_data in enumerate(cards_data):
            try:
                print(f"[Worker {os.getpid()}] Processing {i+1}/{len(cards_data)}: {card_data['name']}", flush=True)

                await scrape_card(
                    card_name=card_data['name'],
                    card_id=card_data['id'],
                    search_term=card_data['search_term'],
                    set_name=card_data['set_name'],
                    product_type=card_data['product_type'],
                    is_backfill=is_backfill
                )
                results.append(True)
            except Exception as e:
                print(f"[Worker {os.getpid()}] Error on {card_data['name']}: {e}", flush=True)
                results.append(False)
                # If error is severe (browser crash), try to restart for next card
                try:
                    await BrowserManager.restart()
                except:
                    pass

    except Exception as e:
        print(f"[Worker {os.getpid()}] Batch failed: {e}", flush=True)
    finally:
        # Close browser at the end of the batch to free resources
        await BrowserManager.close()
        global _process_browser
        _process_browser = None

    return results

def worker_process_batch(args):
    """Wrapper to run async batch in a process."""
    cards_data, is_backfill = args
    return asyncio.run(process_card_batch(cards_data, is_backfill=is_backfill))

async def scrape_all_ebay_parallel(num_workers: int = 2):
    """Scrape all cards, boxes, and packs from eBay using parallel workers"""
    print("=" * 60)
    print(f"SCRAPING EBAY WITH {num_workers} WORKERS (Cards, Boxes, Packs)")
    print("=" * 60)

    # Fetch all cards
    with Session(engine) as session:
        cards = session.exec(select(Card)).all()

    print(f"Found {len(cards)} products to scrape from eBay...")

    # Prepare card data - SKIP "The First" as it's too problematic
    card_data_list = [
        {
            'id': card.id,
            'name': card.name,
            'set_name': card.set_name,
            'search_term': f"{card.name} {card.set_name}",
            'product_type': card.product_type if hasattr(card, 'product_type') else 'Single'
        }
        for card in cards
        if card.name != "The First"  # Skip this problematic card
    ]

    # Chunk data for workers (20 per chunk for safety)
    chunk_size = 20
    chunks = [card_data_list[i:i + chunk_size] for i in range(0, len(card_data_list), chunk_size)]

    print(f"Split into {len(chunks)} batches of size {chunk_size}.")
    print(f"Distributing across {num_workers} workers...")

    total_success = 0
    total_processed = 0

    # Prepare arguments for worker (each chunk needs the is_backfill flag)
    worker_args = [(chunk, True) for chunk in chunks]

    # Use map to process chunks
    with mp.Pool(processes=num_workers) as pool:
        batch_results = pool.map(worker_process_batch, worker_args)

    for res in batch_results:
        total_processed += len(res)
        total_success += sum(1 for r in res if r)

    print(f"\n=== eBay Scraping Complete ===")
    print(f"Processed: {total_processed}")
    print(f"Success: {total_success}")
    print(f"Failed: {total_processed - total_success}")

async def scrape_all_opensea():
    """Scrape OpenSea collections"""
    print("\n" + "=" * 60)
    print("SCRAPING OPENSEA COLLECTIONS")
    print("=" * 60)

    COLLECTION_MAP = {
        "https://opensea.io/collection/wotf-character-proofs": "Character Proofs",
        "https://opensea.io/collection/wotf-existence-collector-boxes": "Collector Booster Box"
    }

    await BrowserManager.get_browser()

    try:
        for url, card_name in COLLECTION_MAP.items():
            print(f"\n📦 Processing OpenSea: {card_name}")

            # 1. Scrape Data
            stats = await scrape_opensea_collection(url)
            print(f"Stats: {stats}")

            if not stats or stats.get("floor_price_usd", 0) == 0:
                print("⚠️  No valid data found, skipping...")
                continue

            # 2. Find Card in DB
            with Session(engine) as session:
                card = session.exec(select(Card).where(Card.name == card_name)).first()

                if not card:
                    print(f"❌ Card '{card_name}' not found in DB.")
                    continue

                # 3. Create Snapshot
                snapshot = MarketSnapshot(
                    card_id=card.id,
                    platform="opensea",
                    min_price=stats["floor_price_usd"],
                    max_price=0,
                    avg_price=stats["floor_price_usd"],
                    volume=int(stats.get("total_volume", 0)),
                    inventory=stats["listed_count"] if stats["listed_count"] > 0 else int(stats["owners"] * 0.1),
                    lowest_ask=stats["floor_price_usd"]
                )

                session.add(snapshot)
                session.commit()
                session.refresh(snapshot)
                print(f"✅ Saved OpenSea Snapshot ID: {snapshot.id} for {card.name}")
    finally:
        await BrowserManager.close()

async def main(num_workers: int):
    print("\n🚀 FULL DATA REFRESH STARTING...")
    print("This will scrape:")
    print("  1. All eBay cards (singles) using parallel workers")
    print("  2. All eBay boxes/packs using parallel workers")
    print("  3. All OpenSea collections")
    print()

    # Check current data
    with Session(engine) as session:
        snapshot_count = len(session.exec(select(MarketSnapshot)).all())
        card_count = len(session.exec(select(Card)).all())

    print(f"📊 Current Data in Neon:")
    print(f"   - Cards: {card_count}")
    print(f"   - Snapshots: {snapshot_count}")
    print()

    # 1. Scrape eBay (all products) with parallel workers
    await scrape_all_ebay_parallel(num_workers=num_workers)

    # 2. Scrape OpenSea
    await scrape_all_opensea()

    # Final stats
    with Session(engine) as session:
        new_snapshot_count = len(session.exec(select(MarketSnapshot)).all())

    print("\n" + "=" * 60)
    print("✅ FULL DATA REFRESH COMPLETE!")
    print("=" * 60)
    print(f"New snapshots created: {new_snapshot_count - snapshot_count}")
    print(f"Total snapshots: {new_snapshot_count}")

if __name__ == "__main__":
    # Parse number of workers from args (default 2)
    num_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 2

    # Set multiprocessing start method BEFORE starting async event loop
    mp.set_start_method('spawn', force=True)

    # Run async main
    asyncio.run(main(num_workers=num_workers))
