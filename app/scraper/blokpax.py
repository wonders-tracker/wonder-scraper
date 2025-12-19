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
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
from dataclasses import dataclass
import asyncio

from sqlmodel import Session, select

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
    "wotf-art-proofs",  # Art Proofs
    "wotf-existence-preslabs",  # Existence Preslabs
    "reward-room",  # Orbital Redemption Tokens (mixed, filter by WOTF)
]

# Cache for BPX price (avoid hammering API)
_bpx_price_cache: Dict[str, Any] = {
    "price": None,
    "timestamp": None,
    "ttl_seconds": 300,  # 5 min cache
}
_bpx_cache_lock = asyncio.Lock()


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
    Uses cached value if available and fresh. Thread-safe via asyncio lock.
    """
    global _bpx_price_cache

    # Quick check without lock (read is safe)
    if _bpx_price_cache["price"] and _bpx_price_cache["timestamp"]:
        age = datetime.now(timezone.utc) - _bpx_price_cache["timestamp"]
        if age.total_seconds() < _bpx_price_cache["ttl_seconds"]:
            return _bpx_price_cache["price"]

    # Acquire lock for cache update
    async with _bpx_cache_lock:
        # Double-check after acquiring lock (another task may have updated)
        if _bpx_price_cache["price"] and _bpx_price_cache["timestamp"]:
            age = datetime.now(timezone.utc) - _bpx_price_cache["timestamp"]
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
                _bpx_price_cache["timestamp"] = datetime.now(timezone.utc)

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
    return raw_price / (10**BPX_DECIMALS)


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
    slug: str, page: int = 1, per_page: int = 24, sort_by: str = "price_asc"
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
    params = {"query": "", "pg": page, "perPage": per_page, "sort": sort_by}

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
    activity_type: str = "sales",  # 'sales', 'listings', 'offers'
) -> Dict[str, Any]:
    """
    Fetches activity/sales history for a storefront.
    """
    url = f"{BLOKPAX_API_BASE}/storefront/{slug}/activity"
    params = {"page": page, "per_page": per_page, "type": activity_type}

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
        traits.append({"trait_type": attr.get("trait_type", ""), "value": attr.get("value", "")})

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
        listings.append(
            BlokpaxListing(
                listing_id=str(listing.get("id", "")),
                asset_id=str(asset_data.get("id", "")),
                price_bpx=bpx_to_float(raw_price),
                price_usd=bpx_to_usd(raw_price, bpx_price_usd),
                quantity=listing.get("quantity", 1),
                seller_address=listing.get("seller", {}).get("username", ""),
                created_at=_parse_datetime(listing.get("created_at")),
            )
        )

    # Parse offers
    offers = []
    for offer in asset_info.get("offers", []):
        raw_price = offer.get("offer_bpx_per_token", 0)
        offers.append(
            BlokpaxOffer(
                offer_id=str(offer.get("id", "")),
                asset_id=str(asset_data.get("id", "")),
                price_bpx=bpx_to_float(raw_price),
                price_usd=bpx_to_usd(raw_price, bpx_price_usd),
                quantity=offer.get("quantity", 1),
                buyer_address=offer.get("offerer", {}).get("address", ""),
                status=offer.get("offer_status", "open"),
                created_at=_parse_datetime(offer.get("created_at")),
            )
        )

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
        offers=offers,
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
        filled_at=_parse_datetime(listing.get("filled_at")) or datetime.now(timezone.utc),
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


async def scrape_all_listings(slug: str, max_pages: int = 200, concurrency: int = 20) -> List[BlokpaxListing]:
    """
    Scrapes ALL active listings from a storefront using an adaptive strategy.

    IMPORTANT: Different storefronts have different behaviors:
    - wotf-art-proofs: Sequential small integers (1-5000), bulk endpoint HIDES listed assets
    - wotf-existence-collector-boxes: Large non-sequential IDs (~4.2B), requires perPage=5 for floor_listing
    - reward-room: Large non-sequential IDs (~2.1B), requires perPage=5 for floor_listing

    Strategy Detection:
    1. First check with perPage=5 (API quirk: only returns floor_listing at small page sizes)
    2. If bulk includes floor_listing with perPage=5: Use small page size to collect all
    3. If bulk hides listings: Use "missing ID" strategy for sequential IDs
    4. For non-sequential IDs without bulk data: Fall back to v2 API probing

    Args:
        slug: Storefront slug
        max_pages: Maximum pages to scan from bulk endpoint
        concurrency: Number of concurrent requests (default 20)

    Returns:
        List of all active BlokpaxListing objects
    """
    import aiohttp

    bpx_price = await get_bpx_price()
    # Ensure valid BPX price for USD calculations
    if not bpx_price or bpx_price <= 0:
        print(f"[Blokpax] Warning: Invalid BPX price ({bpx_price}), using fallback")
        bpx_price = 0.002

    all_listings: List[BlokpaxListing] = []
    seen_listing_ids = set()

    print(f"  Scanning {slug} for active listings...")

    async with aiohttp.ClientSession() as session:
        # Step 0: First probe with perPage=5 to check if API returns floor_listing data
        # This is a Blokpax API quirk: floor_listing data ONLY appears when perPage <= 5
        probe_url = f"{BLOKPAX_API_BASE}/storefront/{slug}/assets"
        probe_params = {"pg": 1, "perPage": 5, "query": "", "sort": "price_asc"}
        use_small_pages = False

        try:
            async with session.get(probe_url, params=probe_params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    probe_data = await resp.json()
                    probe_assets = probe_data.get("data", [])
                    for a in probe_assets:
                        fl = a.get("floor_listing")
                        if fl and fl.get("listing_status") == "active":
                            use_small_pages = True
                            break
        except Exception:
            pass

        # Step 1: Collect all asset IDs from bulk endpoint AND check for floor_listing data
        all_asset_ids = []  # Store as strings (API returns mixed types)
        bulk_has_listings = False  # Track if bulk endpoint includes floor_listing data
        page = 0  # Blokpax API uses 0-indexed pagination
        total_pages = 1
        total_assets = 0

        # Use perPage=5 if the probe found floor_listing data, otherwise use 100 for speed
        per_page = 5 if use_small_pages else 100

        if use_small_pages:
            print("  Using small page mode (perPage=5) - API quirk requires this for floor_listing")
            # With small pages, we need more pages but can early-exit when listings stop appearing
            effective_max_pages = max_pages * 20  # Allow up to 4000 pages for small page mode
        else:
            effective_max_pages = max_pages

        # Track consecutive pages without new listings (for early exit in small page mode)
        pages_without_listings = 0
        max_empty_pages = 10  # Exit after 10 consecutive pages with no listings

        while page <= min(effective_max_pages, total_pages):
            url = f"{BLOKPAX_API_BASE}/storefront/{slug}/assets"
            params = {"pg": page, "perPage": per_page, "query": "", "sort": "price_asc"}

            try:
                async with session.get(url, params=params, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        break
                    data = await resp.json()
                    assets = data.get("data", [])
                    meta = data.get("meta", {})

                    if page == 0:  # First page (0-indexed)
                        total_pages = meta.get("last_page", 1)
                        total_assets = meta.get("total", 0)
                        print(f"  Total assets: {total_assets} across {total_pages} pages")

                    page_had_listings = False
                    for a in assets:
                        aid = a.get("id")
                        if aid is not None:
                            # Store as string for consistency
                            all_asset_ids.append(str(aid))

                        # Check if bulk endpoint includes floor_listing data
                        floor_listing = a.get("floor_listing")
                        if floor_listing and floor_listing.get("listing_status") == "active":
                            bulk_has_listings = True
                            page_had_listings = True
                            raw_price = floor_listing.get("price", 0)
                            if raw_price > 0:
                                listing_id = str(floor_listing.get("id", ""))
                                if listing_id and listing_id not in seen_listing_ids:
                                    seen_listing_ids.add(listing_id)
                                    a.get("name", "Unknown")
                                    all_listings.append(
                                        BlokpaxListing(
                                            listing_id=listing_id,
                                            asset_id=str(aid),
                                            price_bpx=bpx_to_float(raw_price),
                                            price_usd=bpx_to_usd(raw_price, bpx_price),
                                            quantity=floor_listing.get("quantity", 1),
                                            seller_address=floor_listing.get("seller", {}).get("username", "")
                                            if isinstance(floor_listing.get("seller"), dict)
                                            else "",
                                            created_at=_parse_datetime(floor_listing.get("created_at")),
                                        )
                                    )

                    # For small page mode: early exit if we've passed all listings
                    # Since sorted by price_asc, listed items come first
                    if use_small_pages:
                        if page_had_listings:
                            pages_without_listings = 0
                        else:
                            pages_without_listings += 1
                            # If we found listings before but now have many empty pages, stop
                            if bulk_has_listings and pages_without_listings >= max_empty_pages:
                                print(f"  Early exit: {pages_without_listings} consecutive pages without listings")
                                break

                    page += 1
                    await asyncio.sleep(0.05)

            except Exception as e:
                print(f"  Error fetching page {page}: {e}")
                break

        if not all_asset_ids:
            print("  No assets found in bulk endpoint")
            return []

        # If bulk endpoint already gave us listings, we're done!
        if bulk_has_listings and all_listings:
            print(f"  Bulk endpoint included floor_listing data - extracted {len(all_listings)} listings directly")
            all_listings.sort(key=lambda x: x.price_bpx)
            return all_listings

        # Step 2: Detect ID pattern to choose strategy
        # Convert to integers for analysis
        try:
            int_ids = [int(aid) for aid in all_asset_ids]
            max_id = max(int_ids)
            min_id = min(int_ids)
            id_range = max_id - min_id

            # Check if IDs are sequential (small gaps) or non-sequential (large, scattered)
            # Sequential: IDs are within a reasonable range of total count
            # Non-sequential: IDs are huge (>1M) or range is >> count
            is_sequential = max_id < 100000 and id_range < total_assets * 2
        except (ValueError, TypeError):
            # IDs can't be converted to int - treat as non-sequential
            is_sequential = False
            max_id = 0
            min_id = 0

        print(f"  Bulk returned {len(all_asset_ids)} IDs (range: {min_id}-{max_id})")

        # Helper function to probe an asset for listings
        async def check_asset_v2(asset_id: str) -> Optional[List[BlokpaxListing]]:
            url = f"{BLOKPAX_API_BASE}/v2/storefront/{slug}/asset/{asset_id}"
            try:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        return None

                    data = await resp.json()
                    d = data.get("data", {})
                    asset_info = d.get("asset", {})
                    listings_data = asset_info.get("listings", [])
                    asset_name = d.get("name", "Unknown")

                    found_listings = []
                    for listing in listings_data:
                        if listing.get("listing_status") == "active":
                            raw_price = listing.get("price", 0)
                            if raw_price > 0:
                                listing_id = str(listing.get("id", ""))
                                found_listings.append(
                                    BlokpaxListing(
                                        listing_id=listing_id,
                                        asset_id=str(asset_id),
                                        price_bpx=bpx_to_float(raw_price),
                                        price_usd=bpx_to_usd(raw_price, bpx_price),
                                        quantity=listing.get("quantity", 1),
                                        seller_address=listing.get("owner", {}).get("username", ""),
                                        created_at=_parse_datetime(listing.get("created_at")),
                                    )
                                )

                    if found_listings:
                        price = found_listings[0].price_bpx
                        print(f"    ✓ {asset_name[:35]} @ {price:,.0f} BPX")

                    return found_listings if found_listings else None

            except Exception:
                return None

        # Step 3: Choose strategy based on ID pattern
        if is_sequential:
            # SEQUENTIAL IDs: Bulk endpoint hides listed assets
            # Probe "missing" IDs in the range that aren't in bulk response
            print("  Strategy: Missing ID probe (sequential IDs detected)")

            known_ids_set = set(int_ids)
            missing_ids = []
            for i in range(max_id + 100):
                if i not in known_ids_set:
                    missing_ids.append(str(i))

            print(f"  Found {len(missing_ids)} missing IDs to probe")
            ids_to_check = missing_ids
        else:
            # NON-SEQUENTIAL IDs: Bulk endpoint shows ALL assets, just probe each one
            # This is slower but necessary for storefronts with large scattered IDs
            print("  Strategy: Full scan (non-sequential IDs detected)")
            ids_to_check = all_asset_ids

        # Step 4: Probe assets in concurrent batches
        checked = 0
        total_to_check = len(ids_to_check)

        for i in range(0, total_to_check, concurrency):
            batch = ids_to_check[i : i + concurrency]
            tasks = [check_asset_v2(aid) for aid in batch]
            results = await asyncio.gather(*tasks)

            for result in results:
                if result:
                    for listing in result:
                        if listing.listing_id not in seen_listing_ids:
                            seen_listing_ids.add(listing.listing_id)
                            all_listings.append(listing)

            checked += len(batch)
            if checked % 200 == 0 or checked == total_to_check:
                print(f"    Progress: {checked}/{total_to_check} assets checked, {len(all_listings)} listings found")

            await asyncio.sleep(0.05)

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
    # Ensure valid BPX price for USD calculations
    if not bpx_price or bpx_price <= 0:
        print(f"[Blokpax] Warning: Invalid BPX price ({bpx_price}), using fallback")
        bpx_price = 0.002

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
        "listings": all_listings,  # Include all found listings
    }


async def scrape_recent_sales(slug: str, max_pages: int = 3) -> List[BlokpaxSale]:
    """
    Scrapes recent sales (filled listings) from a storefront.
    """
    bpx_price = await get_bpx_price()
    # Ensure valid BPX price for USD calculations
    if not bpx_price or bpx_price <= 0:
        print(f"[Blokpax] Warning: Invalid BPX price ({bpx_price}), using fallback")
        bpx_price = 0.002

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


async def scrape_all_offers(slug: str, max_pages: int = 200, concurrency: int = 20) -> List[BlokpaxOffer]:
    """
    Scrapes ALL active offers (bids) from a storefront.

    This requires fetching individual asset details since offers are attached to assets,
    not available via the activity feed.

    Args:
        slug: Storefront slug (e.g., 'wotf-art-proofs')
        max_pages: Max pages of assets to fetch (50 assets per page)
        concurrency: Number of concurrent asset detail requests

    Returns:
        List of BlokpaxOffer objects sorted by price descending (highest bids first)
    """
    import aiohttp

    bpx_price = await get_bpx_price()
    # Ensure valid BPX price for USD calculations
    if not bpx_price or bpx_price <= 0:
        print(f"[Blokpax] Warning: Invalid BPX price ({bpx_price}), using fallback")
        bpx_price = 0.002

    all_offers: List[BlokpaxOffer] = []
    seen_offer_ids = set()

    print(f"[Blokpax] Scraping offers from {slug}...")

    # Step 1: Get all asset IDs from the storefront
    asset_ids = []
    page = 1

    while page <= max_pages:
        try:
            response = await fetch_storefront_assets(slug, page=page, per_page=50)
            assets = response.get("data", [])

            if not assets:
                break

            for asset in assets:
                asset_id = asset.get("id")
                if asset_id:
                    asset_ids.append(str(asset_id))

            meta = response.get("meta", {})
            total_pages = meta.get("last_page", 1)

            if page >= total_pages:
                break

            page += 1
            await asyncio.sleep(0.3)

        except Exception as e:
            print(f"[Blokpax] Error fetching assets page {page}: {e}")
            break

    print(f"[Blokpax] Found {len(asset_ids)} assets to check for offers")

    # Step 2: Fetch asset details in batches to find offers
    # Use the v2 API endpoint which includes offer data

    async def fetch_asset_offers(session: aiohttp.ClientSession, asset_id: str) -> List[BlokpaxOffer]:
        """Fetch offers for a single asset using v2 API."""
        url = f"https://api.blokpax.com/api/v2/storefront/assets/{asset_id}"
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return []

                data = await response.json()
                asset_data = data.get("data", {})

                offers = []
                offer_list = asset_data.get("offers", [])
                asset_name = asset_data.get("name", "Unknown")

                for offer_data in offer_list:
                    offer_id = str(offer_data.get("id", ""))
                    if not offer_id or offer_id in seen_offer_ids:
                        continue

                    seen_offer_ids.add(offer_id)

                    price_bpx = float(offer_data.get("price", 0))
                    price_usd = price_bpx * bpx_price

                    offer = BlokpaxOffer(
                        offer_id=offer_id,
                        asset_id=asset_id,
                        asset_name=asset_name,
                        price_bpx=price_bpx,
                        price_usd=price_usd,
                        quantity=int(offer_data.get("quantity", 1)),
                        buyer_address=offer_data.get("buyer_address", ""),
                        status=offer_data.get("status", "open"),
                        created_at=None,
                    )
                    offers.append(offer)

                return offers

        except Exception:
            return []

    # Fetch in concurrent batches
    async with aiohttp.ClientSession() as session:
        semaphore = asyncio.Semaphore(concurrency)

        async def fetch_with_semaphore(asset_id: str):
            async with semaphore:
                offers = await fetch_asset_offers(session, asset_id)
                await asyncio.sleep(0.1)  # Rate limiting
                return offers

        tasks = [fetch_with_semaphore(aid) for aid in asset_ids]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, list):
                all_offers.extend(result)

    # Sort by price descending (highest bids first)
    all_offers.sort(key=lambda x: x.price_bpx, reverse=True)

    print(f"[Blokpax] Found {len(all_offers)} total offers in {slug}")

    return all_offers


@dataclass
class BlokpaxRedemptionData:
    """Parsed redemption activity from Blokpax."""

    asset_id: str
    asset_name: str
    box_art: Optional[str]
    serial_number: Optional[str]
    redeemed_at: datetime


# Max supply for collector boxes (from storefront description)
COLLECTOR_BOX_MAX_SUPPLY = 3393


async def fetch_redemptions(slug: str, max_pages: int = 50) -> List[BlokpaxRedemptionData]:
    """
    Fetches redemption activity from Blokpax activity feed.

    The activity API returns events with action='redemption' for redeemed boxes.
    Uses the v4 API: https://api.blokpax.com/api/v4/storefront/{slug}/activity

    Args:
        slug: Storefront slug (e.g., 'wotf-existence-collector-boxes')
        max_pages: Maximum pages to fetch (100 items per page)

    Returns:
        List of BlokpaxRedemptionData objects
    """
    redemptions = []

    async with httpx.AsyncClient() as client:
        for page in range(1, max_pages + 1):
            try:
                url = f"https://api.blokpax.com/api/v4/storefront/{slug}/activity"
                response = await client.get(url, params={"page": page, "query": ""}, timeout=15.0)
                response.raise_for_status()
                data = response.json()

                items = data.get("data", [])
                if not items:
                    break

                for item in items:
                    action = item.get("action")
                    if action != "redemption":
                        continue

                    asset = item.get("asset", {})
                    asset_id = str(asset.get("id", ""))
                    asset_name = asset.get("name", "Unknown")

                    # Extract box art and serial from attributes
                    box_art = None
                    serial_number = None
                    for attr in asset.get("attributes", []):
                        if attr.get("trait_type") == "Box Art":
                            box_art = attr.get("value")
                        elif attr.get("trait_type") == "Serial Number":
                            serial_number = attr.get("value")

                    # Parse timestamp
                    timestamp_str = item.get("timestamp")
                    redeemed_at = _parse_datetime(timestamp_str) or datetime.now(timezone.utc)

                    redemptions.append(
                        BlokpaxRedemptionData(
                            asset_id=asset_id,
                            asset_name=asset_name,
                            box_art=box_art,
                            serial_number=serial_number,
                            redeemed_at=redeemed_at,
                        )
                    )

                # Check if we've reached the last page
                meta = data.get("meta", {})
                last_page = meta.get("last_page", 1)
                if page >= last_page:
                    break

                await asyncio.sleep(0.3)

            except Exception as e:
                print(f"[Blokpax] Error fetching redemptions page {page}: {e}")
                break

    return redemptions


async def scrape_redemption_stats(slug: str = "wotf-existence-collector-boxes") -> Dict[str, Any]:
    """
    Scrapes redemption statistics for a storefront.

    Returns a dict with:
    - total_redeemed: Number of boxes redeemed
    - max_supply: Maximum supply (3393 for collector boxes)
    - remaining: Boxes not yet redeemed
    - redeemed_pct: Percentage redeemed
    - by_box_art: Dict of redemption counts by box art type
    - redemptions: List of individual redemption data
    """
    print(f"[Blokpax] Fetching redemption data for {slug}...")

    redemptions = await fetch_redemptions(slug)

    # Count by box art type
    by_box_art: Dict[str, int] = {}
    for r in redemptions:
        if r.box_art:
            by_box_art[r.box_art] = by_box_art.get(r.box_art, 0) + 1

    total_redeemed = len(redemptions)
    max_supply = COLLECTOR_BOX_MAX_SUPPLY
    remaining = max_supply - total_redeemed
    redeemed_pct = (total_redeemed / max_supply * 100) if max_supply > 0 else 0

    print(f"[Blokpax] Redemption stats: {total_redeemed}/{max_supply} ({redeemed_pct:.1f}% redeemed)")

    return {
        "slug": slug,
        "total_redeemed": total_redeemed,
        "max_supply": max_supply,
        "remaining": remaining,
        "redeemed_pct": redeemed_pct,
        "by_box_art": by_box_art,
        "redemptions": redemptions,
    }


async def scrape_preslab_sales(session: Session, max_pages: int = 10, save_to_db: bool = True) -> Tuple[int, int, int]:
    """
    Scrape preslab sales from Blokpax and create MarketPrice records linked to cards.

    Preslabs are graded singles (TAG graded) sold on Blokpax. Each preslab asset name
    contains the card name, grade, serial, and cert ID. We parse these and link them
    to our existing card database.

    Args:
        session: SQLModel database session
        max_pages: Maximum pages of activity to scrape (50 items per page)
        save_to_db: If True, save MarketPrice records to database

    Returns:
        Tuple of (sales_processed, sales_matched, sales_saved)
    """
    from app.models.market import MarketPrice
    from app.scraper.preslab_parser import parse_preslab_name, find_matching_card

    slug = "wotf-existence-preslabs"
    bpx_price = await get_bpx_price()
    if not bpx_price or bpx_price <= 0:
        print(f"[Blokpax] Warning: Invalid BPX price ({bpx_price}), using fallback")
        bpx_price = 0.002

    sales_processed = 0
    sales_matched = 0
    sales_saved = 0

    print(f"[Blokpax] Scraping preslab sales (max {max_pages} pages)...")

    for page in range(1, max_pages + 1):
        try:
            activity = await fetch_storefront_activity(slug, page=page, activity_type="sales")
            items = activity.get("data", [])

            if not items:
                break

            for item in items:
                listing = item.get("listing", {})

                # Only process filled (completed) listings
                if listing.get("listing_status") != "filled":
                    continue

                asset = item.get("asset", {})
                asset_name = asset.get("name", "")

                sales_processed += 1

                # Parse the preslab name
                parsed = parse_preslab_name(asset_name)
                if not parsed:
                    continue

                # Find matching card in database
                card_match = find_matching_card(parsed.card_name, session)
                if not card_match:
                    continue

                sales_matched += 1

                if not save_to_db:
                    continue

                # Check if we already have this sale (by external_id)
                listing_id = str(listing.get("id", ""))
                existing = session.exec(
                    select(MarketPrice).where(MarketPrice.external_id == listing_id, MarketPrice.platform == "blokpax")
                ).first()

                if existing:
                    continue  # Already saved

                # Get sale details
                raw_price = listing.get("price", 0)
                price_usd = bpx_to_usd(raw_price, bpx_price)
                filled_at = _parse_datetime(listing.get("filled_at"))

                # Extract traits from asset attributes
                traits = []
                for attr in asset.get("attributes", []):
                    traits.append({"trait_type": attr.get("trait_type", ""), "value": attr.get("value", "")})

                # Create MarketPrice record
                mp = MarketPrice(
                    card_id=card_match["id"],
                    title=asset_name,
                    price=round(price_usd, 2),
                    sold_date=filled_at,
                    listing_type="sold",
                    treatment=parsed.treatment,
                    grading=parsed.grading,
                    external_id=listing_id,
                    platform="blokpax",
                    traits=traits if traits else None,
                    seller_name=listing.get("seller", {}).get("username", "")[:20] if listing.get("seller") else None,
                    scraped_at=datetime.now(timezone.utc),
                )

                session.add(mp)
                sales_saved += 1

            # Commit after each page
            if save_to_db:
                session.commit()

            # Rate limiting
            await asyncio.sleep(0.5)

            # Check pagination
            meta = activity.get("meta", {})
            if page >= meta.get("last_page", 1):
                break

        except Exception as e:
            print(f"[Blokpax] Error fetching preslab activity page {page}: {e}")
            break

    print(f"[Blokpax] Preslab sales: {sales_processed} processed, {sales_matched} matched, {sales_saved} saved")
    return sales_processed, sales_matched, sales_saved


async def scrape_preslab_listings(session: Session, save_to_db: bool = True) -> Tuple[int, int, int]:
    """
    Scrape active preslab listings from Blokpax and create MarketPrice records.

    Args:
        session: SQLModel database session
        save_to_db: If True, save MarketPrice records to database

    Returns:
        Tuple of (listings_processed, listings_matched, listings_saved)
    """
    from app.models.market import MarketPrice
    from app.scraper.preslab_parser import parse_preslab_name, find_matching_card

    slug = "wotf-existence-preslabs"
    bpx_price = await get_bpx_price()
    if not bpx_price or bpx_price <= 0:
        print(f"[Blokpax] Warning: Invalid BPX price ({bpx_price}), using fallback")
        bpx_price = 0.002

    listings_processed = 0
    listings_matched = 0
    listings_saved = 0

    print("[Blokpax] Scraping preslab listings...")

    # Use existing scrape_all_listings function
    all_listings = await scrape_all_listings(slug)

    # Need to fetch asset details to get names (listings only have IDs)
    # Batch fetch asset details
    async with httpx.AsyncClient() as client:
        for listing in all_listings:
            try:
                # Fetch asset details
                url = f"{BLOKPAX_API_BASE}/storefront/{slug}/asset/{listing.asset_id}"
                response = await client.get(url, timeout=15.0)
                if response.status_code != 200:
                    continue

                data = response.json()
                asset_data = data.get("data", {})
                asset_name = asset_data.get("name", "")

                listings_processed += 1

                # Parse the preslab name
                parsed = parse_preslab_name(asset_name)
                if not parsed:
                    continue

                # Find matching card
                card_match = find_matching_card(parsed.card_name, session)
                if not card_match:
                    continue

                listings_matched += 1

                if not save_to_db:
                    await asyncio.sleep(0.1)
                    continue

                # Check if we already have this listing
                existing = session.exec(
                    select(MarketPrice).where(
                        MarketPrice.external_id == listing.listing_id,
                        MarketPrice.platform == "blokpax",
                        MarketPrice.listing_type == "active",
                    )
                ).first()

                if existing:
                    # Update price if changed
                    if existing.price != round(listing.price_usd, 2):
                        existing.price = round(listing.price_usd, 2)
                        existing.scraped_at = datetime.now(timezone.utc)
                        session.add(existing)
                    continue

                # Extract traits
                traits = []
                for attr in asset_data.get("attributes", []):
                    traits.append({"trait_type": attr.get("trait_type", ""), "value": attr.get("value", "")})

                # Create MarketPrice record for active listing
                mp = MarketPrice(
                    card_id=card_match["id"],
                    title=asset_name,
                    price=round(listing.price_usd, 2),
                    listing_type="active",
                    treatment=parsed.treatment,
                    grading=parsed.grading,
                    external_id=listing.listing_id,
                    platform="blokpax",
                    traits=traits if traits else None,
                    seller_name=listing.seller_address[:20] if listing.seller_address else None,
                    listed_at=listing.created_at,
                    scraped_at=datetime.now(timezone.utc),
                )

                session.add(mp)
                listings_saved += 1

                await asyncio.sleep(0.1)

            except Exception as e:
                print(f"[Blokpax] Error processing listing {listing.listing_id}: {e}")
                continue

    if save_to_db:
        session.commit()

    print(
        f"[Blokpax] Preslab listings: {listings_processed} processed, {listings_matched} matched, {listings_saved} saved"
    )
    return listings_processed, listings_matched, listings_saved
