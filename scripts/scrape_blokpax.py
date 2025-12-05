"""
Blokpax WOTF Scraper - Scrapes WOTF storefronts on Blokpax marketplace.

Usage:
    python scripts/scrape_blokpax.py                    # Scrape all WOTF storefronts
    python scripts/scrape_blokpax.py --slug wotf-art-proofs  # Scrape specific storefront
    python scripts/scrape_blokpax.py --floors           # Only fetch floor prices
    python scripts/scrape_blokpax.py --sales            # Only fetch recent sales
    python scripts/scrape_blokpax.py --offers           # Only fetch active offers/bids
    python scripts/scrape_blokpax.py --redemptions      # Scrape collector box redemptions
    python scripts/scrape_blokpax.py --deep             # Deep scan for floor prices
"""
import asyncio
import argparse
import time
from datetime import datetime, timedelta
from typing import List

from sqlmodel import Session, select
from app.db import engine
from app.scraper.blokpax import (
    WOTF_STOREFRONTS,
    get_bpx_price,
    fetch_storefront,
    fetch_storefront_assets,
    fetch_storefront_activity,
    scrape_storefront_floor,
    scrape_all_listings,
    scrape_recent_sales,
    scrape_all_offers,
    scrape_redemption_stats,
    parse_asset,
    parse_sale,
    is_wotf_asset,
)
from app.models.blokpax import (
    BlokpaxStorefront,
    BlokpaxAssetDB,
    BlokpaxSale,
    BlokpaxSnapshot,
    BlokpaxOffer as BlokpaxOfferDB,
    BlokpaxRedemption,
)
from app.discord_bot.logger import log_scrape_start, log_scrape_complete, log_scrape_error


async def scrape_storefront_metadata(slug: str) -> dict:
    """
    Fetches and stores storefront metadata.
    """
    print(f"\n=== Fetching Storefront: {slug} ===")

    try:
        data = await fetch_storefront(slug)
        storefront_data = data.get("data", {})

        name = storefront_data.get("name", slug)
        description = storefront_data.get("description")
        image_url = storefront_data.get("image")
        network_id = storefront_data.get("network_id", 1)

        print(f"  Name: {name}")
        print(f"  Network: {'Ethereum' if network_id == 1 else 'Polygon'}")

        # Store in DB
        with Session(engine) as session:
            existing = session.exec(
                select(BlokpaxStorefront).where(BlokpaxStorefront.slug == slug)
            ).first()

            if existing:
                existing.name = name
                existing.description = description
                existing.image_url = image_url
                existing.network_id = network_id
                existing.updated_at = datetime.utcnow()
                session.add(existing)
            else:
                storefront = BlokpaxStorefront(
                    slug=slug,
                    name=name,
                    description=description,
                    image_url=image_url,
                    network_id=network_id,
                )
                session.add(storefront)

            session.commit()

        return {"slug": slug, "name": name, "network_id": network_id}

    except Exception as e:
        print(f"  Error fetching storefront: {e}")
        return {"slug": slug, "error": str(e)}


async def scrape_floor_prices(slugs: List[str] = None, deep_scan: bool = False):
    """
    Scrapes floor prices for all WOTF storefronts and saves snapshots.

    Args:
        slugs: List of storefront slugs to scrape
        deep_scan: If True, scans all assets for listings (slow but accurate)
    """
    if slugs is None:
        slugs = WOTF_STOREFRONTS

    print("\n" + "=" * 60)
    print("BLOKPAX FLOOR PRICE SCRAPER")
    if deep_scan:
        print("MODE: Deep Scan (checking all assets for listings)")
    print("=" * 60)

    bpx_price = await get_bpx_price()
    print(f"Current BPX Price: ${bpx_price:.6f} USD")

    results = []
    for slug in slugs:
        try:
            floor_data = await scrape_storefront_floor(slug, deep_scan=deep_scan)
            results.append(floor_data)

            floor_bpx = floor_data.get("floor_price_bpx")
            floor_usd = floor_data.get("floor_price_usd")
            listed = floor_data.get("listed_count", 0)
            total = floor_data.get("total_tokens", 0)

            print(f"\n{slug}:")
            if floor_bpx:
                print(f"  Floor: {floor_bpx:,.0f} BPX (${floor_usd:.2f} USD)")
            else:
                print(f"  Floor: No listings")
            print(f"  Listed: {listed} / {total} tokens")

            # Fetch redemption stats for collector boxes
            total_redeemed = 0
            max_supply = 0
            if slug == "wotf-existence-collector-boxes":
                try:
                    redemption_stats = await scrape_redemption_stats(slug)
                    total_redeemed = redemption_stats.get("total_redeemed", 0)
                    max_supply = redemption_stats.get("max_supply", 0)
                    print(f"  Redeemed: {total_redeemed}/{max_supply} ({redemption_stats.get('redeemed_pct', 0):.1f}%)")
                except Exception as e:
                    print(f"  Error fetching redemptions: {e}")

            # Save snapshot
            with Session(engine) as session:
                snapshot = BlokpaxSnapshot(
                    storefront_slug=slug,
                    floor_price_bpx=floor_bpx,
                    floor_price_usd=floor_usd,
                    bpx_price_usd=bpx_price,
                    listed_count=listed,
                    total_tokens=total,
                    total_redeemed=total_redeemed,
                    max_supply=max_supply,
                )
                session.add(snapshot)

                # Update storefront record
                storefront = session.exec(
                    select(BlokpaxStorefront).where(BlokpaxStorefront.slug == slug)
                ).first()
                if storefront:
                    storefront.floor_price_bpx = floor_bpx
                    storefront.floor_price_usd = floor_usd
                    storefront.listed_count = listed
                    storefront.total_tokens = total
                    storefront.updated_at = datetime.utcnow()
                    session.add(storefront)

                session.commit()

            # Rate limit
            await asyncio.sleep(1)

        except Exception as e:
            print(f"\n{slug}: ERROR - {e}")
            results.append({"slug": slug, "error": str(e)})

    return results


async def scrape_sales(slugs: List[str] = None, max_pages: int = 3):
    """
    Scrapes recent sales from WOTF storefronts.
    """
    if slugs is None:
        slugs = WOTF_STOREFRONTS

    print("\n" + "=" * 60)
    print("BLOKPAX SALES SCRAPER")
    print("=" * 60)

    total_sales = 0
    new_sales = 0

    for slug in slugs:
        print(f"\n--- {slug} ---")

        try:
            sales = await scrape_recent_sales(slug, max_pages=max_pages)
            total_sales += len(sales)

            # Filter WOTF items for reward-room (mixed storefront)
            if slug == "reward-room":
                sales = [s for s in sales if is_wotf_asset(s.asset_name)]
                print(f"  Filtered to {len(sales)} WOTF items")

            with Session(engine) as session:
                for sale in sales:
                    # Check if already indexed
                    existing = session.exec(
                        select(BlokpaxSale).where(
                            BlokpaxSale.listing_id == sale.listing_id
                        )
                    ).first()

                    if existing:
                        continue

                    # Save new sale
                    db_sale = BlokpaxSale(
                        listing_id=sale.listing_id,
                        asset_id=sale.asset_id,
                        asset_name=sale.asset_name,
                        price_bpx=sale.price_bpx,
                        price_usd=sale.price_usd,
                        quantity=sale.quantity,
                        seller_address=sale.seller_address,
                        buyer_address=sale.buyer_address,
                        filled_at=sale.filled_at,
                    )
                    session.add(db_sale)
                    new_sales += 1

                session.commit()

            print(f"  Found {len(sales)} sales, {new_sales} new")
            await asyncio.sleep(1)

        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nTotal: {total_sales} sales scraped, {new_sales} new saved")
    return {"total": total_sales, "new": new_sales}


async def scrape_offers(slugs: List[str] = None, max_pages: int = 200):
    """
    Scrapes all active offers (bids) from WOTF storefronts.
    """
    if slugs is None:
        slugs = WOTF_STOREFRONTS

    print("\n" + "=" * 60)
    print("BLOKPAX OFFERS SCRAPER")
    print("=" * 60)

    total_offers = 0
    new_offers = 0

    for slug in slugs:
        print(f"\n--- {slug} ---")

        try:
            offers = await scrape_all_offers(slug, max_pages=max_pages)
            total_offers += len(offers)

            # Filter WOTF items for reward-room (mixed storefront)
            if slug == "reward-room":
                offers = [o for o in offers if is_wotf_asset(o.asset_name)]
                print(f"  Filtered to {len(offers)} WOTF items")

            with Session(engine) as session:
                for offer in offers:
                    # Check if already indexed
                    existing = session.exec(
                        select(BlokpaxOfferDB).where(
                            BlokpaxOfferDB.external_id == offer.offer_id
                        )
                    ).first()

                    if existing:
                        # Update existing offer
                        existing.price_bpx = offer.price_bpx
                        existing.price_usd = offer.price_usd
                        existing.quantity = offer.quantity
                        existing.status = offer.status
                        existing.scraped_at = datetime.utcnow()
                        session.add(existing)
                        continue

                    # Save new offer
                    db_offer = BlokpaxOfferDB(
                        external_id=offer.offer_id,
                        asset_id=offer.asset_id,
                        price_bpx=offer.price_bpx,
                        price_usd=offer.price_usd,
                        quantity=offer.quantity,
                        buyer_address=offer.buyer_address,
                        status=offer.status,
                        created_at=offer.created_at,
                    )
                    session.add(db_offer)
                    new_offers += 1

                session.commit()

            print(f"  Found {len(offers)} offers, {new_offers} new")
            await asyncio.sleep(1)

        except Exception as e:
            print(f"  Error: {e}")

    print(f"\nTotal: {total_offers} offers scraped, {new_offers} new saved")
    return {"total": total_offers, "new": new_offers}


async def scrape_redemptions(slug: str = "wotf-existence-collector-boxes"):
    """
    Scrapes redemption data from collector boxes activity feed.
    Stores individual redemption events and updates snapshot with totals.
    """
    print("\n" + "=" * 60)
    print("BLOKPAX REDEMPTION TRACKER")
    print("=" * 60)

    try:
        stats = await scrape_redemption_stats(slug)

        total_redeemed = stats["total_redeemed"]
        max_supply = stats["max_supply"]
        remaining = stats["remaining"]
        redeemed_pct = stats["redeemed_pct"]
        by_box_art = stats["by_box_art"]
        redemptions = stats["redemptions"]

        print(f"\nCollector Box Redemptions: {total_redeemed}/{max_supply} ({redeemed_pct:.1f}%)")
        print(f"Remaining: {remaining}")
        print("\nBy Box Art:")
        for art, count in sorted(by_box_art.items(), key=lambda x: -x[1]):
            print(f"  {art}: {count}")

        # Save individual redemptions to database
        with Session(engine) as session:
            new_count = 0
            for r in redemptions:
                # Check if already indexed
                existing = session.exec(
                    select(BlokpaxRedemption).where(
                        BlokpaxRedemption.asset_id == r.asset_id,
                        BlokpaxRedemption.redeemed_at == r.redeemed_at
                    )
                ).first()

                if existing:
                    continue

                db_redemption = BlokpaxRedemption(
                    storefront_slug=slug,
                    asset_id=r.asset_id,
                    asset_name=r.asset_name,
                    box_art=r.box_art,
                    serial_number=r.serial_number,
                    redeemed_at=r.redeemed_at,
                )
                session.add(db_redemption)
                new_count += 1

            session.commit()
            print(f"\nSaved {new_count} new redemption records to database")

        return {
            "total_redeemed": total_redeemed,
            "max_supply": max_supply,
            "remaining": remaining,
            "redeemed_pct": redeemed_pct,
            "new_records": new_count,
        }

    except Exception as e:
        print(f"Error scraping redemptions: {e}")
        return {"error": str(e)}


async def scrape_all_assets(slug: str, max_pages: int = 10):
    """
    Scrapes all assets from a storefront (for initial indexing).
    """
    print(f"\n=== Indexing Assets: {slug} ===")

    bpx_price = await get_bpx_price()
    all_assets = []
    page = 1

    while page <= max_pages:
        try:
            response = await fetch_storefront_assets(slug, page=page, per_page=50)
            assets = response.get("data", [])

            if not assets:
                break

            for asset_data in assets:
                asset = parse_asset({"data": asset_data}, slug, bpx_price)
                all_assets.append(asset)

            meta = response.get("meta", {})
            total_pages = meta.get("last_page", 1)
            print(f"  Page {page}/{total_pages}: {len(assets)} assets")

            if page >= total_pages:
                break

            page += 1
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"  Error on page {page}: {e}")
            break

    # Save to DB
    with Session(engine) as session:
        saved = 0
        for asset in all_assets:
            # Filter WOTF for reward-room
            if slug == "reward-room" and not is_wotf_asset(asset.name):
                continue

            existing = session.exec(
                select(BlokpaxAssetDB).where(
                    BlokpaxAssetDB.external_id == asset.asset_id
                )
            ).first()

            if existing:
                # Update existing
                existing.floor_price_bpx = asset.floor_price_bpx
                existing.floor_price_usd = asset.floor_price_usd
                existing.owner_count = asset.owner_count
                existing.updated_at = datetime.utcnow()
                session.add(existing)
            else:
                # Create new
                db_asset = BlokpaxAssetDB(
                    external_id=asset.asset_id,
                    storefront_slug=slug,
                    name=asset.name,
                    description=asset.description,
                    image_url=asset.image_url,
                    network_id=asset.network_id,
                    contract_address=asset.contract_address,
                    token_id=asset.token_id,
                    owner_count=asset.owner_count,
                    token_count=asset.token_count,
                    traits=asset.traits,
                    floor_price_bpx=asset.floor_price_bpx,
                    floor_price_usd=asset.floor_price_usd,
                )
                session.add(db_asset)
                saved += 1

        session.commit()
        print(f"\n  Total: {len(all_assets)} assets, {saved} new saved")

    return all_assets


async def main():
    parser = argparse.ArgumentParser(description="Blokpax WOTF Scraper")
    parser.add_argument(
        "--slug", type=str, help="Specific storefront slug to scrape"
    )
    parser.add_argument(
        "--floors", action="store_true", help="Only scrape floor prices"
    )
    parser.add_argument(
        "--sales", action="store_true", help="Only scrape recent sales"
    )
    parser.add_argument(
        "--assets", action="store_true", help="Index all assets (slow)"
    )
    parser.add_argument(
        "--offers", action="store_true", help="Only scrape active offers/bids"
    )
    parser.add_argument(
        "--pages", type=int, default=3, help="Max pages to scrape"
    )
    parser.add_argument(
        "--deep", action="store_true",
        help="Deep scan: check each asset for listings (slow but accurate)"
    )
    parser.add_argument(
        "--redemptions", action="store_true",
        help="Scrape collector box redemption data"
    )
    args = parser.parse_args()

    # Determine which storefronts to scrape
    slugs = [args.slug] if args.slug else WOTF_STOREFRONTS

    # Log scrape start to Discord
    start_time = time.time()
    log_scrape_start(len(slugs), scrape_type="blokpax")

    errors = 0
    new_sales = 0

    try:
        # Ensure storefronts exist in DB
        for slug in slugs:
            await scrape_storefront_metadata(slug)

        # Run requested scrapers
        if args.assets:
            for slug in slugs:
                await scrape_all_assets(slug, max_pages=args.pages)
        elif args.offers:
            await scrape_offers(slugs, max_pages=args.pages)
        elif args.floors:
            await scrape_floor_prices(slugs, deep_scan=args.deep)
        elif args.sales:
            result = await scrape_sales(slugs, max_pages=args.pages)
            new_sales = result.get("new", 0)
        elif args.redemptions:
            await scrape_redemptions()
        else:
            # Default: floors + sales + redemptions (for collector boxes)
            await scrape_floor_prices(slugs, deep_scan=args.deep)
            result = await scrape_sales(slugs, max_pages=args.pages)
            new_sales = result.get("new", 0)
            # Also scrape redemptions for collector boxes
            if "wotf-existence-collector-boxes" in slugs:
                await scrape_redemptions()

    except Exception as e:
        errors += 1
        log_scrape_error("Blokpax", str(e))
        raise

    finally:
        # Log scrape complete to Discord
        duration = time.time() - start_time
        log_scrape_complete(
            cards_processed=len(slugs),
            new_listings=0,
            new_sales=new_sales,
            duration_seconds=duration,
            errors=errors
        )

    print("\n" + "=" * 60)
    print("SCRAPE COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
