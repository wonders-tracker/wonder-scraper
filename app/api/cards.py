import hashlib
import json
import threading
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

from cachetools import TTLCache
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session, desc, func, select

from app.core.config import settings
from app.core.typing import col, ensure_int
from app.db import get_session
from app.models.card import Card, Rarity
from app.models.market import MarketPrice, MarketSnapshot
from app.schemas import CardListItem, CardOut, MarketPriceOut, MarketSnapshotOut
from app.services.floor_price import get_floor_price_service
from app.services.order_book import get_order_book_analyzer
from app.services.pricing import FMP_AVAILABLE, FairMarketPriceService

router = APIRouter()

# Thread-safe LRU cache with TTL
_cache = TTLCache(maxsize=settings.CARDS_CACHE_MAXSIZE, ttl=settings.CARDS_CACHE_TTL_SECONDS)
_cache_lock = threading.Lock()


def get_cache_key(endpoint: str, **params) -> str:
    """Generate cache key from endpoint and params."""
    param_str = json.dumps(params, sort_keys=True)
    return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()


def get_cached(key: str) -> Optional[Any]:
    """Get cached response if not expired (thread-safe)."""
    with _cache_lock:
        return _cache.get(key)


def set_cache(key: str, value: Any):
    """Set cache entry (thread-safe). TTL managed by TTLCache."""
    with _cache_lock:
        _cache[key] = value


def normalize_floor_cutoff(days: int = 30) -> datetime:
    """
    Get a normalized cutoff time for floor price calculations.

    Rounds down to the nearest 5-minute boundary to ensure consistency
    between list and detail endpoints within the same cache window.
    This prevents floor price mismatches due to microsecond timing differences.
    """
    now = datetime.now(timezone.utc)
    # Round down to nearest 5 minutes (matches cache TTL)
    rounded = now.replace(second=0, microsecond=0)
    rounded = rounded.replace(minute=(rounded.minute // 5) * 5)
    return rounded - timedelta(days=days)


@router.get("/")
def read_cards(
    session: Session = Depends(get_session),
    skip: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(
        default=settings.CARDS_DEFAULT_LIMIT,
        ge=1,
        le=settings.CARDS_MAX_LIMIT,
        description=f"Items per page (max {settings.CARDS_MAX_LIMIT})",
    ),
    search: Optional[str] = None,
    time_period: Optional[str] = Query(default="7d", pattern="^(24h|7d|30d|90d|all)$"),
    product_type: Optional[str] = Query(default=None, description="Filter by product type (e.g., Single, Box, Pack)"),
    platform: Optional[str] = Query(default=None, description="Filter by platform (ebay, blokpax)"),
    include_total: bool = Query(default=False, description="Include total count (slower)"),
    slim: bool = Query(default=False, description="Return lightweight payload (~50% smaller)"),
) -> Any:
    """
    Retrieve cards with latest market data - OPTIMIZED with caching.
    Single batch query instead of N+1 + 5-minute cache.
    Returns paginated response with {items, total?, hasMore} when include_total=true.
    Use slim=true for ~50% smaller payload (recommended for list views).
    """
    # Check cache first (v15 = platform filter support)
    cache_key = get_cache_key(
        "cards_v15",
        skip=skip,
        limit=limit,
        search=search or "",
        time_period=time_period,
        product_type=product_type or "",
        platform=platform or "",
        include_total=include_total,
        slim=slim,
    )
    cached = get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    # Calculate time cutoff
    time_cutoffs = {
        "24h": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None,
    }
    cutoff_delta = time_cutoffs.get(time_period)
    cutoff_time = datetime.now(timezone.utc) - cutoff_delta if cutoff_delta else None

    # Build base query with filters
    base_query = select(Card)
    if search:
        base_query = base_query.where(col(Card.name).ilike(f"%{search}%"))
    if product_type:
        base_query = base_query.where(col(Card.product_type).ilike(product_type))

    # Get total count if requested (adds ~10ms overhead)
    total = None
    if include_total:
        count_query = select(func.count()).select_from(base_query.subquery())
        total = session.execute(count_query).scalar_one()

    # Fetch paginated cards with deterministic ordering
    card_query = base_query.order_by(col(Card.name), col(Card.id)).offset(skip).limit(limit)
    cards = session.execute(card_query).scalars().all()

    if not cards:
        return []

    # Batch fetch ALL snapshots for these cards in ONE query
    card_ids = [c.id for c in cards]
    snapshot_query = select(MarketSnapshot).where(col(MarketSnapshot.card_id).in_(card_ids))
    if cutoff_time:
        snapshot_query = snapshot_query.where(col(MarketSnapshot.timestamp) >= cutoff_time)
    snapshot_query = snapshot_query.order_by(col(MarketSnapshot.card_id), desc(MarketSnapshot.timestamp))
    all_snapshots = session.execute(snapshot_query).scalars().all()

    # Group snapshots by card_id
    snapshots_by_card = {}
    for snap in all_snapshots:
        if snap.card_id not in snapshots_by_card:
            snapshots_by_card[snap.card_id] = []
        if len(snapshots_by_card[snap.card_id]) < 2:  # Keep latest and oldest in window logic
            snapshots_by_card[snap.card_id].append(snap)
        # Actually, since we need OLDEST in window for meaningful delta, we should probably keep first and last
        # But `snapshots_by_card` is populated from `all_snapshots` which is ordered DESC by timestamp
        # So we want index 0 (newest) and index -1 (oldest in filtered set)
        # The loop currently just appends. Let's fix this logic:
        # We will just group ALL valid snapshots then pick first/last after loop

    # Correct logic: Group all then pick
    snapshots_by_card = {}
    for snap in all_snapshots:
        if snap.card_id not in snapshots_by_card:
            snapshots_by_card[snap.card_id] = []
        snapshots_by_card[snap.card_id].append(snap)

    # Batch fetch rarities
    rarities = session.execute(select(Rarity)).scalars().all()
    rarity_map = {r.id: r.name for r in rarities}

    # Batch fetch actual LAST SALE price (Postgres DISTINCT ON)
    last_sale_map = {}
    vwap_map = {}
    active_stats_map = {}  # Computed from MarketPrice for fresh lowest_ask/inventory
    floor_price_map = {}  # Floor price (avg of 4 lowest sales) - cheapest variant
    floor_by_variant_map = {}  # Floor price per variant {card_id: {variant: price}}
    lowest_ask_by_variant_map = {}  # Lowest ask per variant {card_id: {variant: price}}
    volume_map = {}  # Volume filtered by time period

    # Build platform filter clause for SQL queries
    platform_clause = "AND platform = :platform" if platform else ""
    query_params_base = {"card_ids": card_ids}
    if platform:
        query_params_base["platform"] = platform

    if card_ids:
        try:
            from sqlalchemy import text

            # Use parameterized queries to prevent SQL injection
            # PostgreSQL ANY() syntax for array parameters
            # Use COALESCE(sold_date, scraped_at) to include sales with NULL sold_date
            query = text(f"""
                SELECT DISTINCT ON (card_id) card_id, price, treatment
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                AND listing_type = 'sold'
                {platform_clause}
                ORDER BY card_id, COALESCE(sold_date, scraped_at) DESC
            """)
            results = session.execute(query, query_params_base).all()
            last_sale_map = {row[0]: {"price": row[1], "treatment": row[2]} for row in results}

            # Calculate AVG price (commonly called VWAP for single-item sales)
            # Use COALESCE(sold_date, scraped_at) for consistent time filtering
            if cutoff_time:
                vwap_query = text(f"""
                    SELECT card_id, AVG(price) as vwap
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    AND COALESCE(sold_date, scraped_at) >= :cutoff_time
                    {platform_clause}
                    GROUP BY card_id
                """)
                vwap_params = {**query_params_base, "cutoff_time": cutoff_time}
                vwap_results = session.execute(vwap_query, vwap_params).all()
            else:
                vwap_query = text(f"""
                    SELECT card_id, AVG(price) as vwap
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    {platform_clause}
                    GROUP BY card_id
                """)
                vwap_results = session.execute(vwap_query, query_params_base).all()
            vwap_map = {row[0]: round(float(row[1]), 2) if row[1] else None for row in vwap_results}

            # Fetch LIVE active listing stats (lowest_ask, inventory) from MarketPrice
            # This ensures fresh data even when snapshots are stale
            active_stats_query = text(f"""
                SELECT card_id, MIN(price) as lowest_ask, COUNT(*) as inventory
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                AND listing_type = 'active'
                {platform_clause}
                GROUP BY card_id
            """)
            active_stats_results = session.execute(active_stats_query, query_params_base).all()
            active_stats_map = {row[0]: {"lowest_ask": row[1], "inventory": row[2]} for row in active_stats_results}

            # Batch calculate floor prices per variant (avg of up to 4 lowest sales)
            # Unified approach: Singles use 'treatment', Sealed uses 'product_subtype'
            # Use COALESCE(sold_date, scraped_at) as fallback when sold_date is NULL
            platform_filter_sql = f"AND platform = '{platform}'" if platform else ""

            # Query returns floor price for EACH variant (treatment or product_subtype)
            # Singles: variant = treatment (Classic Paper, Classic Foil, etc.)
            # Sealed: variant = product_subtype (Silver Pack, Collector Booster Pack, etc.)
            floor_by_variant_query = text(f"""
                SELECT card_id, variant, AVG(price) as floor_price
                FROM (
                    SELECT card_id,
                           CASE
                               WHEN product_subtype IS NOT NULL AND product_subtype != ''
                               THEN product_subtype
                               ELSE treatment
                           END as variant,
                           price,
                           ROW_NUMBER() OVER (
                               PARTITION BY card_id,
                                   CASE
                                       WHEN product_subtype IS NOT NULL AND product_subtype != ''
                                       THEN product_subtype
                                       ELSE treatment
                                   END
                               ORDER BY price ASC
                           ) as rn
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                      AND listing_type = 'sold'
                      AND COALESCE(sold_date, scraped_at) >= :cutoff
                      {platform_filter_sql}
                ) ranked
                WHERE rn <= 4
                GROUP BY card_id, variant
                ORDER BY card_id, floor_price ASC
            """)

            # Query for lowest ask per variant (active listings)
            # Note: Must GROUP BY the full CASE expression, not the alias
            lowest_ask_by_variant_query = text(f"""
                SELECT card_id,
                       CASE
                           WHEN product_subtype IS NOT NULL AND product_subtype != ''
                           THEN product_subtype
                           ELSE treatment
                       END as variant,
                       MIN(price) as lowest_ask
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                  AND listing_type = 'active'
                  {platform_filter_sql}
                GROUP BY card_id,
                         CASE
                             WHEN product_subtype IS NOT NULL AND product_subtype != ''
                             THEN product_subtype
                             ELSE treatment
                         END
                ORDER BY card_id, lowest_ask ASC
            """)

            # First try 30 days (use normalized cutoff for consistency with detail endpoint)
            floor_cutoff_30d = normalize_floor_cutoff(days=30)
            floor_variant_results = session.execute(
                floor_by_variant_query, {"card_ids": card_ids, "cutoff": floor_cutoff_30d}
            ).all()

            # Build floor_by_variant_map and floor_price_map (cheapest variant)
            for row in floor_variant_results:
                card_id, variant, floor_price = row[0], row[1], round(float(row[2]), 2)
                if card_id not in floor_by_variant_map:
                    floor_by_variant_map[card_id] = {}
                floor_by_variant_map[card_id][variant] = floor_price
                # floor_price_map stores the cheapest variant's floor
                if card_id not in floor_price_map or floor_price < floor_price_map[card_id]:
                    floor_price_map[card_id] = floor_price

            # Fallback: 90 days for cards still missing
            missing_floor_ids = [cid for cid in card_ids if cid not in floor_price_map]
            if missing_floor_ids:
                floor_cutoff_90d = normalize_floor_cutoff(days=90)
                floor_variant_results_90d = session.execute(
                    floor_by_variant_query, {"card_ids": missing_floor_ids, "cutoff": floor_cutoff_90d}
                ).all()
                for row in floor_variant_results_90d:
                    card_id, variant, floor_price = row[0], row[1], round(float(row[2]), 2)
                    if card_id not in floor_by_variant_map:
                        floor_by_variant_map[card_id] = {}
                    floor_by_variant_map[card_id][variant] = floor_price
                    if card_id not in floor_price_map or floor_price < floor_price_map[card_id]:
                        floor_price_map[card_id] = floor_price

            # Fetch lowest ask by variant (active listings)
            lowest_ask_variant_results = session.execute(lowest_ask_by_variant_query, {"card_ids": card_ids}).all()
            for row in lowest_ask_variant_results:
                card_id, variant, lowest_ask = row[0], row[1], round(float(row[2]), 2)
                if card_id not in lowest_ask_by_variant_map:
                    lowest_ask_by_variant_map[card_id] = {}
                lowest_ask_by_variant_map[card_id][variant] = lowest_ask

            # Calculate volume filtered by time period
            # Use COALESCE(sold_date, scraped_at) for consistent time filtering
            if cutoff_time:
                volume_query = text(f"""
                    SELECT card_id, COUNT(*) as volume
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    AND COALESCE(sold_date, scraped_at) >= :cutoff_time
                    {platform_clause}
                    GROUP BY card_id
                """)
                vol_params = {**query_params_base, "cutoff_time": cutoff_time}
                volume_results = session.execute(volume_query, vol_params).all()
            else:
                # All time
                volume_query = text(f"""
                    SELECT card_id, COUNT(*) as volume
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    {platform_clause}
                    GROUP BY card_id
                """)
                volume_results = session.execute(volume_query, query_params_base).all()
            volume_map = {row[0]: row[1] for row in volume_results}

            # Fetch average price with conditional rolling window
            # Try 30d first, fallback to 90d, then all-time
            # Delta = how does latest sale compare to historical average?
            # Use COALESCE(sold_date, scraped_at) for consistent time filtering
            avg_price_map = {}

            for days, label in [(30, "30d"), (90, "90d"), (None, "all")]:
                if days:
                    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                    avg_query = text(f"""
                        SELECT card_id, AVG(price) as avg_price
                        FROM marketprice
                        WHERE card_id = ANY(:card_ids)
                        AND listing_type = 'sold'
                        AND COALESCE(sold_date, scraped_at) >= :cutoff
                        {platform_clause}
                        GROUP BY card_id
                    """)
                    avg_params = {**query_params_base, "cutoff": cutoff}
                    results = session.execute(avg_query, avg_params).all()
                else:
                    # All-time average
                    avg_query = text(f"""
                        SELECT card_id, AVG(price) as avg_price
                        FROM marketprice
                        WHERE card_id = ANY(:card_ids)
                        AND listing_type = 'sold'
                        {platform_clause}
                        GROUP BY card_id
                    """)
                    results = session.execute(avg_query, query_params_base).all()

                # Only add cards not already in map (prefer shorter windows)
                for row in results:
                    if row[0] not in avg_price_map:
                        avg_price_map[row[0]] = row[1]

        except Exception as e:
            print(f"Error fetching sales data: {e}")

    # FMP is calculated on detail page only (too expensive for batch)
    # List view uses median price (vwap) as "Fair Price"

    # Build results
    results = []
    for card in cards:
        card_snaps = snapshots_by_card.get(card.id, [])
        latest_snap = card_snaps[0] if card_snaps else None

        # Use actual last sale if available, otherwise fallback to avg
        last_sale_data = last_sale_map.get(card.id)
        last_price = last_sale_data["price"] if last_sale_data else None
        last_treatment = last_sale_data["treatment"] if last_sale_data else None

        if last_price is None and latest_snap:
            last_price = latest_snap.avg_price

        # Get VWAP (true volume-weighted average price)
        card_vwap = vwap_map.get(card.id)

        # Get LIVE active stats from MarketPrice (preferred), fallback to snapshot only if None
        live_active = active_stats_map.get(card.id, {})
        live_lowest = live_active.get("lowest_ask")
        live_inv = live_active.get("inventory")
        lowest_ask = live_lowest if live_lowest is not None else (latest_snap.lowest_ask if latest_snap else None)
        inventory = live_inv if live_inv is not None else (latest_snap.inventory if latest_snap else 0)

        # Get floor price from batch calculation (cheapest variant)
        card_floor_price = floor_price_map.get(card.id)

        # Get floor_by_variant and lowest_ask_by_variant
        card_floor_by_variant = floor_by_variant_map.get(card.id)
        card_lowest_ask_by_variant = lowest_ask_by_variant_map.get(card.id)

        # Get volume filtered by time period
        card_volume = volume_map.get(card.id, 0)

        # Price Delta: Last sale vs rolling average (%)
        price_delta = 0.0
        avg_price = avg_price_map.get(card.id)
        if last_price and avg_price and avg_price > 0:
            price_delta = round(((last_price - avg_price) / avg_price) * 100, 1)

        # Floor Delta: Last sale vs floor price (%)
        floor_delta = 0.0
        if last_price and card_floor_price and card_floor_price > 0:
            floor_delta = round(((last_price - card_floor_price) / card_floor_price) * 100, 1)

        c_out = CardOut(
            id=ensure_int(card.id),
            name=card.name,
            set_name=card.set_name,
            rarity_id=ensure_int(card.rarity_id),
            rarity_name=rarity_map.get(card.rarity_id or 0, "Unknown"),
            product_type=card.product_type if hasattr(card, "product_type") else "Single",
            # Prices
            floor_price=card_floor_price,
            floor_by_variant=card_floor_by_variant,
            vwap=card_vwap,
            latest_price=last_price,
            lowest_ask=lowest_ask,
            lowest_ask_by_variant=card_lowest_ask_by_variant,
            max_price=latest_snap.max_price if latest_snap else None,
            avg_price=latest_snap.avg_price if latest_snap else None,
            fair_market_price=None,  # FMP only on detail page
            # Volume & Inventory
            volume=card_volume,
            inventory=inventory,
            # Deltas
            price_delta=price_delta,
            floor_delta=floor_delta,
            # Metadata
            last_treatment=last_treatment,
            last_updated=latest_snap.timestamp if latest_snap else None,
            image_url=card.image_url if hasattr(card, "image_url") else None,
            # Carde.io data
            card_type=card.card_type if hasattr(card, "card_type") else None,
            orbital=card.orbital if hasattr(card, "orbital") else None,
            orbital_color=card.orbital_color if hasattr(card, "orbital_color") else None,
            card_number=card.card_number if hasattr(card, "card_number") else None,
            cardeio_image_url=card.cardeio_image_url if hasattr(card, "cardeio_image_url") else None,
            # Deprecated fields (backwards compat)
            volume_30d=card_volume,
            price_delta_24h=price_delta,
            last_sale_diff=floor_delta,
            last_sale_treatment=last_treatment,
        )
        results.append(c_out)

    # Convert to dict for caching - use slim schema if requested
    if slim:
        results_dict = [
            CardListItem(
                id=r.id,
                name=r.name,
                slug=r.slug,
                set_name=r.set_name,
                rarity_name=r.rarity_name,
                product_type=r.product_type,
                floor_price=r.floor_price,
                latest_price=r.latest_price,
                lowest_ask=r.lowest_ask,
                max_price=r.max_price,
                volume=r.volume,
                inventory=r.inventory,
                price_delta=r.price_delta,
                last_treatment=r.last_treatment,
                image_url=r.image_url,
                orbital=r.orbital,
                orbital_color=r.orbital_color,
            ).model_dump(mode="json")
            for r in results
        ]
    else:
        results_dict = [r.model_dump(mode="json") for r in results]

    # Build response with pagination metadata
    if include_total:
        response_data = {
            "items": results_dict,
            "total": total,
            "skip": skip,
            "limit": limit,
            "hasMore": skip + len(results_dict) < total if total else False,
        }
    else:
        # Backwards compatible: return array directly when no pagination requested
        response_data = results_dict

    set_cache(cache_key, response_data)

    return JSONResponse(content=response_data, headers={"X-Cache": "MISS"})


def get_card_by_id_or_slug(session: Session, card_identifier: str) -> Card:
    """Resolve card by ID (numeric) or slug (string)."""
    # Try numeric ID first
    if card_identifier.isdigit():
        card = session.get(Card, int(card_identifier))
        if card:
            return card
    # Try slug lookup
    card = session.execute(select(Card).where(Card.slug == card_identifier)).scalars().first()
    if card:
        return card
    raise HTTPException(status_code=404, detail="Card not found")


@router.get("/{card_id}", response_model=CardOut)
def read_card(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
) -> Any:
    # Check cache
    cache_key = get_cache_key("card", card_id=card_id)
    cached = get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    card = get_card_by_id_or_slug(session, card_id)

    # Fetch rarity name
    rarity_name = "Unknown"
    if card.rarity_id:
        rarity = session.get(Rarity, card.rarity_id)
        if rarity:
            rarity_name = rarity.name

    # Fetch latest 2 snapshots to calculate delta
    # We want to find OLDEST snapshot in the window for meaningful delta
    # Since this is single card view, let's just get all recent ones and pick
    # Or simpler: Get latest and one from 24h ago
    stmt = (
        select(MarketSnapshot)
        .where(MarketSnapshot.card_id == card.id)
        .order_by(desc(MarketSnapshot.timestamp), desc(MarketSnapshot.id))
        .limit(50)
    )
    snapshots = session.execute(stmt).scalars().all()

    latest_snap = snapshots[0] if snapshots else None

    # Fetch actual last sale using COALESCE for proper date ordering
    from sqlalchemy import text as sql_text

    last_sale_query = sql_text("""
        SELECT id, price, treatment, sold_date, scraped_at
        FROM marketprice
        WHERE card_id = :card_id AND listing_type = 'sold'
        ORDER BY COALESCE(sold_date, scraped_at) DESC
        LIMIT 1
    """)
    last_sale_result = session.execute(last_sale_query, {"card_id": card.id}).first()

    real_price = last_sale_result[1] if last_sale_result else (latest_snap.avg_price if latest_snap else None)
    real_treatment = last_sale_result[2] if last_sale_result else None

    # Calculate MEDIAN price and 30-day volume for single card
    vwap = None
    volume_30d = 0
    try:
        from sqlalchemy import text

        cutoff_30d = datetime.now(timezone.utc) - timedelta(days=30)

        # Get AVG price (consistent with list view VWAP calculation)
        # Use COALESCE(sold_date, scraped_at) for consistent time filtering
        avg_q = text("""
            SELECT AVG(price) FROM marketprice
            WHERE card_id = :cid AND listing_type = 'sold'
            AND COALESCE(sold_date, scraped_at) >= :cutoff
        """)
        avg_res = session.execute(avg_q, {"cid": card.id, "cutoff": cutoff_30d}).first()
        if avg_res:
            vwap = avg_res[0]

        # Get volume separately
        vol_q = text("""
            SELECT COUNT(*) FROM marketprice
            WHERE card_id = :cid AND listing_type = 'sold'
            AND COALESCE(sold_date, scraped_at) >= :cutoff
        """)
        vol_res = session.execute(vol_q, {"cid": card.id, "cutoff": cutoff_30d}).first()
        if vol_res:
            volume_30d = vol_res[0] or 0

    except Exception:
        pass

    # Fetch LIVE active stats from MarketPrice table (always fresh)
    live_lowest_ask = None
    live_inventory = 0
    try:
        active_stats_q = text("""
            SELECT MIN(price) as lowest_ask, COUNT(*) as inventory
            FROM marketprice
            WHERE card_id = :cid AND listing_type = 'active'
        """)
        active_res = session.execute(active_stats_q, {"cid": card.id}).first()
        if active_res:
            live_lowest_ask = active_res[0]
            live_inventory = active_res[1] or 0
    except Exception:
        pass

    # Use live data from MarketPrice table (preferred), fallback to snapshot only if None
    # Note: Use explicit None check since 0 is a valid value (no active listings)
    lowest_ask = live_lowest_ask if live_lowest_ask is not None else (latest_snap.lowest_ask if latest_snap else None)
    inventory = live_inventory if live_inventory is not None else (latest_snap.inventory if latest_snap else 0)

    # Price vs Avg: Rolling window - try 30d, 90d, then all-time
    # Positive = sold above average (hot/premium)
    # Negative = sold below average (deal/declining)
    price_delta = 0.0
    avg_price = None
    try:
        for days in [30, 90, None]:
            if days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=days)
                avg_q = text("""
                    SELECT AVG(price) FROM marketprice
                    WHERE card_id = :cid AND listing_type = 'sold'
                    AND COALESCE(sold_date, scraped_at) >= :cutoff
                """)
                avg_res = session.execute(avg_q, {"cid": card.id, "cutoff": cutoff}).first()
            else:
                avg_q = text("""
                    SELECT AVG(price) FROM marketprice
                    WHERE card_id = :cid AND listing_type = 'sold'
                """)
                avg_res = session.execute(avg_q, {"cid": card.id}).first()

            if avg_res and avg_res[0]:
                avg_price = avg_res[0]
                break
    except Exception:
        pass
    if real_price and avg_price and avg_price > 0:
        price_delta = ((real_price - avg_price) / avg_price) * 100

    # Last Sale vs Floor: How does last sale compare to current floor?
    # Positive = sold above floor (premium)
    # Negative = sold below floor (deal)
    sale_delta = 0.0
    if real_price and lowest_ask and lowest_ask > 0:
        sale_delta = ((real_price - lowest_ask) / lowest_ask) * 100

    # Calculate Fair Market Price and Floor Price
    fair_market_price = None
    floor_price = None
    floor_by_variant = None
    lowest_ask_by_variant = None
    product_type = card.product_type if hasattr(card, "product_type") else "Single"
    try:
        pricing_service = FairMarketPriceService(session)
        fmp_result = pricing_service.calculate_fmp(
            card_id=ensure_int(card.id), set_name=card.set_name, rarity_name=rarity_name, product_type=product_type
        )
        fair_market_price = fmp_result.get("fair_market_price")
        floor_price = fmp_result.get("floor_price")
    except Exception as e:
        print(f"Error calculating FMP for card {card.id}: {e}")

    # Calculate floor_by_variant and lowest_ask_by_variant for single card
    try:
        floor_cutoff = normalize_floor_cutoff(days=30)

        # Floor by variant query
        floor_variant_query = text("""
            SELECT variant, AVG(price) as floor_price
            FROM (
                SELECT
                    CASE
                        WHEN product_subtype IS NOT NULL AND product_subtype != ''
                        THEN product_subtype
                        ELSE treatment
                    END as variant,
                    price,
                    ROW_NUMBER() OVER (
                        PARTITION BY
                            CASE
                                WHEN product_subtype IS NOT NULL AND product_subtype != ''
                                THEN product_subtype
                                ELSE treatment
                            END
                        ORDER BY price ASC
                    ) as rn
                FROM marketprice
                WHERE card_id = :card_id
                  AND listing_type = 'sold'
                  AND COALESCE(sold_date, scraped_at) >= :cutoff
            ) ranked
            WHERE rn <= 4
            GROUP BY variant
            ORDER BY floor_price ASC
        """)
        floor_variant_results = session.execute(floor_variant_query, {"card_id": card.id, "cutoff": floor_cutoff}).all()

        if floor_variant_results:
            floor_by_variant = {row[0]: round(float(row[1]), 2) for row in floor_variant_results}
            # Always use SQL-calculated floor_price for consistency with list endpoint
            # (FMP service's floor_price uses different time anchor, causing mismatches)
            if floor_by_variant:
                floor_price = min(floor_by_variant.values())

        # Fallback: 90 days if no 30-day data (matches list endpoint behavior)
        if not floor_by_variant:
            floor_cutoff_90d = normalize_floor_cutoff(days=90)
            floor_variant_results_90d = session.execute(
                floor_variant_query, {"card_id": card.id, "cutoff": floor_cutoff_90d}
            ).all()
            if floor_variant_results_90d:
                floor_by_variant = {row[0]: round(float(row[1]), 2) for row in floor_variant_results_90d}
                if floor_by_variant:
                    floor_price = min(floor_by_variant.values())

        # Lowest ask by variant query
        # Note: Must GROUP BY the full CASE expression, not the alias
        lowest_ask_variant_query = text("""
            SELECT
                CASE
                    WHEN product_subtype IS NOT NULL AND product_subtype != ''
                    THEN product_subtype
                    ELSE treatment
                END as variant,
                MIN(price) as lowest_ask
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'active'
            GROUP BY
                CASE
                    WHEN product_subtype IS NOT NULL AND product_subtype != ''
                    THEN product_subtype
                    ELSE treatment
                END
            ORDER BY lowest_ask ASC
        """)
        lowest_ask_variant_results = session.execute(lowest_ask_variant_query, {"card_id": card.id}).all()

        if lowest_ask_variant_results:
            lowest_ask_by_variant = {row[0]: round(float(row[1]), 2) for row in lowest_ask_variant_results}
    except Exception as e:
        print(f"Error calculating variant prices for card {card.id}: {e}")

    c_out = CardOut(
        id=ensure_int(card.id),
        slug=card.slug,
        name=card.name,
        set_name=card.set_name,
        rarity_id=ensure_int(card.rarity_id),
        rarity_name=rarity_name,
        latest_price=real_price,
        volume_30d=volume_30d,
        price_delta_24h=price_delta,  # Sale price change (recent vs oldest in period)
        last_sale_diff=sale_delta,  # Last sale vs current floor
        last_sale_treatment=real_treatment,
        lowest_ask=lowest_ask,
        lowest_ask_by_variant=lowest_ask_by_variant,
        inventory=inventory,
        product_type=card.product_type if hasattr(card, "product_type") else "Single",
        max_price=latest_snap.max_price if latest_snap else None,
        avg_price=latest_snap.avg_price if latest_snap else None,
        vwap=vwap if vwap else (latest_snap.avg_price if latest_snap else None),
        last_updated=latest_snap.timestamp if latest_snap else None,
        fair_market_price=fair_market_price,
        floor_price=floor_price,
        floor_by_variant=floor_by_variant,
        # Carde.io data
        image_url=card.image_url if hasattr(card, "image_url") else None,
        card_type=card.card_type if hasattr(card, "card_type") else None,
        orbital=card.orbital if hasattr(card, "orbital") else None,
        orbital_color=card.orbital_color if hasattr(card, "orbital_color") else None,
        card_number=card.card_number if hasattr(card, "card_number") else None,
        cardeio_image_url=card.cardeio_image_url if hasattr(card, "cardeio_image_url") else None,
    )

    # Cache result
    result_dict = c_out.model_dump(mode="json")
    set_cache(cache_key, result_dict)

    return JSONResponse(content=result_dict, headers={"X-Cache": "MISS"})


@router.get("/{card_id}/market", response_model=Optional[MarketSnapshotOut])
def read_market_data(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
) -> Any:
    """
    Get latest market snapshot for a card.
    """
    card = get_card_by_id_or_slug(session, card_id)
    statement = (
        select(MarketSnapshot)
        .where(MarketSnapshot.card_id == card.id)
        .order_by(col(MarketSnapshot.timestamp).desc(), col(MarketSnapshot.id).desc())
    )
    snapshot = session.execute(statement).scalars().first()

    if not snapshot:
        raise HTTPException(status_code=404, detail="Market data not found for this card")

    return MarketSnapshotOut.model_validate(snapshot)


@router.get("/{card_id}/history")
def read_sales_history(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
    limit: int = Query(default=50, ge=1, le=200, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
    paginated: bool = Query(default=False, description="Return paginated response with metadata"),
) -> Any:
    """
    Get sales history (individual sold listings).
    Uses COALESCE(sold_date, scraped_at) for proper date ordering.

    By default returns array of items (backwards compatible).
    Use paginated=true to get {items, total, hasMore} format.
    """
    card = get_card_by_id_or_slug(session, card_id)

    # Fetch results
    statement = (
        select(MarketPrice)
        .where(MarketPrice.card_id == card.id, MarketPrice.listing_type == "sold")
        .order_by(desc(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at)))
        .offset(offset)
        .limit(limit)
    )
    prices = session.execute(statement).scalars().all()

    # Convert to output schema
    prices_out = [MarketPriceOut.model_validate(p) for p in prices]

    # Return array by default (backwards compatible)
    if not paginated:
        return prices_out

    # Get total count only when paginated (avoids extra query)
    count_stmt = select(func.count(MarketPrice.id)).where(
        MarketPrice.card_id == card.id, MarketPrice.listing_type == "sold"
    )
    total = session.execute(count_stmt).scalar_one()

    return {
        "items": prices_out,
        "total": total,
        "offset": offset,
        "limit": limit,
        "hasMore": offset + len(prices_out) < total,
    }


@router.get("/{card_id}/active", response_model=List[MarketPriceOut])
def read_active_listings(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
    limit: int = 50,
) -> Any:
    """
    Get active listings for a card.
    """
    card = get_card_by_id_or_slug(session, card_id)
    statement = (
        select(MarketPrice)
        .where(MarketPrice.card_id == card.id, MarketPrice.listing_type == "active")
        .order_by(desc(MarketPrice.scraped_at))
        .limit(limit)
    )
    active = session.execute(statement).scalars().all()
    return [MarketPriceOut.model_validate(a) for a in active]


@router.get("/{card_id}/pricing")
def read_card_pricing(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
) -> Any:
    """
    Get FMP breakdown by treatment for a card.
    Returns FMP, floor, and price stats for each treatment variant.

    Note: FMP pricing is only available in SaaS mode.
    """
    if not FMP_AVAILABLE:
        raise HTTPException(
            status_code=403, detail="FMP pricing is not available in OSS mode. This feature requires SaaS access."
        )

    card = get_card_by_id_or_slug(session, card_id)

    # Fetch rarity name
    rarity_name = "Unknown"
    if card.rarity_id:
        rarity = session.get(Rarity, card.rarity_id)
        if rarity:
            rarity_name = rarity.name

    product_type = card.product_type if hasattr(card, "product_type") else "Single"
    pricing_service = FairMarketPriceService(session)

    # Get FMP breakdown by treatment/variant
    treatment_fmps = pricing_service.get_fmp_by_treatment(
        card_id=ensure_int(card.id), set_name=card.set_name, rarity_name=rarity_name, product_type=product_type
    )

    # Also get overall FMP and floor
    fmp_result = pricing_service.calculate_fmp(
        card_id=ensure_int(card.id), set_name=card.set_name, rarity_name=rarity_name, product_type=product_type
    )

    return {
        "card_id": card.id,
        "card_name": card.name,
        "product_type": product_type,
        "fair_market_price": fmp_result.get("fair_market_price"),
        "floor_price": fmp_result.get("floor_price"),
        "calculation_method": fmp_result.get("calculation_method"),  # 'formula' or 'median'
        "breakdown": fmp_result.get("breakdown"),  # None for non-Singles
        "by_treatment": treatment_fmps,
    }


@router.get("/{card_id}/order-book")
def read_card_order_book(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
    treatment: Optional[str] = Query(default=None, description="Filter by treatment (e.g., 'Classic Foil')"),
    days: int = Query(default=30, ge=1, le=90, description="Lookback window for active listings"),
) -> Any:
    """
    Get order book floor analysis for a card.

    Analyzes active listings to find the floor price based on order book depth.
    Returns the price bucket with most liquidity as the floor estimate.

    The algorithm:
    1. Fetches active listings (excluding bulk lots)
    2. Filters outliers using gap analysis (>2σ from mean gap)
    3. Creates adaptive price buckets (width = range/√n)
    4. Finds the deepest bucket (most listings)
    5. Returns the midpoint as floor estimate with confidence score

    Confidence is based on:
    - Depth ratio: How much of total liquidity is in the floor bucket
    - Freshness: Penalty for stale listings (>14 days old)

    Falls back to sales data if insufficient active listings (<3).
    """
    card = get_card_by_id_or_slug(session, card_id)

    analyzer = get_order_book_analyzer(session)
    result = analyzer.estimate_floor(
        card_id=ensure_int(card.id),
        treatment=treatment,
        days=days,
    )

    if not result:
        return {
            "card_id": card.id,
            "card_name": card.name,
            "treatment": treatment,
            "floor_estimate": None,
            "confidence": 0,
            "message": "Insufficient market data for floor estimation",
        }

    return {
        "card_id": card.id,
        "card_name": card.name,
        "treatment": treatment,
        **result.to_dict(),
    }


@router.get("/{card_id}/order-book/by-treatment")
def read_card_order_book_by_treatment(
    card_id: str,
    session: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=90, description="Lookback window for active listings"),
) -> Any:
    """
    Get order book floor analysis for each treatment variant.

    Returns floor price estimates for all common treatments (Classic Paper, Classic Foil, etc.)
    This is the OSS-compatible alternative to /pricing which requires FMP (SaaS).

    Useful for:
    - Comparing floor prices across treatments
    - Showing price breakdown in the UI when FMP is unavailable
    """
    card = get_card_by_id_or_slug(session, card_id)
    analyzer = get_order_book_analyzer(session)

    # Standard treatments for Singles
    treatments = [
        "Classic Paper",
        "Classic Foil",
        "Stonefoil",
        "Formless Foil",
        "Prerelease",
        "Promo",
        "OCM Serialized",
    ]

    results = []
    for treatment in treatments:
        result = analyzer.estimate_floor(
            card_id=ensure_int(card.id),
            treatment=treatment,
            days=days,
        )
        if result:
            results.append({
                "treatment": treatment,
                "floor_estimate": result.floor_estimate,
                "confidence": result.confidence,
                "total_listings": result.total_listings,
                "source": result.source,
            })
        else:
            results.append({
                "treatment": treatment,
                "floor_estimate": None,
                "confidence": 0,
                "total_listings": 0,
                "source": None,
            })

    # Also get overall floor (all treatments combined)
    overall = analyzer.estimate_floor(card_id=ensure_int(card.id), days=days)

    return {
        "card_id": card.id,
        "card_name": card.name,
        "overall_floor": overall.floor_estimate if overall else None,
        "overall_confidence": overall.confidence if overall else 0,
        "by_treatment": results,
    }


@router.get("/{card_id}/floor-price")
def read_card_floor_price(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
    treatment: Optional[str] = Query(default=None, description="Filter by treatment (e.g., 'Classic Foil')"),
    days: int = Query(default=30, ge=1, le=90, description="Initial lookback window (auto-expands to 90d if needed)"),
    include_blokpax: bool = Query(default=True, description="Include Blokpax sales in calculation"),
) -> Any:
    """
    Get hybrid floor price estimate for a card.

    Uses a decision tree that combines sales data and order book analysis:
    1. If >=4 sales in window: Return sales floor (avg of lowest 4) with HIGH confidence
    2. If order book confidence >30%: Return order book floor with mapped confidence
    3. If 2-3 sales: Return sales floor with LOW/MEDIUM confidence
    4. Auto-expands to 90 days if insufficient data in initial window
    5. Returns null if no data available

    Sources combined:
    - eBay sales (marketprice.platform='ebay')
    - OpenSea sales (marketprice.platform='opensea')
    - Blokpax sales (blokpaxsale table) when include_blokpax=True

    Response includes:
    - price: The floor price estimate (or null)
    - source: 'sales', 'order_book', or 'none'
    - confidence: 'high', 'medium', or 'low'
    - confidence_score: Raw 0.0-1.0 score
    - metadata: Source-specific details (sales_count, platforms, bucket_depth, etc.)
    """
    card = get_card_by_id_or_slug(session, card_id)

    service = get_floor_price_service(session)
    result = service.get_floor_price(
        card_id=ensure_int(card.id),
        treatment=treatment,
        days=days,
        include_blokpax=include_blokpax,
    )

    return {
        "card_id": card.id,
        "card_name": card.name,
        "treatment": treatment,
        **result.to_dict(),
    }


@router.get("/{card_id}/snapshots", response_model=List[MarketSnapshotOut])
def read_snapshot_history(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
    days: int = Query(default=90, ge=1, le=365, description="Number of days of history"),
    limit: int = Query(default=100, ge=1, le=500),
) -> Any:
    """
    Get snapshot history for a card (for price charts).
    Useful for OpenSea/NFT items that don't have individual sales records.
    Returns aggregate market data over time.
    """
    card = get_card_by_id_or_slug(session, card_id)

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    statement = (
        select(MarketSnapshot)
        .where(MarketSnapshot.card_id == card.id, col(MarketSnapshot.timestamp) >= cutoff)
        .order_by(desc(MarketSnapshot.timestamp), desc(MarketSnapshot.id))
        .limit(limit)
    )

    snapshots = session.execute(statement).scalars().all()
    return [MarketSnapshotOut.model_validate(s) for s in snapshots]
