import asyncio
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot, MarketPrice
from app.scraper.opensea import scrape_opensea_collection, scrape_opensea_sales
from app.scraper.browser import BrowserManager

# Define OpenSea collections to track and their corresponding card names
OPENSEA_COLLECTIONS = {
    "wotf-character-proofs": {
        "url": "https://opensea.io/collection/wotf-character-proofs",
        "card_name": "Character Proofs",
        "slug": "wotf-character-proofs"
    },
    "wotf-existence-collector-boxes": {
        "url": "https://opensea.io/collection/wotf-existence-collector-boxes",
        "card_name": "Collector Booster Box",
        "slug": "wotf-existence-collector-boxes"
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
                slug = details["slug"]

                print(f"--- Processing {card_name} ---")

                # Find the corresponding card in the DB
                card = session.exec(select(Card).where(Card.name == card_name)).first()
                if not card:
                    print(f"Card '{card_name}' not found in DB, skipping OpenSea scrape for this collection.")
                    continue

                # Scrape collection stats
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
                    print("Skipping snapshot save: No valid data found.")

                # Scrape sales history
                print(f"--- Fetching Sales for {card_name} ---")
                sales = await scrape_opensea_sales(slug, limit=50)

                new_sales_count = 0
                for sale in sales:
                    # Check if sale already exists (by tx_hash or token_id + sold_date combo)
                    existing = None
                    if sale.tx_hash:
                        existing = session.exec(
                            select(MarketPrice).where(
                                MarketPrice.card_id == card.id,
                                MarketPrice.external_id == sale.tx_hash,
                                MarketPrice.platform == "opensea"
                            )
                        ).first()

                    if not existing:
                        # Also check by token_id + date to avoid duplicates
                        existing = session.exec(
                            select(MarketPrice).where(
                                MarketPrice.card_id == card.id,
                                MarketPrice.title == sale.token_name,
                                MarketPrice.sold_date == sale.sold_at,
                                MarketPrice.platform == "opensea"
                            )
                        ).first()

                    if existing:
                        continue  # Skip duplicate

                    # Create new MarketPrice record
                    market_price = MarketPrice(
                        card_id=card.id,
                        price=sale.price_usd,
                        title=sale.token_name,
                        sold_date=sale.sold_at,
                        listing_type="sold",
                        treatment="NFT",  # OpenSea items are NFTs
                        external_id=sale.tx_hash or f"opensea_{sale.token_id}_{sale.sold_at.isoformat()}",
                        url=f"https://opensea.io/assets/ethereum/{slug}/{sale.token_id}" if sale.token_id else None,
                        image_url=sale.image_url,
                        description=f"Token #{sale.token_id} - {sale.price_eth:.4f} ETH",
                        platform="opensea",
                        seller_name=sale.seller[:20] if sale.seller else None,  # Truncate wallet address
                    )
                    session.add(market_price)
                    new_sales_count += 1

                if new_sales_count > 0:
                    session.commit()
                    print(f"Saved {new_sales_count} new OpenSea sales for {card_name}")
                else:
                    print(f"No new sales to save for {card_name}")

                await asyncio.sleep(2) # Polite delay
    finally:
        await BrowserManager.close()
        print("--- OpenSea Scrape Complete ---")

if __name__ == "__main__":
    asyncio.run(main())
