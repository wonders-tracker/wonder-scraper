import asyncio
import random
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from scripts.scrape_card import scrape_card as scrape_sold_data
from app.scraper.active import scrape_active_data
from app.scraper.browser import BrowserManager
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
    """
    print(f"[{datetime.utcnow()}] Starting Scheduled Market Update...")
    
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
    
    # Initialize browser once
    await BrowserManager.get_browser()
    
    try:
        # Process cards with controlled concurrency (max 3 concurrent)
        batch_size = 3
        for i in range(0, len(cards_to_update), batch_size):
            batch = cards_to_update[i:i+batch_size]
            
            # Process batch concurrently
            tasks = [scrape_single_card(card) for card in batch]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # Brief delay between batches
            if i + batch_size < len(cards_to_update):
                await asyncio.sleep(5)
    
    finally:
        await BrowserManager.close()
    
    print(f"[{datetime.utcnow()}] Scheduled Update Complete.") 
            search_term = f"{card.name} {card.set_name}"
            print(f"Updating: {search_term}")
            
            # 1. Sold Data
            # We need to refactor `scrape_card` to return stats instead of saving directly 
            # so we can merge with active data? Or just update snapshot?
            # Let's just run them sequentially.
            
            # ... actually `scrape_card` creates a snapshot. We should probably update that snapshot with active data.
            # But `scrape_card` is designed as a script.
            
            # Let's implement a clean service function here.
            
            # A. Get Active Data
            low_ask, inventory = await scrape_active_data(search_term, card.id)
            
            # B. Get Sold Data (via script function logic re-implementation or import)
            # For simplicity in this constrained environment, we will just use `scrape_card` 
            # which creates a snapshot, and then we UPDATE that snapshot with active data.
            
            # This is slightly inefficient (writes twice) but safe.
            await scrape_sold_data(search_term, card.id)
            
            # Find the just-created snapshot and update it
            with Session(engine) as session:
                statement = select(MarketSnapshot).where(MarketSnapshot.card_id == card.id).order_by(MarketSnapshot.timestamp.desc())
                snapshot = session.exec(statement).first()
                if snapshot:
                    snapshot.lowest_ask = low_ask
                    snapshot.inventory = inventory
                    session.add(snapshot)
                    session.commit()
                    print(f"Updated Snapshot {snapshot.id} with Active Data (Ask: {low_ask}, Inv: {inventory})")
            
            await asyncio.sleep(2) # Polite delay
            
    finally:
        await BrowserManager.close()
    
    print(f"[{datetime.utcnow()}] Scheduled Update Complete.")

def start_scheduler():
    # Schedule to run every 30 minutes for more frequent updates
    scheduler.add_job(job_update_market_data, IntervalTrigger(minutes=30))
    scheduler.start()
    print("✅ Scheduler started. Job 'job_update_market_data' registered (30m interval).")

