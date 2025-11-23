import asyncio
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.scraper.opensea import scrape_opensea_collection
from app.scraper.browser import BrowserManager

# Define OpenSea collections to track and their corresponding card names
OPENSEA_COLLECTIONS = {
    "wotf-character-proofs": {
        "url": "https://opensea.io/collection/wotf-character-proofs",
        "card_name": "Character Proofs"
    },
    "wotf-existence-collector-boxes": {
        "url": "https://opensea.io/collection/wotf-existence-collector-boxes",
        "card_name": "Collector Booster Box"
    }
}

async def main():
    print("--- Starting OpenSea Scrape ---")
    
    # Initialize browser once
    await BrowserManager.get_browser()
    
    try:
        with Session(engine) as session:
            for collection_slug, details in OPENSEA_COLLECTIONS.items():
                card_name = details["card_name"]
                collection_url = details["url"]
                
                print(f"--- Processing {card_name} ---")
                
                # Find the corresponding card in the DB
                card = session.exec(select(Card).where(Card.name == card_name)).first()
                if not card:
                    print(f"Card '{card_name}' not found in DB, skipping OpenSea scrape for this collection.")
                    continue
                    
                scraped_stats = await scrape_opensea_collection(collection_url)
                print(f"Scraped Stats: {scraped_stats}")
                
                # Check for valid data (Floor Price OR Volume)
                if scraped_stats and (scraped_stats.get("floor_price_usd", 0) > 0 or scraped_stats.get("total_volume_usd", 0) > 0):
                    snapshot = MarketSnapshot(
                        card_id=card.id,
                        min_price=scraped_stats.get("floor_price_usd", 0.0), # Floor price
                        max_price=0.0, 
                        avg_price=scraped_stats.get("floor_price_usd", 0.0), # Use floor as avg
                        volume=int(scraped_stats.get("total_volume", 0)), # Total volume
                        lowest_ask=scraped_stats.get("floor_price_usd", 0.0),
                        highest_bid=0.0, 
                        inventory=scraped_stats.get("listed_count", 0),
                        platform="opensea"
                    )
                    session.add(snapshot)
                    session.commit()
                    session.refresh(snapshot)
                    print(f"Saved OpenSea Snapshot ID: {snapshot.id} for {card_name}")
                else:
                    print("Skipping save: No valid data found.")
                
                await asyncio.sleep(2) # Polite delay
    finally:
        await BrowserManager.close()
        print("--- OpenSea Scrape Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
