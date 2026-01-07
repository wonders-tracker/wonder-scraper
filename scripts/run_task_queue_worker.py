#!/usr/bin/env python3
"""
Task Queue Worker - Processes scrape tasks from the persistent queue.

Run with: python scripts/run_task_queue_worker.py

This provides crash recovery - if the worker dies, tasks remain in the queue
and will be picked up on restart.

The worker claims tasks atomically using SELECT FOR UPDATE SKIP LOCKED,
so multiple workers can run concurrently without conflicts.

Usage:
    python scripts/run_task_queue_worker.py                # Process eBay tasks
    python scripts/run_task_queue_worker.py --source ebay  # Explicit source
    python scripts/run_task_queue_worker.py --source blokpax  # Different source
"""

import asyncio
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add project root to path
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from sqlmodel import Session  # noqa: E402

from app.db import engine  # noqa: E402
from app.models.card import Card, Rarity  # noqa: E402
from app.models.scrape_task import ScrapeTask  # noqa: E402
from app.services.task_queue import (  # noqa: E402
    claim_next_task_sync,
    complete_task_sync,
    fail_task_sync,
    reset_stale_tasks_sync,
    get_queue_stats_sync,
)
from app.scraper.browser import BrowserManager  # noqa: E402
from scripts.scrape_card import scrape_card as scrape_sold_data  # noqa: E402

# Global shutdown flag
shutdown_requested = False


def handle_shutdown(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    global shutdown_requested
    print("\n[Worker] Shutdown requested, finishing current task...")
    shutdown_requested = True


async def process_task(session: Session, task: ScrapeTask) -> bool:
    """
    Process a single scrape task.

    Args:
        session: Database session
        task: The ScrapeTask to process

    Returns:
        True if successful, False otherwise
    """
    card = None
    try:
        # Get card info
        card = session.get(Card, task.card_id)
        if not card:
            fail_task_sync(session, task.id, f"Card {task.card_id} not found")
            return False

        # Get rarity name for better scraping
        rarity_name = ""
        if card.rarity_id:
            rarity = session.get(Rarity, card.rarity_id)
            if rarity:
                rarity_name = rarity.name

        search_term = f"{card.name} {card.set_name}"
        product_type = getattr(card, "product_type", "Single") or "Single"

        print(f"[Worker] Processing: {card.name} (task {task.id}, attempt {task.attempts})")

        # Scrape based on source
        if task.source == "ebay":
            await scrape_sold_data(
                card_name=card.name,
                card_id=card.id,
                rarity_name=rarity_name,
                search_term=search_term,
                set_name=card.set_name,
                product_type=product_type,
            )
        elif task.source == "blokpax":
            # Future: Add Blokpax per-card scraping
            print(f"[Worker] Blokpax scraping not yet implemented for card {card.name}")
        elif task.source == "opensea":
            # Future: Add OpenSea per-card scraping
            print(f"[Worker] OpenSea scraping not yet implemented for card {card.name}")
        else:
            fail_task_sync(session, task.id, f"Unknown source: {task.source}")
            return False

        complete_task_sync(session, task.id)
        print(f"[Worker] Completed: {card.name}")
        return True

    except Exception as e:
        error_msg = f"{type(e).__name__}: {str(e)}"
        card_name = card.name if card else f"card_id={task.card_id}"
        fail_task_sync(session, task.id, error_msg)
        print(f"[Worker] Failed: {card_name} - {error_msg[:100]}")
        return False


async def worker_loop(source: str = "ebay"):
    """
    Main worker loop.

    Continuously claims and processes tasks from the queue until shutdown.

    Args:
        source: The source platform to process tasks for ("ebay", "blokpax", "opensea")
    """
    global shutdown_requested

    print(f"[Worker] Starting {source} worker...")

    # Reset stale tasks from previous crashes
    with Session(engine) as session:
        stats = reset_stale_tasks_sync(session, timeout_minutes=30)
        if stats["reset"] > 0:
            print(f"[Worker] Reset {stats['reset']} stale tasks from previous run")

        # Show initial queue stats
        queue_stats = get_queue_stats_sync(session, source=source)
        print(f"[Worker] Queue stats: {queue_stats}")

    idle_count = 0
    processed_count = 0
    failed_count = 0

    while not shutdown_requested:
        with Session(engine) as session:
            task = claim_next_task_sync(session, source=source)

            if task:
                idle_count = 0
                success = await process_task(session, task)
                if success:
                    processed_count += 1
                else:
                    failed_count += 1

                # Brief delay between tasks to avoid hammering eBay
                if not shutdown_requested:
                    await asyncio.sleep(2)
            else:
                idle_count += 1
                # Log every minute when idle (12 * 5s = 60s)
                if idle_count % 12 == 1:
                    queue_stats = get_queue_stats_sync(session, source=source)
                    print(f"[Worker] Queue empty, waiting... (stats: {queue_stats})")
                await asyncio.sleep(5)

    # Shutdown summary
    print(f"[Worker] Shutting down... Processed: {processed_count}, Failed: {failed_count}")

    # Close browser if it was started
    try:
        await BrowserManager.close()
    except Exception:
        pass


async def main(source: str = "ebay"):
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print(f"[Worker] Starting at {datetime.now(timezone.utc).isoformat()}")
    print("[Worker] Press Ctrl+C to gracefully shutdown")

    try:
        await worker_loop(source)
    finally:
        print("[Worker] Cleanup complete")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Task Queue Worker - Process scrape tasks from queue")
    parser.add_argument(
        "--source",
        type=str,
        default="ebay",
        choices=["ebay", "blokpax", "opensea"],
        help="Source platform to process tasks for (default: ebay)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.source))
