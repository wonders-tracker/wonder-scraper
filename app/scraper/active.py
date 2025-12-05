import asyncio
from sqlmodel import Session, select
from app.db import engine
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.scraper.browser import BrowserManager, get_page_content
from app.scraper.simple_http import get_page_simple
from app.scraper.utils import build_ebay_url
from app.scraper.ebay import parse_active_results, parse_total_results
from app.discord_bot.logger import log_new_listing
from typing import Tuple, Optional

async def scrape_active_data(card_name: str, card_id: int, search_term: Optional[str] = None, save_to_db: bool = True, product_type: str = "Single") -> Tuple[float, int, float]:
    """
    Scrapes active listings to find:
    - Lowest Ask (min price)
    - Highest Bid (max bid on active auctions)
    - Inventory (Volume of active listings)

    Args:
        card_name: Name of the card
        card_id: Database ID of the card
        search_term: Optional search term override
        save_to_db: If True, saves individual active listings to database

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
        items = parse_active_results(html, card_id, card_name=card_name, product_type=product_type)

        if not items:
            return (0.0, 0, 0.0)

        # Calculate stats BEFORE saving to DB to avoid detached instance errors
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

        # Save active listings to database if requested (separate try/except so stats aren't lost)
        if save_to_db and card_id > 0:
            try:
                with Session(engine) as session:
                    # First, delete old active listings for this card (older than 1 hour)
                    # to prevent stale data accumulation
                    from datetime import datetime, timedelta
                    from app.models.market import MarketPrice
                    cutoff = datetime.utcnow() - timedelta(hours=1)

                    # Delete stale active listings
                    stmt = select(MarketPrice).where(
                        MarketPrice.card_id == card_id,
                        MarketPrice.listing_type == "active",
                        MarketPrice.scraped_at < cutoff
                    )
                    old_listings = session.exec(stmt).all()
                    for old in old_listings:
                        session.delete(old)

                    # Add new active listings (skip duplicates by checking external_id)
                    existing_ids = set()
                    stmt = select(MarketPrice.external_id).where(
                        MarketPrice.card_id == card_id,
                        MarketPrice.listing_type == "active",
                        MarketPrice.external_id.isnot(None)
                    )
                    existing_ids = {r for r in session.exec(stmt).all()}

                    new_items = [item for item in items if item.external_id not in existing_ids]
                    if new_items:
                        session.add_all(new_items)
                        session.commit()
                        print(f"Saved {len(new_items)} new active listings for {card_name} (skipped {len(items) - len(new_items)} duplicates)")

                        # Send webhook notifications for new listings
                        for item in new_items:
                            try:
                                # Check if auction based on bid_count
                                is_auction = getattr(item, 'bid_count', 0) > 0
                                log_new_listing(
                                    card_name=card_name,
                                    price=item.price,
                                    treatment=getattr(item, 'treatment', None),
                                    url=item.url,
                                    is_auction=is_auction
                                )
                            except Exception as webhook_err:
                                # Don't let webhook errors affect scraping
                                pass
                    else:
                        print(f"No new active listings to save for {card_name} (all {len(items)} already exist)")
            except Exception as db_err:
                print(f"DB save error for {card_name} active listings (stats still valid): {db_err}")

        return (lowest_ask, inventory, highest_bid)
    except Exception as e:
        print(f"Active scrape error for {card_name}: {e}")
        return (0.0, 0, 0.0)
