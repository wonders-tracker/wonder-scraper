import asyncio
import random
import time
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select
from sqlalchemy import func
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.models.blokpax import BlokpaxStorefront, BlokpaxSnapshot
from scripts.scrape_card import scrape_card as scrape_sold_data
from app.scraper.active import scrape_active_data
from app.scraper.browser import BrowserManager
from app.scraper.blokpax import (
    WOTF_STOREFRONTS,
    get_bpx_price,
    scrape_storefront_floor,
    scrape_recent_sales,
    is_wotf_asset,
)
from app.discord_bot.logger import log_scrape_start, log_scrape_complete, log_scrape_error
from datetime import datetime, timedelta
import concurrent.futures

scheduler = AsyncIOScheduler()

async def scrape_single_card(card: Card):
    """Scrape a single card with full data (sold + active)."""
    try:
        search_term = f"{card.name} {card.set_name}"
        print(f"[Polling] Updating: {search_term}")
        
        # Scrape sold data (creates snapshot)
        await scrape_sold_data(
            card_name=card.name,
            card_id=card.id,
            search_term=search_term,
            set_name=card.set_name,
            product_type=card.product_type if hasattr(card, 'product_type') else 'Single'
        )
        
        # Get active data
        low_ask, inventory, high_bid = await scrape_active_data(card.name, card.id, search_term=search_term)
        
        # Update snapshot with active data
        with Session(engine) as session:
            statement = select(MarketSnapshot).where(
                MarketSnapshot.card_id == card.id
            ).order_by(MarketSnapshot.timestamp.desc())
            snapshot = session.exec(statement).first()
            if snapshot:
                snapshot.lowest_ask = low_ask
                snapshot.inventory = inventory
                snapshot.highest_bid = high_bid
                session.add(snapshot)
                session.commit()
                print(f"[Polling] Updated {card.name}: Ask=${low_ask}, Inv={inventory}")
        
        return True
    except Exception as e:
        print(f"[Polling] Error updating {card.name}: {e}")
        return False

async def job_update_market_data():
    """
    Optimized polling job - scrapes cards in batches with concurrency control.
    Includes robust error handling for browser startup failures.
    """
    print(f"[{datetime.utcnow()}] Starting Scheduled Market Update...")
    start_time = time.time()

    with Session(engine) as session:
        # Get cards that haven't been updated in the last hour (or all if none)
        cutoff_time = datetime.utcnow() - timedelta(hours=1)

        # Subquery for latest snapshot per card
        latest_snapshots = (
            select(
                MarketSnapshot.card_id,
                func.max(MarketSnapshot.timestamp).label('latest_timestamp')
            )
            .group_by(MarketSnapshot.card_id)
            .subquery()
        )

        # Get cards needing updates
        cards_query = (
            select(Card)
            .outerjoin(latest_snapshots, Card.id == latest_snapshots.c.card_id)
            .where(
                (latest_snapshots.c.latest_timestamp < cutoff_time) |
                (latest_snapshots.c.latest_timestamp == None)
            )
        )

        cards_to_update = session.exec(cards_query).all()

        # If no stale cards, update a random sample
        if not cards_to_update:
            all_cards = session.exec(select(Card)).all()
            cards_to_update = random.sample(all_cards, min(10, len(all_cards)))

    if not cards_to_update:
        print("[Polling] No cards to update.")
        return

    print(f"[Polling] Updating {len(cards_to_update)} cards...")

    # Log scrape start to Discord
    log_scrape_start(len(cards_to_update), scrape_type="scheduled")

    # Initialize browser with retry logic
    max_browser_retries = 3
    browser_started = False

    for attempt in range(max_browser_retries):
        try:
            print(f"[Polling] Browser startup attempt {attempt + 1}/{max_browser_retries}...")
            await BrowserManager.get_browser()
            browser_started = True
            print("[Polling] Browser started successfully!")
            break
        except Exception as e:
            print(f"[Polling] Browser startup failed (attempt {attempt + 1}): {type(e).__name__}: {e}")
            # Clean up any partial state
            await BrowserManager.close()
            if attempt < max_browser_retries - 1:
                wait_time = (attempt + 1) * 10  # 10s, 20s, 30s
                print(f"[Polling] Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

    if not browser_started:
        print("[Polling] ERROR: Could not start browser after all retries. Skipping this update cycle.")
        return

    try:
        # Process cards with controlled concurrency (max 3 concurrent)
        batch_size = 3
        successful = 0
        failed = 0

        for i in range(0, len(cards_to_update), batch_size):
            batch = cards_to_update[i:i+batch_size]

            # Process batch concurrently
            tasks = [scrape_single_card(card) for card in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Count successes/failures
            for result in results:
                if isinstance(result, Exception):
                    failed += 1
                elif result:
                    successful += 1
                else:
                    failed += 1

            # Brief delay between batches
            if i + batch_size < len(cards_to_update):
                await asyncio.sleep(5)

        print(f"[Polling] Results: {successful} successful, {failed} failed out of {len(cards_to_update)} cards")

        # Log scrape complete to Discord
        duration = time.time() - start_time
        log_scrape_complete(
            cards_processed=len(cards_to_update),
            new_listings=0,  # Scheduled scrapes don't track new listings separately
            new_sales=0,
            duration_seconds=duration,
            errors=failed
        )

    except Exception as e:
        print(f"[Polling] ERROR during scraping: {type(e).__name__}: {e}")
        log_scrape_error("Scheduled Job", str(e))

    finally:
        await BrowserManager.close()

    print(f"[{datetime.utcnow()}] Scheduled Update Complete.")


async def job_update_blokpax_data():
    """
    Scheduled job to update Blokpax floor prices and sales.
    Runs on a separate interval from eBay since it's lightweight (API-based).
    """
    print(f"[{datetime.utcnow()}] Starting Blokpax Update...")
    start_time = time.time()

    log_scrape_start(len(WOTF_STOREFRONTS), scrape_type="blokpax")

    errors = 0
    total_sales = 0

    try:
        bpx_price = await get_bpx_price()
        print(f"[Blokpax] BPX Price: ${bpx_price:.6f} USD")

        for slug in WOTF_STOREFRONTS:
            try:
                # Scrape floor prices
                floor_data = await scrape_storefront_floor(slug, deep_scan=False)
                floor_bpx = floor_data.get("floor_price_bpx")
                floor_usd = floor_data.get("floor_price_usd")
                listed = floor_data.get("listed_count", 0)
                total = floor_data.get("total_tokens", 0)

                print(f"[Blokpax] {slug}: Floor={floor_bpx:,.0f} BPX (${floor_usd:.2f})" if floor_bpx else f"[Blokpax] {slug}: No listings")

                # Save snapshot
                with Session(engine) as session:
                    snapshot = BlokpaxSnapshot(
                        storefront_slug=slug,
                        floor_price_bpx=floor_bpx,
                        floor_price_usd=floor_usd,
                        bpx_price_usd=bpx_price,
                        listed_count=listed,
                        total_tokens=total,
                    )
                    session.add(snapshot)

                    # Update storefront record
                    storefront = session.exec(
                        select(BlokpaxStorefront).where(BlokpaxStorefront.slug == slug)
                    ).first()
                    if storefront:
                        storefront.floor_price_bpx = floor_bpx
                        storefront.floor_price_usd = floor_usd
                        storefront.listed_count = listed
                        storefront.total_tokens = total
                        storefront.updated_at = datetime.utcnow()
                        session.add(storefront)

                    session.commit()

                # Scrape recent sales (limit pages for scheduled runs)
                sales = await scrape_recent_sales(slug, max_pages=2)
                if slug == "reward-room":
                    sales = [s for s in sales if is_wotf_asset(s.asset_name)]
                total_sales += len(sales)

                await asyncio.sleep(1)

            except Exception as e:
                print(f"[Blokpax] Error on {slug}: {e}")
                errors += 1

    except Exception as e:
        print(f"[Blokpax] Fatal error: {e}")
        log_scrape_error("Blokpax Scheduled", str(e))
        errors += 1

    duration = time.time() - start_time
    log_scrape_complete(
        cards_processed=len(WOTF_STOREFRONTS),
        new_listings=0,
        new_sales=total_sales,
        duration_seconds=duration,
        errors=errors
    )

    print(f"[{datetime.utcnow()}] Blokpax Update Complete. Duration: {duration:.1f}s")


def start_scheduler():
    # Schedule eBay scraping to run every 30 minutes
    scheduler.add_job(job_update_market_data, IntervalTrigger(minutes=30))

    # Schedule Blokpax scraping to run every 15 minutes (lightweight API-based)
    scheduler.add_job(job_update_blokpax_data, IntervalTrigger(minutes=15))

    scheduler.start()
    print("Scheduler started:")
    print("  - job_update_market_data (eBay): 30m interval")
    print("  - job_update_blokpax_data (Blokpax): 15m interval")

