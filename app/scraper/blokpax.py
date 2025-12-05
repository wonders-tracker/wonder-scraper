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
        page = 1
        total_pages = 1
        total_assets = 0

        # Use perPage=5 if the probe found floor_listing data, otherwise use 100 for speed
        per_page = 5 if use_small_pages else 100

        if use_small_pages:
            print(f"  Using small page mode (perPage=5) - API quirk requires this for floor_listing")
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

                    if page == 1:
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
                                    asset_name = a.get("name", "Unknown")
                                    all_listings.append(BlokpaxListing(
                                        listing_id=listing_id,
                                        asset_id=str(aid),
                                        price_bpx=bpx_to_float(raw_price),
                                        price_usd=bpx_to_usd(raw_price, bpx_price),
                                        quantity=floor_listing.get("quantity", 1),
                                        seller_address=floor_listing.get("seller", {}).get("address", "") if isinstance(floor_listing.get("seller"), dict) else "",
                                        created_at=_parse_datetime(floor_listing.get("created_at"))
                                    ))

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
            print(f"  No assets found in bulk endpoint")
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
                                found_listings.append(BlokpaxListing(
                                    listing_id=listing_id,
                                    asset_id=str(asset_id),
                                    price_bpx=bpx_to_float(raw_price),
                                    price_usd=bpx_to_usd(raw_price, bpx_price),
                                    quantity=listing.get("quantity", 1),
                                    seller_address=listing.get("owner", {}).get("username", ""),
                                    created_at=_parse_datetime(listing.get("created_at"))
                                ))

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
            print(f"  Strategy: Missing ID probe (sequential IDs detected)")

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
            print(f"  Strategy: Full scan (non-sequential IDs detected)")
            ids_to_check = all_asset_ids

        # Step 4: Probe assets in concurrent batches
        checked = 0
        total_to_check = len(ids_to_check)

        for i in range(0, total_to_check, concurrency):
            batch = ids_to_check[i:i + concurrency]
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
