import asyncio
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot, MarketPrice
from app.scraper.opensea import scrape_opensea_collection, scrape_opensea_sales
from app.scraper.browser import BrowserManager

# Define OpenSea collections to track and their corresponding card names
# Contract addresses are required for proper OpenSea item URLs
OPENSEA_COLLECTIONS = {
    "wotf-character-proofs": {
        "url": "https://opensea.io/collection/wotf-character-proofs",
        "card_name": "Character Proofs",
        "slug": "wotf-character-proofs",
        "contract": "0x05f08b01971cf70bcd4e743a8906790cfb9a8fb8",
        "chain": "ethereum"
    },
    "wotf-existence-collector-boxes": {
        "url": "https://opensea.io/collection/wotf-existence-collector-boxes",
        "card_name": "Existence Collector Box",
        "slug": "wotf-existence-collector-boxes",
        "contract": "0x28a11da34a93712b1fde4ad15da217a3b14d9465",
        "chain": "ethereum"
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
                contract = details.get("contract", "")
                chain = details.get("chain", "ethereum")
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

                    # Build proper OpenSea item URL: https://opensea.io/item/{chain}/{contract}/{token_id}
                    opensea_url = None
                    if sale.token_id and contract:
                        opensea_url = f"https://opensea.io/item/{chain}/{contract}/{sale.token_id}"

                    # Use NFT traits as treatment if available
                    treatment = None
                    if hasattr(sale, 'traits') and sale.traits:
                        # Extract the most relevant trait for display
                        # Priority: Hierarchy (Character Proofs), Box Art (Collector Boxes)
                        trait_dict = {}
                        for trait in sale.traits:
                            if isinstance(trait, dict):
                                tt = (trait.get("trait_type") or "").lower()
                                tv = trait.get("value") or ""
                                if tt and tv:
                                    trait_dict[tt] = tv

                        # Priority order for treatment display
                        if "hierarchy" in trait_dict:
                            treatment = trait_dict["hierarchy"]
                        elif "box art" in trait_dict:
                            treatment = trait_dict["box art"]
                        elif "orbital class" in trait_dict:
                            treatment = trait_dict["orbital class"]
                        elif "type" in trait_dict:
                            treatment = trait_dict["type"]
                        elif sale.traits and isinstance(sale.traits[0], dict):
                            # Fallback: first trait value
                            treatment = sale.traits[0].get("value", "")

                    # If no traits, try to extract from token name
                    if not treatment and sale.token_name:
                        name_lower = sale.token_name.lower()
                        if "foil" in name_lower or "holo" in name_lower:
                            treatment = "Foil"
                        elif "serial" in name_lower or "/50" in name_lower or "/100" in name_lower or "/250" in name_lower:
                            treatment = "Serialized"
                        elif "proof" in name_lower:
                            treatment = "Proof"
                        elif "promo" in name_lower or "prerelease" in name_lower:
                            treatment = "Promo"
                        else:
                            # Use token name as treatment for NFTs (more informative than just "NFT")
                            treatment = sale.token_name

                    # Final fallback
                    if not treatment:
                        treatment = "NFT"

                    # Prepare traits for storage (normalize format)
                    traits_data = None
                    if hasattr(sale, 'traits') and sale.traits:
                        traits_data = [
                            {"trait_type": t.get("trait_type", ""), "value": t.get("value", "")}
                            for t in sale.traits if isinstance(t, dict)
                        ]

                    # Create new MarketPrice record
                    market_price = MarketPrice(
                        card_id=card.id,
                        price=sale.price_usd,
                        title=sale.token_name,
                        sold_date=sale.sold_at,
                        listing_type="sold",
                        treatment=treatment,
                        traits=traits_data,  # Store all NFT traits
                        external_id=sale.tx_hash or f"opensea_{sale.token_id}_{sale.sold_at.isoformat()}",
                        url=opensea_url,
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
