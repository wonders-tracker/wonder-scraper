import asyncio
import random
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager

async def bulk_scrape(limit: int = 1000):
    """
    Scrapes a batch of cards that don't have recent market data (or just first N for seeding).
    """
    print(f"Starting Bulk Scrape (Limit: {limit})...")
    
    with Session(engine) as session:
        # Get all cards
        cards = session.exec(select(Card).limit(limit)).all()
        
    print(f"Found {len(cards)} cards to scrape.")
    
    # Initialize browser once
    await BrowserManager.get_browser()
    
    try:
        for i, card in enumerate(cards):
            search_term = f"{card.name} {card.set_name}"
            print(f"\n[{i+1}/{len(cards)}] Processing: {search_term}")
            
            try:
                await scrape_card(search_term, card.id)
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
    asyncio.run(bulk_scrape(limit=1000))
