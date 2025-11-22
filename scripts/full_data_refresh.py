"""
Complete data refresh: eBay cards + boxes/packs + OpenSea collections
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager
from app.scraper.opensea import scrape_opensea_collection
from app.models.market import MarketSnapshot

async def scrape_all_ebay():
    """Scrape all cards, boxes, and packs from eBay"""
    print("=" * 60)
    print("SCRAPING EBAY (Cards, Boxes, Packs)")
    print("=" * 60)
    
    with Session(engine) as session:
        cards = session.exec(select(Card)).all()
    
    print(f"Found {len(cards)} products to scrape from eBay...")
    
    for i, card in enumerate(cards, 1):
        search_term = f"{card.name} {card.set_name}"
        print(f"\n[{i}/{len(cards)}] Scraping: {card.name} ({card.product_type})")
        
        # Restart browser every 10 cards to prevent memory issues
        if i % 10 == 1:
            print("🔄 Refreshing browser instance...")
            await BrowserManager.close()
            await asyncio.sleep(2)
            await BrowserManager.get_browser()
        
        try:
            await scrape_card(
                card_name=card.name,
                card_id=card.id,
                search_term=search_term,
                set_name=card.set_name,
                product_type=card.product_type if hasattr(card, 'product_type') else 'Single'
            )
            print(f"✅ Completed: {card.name}")
        except Exception as e:
            print(f"❌ Error on {card.name}: {e}")
            # Try to restart browser on error
            print("🔄 Attempting browser restart...")
            try:
                await BrowserManager.restart()
                await asyncio.sleep(3)
            except:
                pass
        
        # Brief delay
        await asyncio.sleep(2)
    
    await BrowserManager.close()

async def scrape_all_opensea():
    """Scrape OpenSea collections"""
    print("\n" + "=" * 60)
    print("SCRAPING OPENSEA COLLECTIONS")
    print("=" * 60)
    
    COLLECTION_MAP = {
        "https://opensea.io/collection/wotf-character-proofs": "Character Proofs",
        "https://opensea.io/collection/wotf-existence-collector-boxes": "Existence Collector Box"
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

async def main():
    print("\n🚀 FULL DATA REFRESH STARTING...")
    print("This will scrape:")
    print("  1. All eBay cards (singles)")
    print("  2. All eBay boxes/packs")
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
    
    # 1. Scrape eBay (all products)
    await scrape_all_ebay()
    
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
    asyncio.run(main())

