import asyncio
import random
from datetime import datetime, timedelta
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager

async def bulk_scrape(limit: int = 1000, force_all: bool = False):
    """
    Scrapes a batch of cards.
    If force_all is True, it ignores the 24h check and scrapes everything.
    """
    print(f"Starting Bulk Scrape (Limit: {limit}, Force: {force_all})...", flush=True)
    print("Connecting to database...", flush=True)
    
    with Session(engine) as session:
        print("Database connected. Fetching cards...", flush=True)
        # Get all cards
        all_cards = session.exec(select(Card)).all()
        
        cards_to_scrape = []
        cutoff_time = datetime.utcnow() - timedelta(hours=24)
        
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
                
    print(f"Found {len(cards_to_scrape)} cards needing update (out of {len(all_cards)} total).")
    
    if not cards_to_scrape:
        print("No cards need updating.")
        return

    # Initialize browser once (with Pydoll's internal 60s timeout)
    print("Initializing browser (may take up to 60 seconds)...")
    try:
        await BrowserManager.get_browser()
        print("Browser ready!")
    except Exception as e:
        print(f"Browser initialization failed: {e}")
        print("Attempting to continue with simple HTTP fallback...")
        # Don't exit - the simple_http fallback in scrape_card will handle it
    
    try:
        for i, card in enumerate(cards_to_scrape):
            search_term = f"{card.name} {card.set_name}"
            print(f"\n[{i+1}/{len(cards_to_scrape)}] Processing: {card.name}")
            
            try:
                # Pass card_name separately from search_term to ensure strict validation
                # Pass set_name to help build search variations
                await scrape_card(
                    card_name=card.name,
                    card_id=card.id,
                    search_term=search_term,
                    set_name=card.set_name,
                    product_type=card.product_type,  # Pass product type
                    is_backfill=True  # Bulk scrape should capture max historical data
                )
            except Exception as e:
                print(f"Error scraping {card.name}: {e}")
            
            # Random delay to be polite/safe
            delay = random.uniform(2, 5)
            print(f"Sleeping for {delay:.2f}s...")
            await asyncio.sleep(delay)
            
    finally:
        await BrowserManager.close()
        print("Bulk Scrape Complete.")

if __name__ == "__main__":
    import sys
    # Parse command line args
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 10000  # Higher default for full backfill
    force_all = '--force' in sys.argv or len(sys.argv) <= 2  # Default to force for backfill

    print(f"Running bulk scrape with limit={limit}, force_all={force_all}")
    asyncio.run(bulk_scrape(limit=limit, force_all=force_all))
