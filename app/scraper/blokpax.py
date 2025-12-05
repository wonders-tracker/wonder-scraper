"""
Blokpax API client for scraping WOTF marketplace data.

API Endpoints:
- GET /api/storefront/{slug} - Collection metadata
- GET /api/storefront/{slug}/assets - List assets (paginated)
- GET /api/storefront/{slug}/asset/{id} - Individual asset details with listings
- GET /api/storefront/{slug}/activity - Sales history (filled listings)

IMPORTANT: Floor price computation
The bulk /assets endpoint returns `floor_listing: null` for all assets.
To find active listings, we must:
1. Paginate through all assets using the bulk endpoint
2. Fetch each asset's detail endpoint individually
3. Check the `listings` array for `listing_status: "active"`
4. Compute the floor price as the minimum of all active listing prices

This is slow but necessary - there's no API to filter by "listed only".
"""
import httpx
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass
import asyncio

# Blokpax API base URL
BLOKPAX_API_BASE = "https://api.blokpax.com/api"

# GeckoTerminal pool for BPX/WETH
GECKO_POOL_URL = "https://api.geckoterminal.com/api/v2/networks/eth/pools/0x183b1a923800071eb88e86ee802bde31acfa85b7"

# BPX uses 9 decimal places in Blokpax API (prices stored as integers)
# 500000000000000 = 500,000 BPX
BPX_DECIMALS = 9

# WOTF storefronts to track
WOTF_STOREFRONTS = [
    "wotf-existence-collector-boxes",  # Serialized Booster Boxes
    "wotf-art-proofs",                  # Art Proofs
    "wotf-existence-preslabs",          # Existence Preslabs
    "reward-room",                      # Orbital Redemption Tokens (mixed, filter by WOTF)
]

# Cache for BPX price (avoid hammering API)
_bpx_price_cache: Dict[str, Any] = {
    "price": None,
    "timestamp": None,
    "ttl_seconds": 300  # 5 min cache
}


@dataclass
class BlokpaxListing:
    """Represents an active listing on Blokpax."""
    listing_id: str
    asset_id: str
    price_bpx: float
    price_usd: float
    quantity: int
    seller_address: str
    created_at: Optional[datetime] = None


@dataclass
class BlokpaxOffer:
    """Represents an offer on a Blokpax asset."""
    offer_id: str
    asset_id: str
    price_bpx: float
    price_usd: float
    quantity: int
    buyer_address: str
    status: str  # 'open', 'filled', 'cancelled'
    created_at: Optional[datetime] = None


@dataclass
class BlokpaxSale:
    """Represents a completed sale (filled listing)."""
    listing_id: str
    asset_id: str
    asset_name: str
    price_bpx: float
    price_usd: float
    quantity: int
    seller_address: str
    buyer_address: str
    filled_at: datetime


@dataclass
class BlokpaxAsset:
    """Represents an asset/NFT on Blokpax."""
    asset_id: str
    name: str
    description: Optional[str]
    image_url: Optional[str]
    storefront_slug: str
    network_id: int  # 1 = Ethereum, 137 = Polygon
    contract_address: str
    token_id: str
    owner_count: int
    token_count: int
    traits: List[Dict[str, str]]
    floor_price_bpx: Optional[float] = None
    floor_price_usd: Optional[float] = None
    listings: List[BlokpaxListing] = None
    offers: List[BlokpaxOffer] = None


async def get_bpx_price() -> float:
    """
    Fetches current BPX price in USD from GeckoTerminal.
    Uses cached value if available and fresh.
    """
    global _bpx_price_cache

    # Check cache
    if _bpx_price_cache["price"] and _bpx_price_cache["timestamp"]:
        age = datetime.now() - _bpx_price_cache["timestamp"]
        if age.total_seconds() < _bpx_price_cache["ttl_seconds"]:
            return _bpx_price_cache["price"]

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(GECKO_POOL_URL, timeout=10.0)
            data = response.json()

            # Extract base_token_price_usd (BPX is base token)
            price_str = data["data"]["attributes"]["base_token_price_usd"]
            price = float(price_str)

            # Update cache
            _bpx_price_cache["price"] = price
            _bpx_price_cache["timestamp"] = datetime.now()

            print(f"BPX Price: ${price:.6f} USD")
            return price

    except Exception as e:
        print(f"Failed to fetch BPX price: {e}")
        # Fallback to cached or approximate value
        if _bpx_price_cache["price"]:
            return _bpx_price_cache["price"]
        return 0.002  # Approximate fallback


def bpx_to_float(raw_price: int) -> float:
    """
    Converts raw BPX price (with 12 decimals) to float.
    Example: 500000000000000 -> 500,000 BPX
    """
    return raw_price / (10 ** BPX_DECIMALS)


def bpx_to_usd(raw_price: int, bpx_price_usd: float) -> float:
    """
    Converts raw BPX price to USD value.
    """
    bpx_amount = bpx_to_float(raw_price)
    return bpx_amount * bpx_price_usd


async def fetch_storefront(slug: str) -> Dict[str, Any]:
    """
    Fetches storefront/collection metadata.
    """
    url = f"{BLOKPAX_API_BASE}/storefront/{slug}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=15.0)
        response.raise_for_status()
        return response.json()


async def fetch_storefront_assets(
    slug: str,
    page: int = 1,
    per_page: int = 24,
    sort_by: str = "price_asc"
) -> Dict[str, Any]:
    """
    Fetches assets from a storefront with pagination.

    Args:
        slug: Storefront slug (e.g., 'wotf-existence-collector-boxes')
        page: Page number (1-indexed)
        per_page: Items per page (default 24, matches website)
        sort_by: Sort order ('price_asc', 'price_desc', 'recent', etc.)
    """
    url = f"{BLOKPAX_API_BASE}/storefront/{slug}/assets"
    # Use website's param names: pg, perPage, sort
    params = {
        "query": "",
        "pg": page,
        "perPage": per_page,
        "sort": sort_by
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()


async def fetch_asset_details(slug: str, asset_id: str) -> Dict[str, Any]:
    """
    Fetches detailed information about a specific asset.
    Includes: listings, offers, traits, owner info.
    """
    url = f"{BLOKPAX_API_BASE}/storefront/{slug}/asset/{asset_id}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url, timeout=15.0)
        response.raise_for_status()
        return response.json()


async def fetch_storefront_activity(
    slug: str,
    page: int = 1,
    per_page: int = 50,
    activity_type: str = "sales"  # 'sales', 'listings', 'offers'
) -> Dict[str, Any]:
    """
    Fetches activity/sales history for a storefront.
    """
    url = f"{BLOKPAX_API_BASE}/storefront/{slug}/activity"
    params = {
        "page": page,
        "per_page": per_page,
        "type": activity_type
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(url, params=params, timeout=15.0)
        response.raise_for_status()
        return response.json()


def parse_asset(data: Dict[str, Any], slug: str, bpx_price_usd: float) -> BlokpaxAsset:
    """
    Parses API response into BlokpaxAsset dataclass.
    """
    asset_data = data.get("data", data)
    asset_info = asset_data.get("asset", {})

    # Parse traits
    traits = []
    for attr in asset_data.get("attributes", []):
        traits.append({
            "trait_type": attr.get("trait_type", ""),
            "value": attr.get("value", "")
        })

    # Parse floor listing if present
    floor_price_bpx = None
    floor_price_usd = None
    floor_listing = asset_info.get("floor_listing")
    if floor_listing:
        raw_price = floor_listing.get("price", 0)
        floor_price_bpx = bpx_to_float(raw_price)
        floor_price_usd = bpx_to_usd(raw_price, bpx_price_usd)

    # Parse listings
    listings = []
    for listing in asset_info.get("listings", []):
        raw_price = listing.get("price", 0)
        listings.append(BlokpaxListing(
            listing_id=str(listing.get("id", "")),
            asset_id=str(asset_data.get("id", "")),
            price_bpx=bpx_to_float(raw_price),
            price_usd=bpx_to_usd(raw_price, bpx_price_usd),
            quantity=listing.get("quantity", 1),
            seller_address=listing.get("seller", {}).get("address", ""),
            created_at=_parse_datetime(listing.get("created_at"))
        ))

    # Parse offers
    offers = []
    for offer in asset_info.get("offers", []):
        raw_price = offer.get("offer_bpx_per_token", 0)
        offers.append(BlokpaxOffer(
            offer_id=str(offer.get("id", "")),
            asset_id=str(asset_data.get("id", "")),
            price_bpx=bpx_to_float(raw_price),
            price_usd=bpx_to_usd(raw_price, bpx_price_usd),
            quantity=offer.get("quantity", 1),
            buyer_address=offer.get("offerer", {}).get("address", ""),
            status=offer.get("offer_status", "open"),
            created_at=_parse_datetime(offer.get("created_at"))
        ))

    return BlokpaxAsset(
        asset_id=str(asset_data.get("id", "")),
        name=asset_data.get("name", ""),
        description=asset_data.get("description"),
        image_url=asset_data.get("image"),
        storefront_slug=slug,
        network_id=asset_data.get("network_id", 1),
        contract_address=asset_data.get("contract_address", ""),
        token_id=str(asset_data.get("token_id", "")),
        owner_count=asset_info.get("owner_count", 0),
        token_count=asset_info.get("token_count", 1),
        traits=traits,
        floor_price_bpx=floor_price_bpx,
        floor_price_usd=floor_price_usd,
        listings=listings,
        offers=offers
    )


def parse_sale(activity: Dict[str, Any], bpx_price_usd: float) -> Optional[BlokpaxSale]:
    """
    Parses activity item into BlokpaxSale if it's a completed sale.
    """
    listing = activity.get("listing", {})

    # Only process filled (completed) listings
    if listing.get("listing_status") != "filled":
        return None

    asset = activity.get("asset", {})
    raw_price = listing.get("price", 0)

    return BlokpaxSale(
        listing_id=str(listing.get("id", "")),
        asset_id=str(asset.get("id", "")),
        asset_name=asset.get("name", ""),
        price_bpx=bpx_to_float(raw_price),
        price_usd=bpx_to_usd(raw_price, bpx_price_usd),
        quantity=listing.get("quantity", 1),
        seller_address=listing.get("seller", {}).get("address", ""),
        buyer_address=listing.get("buyer", {}).get("address", ""),
        filled_at=_parse_datetime(listing.get("filled_at")) or datetime.now()
    )


def _parse_datetime(dt_str: Optional[str]) -> Optional[datetime]:
    """
    Parses ISO datetime string from API.
    Format: 2025-10-30T05:56:30.000000Z
    """
    if not dt_str:
        return None
    try:
        # Handle both formats
        if "." in dt_str:
            return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        return datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
    except (ValueError, TypeError):
        return None


async def scrape_all_listings(slug: str, max_pages: int = 200) -> List[BlokpaxListing]:
    """
    Scrapes ALL active listings from a storefront by checking each asset.
    This is slower but necessary because the bulk endpoint doesn't include
    floor_listing data.

    Args:
        slug: Storefront slug
        max_pages: Maximum pages to scan (24 assets per page)

    Returns:
        List of all active BlokpaxListing objects
    """
    bpx_price = await get_bpx_price()
    all_listings: List[BlokpaxListing] = []
    seen_listing_ids = set()

    print(f"  Scanning all assets for listings (this may take a while)...")

    # First get total pages
    first_response = await fetch_storefront_assets(slug, page=1, per_page=24)
    meta = first_response.get("meta", {})
    total_pages = meta.get("last_page", 1)
    total_assets = meta.get("total", 0)
    print(f"  Total: {total_assets} assets across {total_pages} pages")

    page = 1
    while page <= min(max_pages, total_pages):
        try:
            if page > 1:
                assets_response = await fetch_storefront_assets(slug, page=page, per_page=24)
            else:
                assets_response = first_response

            assets = assets_response.get("data", [])

            if not assets:
                break

            # Check each asset for listings
            for asset_data in assets:
                asset_id = asset_data.get("id")
                asset_name = asset_data.get("name", "Unknown")
                if not asset_id:
                    continue

                try:
                    detail = await fetch_asset_details(slug, str(asset_id))
                    asset_info = detail.get("data", {}).get("asset", {})
                    listings = asset_info.get("listings", [])

                    for listing in listings:
                        listing_id = str(listing.get("id", ""))
                        if listing_id in seen_listing_ids:
                            continue

                        if listing.get("listing_status") == "active":
                            raw_price = listing.get("price", 0)
                            if raw_price > 0:
                                seen_listing_ids.add(listing_id)
                                all_listings.append(BlokpaxListing(
                                    listing_id=listing_id,
                                    asset_id=str(asset_id),
                                    price_bpx=bpx_to_float(raw_price),
                                    price_usd=bpx_to_usd(raw_price, bpx_price),
                                    quantity=listing.get("quantity", 1),
                                    seller_address=listing.get("owner", {}).get("username", ""),
                                    created_at=_parse_datetime(listing.get("created_at"))
                                ))
                                print(f"    Found: {asset_name[:30]} @ {bpx_to_float(raw_price):,.0f} BPX")

                    await asyncio.sleep(0.15)  # Rate limit between asset calls

                except Exception as e:
                    print(f"    Error fetching asset {asset_id}: {e}")

            print(f"    Page {page}/{total_pages}: scanned {len(assets)} assets, {len(all_listings)} listings found")

            page += 1
            await asyncio.sleep(0.3)  # Rate limit between pages

        except Exception as e:
            print(f"    Error on page {page}: {e}")
            break

    # Sort by price ascending
    all_listings.sort(key=lambda x: x.price_bpx)
    print(f"  Done! Found {len(all_listings)} active listings")
    return all_listings


async def scrape_storefront_floor(slug: str, deep_scan: bool = True) -> Dict[str, Any]:
    """
    Scrapes floor price and basic stats for a storefront.
    Returns dict with floor_price_bpx, floor_price_usd, listed_count, etc.

    NOTE: The bulk /assets endpoint does NOT include floor_listing data,
    so deep_scan=True is required to get actual listings.

    Args:
        slug: Storefront slug
        deep_scan: If True (default), scans all assets for listings.
                   If False, only gets metadata without listings.
    """
    bpx_price = await get_bpx_price()

    # Get first page for metadata
    assets_response = await fetch_storefront_assets(slug, page=1, per_page=24, sort_by="price_asc")

    floor_price_bpx = None
    floor_price_usd = None
    listed_count = 0
    all_listings: List[BlokpaxListing] = []

    # Deep scan to find all listings (required since bulk endpoint doesn't include floor_listing)
    if deep_scan:
        print(f"  Scanning {slug} for active listings...")
        all_listings = await scrape_all_listings(slug)
        listed_count = len(all_listings)

    # Find floor from all collected listings
    if all_listings:
        # Sort by price ascending
        all_listings.sort(key=lambda x: x.price_bpx)
        floor_listing = all_listings[0]
        floor_price_bpx = floor_listing.price_bpx
        floor_price_usd = floor_listing.price_usd

    # Get metadata for total counts
    try:
        meta = assets_response.get("meta", {})
        total_tokens = meta.get("total", 0)
    except Exception:
        total_tokens = 0

    return {
        "slug": slug,
        "floor_price_bpx": floor_price_bpx,
        "floor_price_usd": floor_price_usd,
        "bpx_price_usd": bpx_price,
        "listed_count": listed_count,
        "total_tokens": total_tokens,
        "listings": all_listings  # Include all found listings
    }


async def scrape_recent_sales(slug: str, max_pages: int = 3) -> List[BlokpaxSale]:
    """
    Scrapes recent sales (filled listings) from a storefront.
    """
    bpx_price = await get_bpx_price()
    all_sales = []

    for page in range(1, max_pages + 1):
        try:
            activity = await fetch_storefront_activity(slug, page=page, activity_type="sales")
            items = activity.get("data", [])

            if not items:
                break

            for item in items:
                sale = parse_sale(item, bpx_price)
                if sale:
                    all_sales.append(sale)

            # Rate limiting
            await asyncio.sleep(0.5)

        except Exception as e:
            print(f"Error fetching activity page {page} for {slug}: {e}")
            break

    return all_sales


def is_wotf_asset(asset_name: str) -> bool:
    """
    Checks if an asset is a WOTF (Wonders of the First) item.
    Used to filter WOTF items from mixed storefronts like reward-room.
    """
    wotf_keywords = [
        "wonders of the first",
        "wotf",
        "orbital redemption token",
        "existence",
    ]
    name_lower = asset_name.lower()
    return any(kw in name_lower for kw in wotf_keywords)
