import asyncio
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.scraper.browser import BrowserManager, get_page_content
from app.scraper.simple_http import get_page_simple
from app.scraper.utils import build_ebay_url
from app.scraper.ebay import parse_active_results, parse_total_results
from typing import Tuple, Optional

async def scrape_active_data(card_name: str, card_id: int, search_term: Optional[str] = None) -> Tuple[float, int, float]:
    """
    Scrapes active listings to find:
    - Lowest Ask (min price)
    - Highest Bid (max bid on active auctions)
    - Inventory (Volume of active listings)
    
    Returns: (lowest_ask, inventory_count, highest_bid)
    """
    # Use search_term if provided, else card_name
    query = search_term if search_term else card_name
    
    # Search Active Listings (sold_only=False)
    url = build_ebay_url(query, sold_only=False)
    try:
        # Use Pydoll browser (handles eBay's bot detection)
        html = await get_page_content(url)
        # Validate against pure card_name, not search_term
        items = parse_active_results(html, card_id, card_name=card_name)
        
        if not items:
            return (0.0, 0, 0.0)
            
        # Calculate stats
        prices = [i.price for i in items]
        lowest_ask = min(prices) if prices else 0.0
        
        # Calculate Highest Bid
        # We need to check which items are auctions and have bids.
        # In `ebay.py`, we added `bid_count` to the MarketPrice object (monkey-patched).
        # We want the highest PRICE among items that have > 0 bids.
        highest_bid = 0.0
        
        for item in items:
            # Check if it has bids (we monkey-patched this property in parse_generic_results)
            bid_count = getattr(item, 'bid_count', 0)
            if bid_count > 0:
                if item.price > highest_bid:
                    highest_bid = item.price
        
        # Try to get total inventory count from page header, fallback to list length
        total_count = parse_total_results(html)
        inventory = total_count if total_count > 0 else len(prices)
        
        return (lowest_ask, inventory, highest_bid)
    except Exception as e:
        print(f"Active scrape error for {card_name}: {e}")
        return (0.0, 0, 0.0)
