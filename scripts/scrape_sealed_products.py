"""
Scrapes all sealed products (boxes, packs, lots, proofs) to populate initial market data.
"""
import asyncio
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from scripts.scrape_card import scrape_card
from app.scraper.browser import BrowserManager

async def scrape_sealed_products():
    """
    Scrape all non-Single products to populate initial market data.
    """
    print("="*70)
    print("🔍 Scraping Sealed Products (Boxes, Packs, Lots, Proofs)")
    print("="*70)
    
    with Session(engine) as session:
        # Get all non-single products
        sealed_products = session.exec(
            select(Card).where(Card.product_type != "Single")
        ).all()
        
        print(f"\nFound {len(sealed_products)} sealed products to scrape\n")
        
        for i, card in enumerate(sealed_products, 1):
            print(f"\n[{i}/{len(sealed_products)}] Processing: {card.name} ({card.product_type})")
            print("-" * 70)
            
            try:
                await scrape_card(
                    card_name=card.name,
                    card_id=card.id,
                    rarity_name="Sealed",
                    search_term=card.name,
                    set_name=card.set_name,
                    product_type=card.product_type,
                    max_pages=2  # Fewer pages for sealed products (less data)
                )
                print(f"✓ Successfully scraped {card.name}")
                
                # Small delay between scrapes to be respectful
                await asyncio.sleep(2)
                
            except Exception as e:
                print(f"✗ Error scraping {card.name}: {e}")
                continue
    
    # Close browser
    await BrowserManager.close()
    
    print("\n" + "="*70)
    print("✓ Sealed Products Scraping Complete!")
    print("="*70)

if __name__ == "__main__":
    asyncio.run(scrape_sealed_products())

