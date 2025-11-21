import asyncio
import sys
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot, MarketPrice
from app.scraper.browser import get_page_content
from app.scraper.utils import build_ebay_url
from app.scraper.ebay import parse_search_results
from app.services.math import calculate_stats
from app.scraper.browser import BrowserManager
from app.scraper.active import scrape_active_data

async def scrape_card(card_name: str, card_id: int = 0):
    print(f"--- Scraping: {card_name} ---")
    
    # 1. Active Data (Ask, Bid, Inventory)
    print("Fetching active listings...")
    active_ask, active_inv = await scrape_active_data(card_name, card_id)
    # Note: active_bid logic is not yet implemented fully in active.py, defaulted to 0 or calculated later
    # We'll use active_ask as lowest_ask and active_inv as inventory
    
    # 2. Build URL for SOLD listings
    url = build_ebay_url(card_name, sold_only=True)
    print(f"Sold URL: {url}")
    
    # 2. Fetch HTML
    try:
        html = await get_page_content(url)
    except Exception as e:
        print(f"Failed to fetch: {e}")
        return

    # 3. Parse
    # We pass card_id so MarketPrice objects have it
    prices = parse_search_results(html, card_id=card_id)
    print(f"Found {len(prices)} sold listings.")
    
    if not prices:
        print("No data found. Exiting.")
        return

    # 4. Calculate Stats
    price_values = [p.price for p in prices]
    stats = calculate_stats(price_values)
    print(f"Stats: {stats}")
    
    # 5. Save to DB (if card_id is valid)
    if card_id > 0:
        with Session(engine) as session:
            # Save individual prices (optional, usually we just want snapshot)
            session.add_all(prices)
            
            # Save Snapshot
            snapshot = MarketSnapshot(
                card_id=card_id,
                min_price=stats["min"],
                max_price=stats["max"],
                avg_price=stats["avg"],
                volume=stats["volume"],
                lowest_ask=active_ask,
                highest_bid=0.0, # Placeholder
                inventory=active_inv
            )
            session.add(snapshot)
            session.commit()
            session.refresh(snapshot)
            print(f"Saved Snapshot ID: {snapshot.id}")

async def main():
    # 1. Get a card from DB
    with Session(engine) as session:
        # Try to find 'Aerius of Thalwind'
        statement = select(Card).where(Card.name == "Aerius of Thalwind")
        card = session.exec(statement).first()
        
        if not card:
            print("Card not found in DB. Using dummy ID.")
            card_name = "Aerius of Thalwind"
            card_id = 0
        else:
            card_name = f"{card.name} {card.set_name}" # Search with set name for better results
            card_id = card.id
            
    await scrape_card(card_name, card_id)
    
    # Close browser
    await BrowserManager.close()

if __name__ == "__main__":
    # Check args
    if len(sys.argv) > 1:
        # Manual search override
        asyncio.run(scrape_card(sys.argv[1]))
    else:
        asyncio.run(main())

