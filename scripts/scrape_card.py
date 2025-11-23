import asyncio
import sys
from typing import Optional
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice
from app.scraper.browser import get_page_content
from app.scraper.simple_http import get_page_simple
from app.scraper.utils import build_ebay_url
from app.scraper.ebay import parse_search_results, parse_total_results
from app.services.math import calculate_stats
from app.scraper.browser import BrowserManager
from app.scraper.active import scrape_active_data

async def scrape_card(card_name: str, card_id: int = 0, rarity_name: str = "", search_term: Optional[str] = None, set_name: str = "", product_type: str = "Single", max_pages: int = 3):
    # If no search_term provided, default to card_name
    initial_query = search_term if search_term else card_name
    
    # Generate search variations to ensure we find results
    queries = [initial_query]
    
    # Logic based on Product Type
    if product_type == "Box":
        # For boxes, we want strict matching on "Box" and "Sealed" usually
        if "box" not in initial_query.lower():
            queries.append(f"{card_name} Box")
        queries.append(f"{card_name} Sealed")
        queries.append(f"{card_name} Collector Box")
        queries.append(f"{card_name} Booster Box")
        queries.append(f"{card_name} Case")
        
    elif product_type == "Pack":
        if "pack" not in initial_query.lower():
            queries.append(f"{card_name} Pack")
        queries.append(f"{card_name} Booster Pack")
        queries.append(f"{card_name} Sealed Pack")
        
    elif product_type == "Lot":
        # For lots, we want to capture bundles, collections, and bulk sales
        if "lot" not in initial_query.lower():
            queries.append(f"{card_name} Lot")
        queries.append(f"{card_name} Bundle")
        queries.append(f"{card_name} Collection")
        queries.append(f"{card_name} Bulk")
        queries.append(f"{card_name} Mixed Lot")
        
    elif product_type == "Proof":
        # For proofs and samples
        if "proof" not in initial_query.lower() and "sample" not in initial_query.lower():
            queries.append(f"{card_name} Proof")
        queries.append(f"{card_name} Sample")
        queries.append(f"{card_name} Prototype")
        
    else:
        # Standard Single Card Logic
        # 1. Card name alone (captures sellers who just use card name)
        # "The First" is too generic and would match many irrelevant items
        if card_name.lower() != "the first":
            queries.append(card_name)
        
        if "wonders" not in initial_query.lower():
            queries.append(f"{card_name} Wonders of the First")
            queries.append(f"{card_name} Wonders of the First TCG")
            queries.append(f"{card_name} Wonders of the First CCG")
            
        if set_name and set_name.lower() not in initial_query.lower():
             queries.append(f"{card_name} {set_name}")

    # Deduplicate queries (preserve order)
    seen_queries = set()
    unique_queries = []
    for q in queries:
        if q.lower() not in seen_queries:
            unique_queries.append(q)
            seen_queries.add(q.lower())
            
    print(f"--- Scraping: {card_name} (Rarity: {rarity_name}) ---")
    print(f"Search Queries: {unique_queries}")
    
    # 1. Active Data (Use the primary query)
    print("Fetching active listings...")
    active_ask, active_inv, highest_bid = await scrape_active_data(card_name, card_id, search_term=unique_queries[0])
    
    # 2. Scrape SOLD listings using variations if needed
    all_prices = []
    total_volume = 0
    clean_name = card_name.replace("Wonders of the First", "").strip()
    
    # Track unique listings to prevent duplicates from multiple queries
    # Key: external_id (preferred) or (title, price, sold_date)
    seen_ids = set()
    seen_keys = set()
    
    for query in unique_queries:
        print(f"Trying Query: {query}")
        
        query_prices = []
        for page in range(1, max_pages + 1):
            url = build_ebay_url(query, sold_only=True, page=page)
            
            try:
                # Use Pydoll browser (handles eBay's bot detection)
                html = await get_page_content(url)
            except Exception as e:
                print(f"Failed to fetch page {page}: {e}")
                break
            
            # Parse this page
            page_prices = parse_search_results(html, card_id=card_id, card_name=clean_name, target_rarity=rarity_name)
            
            if not page_prices:
                break
                
            # Add unique prices
            for mp in page_prices:
                is_duplicate = False
                
                # Check ID match (Best)
                if mp.external_id and mp.external_id in seen_ids:
                    is_duplicate = True
                
                # Check composite key match (Fallback)
                key = (mp.title, mp.price, mp.sold_date)
                if key in seen_keys:
                    is_duplicate = True
                    
                if not is_duplicate:
                    if mp.external_id:
                        seen_ids.add(mp.external_id)
                    seen_keys.add(key)
                    
                    query_prices.append(mp)
                    all_prices.append(mp)
            
            # Get total from first page of FIRST query only (best approximation)
            if page == 1 and query == unique_queries[0]:
                total_volume = parse_total_results(html)
            
            await asyncio.sleep(1)
            
        print(f"Found {len(query_prices)} new results with '{query}'. Total unique: {len(all_prices)}")
        
        # If we found a good amount of data (e.g. > 10), we can probably stop trying variations
        # unless it's a very high volume card.
        if len(all_prices) > 20:
            print("Sufficient data found, stopping search variations.")
            break
            
    prices = all_prices
    print(f"Total sold listings across {page} page(s): {len(prices)}")
    
    # 4. Calculate Stats
    # Use parsed total from header, fallback to actual count
    if total_volume == 0 and prices:
        total_volume = len(prices)
    
    if not prices:
        print("No sold data found.")
        stats = {"min": 0.0, "max": 0.0, "avg": 0.0, "volume": 0}
    else:
        price_values = [p.price for p in prices]
        stats = calculate_stats(price_values)
        # Override volume with the parsed total from header
        stats["volume"] = total_volume
        print(f"Stats: {stats} (Total Vol from Header: {total_volume})")
    
    # 5. Save to DB
    if card_id > 0:
        with Session(engine) as session:
            if prices:
                session.add_all(prices)
            
            snapshot = MarketSnapshot(
                card_id=card_id,
                min_price=stats["min"],
                max_price=stats["max"],
                avg_price=stats["avg"],
                volume=stats["volume"],
                lowest_ask=active_ask,
                highest_bid=highest_bid,
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
            rarity_name = ""
            set_name = "Existence"
            search_term = "Aerius of Thalwind Existence"
        else:
            card_name = card.name
            search_term = f"{card.name} {card.set_name}"
            card_id = card.id
            set_name = card.set_name
            rarity = session.get(Rarity, card.rarity_id)
            rarity_name = rarity.name if rarity else ""
            
    await scrape_card(card_name, card_id, rarity_name, search_term=search_term, set_name=set_name)
    
    # Close browser
    await BrowserManager.close()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        asyncio.run(scrape_card(sys.argv[1]))
    else:
        asyncio.run(main())
