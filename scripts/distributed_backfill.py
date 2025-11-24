"""
Distributed backfill script using multiprocessing for parallel scraping.
"""
import asyncio
import multiprocessing as mp
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager
import sys

import asyncio
import multiprocessing as mp
from datetime import datetime, timedelta
from typing import List
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager
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

async def process_card_batch(cards_data: List[dict], is_backfill: bool = False):
    """Process a batch of cards using a single browser instance."""
    results = []
    try:
        # Ensure browser is ready
        await get_process_browser()

        for i, card_data in enumerate(cards_data):
            try:
                print(f"[Worker {os.getpid()}] Processing {i+1}/{len(cards_data)}: {card_data['name']}")
                # We need to modify scrape_card to accept an existing browser or handle the browser internally
                # better. For now, since scrape_card calls get_page_content which calls BrowserManager.get_browser(),
                # and we've initialized it in this process, it should reuse the global one if BrowserManager is designed right.
                # However, BrowserManager._browser is a class attribute, so it is global per process.
                # We just need to ensure we DON'T close it inside scrape_card.

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
                print(f"[Worker {os.getpid()}] Error on {card_data['name']}: {e}")
                results.append(False)
                # If error is severe (browser crash), try to restart for next card
                try:
                    await BrowserManager.restart()
                except:
                    pass
                    
    except Exception as e:
        print(f"[Worker {os.getpid()}] Batch failed: {e}")
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

async def distributed_backfill(num_workers: int = 2, force_all: bool = False, limit: int = 1000, is_backfill: bool = False):
    """
    Distributed backfill using multiprocessing with batching.

    Args:
        num_workers: Number of parallel worker processes (Default 2 for safety)
        force_all: If True, scrape all cards regardless of age
        limit: Maximum cards to process
        is_backfill: If True, use higher page limits for historical data capture
    """
    mode = "HISTORICAL BACKFILL" if is_backfill else "Incremental Update"
    print(f"Starting {mode} with {num_workers} workers...")
    
    # Fetch cards that need scraping
    with Session(engine) as session:
        all_cards = session.exec(select(Card)).all()
        
        cards_to_scrape = []
        cutoff_time = datetime.utcnow() - timedelta(hours=4) # Reduced to 4 hours for freshness
        
        for card in all_cards:
            if force_all:
                cards_to_scrape.append(card)
            else:
                # Check latest snapshot
                snapshot = session.exec(
                    select(MarketSnapshot)
                    .where(MarketSnapshot.card_id == card.id)
                    .order_by(MarketSnapshot.timestamp.desc())
                    .limit(1)
                ).first()
                
                if not snapshot or snapshot.timestamp < cutoff_time:
                    cards_to_scrape.append(card)
                    
            if len(cards_to_scrape) >= limit:
                break
    
    if not cards_to_scrape:
        print("No cards need updating.")
        return
    
    print(f"Found {len(cards_to_scrape)} cards to scrape.")
    
    # Prepare card data
    card_data_list = [
        {
            'id': card.id,
            'name': card.name,
            'set_name': card.set_name,
            'search_term': f"{card.name} {card.set_name}",
            'product_type': card.product_type if hasattr(card, 'product_type') else 'Single'
        }
        for card in cards_to_scrape
    ]
    
    # Chunk data for workers
    # Larger chunks = less browser restarts = faster, but higher memory risk. 
    # 20 per chunk seems safe for Chrome.
    chunk_size = 20 
    chunks = [card_data_list[i:i + chunk_size] for i in range(0, len(card_data_list), chunk_size)]
    
    print(f"Split into {len(chunks)} batches of size {chunk_size}.")
    print(f"Distributing across {num_workers} workers...")
    
    total_success = 0
    total_processed = 0

    # Prepare arguments for worker (each chunk needs the is_backfill flag)
    worker_args = [(chunk, is_backfill) for chunk in chunks]

    # Use map to process chunks
    with mp.Pool(processes=num_workers) as pool:
        batch_results = pool.map(worker_process_batch, worker_args)
        
    for res in batch_results:
        total_processed += len(res)
        total_success += sum(1 for r in res if r)
    
    print(f"\n=== Backfill Complete ===")
    print(f"Processed: {total_processed}")
    print(f"Success: {total_success}")
    print(f"Failed: {total_processed - total_success}")

if __name__ == "__main__":
    # Parse command line args
    num_workers = int(sys.argv[1]) if len(sys.argv) > 1 else 3 # Default to 3 for balanced performance
    force_all = '--force' in sys.argv
    is_backfill = '--historical' in sys.argv or '--backfill' in sys.argv
    # For historical backfill, process all cards; otherwise limit to 1000
    limit = 10000 if is_backfill else 1000

    # Set multiprocessing start method
    mp.set_start_method('spawn', force=True)

    asyncio.run(distributed_backfill(num_workers=num_workers, force_all=force_all, limit=limit, is_backfill=is_backfill))

