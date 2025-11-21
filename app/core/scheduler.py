import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from scripts.scrape_card import scrape_card as scrape_sold_data
from app.scraper.active import scrape_active_data
from app.scraper.browser import BrowserManager
from datetime import datetime

scheduler = AsyncIOScheduler()

async def job_update_market_data():
    print(f"[{datetime.utcnow()}] Starting Scheduled Market Update...")
    
    # To be safe, we process a batch or all. 
    # processing 400 cards serially takes 45mins.
    # Ideally we might want to randomize or split this.
    # For now, let's just do the first 20 to prove it works without blocking forever in this demo
    # Real production: Use a Celery worker queue.
    
    with Session(engine) as session:
        cards = session.exec(select(Card)).all()
    
    # Re-init browser
    await BrowserManager.get_browser()
    
    try:
        # Scrape loop
        # Limit to 5 for the hourly check in this environment to not spam logs
        # In prod, remove slice
        for card in cards[:5]: 
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
    # Schedule to run every 60 minutes
    scheduler.add_job(job_update_market_data, IntervalTrigger(minutes=60))
    scheduler.start()
    print("Scheduler started. Job 'job_update_market_data' registered (60m interval).")

