from sqlmodel import Session, select
from app.db import engine
from app.scraper.browser import get_page_content
from app.scraper.utils import build_ebay_url
from app.scraper.ebay import parse_active_results, parse_total_results
from app.discord_bot.logger import log_new_listing
from typing import Tuple, Optional


async def scrape_active_data(
    card_name: str,
    card_id: int,
    search_term: Optional[str] = None,
    save_to_db: bool = True,
    product_type: str = "Single",
) -> Tuple[float, int, float]:
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
            bid_count = getattr(item, "bid_count", 0)
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
                    from datetime import datetime, timedelta, timezone
                    from app.models.market import MarketPrice

                    # Delete stale active listings (older than 30 days)
                    # Keep listings long enough to track active->sold transitions
                    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
                    stmt = select(MarketPrice).where(
                        MarketPrice.card_id == card_id,
                        MarketPrice.listing_type == "active",
                        MarketPrice.scraped_at < cutoff,
                    )
                    old_listings = session.exec(stmt).all()
                    deleted_count = len(old_listings)
                    for old in old_listings:
                        session.delete(old)

                    # Get existing active listings by external_id for upsert logic
                    # Check GLOBALLY (any card_id) to prevent duplicate key errors
                    # when the same eBay listing matches multiple cards
                    stmt = select(MarketPrice).where(
                        MarketPrice.listing_type == "active", MarketPrice.external_id.isnot(None)
                    )
                    all_existing = session.exec(stmt).all()

                    # Group by external_id - existing for THIS card (update) vs OTHER cards (skip)
                    existing_for_this_card = {mp.external_id: mp for mp in all_existing if mp.card_id == card_id}
                    existing_for_other_cards = {mp.external_id for mp in all_existing if mp.card_id != card_id}

                    new_count = 0
                    updated_count = 0
                    skipped_count = 0

                    # Track external_ids we've seen in THIS batch to avoid duplicates within same scrape
                    seen_in_batch = set()
                    duplicate_in_batch = 0

                    for item in items:
                        # Skip if this listing already belongs to a DIFFERENT card
                        # (prevents duplicate key violation for overlapping searches)
                        if item.external_id and item.external_id in existing_for_other_cards:
                            skipped_count += 1
                            continue

                        # Skip duplicates within the same batch (same external_id appearing twice in results)
                        if item.external_id and item.external_id in seen_in_batch:
                            duplicate_in_batch += 1
                            continue
                        if item.external_id:
                            seen_in_batch.add(item.external_id)

                        if item.external_id in existing_for_this_card:
                            # Update existing listing with fresh data
                            # IMPORTANT: Preserve listed_at (when first seen)
                            existing = existing_for_this_card[item.external_id]
                            existing.price = item.price
                            existing.title = item.title
                            existing.url = item.url
                            existing.scraped_at = datetime.now(timezone.utc)
                            # Don't update listed_at - preserve original "first seen" time
                            existing.image_url = getattr(item, "image_url", existing.image_url)
                            existing.seller_name = getattr(item, "seller_name", existing.seller_name)
                            existing.condition = getattr(item, "condition", existing.condition)
                            existing.shipping_cost = getattr(item, "shipping_cost", existing.shipping_cost)
                            session.add(existing)
                            updated_count += 1
                        else:
                            # Add new listing - set listed_at to track when first seen
                            item.listed_at = datetime.now(timezone.utc)
                            try:
                                session.add(item)
                                session.flush()  # Force immediate insert to catch constraint violations
                                new_count += 1

                                # Send webhook notification for NEW listings only
                                try:
                                    is_auction = getattr(item, "bid_count", 0) > 0
                                    log_new_listing(
                                        card_name=card_name,
                                        price=item.price,
                                        treatment=getattr(item, "treatment", None),
                                        url=item.url,
                                        is_auction=is_auction,
                                        floor_price=lowest_ask if lowest_ask > 0 else None,
                                    )
                                except Exception as webhook_err:
                                    print(f"Discord webhook failed for {card_name}: {webhook_err}")
                            except Exception as insert_err:
                                session.rollback()
                                if "unique" in str(insert_err).lower() or "duplicate" in str(insert_err).lower():
                                    skipped_count += 1
                                else:
                                    raise  # Re-raise non-duplicate errors

                    session.commit()
                    skip_msg = f", {skipped_count} duplicates skipped" if skipped_count > 0 else ""
                    batch_msg = f", {duplicate_in_batch} batch duplicates" if duplicate_in_batch > 0 else ""
                    print(
                        f"Active listings for {card_name}: {new_count} new, {updated_count} updated, {deleted_count} stale removed{skip_msg}{batch_msg}"
                    )
            except Exception as db_err:
                print(f"DB save error for {card_name} active listings (stats still valid): {db_err}")

        return (lowest_ask, inventory, highest_bid)
    except Exception as e:
        print(f"Active scrape error for {card_name}: {e}")
        return (0.0, 0, 0.0)
