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

async def scrape_card(card_name: str, card_id: int = 0, rarity_name: str = "", search_term: Optional[str] = None, set_name: str = "", product_type: str = "Single", max_pages: int = 3, is_backfill: bool = False):
    """
    Scrape eBay for a card with OPTIMIZED query generation.

    Strategy: Use 1-2 targeted queries instead of 8+ variations.
    - Primary: "Wonders of the First [card_name]" - specific, filters non-Wonders
    - Fallback: "[card_name] Existence" - catches abbreviated listings
    """

    # Build optimized query list (max 2-3 queries)
    unique_queries = []

    # ALWAYS include "Wonders of the First" to filter out non-Wonders products
    primary_query = f"Wonders of the First {card_name}"
    unique_queries.append(primary_query)

    # Add product-type specific fallback
    if product_type == "Box":
        # For boxes, also try with "Existence" set name
        unique_queries.append(f"Wonders of the First Existence {card_name}")
        # Also try just the card name for boxes
        unique_queries.append(card_name)

    elif product_type == "Pack":
        # Use actual card name, not generic "Booster Pack"
        unique_queries.append(card_name)
        if "booster" not in card_name.lower():
            unique_queries.append(f"Wonders of the First Booster Pack")

    elif product_type == "Lot":
        # Use actual card name for lots
        unique_queries.append(card_name)
        # Also try generic searches
        unique_queries.append(f"Wonders of the First Lot")
        unique_queries.append(f"Wonders of the First Bundle")

    elif product_type == "Proof":
        # Use actual card name for proofs
        unique_queries.append(card_name)
        if "proof" not in card_name.lower():
            unique_queries.append(f"Wonders of the First Proof")

    else:
        # Single cards - add Existence set search
        unique_queries.append(f"Wonders of the First Existence {card_name}")
        # For very specific cards, add rarity if available
        if rarity_name and rarity_name.lower() not in ['common', 'uncommon']:
            unique_queries.append(f"{card_name} {rarity_name} Wonders")

    # Deduplicate (case-insensitive)
    seen = set()
    deduped = []
    for q in unique_queries:
        if q.lower() not in seen:
            deduped.append(q)
            seen.add(q.lower())
    unique_queries = deduped
            
    # Override max_pages for historical backfills to capture more data
    if is_backfill and max_pages < 10:
        max_pages = 10
        print(f"BACKFILL MODE: Increasing max_pages to {max_pages} for historical data capture")

    print(f"--- Scraping: {card_name} (Rarity: {rarity_name}) ---")
    print(f"Search Queries: {unique_queries}")
    print(f"Max Pages: {max_pages} | Backfill: {is_backfill}")
    
    # 1. Active Data (Use the primary query)
    print("Fetching active listings...")
    active_ask, active_inv, highest_bid = await scrape_active_data(card_name, card_id, search_term=unique_queries[0])
    
    # 2. Scrape SOLD listings using variations if needed
    all_prices = []  # For saving to DB (new listings only)
    all_prices_for_stats = []  # For calculating stats (all listings)
    total_volume = 0
    clean_name = card_name.replace("Wonders of the First", "").strip()

    # Track unique listings to prevent duplicates from multiple queries
    # Key: external_id (preferred) or (title, price, sold_date)
    seen_ids = set()
    seen_keys = set()

    for query in unique_queries:
        print(f"Trying Query: {query}")

        query_prices = []
        query_prices_for_stats = []
        for page in range(1, max_pages + 1):
            url = build_ebay_url(query, sold_only=True, page=page)

            try:
                # Use Pydoll browser (handles eBay's bot detection)
                html = await get_page_content(url)
            except Exception as e:
                print(f"Failed to fetch page {page}: {e}")
                break

            # Parse this page - get ALL listings for stats calculation
            page_prices_for_stats = parse_search_results(html, card_id=card_id, card_name=clean_name,
                                                         target_rarity=rarity_name, return_all=True)
            # Parse this page - get only NEW listings for saving to DB
            page_prices = parse_search_results(html, card_id=card_id, card_name=clean_name,
                                              target_rarity=rarity_name, return_all=False)

            if not page_prices_for_stats:
                break

            # Add unique prices for DB saving (new listings only)
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

            # Add ALL listings for stats calculation (includes already-indexed ones)
            for mp in page_prices_for_stats:
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

                    query_prices_for_stats.append(mp)
                    all_prices_for_stats.append(mp)
            
            # Get total from first page of FIRST query only (best approximation)
            if page == 1 and query == unique_queries[0]:
                total_volume = parse_total_results(html)
            await asyncio.sleep(1)

        print(f"Found {len(query_prices)} new listings to save, {len(query_prices_for_stats)} total for stats. Total unique: {len(all_prices_for_stats)}")

        # Early stopping: If we have enough data, stop trying more queries
        # Threshold based on product type (singles need less, boxes need more variety)
        min_results = 5 if product_type == "Single" else 10

        if not is_backfill and len(all_prices_for_stats) >= min_results:
            print(f"✓ Sufficient data ({len(all_prices_for_stats)} results), skipping remaining queries.")
            break

    # Use stats prices (includes existing listings) for market snapshot
    prices_for_stats = all_prices_for_stats
    # Use new prices for saving to database
    prices_to_save = all_prices

    print(f"Total listings for stats: {len(prices_for_stats)} | New listings to save: {len(prices_to_save)}")

    # 4. Calculate Stats from ALL listings (including existing ones)
    # Use parsed total from header, fallback to actual count
    if total_volume == 0 and prices_for_stats:
        total_volume = len(prices_for_stats)

    # Find the most recent sale for last_sale_price/date
    last_sale_price = None
    last_sale_date = None

    if not prices_for_stats:
        print("No sold data found.")
        stats = {"min": 0.0, "max": 0.0, "avg": 0.0, "volume": 0}
    else:
        price_values = [p.price for p in prices_for_stats]
        stats = calculate_stats(price_values)
        # Override volume with the parsed total from header
        stats["volume"] = total_volume
        print(f"Stats: {stats} (Total Vol from Header: {total_volume})")

        # Get most recent sale (sort by sold_date descending)
        sorted_by_date = sorted(
            [p for p in prices_for_stats if p.sold_date],
            key=lambda x: x.sold_date,
            reverse=True
        )
        if sorted_by_date:
            last_sale_price = sorted_by_date[0].price
            last_sale_date = sorted_by_date[0].sold_date
            print(f"Last Sale: ${last_sale_price:.2f} on {last_sale_date.strftime('%Y-%m-%d')}")
    
    # 5. Save to DB
    if card_id > 0:
        with Session(engine) as session:
            # Save only NEW listings to database
            if prices_to_save:
                session.add_all(prices_to_save)
                print(f"Saving {len(prices_to_save)} new listings to database")
            
            snapshot = MarketSnapshot(
                card_id=card_id,
                min_price=stats["min"],
                max_price=stats["max"],
                avg_price=stats["avg"],
                volume=stats["volume"],
                lowest_ask=active_ask,
                highest_bid=highest_bid,
                inventory=active_inv,
                last_sale_price=last_sale_price,
                last_sale_date=last_sale_date
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
