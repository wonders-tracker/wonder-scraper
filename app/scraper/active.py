import asyncio
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.scraper.browser import BrowserManager, get_page_content
from app.scraper.utils import build_ebay_url
from app.scraper.ebay import parse_active_results, parse_total_results
from typing import Tuple

async def scrape_active_data(card_name: str, card_id: int) -> Tuple[float, int, int]:
    """
    Scrapes active listings to find:
    - Lowest Ask (min price)
    - Highest Bid (not easily available on search list without sorting by bids, assuming 0 for now or need specific sort)
    - Inventory (Volume of active listings)
    
    Returns: (lowest_ask, inventory_count)
    """
    # Search Active Listings (sold_only=False)
    url = build_ebay_url(card_name, sold_only=False)
    try:
        html = await get_page_content(url)
        items = parse_active_results(html, card_id)
        
        if not items:
            return (0.0, 0)
            
        # Calculate stats
        prices = [i.price for i in items]
        lowest_ask = min(prices) if prices else 0.0
        
        # Try to get total inventory count from page header, fallback to list length
        total_count = parse_total_results(html)
        inventory = total_count if total_count > 0 else len(prices)
        
        return (lowest_ask, inventory)
    except Exception as e:
        print(f"Active scrape error for {card_name}: {e}")
        return (0.0, 0)

