from typing import Any, Optional
import threading
import time
import logging
from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session, select, desc
from datetime import datetime, timedelta, timezone
from cachetools import TTLCache

from app.core.typing import col
from app.db import get_session
from app.models.card import Card
from app.models.market import MarketPrice

router = APIRouter()
logger = logging.getLogger(__name__)

# Thread-safe cache with TTL (5 min for market data - balance freshness vs performance)
_market_cache = TTLCache(maxsize=100, ttl=300)
_market_cache_lock = threading.Lock()


def log_query_time(operation: str, start_time: float, threshold: float = 0.5):
    """Log slow queries for debugging."""
    elapsed = time.time() - start_time
    if elapsed > threshold:
        logger.warning(f"SLOW QUERY [{operation}]: {elapsed:.2f}s")
    return elapsed


def get_market_cache(key: str) -> Optional[Any]:
    with _market_cache_lock:
        return _market_cache.get(key)


def set_market_cache(key: str, value: Any):
    with _market_cache_lock:
        _market_cache[key] = value


@router.get("/treatments")
def read_treatments(
    session: Session = Depends(get_session),
) -> Any:
    """
    Get price floors by treatment.
    Cached for 2 minutes.
    """
    # Check cache
    cache_key = "market_treatments"
    cached = get_market_cache(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    from sqlalchemy import text

    query = text("""
        SELECT
            treatment,
            MIN(price) as min_price,
            COUNT(*) as count
        FROM marketprice
        WHERE listing_type = 'sold' AND treatment IS NOT NULL
        GROUP BY treatment
        ORDER BY treatment
    """)
    results = session.execute(query).all()
    data = [{"name": row[0], "min_price": float(row[1]), "count": int(row[2])} for row in results]

    # Cache result
    set_market_cache(cache_key, data)

    return JSONResponse(content=data, headers={"X-Cache": "MISS"})


@router.get("/overview")
def read_market_overview(
    session: Session = Depends(get_session),
    time_period: Optional[str] = Query(default="30d", pattern="^(1h|24h|7d|30d|90d|all)$"),
) -> Any:
    """
    Get robust market overview statistics with temporal data.
    OPTIMIZED: Single CTE query replaces 6+ separate queries.
    Cached for 5 minutes (longer periods get longer cache).
    """
    # Check cache first
    cache_key = f"market_overview_{time_period}"
    cached = get_market_cache(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    from sqlalchemy import text

    # Calculate time cutoff
    time_cutoffs = {
        "1h": timedelta(hours=1),
        "24h": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": timedelta(days=3650),  # ~10 years for "all"
    }
    cutoff_delta = time_cutoffs.get(time_period, timedelta(days=30))
    cutoff_time = datetime.now(timezone.utc) - cutoff_delta

    # Floor price lookback (use longer window for floor calculation)
    floor_days = {"1h": 30, "24h": 30, "7d": 30, "30d": 30, "90d": 90, "all": 365}.get(time_period, 30)
    floor_cutoff = datetime.now(timezone.utc) - timedelta(days=floor_days)

    # SINGLE CONSOLIDATED CTE QUERY - replaces 6+ separate queries
    # NOTE: Floor price calculation now includes Blokpax sales to match FloorPriceService
    consolidated_query = text("""
        WITH card_sales AS (
            -- All sold listings with effective date (eBay, OpenSea)
            SELECT
                card_id,
                price,
                COALESCE(sold_date, scraped_at) as sale_date,
                ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY COALESCE(sold_date, scraped_at) DESC) as rn_desc
            FROM marketprice
            WHERE listing_type = 'sold' AND is_bulk_lot = FALSE
        ),
        blokpax_sales AS (
            -- Blokpax sales (merged with marketprice for floor calculation)
            SELECT card_id, price_usd as price, filled_at as sale_date
            FROM blokpaxsale
        ),
        all_sales AS (
            -- Combined sales from all platforms
            SELECT card_id, price, sale_date FROM card_sales
            UNION ALL
            SELECT card_id, price, sale_date FROM blokpax_sales
        ),
        last_sale AS (
            -- Most recent sale per card (any time, eBay/OpenSea only for consistency)
            SELECT card_id, price as last_price
            FROM card_sales WHERE rn_desc = 1
        ),
        period_stats AS (
            -- Stats for the selected time period (all platforms)
            SELECT
                card_id,
                COUNT(*) as sale_count,
                SUM(price) as total_value,
                AVG(price) as vwap
            FROM all_sales
            WHERE sale_date >= :cutoff_time
            GROUP BY card_id
        ),
        floor_prices AS (
            -- Floor = avg of 4 lowest prices in floor window (all platforms)
            -- This matches FloorPriceService logic
            SELECT card_id, ROUND(AVG(price)::numeric, 2) as floor_price
            FROM (
                SELECT card_id, price,
                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY price ASC) as rn
                FROM all_sales
                WHERE sale_date >= :floor_cutoff
            ) ranked
            WHERE rn <= 4
            GROUP BY card_id
        )
        SELECT
            c.id,
            c.slug,
            c.name,
            c.set_name,
            c.rarity_id,
            COALESCE(ls.last_price, 0) as latest_price,
            COALESCE(ps.vwap, 0) as vwap,
            fp.floor_price,
            COALESCE(ps.sale_count, 0) as volume_period,
            COALESCE(ps.total_value, 0) as dollar_volume,
            -- Price delta: compare last sale to floor (shows premium/discount)
            CASE
                WHEN ls.last_price IS NOT NULL AND fp.floor_price IS NOT NULL AND fp.floor_price > 0 AND ps.sale_count >= 2
                THEN LEAST(200, GREATEST(-200, ((ls.last_price - fp.floor_price) / fp.floor_price) * 100))
                WHEN ls.last_price IS NOT NULL AND ps.vwap IS NOT NULL AND ps.vwap > 0
                THEN LEAST(200, GREATEST(-200, ((ls.last_price - ps.vwap) / ps.vwap) * 100))
                ELSE 0
            END as price_delta_period,
            -- Deal rating: compare last sale to VWAP
            CASE
                WHEN ls.last_price IS NOT NULL AND ps.vwap IS NOT NULL AND ps.vwap > 0
                THEN LEAST(100, GREATEST(-100, ((ls.last_price - ps.vwap) / ps.vwap) * 100))
                ELSE 0
            END as deal_rating
        FROM card c
        LEFT JOIN last_sale ls ON c.id = ls.card_id
        LEFT JOIN period_stats ps ON c.id = ps.card_id
        LEFT JOIN floor_prices fp ON c.id = fp.card_id
        ORDER BY c.name
    """)

    results = session.execute(
        consolidated_query,
        {
            "cutoff_time": cutoff_time,
            "floor_cutoff": floor_cutoff,
        },
    ).all()

    overview_data = []
    for row in results:
        (
            card_id,
            slug,
            name,
            set_name,
            rarity_id,
            latest_price,
            vwap,
            floor_price,
            volume_period,
            dollar_volume,
            price_delta,
            deal_rating,
        ) = row

        overview_data.append(
            {
                "id": card_id,
                "slug": slug,
                "name": name,
                "set_name": set_name,
                "rarity_id": rarity_id,
                "latest_price": float(latest_price) if latest_price else 0.0,
                "avg_price": float(vwap) if vwap else 0.0,
                "vwap": float(vwap) if vwap else 0.0,
                "floor_price": float(floor_price) if floor_price else None,
                "volume_period": int(volume_period) if volume_period else 0,
                "volume_change": 0,
                "price_delta_period": float(price_delta) if price_delta else 0.0,
                "deal_rating": float(deal_rating) if deal_rating else 0.0,
                "dollar_volume": float(dollar_volume) if dollar_volume else 0.0,
            }
        )

    # Cache the result
    set_market_cache(cache_key, overview_data)
    return overview_data


@router.get("/marquee")
def read_marquee_data(
    session: Session = Depends(get_session),
    time_period: Optional[str] = Query(default="7d", pattern="^(24h|7d|30d)$"),
) -> Any:
    """
    Get lightweight data for the marquee ticker.
    Returns top gainers, losers, and volume cards (35 items total).
    OPTIMIZED: Replaces fetching 500 cards - reduces payload from ~100KB to ~8KB.
    Cached for 5 minutes.
    """
    cache_key = f"marquee_{time_period}"
    cached = get_market_cache(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    from sqlalchemy import text

    # Calculate time cutoff
    time_cutoffs = {
        "24h": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
    }
    cutoff_delta = time_cutoffs.get(time_period, timedelta(days=7))
    cutoff_time = datetime.now(timezone.utc) - cutoff_delta
    floor_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    # OPTIMIZED: Simple query for marquee - prioritize speed over complexity
    # Returns cards with floor prices, sorted by price (highest first)
    # Frontend will dedupe and categorize based on price_delta
    marquee_query = text("""
        WITH floor_prices AS (
            -- Get floor price per card (avg of 4 lowest recent sales)
            SELECT card_id, ROUND(AVG(price)::numeric, 2) as floor_price
            FROM (
                SELECT card_id, price,
                       ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY price ASC) as rn
                FROM marketprice
                WHERE listing_type = 'sold' AND is_bulk_lot = FALSE
                  AND COALESCE(sold_date, scraped_at) >= :floor_cutoff
            ) ranked
            WHERE rn <= 4
            GROUP BY card_id
        ),
        recent_volume AS (
            -- Count sales in time period
            SELECT card_id,
                   COUNT(*) as volume,
                   SUM(price) as dollar_volume
            FROM marketprice
            WHERE listing_type = 'sold' AND is_bulk_lot = FALSE
              AND COALESCE(sold_date, scraped_at) >= :cutoff_time
            GROUP BY card_id
        ),
        latest_sale AS (
            -- Most recent sale per card
            SELECT DISTINCT ON (card_id) card_id, price as latest_price
            FROM marketprice
            WHERE listing_type = 'sold' AND is_bulk_lot = FALSE
            ORDER BY card_id, COALESCE(sold_date, scraped_at) DESC
        )
        SELECT
            c.id,
            c.slug,
            c.name,
            c.set_name,
            COALESCE(rv.volume, 0) as volume,
            COALESCE(rv.dollar_volume, 0) as dollar_volume,
            fp.floor_price,
            ls.latest_price,
            CASE
                WHEN ls.latest_price IS NOT NULL AND fp.floor_price IS NOT NULL AND fp.floor_price > 0
                THEN ROUND(((ls.latest_price - fp.floor_price) / fp.floor_price * 100)::numeric, 1)
                ELSE 0
            END as price_delta
        FROM card c
        LEFT JOIN floor_prices fp ON c.id = fp.card_id
        LEFT JOIN recent_volume rv ON c.id = rv.card_id
        LEFT JOIN latest_sale ls ON c.id = ls.card_id
        WHERE fp.floor_price IS NOT NULL
        ORDER BY fp.floor_price DESC
        LIMIT 50
    """)

    results = session.execute(
        marquee_query,
        {
            "cutoff_time": cutoff_time,
            "floor_cutoff": floor_cutoff,
        },
    ).all()

    # Categorize results based on price_delta and volume
    gainers = []
    losers = []
    volume = []
    recent = []
    total_volume = 0
    total_dollar_volume = 0.0

    for row in results:
        item = {
            "id": row.id,
            "slug": row.slug,
            "name": row.name,
            "set_name": row.set_name,
            "floor_price": float(row.floor_price) if row.floor_price else None,
            "latest_price": float(row.latest_price) if row.latest_price else None,
            "price_delta": float(row.price_delta) if row.price_delta else 0,
            "volume": int(row.volume) if row.volume else 0,
            "dollar_volume": float(row.dollar_volume) if row.dollar_volume else 0,
        }

        # Categorize by price movement
        if item["price_delta"] > 5 and len(gainers) < 15:
            gainers.append(item)
        elif item["price_delta"] < -5 and len(losers) < 10:
            losers.append(item)
        elif item["volume"] > 0 and len(volume) < 10:
            volume.append(item)
            total_volume += item["volume"]
            total_dollar_volume += item["dollar_volume"]
        elif len(recent) < 20:
            recent.append(item)

    response = {
        "gainers": gainers,
        "losers": losers,
        "volume": volume,
        "recent": recent,
        "metrics": {
            "total_volume": total_volume,
            "total_dollar_volume": round(total_dollar_volume, 2),
        },
        "time_period": time_period,
    }

    set_market_cache(cache_key, response)
    return JSONResponse(content=response, headers={"X-Cache": "MISS"})


@router.get("/activity")
def read_market_activity(
    session: Session = Depends(get_session),
    limit: int = 20,
) -> Any:
    """
    Get recent market activity (sales) across all cards.
    """
    from app.models.market import MarketPrice

    # Join with Card to get card details
    query = (
        select(MarketPrice, Card.name, Card.id)
        .join(Card)
        .where(MarketPrice.listing_type == "sold")
        .order_by(desc(MarketPrice.sold_date))
        .limit(limit)
    )
    results = session.execute(query).all()

    activity_data = []
    for sale, card_name, card_id in results:
        activity_data.append(
            {
                "card_id": card_id,
                "card_name": card_name,
                "price": sale.price,
                "date": sale.sold_date,
                "treatment": sale.treatment,
                "platform": sale.platform,
            }
        )

    return activity_data


@router.get("/listings")
def read_market_listings(
    session: Session = Depends(get_session),
    listing_type: Optional[str] = Query(default="active", description="Filter by listing type: active, sold, or all"),
    platform: Optional[str] = Query(default=None, description="Filter by platform: ebay, blokpax, opensea"),
    product_type: Optional[str] = Query(default=None, description="Filter by product type: Single, Box, Pack"),
    treatment: Optional[str] = Query(default=None, description="Filter by treatment: Classic Paper, Foil, etc."),
    time_period: Optional[str] = Query(default=None, description="Filter by time period: 7d, 30d, 90d, all"),
    min_price: Optional[float] = Query(default=None, ge=0, description="Minimum price filter"),
    max_price: Optional[float] = Query(default=None, description="Maximum price filter"),
    search: Optional[str] = Query(default=None, description="Search by listing title or card name"),
    sort_by: Optional[str] = Query(default="scraped_at", description="Sort by: price, scraped_at, sold_date"),
    sort_order: Optional[str] = Query(default="desc", description="Sort order: asc or desc"),
    limit: int = Query(default=100, ge=1, le=500, description="Items per page"),
    offset: int = Query(default=0, ge=0, description="Offset for pagination"),
) -> Any:
    """
    Get marketplace listings across all cards with comprehensive filtering.
    Returns individual listings from MarketPrice table with card details including floor price.
    Cached for 2 minutes to improve performance.
    """
    # Normalize search for cache key (strip and lowercase)
    search_normalized = search.strip().lower() if search and len(search.strip()) >= 3 else None

    # Build cache key from all filter parameters
    cache_key = f"listings_{listing_type}_{platform}_{product_type}_{treatment}_{time_period}_{min_price}_{max_price}_{search_normalized}_{sort_by}_{sort_order}_{limit}_{offset}"
    cached = get_market_cache(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    start_time = time.time()
    from sqlalchemy import func, or_, text
    from app.models.market import MarketPrice

    # Calculate time cutoff for time_period filter
    time_cutoffs = {
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None,
    }
    cutoff_delta = time_cutoffs.get(time_period) if time_period else None
    cutoff_time = datetime.now(timezone.utc) - cutoff_delta if cutoff_delta else None

    # Build base query with join to Card for product info
    # Select both full models for type-safe tuple unpacking
    query = select(MarketPrice, Card).join(Card, col(MarketPrice.card_id) == col(Card.id))

    # Apply listing type filter
    if listing_type and listing_type != "all":
        query = query.where(MarketPrice.listing_type == listing_type)

    # Apply platform filter
    if platform:
        query = query.where(MarketPrice.platform == platform)

    # Apply product type filter (on Card)
    if product_type:
        query = query.where(col(Card.product_type).ilike(product_type))

    # Apply treatment filter
    if treatment:
        query = query.where(col(MarketPrice.treatment).ilike(f"%{treatment}%"))

    # Apply time period filter - smart behavior based on listing type
    # Active listings: filter by listed_at (when seller posted it)
    # Sold listings: filter by sold_date (when it sold)
    if cutoff_time:
        if listing_type == "active":
            # Use listed_at for active listings, fallback to scraped_at
            query = query.where(func.coalesce(MarketPrice.listed_at, MarketPrice.scraped_at) >= cutoff_time)
        elif listing_type == "sold":
            # Use sold_date for sold listings
            query = query.where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= cutoff_time)
        else:
            # "all" - use appropriate date for each type
            query = query.where(
                func.coalesce(MarketPrice.sold_date, MarketPrice.listed_at, MarketPrice.scraped_at) >= cutoff_time
            )

    # Apply price range filters
    if min_price is not None:
        query = query.where(MarketPrice.price >= min_price)
    if max_price is not None:
        query = query.where(MarketPrice.price <= max_price)

    # Apply search filter (minimum 3 characters to avoid expensive ILIKE on short strings)
    if search and len(search.strip()) >= 3:
        search_pattern = f"%{search.strip()}%"
        query = query.where(
            or_(
                col(MarketPrice.title).ilike(search_pattern),
                col(Card.name).ilike(search_pattern),
            )
        )

    # SKIP expensive COUNT entirely - use "hasMore" pagination instead
    # Fetch limit+1 to check if there are more results
    total = None  # Not calculated - frontend should use hasMore instead

    # Apply sorting - use explicit Any typing for SQLAlchemy column expressions
    sort_key = sort_by if sort_by else "scraped_at"
    sort_column_map: dict[str, Any] = {
        "price": col(MarketPrice.price),
        "scraped_at": col(MarketPrice.scraped_at),
        "listed_at": func.coalesce(MarketPrice.listed_at, MarketPrice.scraped_at),
        "sold_date": func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at),
    }
    sort_column: Any = sort_column_map.get(sort_key, col(MarketPrice.scraped_at))

    # For active listings default to listed_at (more meaningful than scraped_at)
    if sort_key == "scraped_at" and listing_type == "active":
        sort_column = func.coalesce(MarketPrice.listed_at, MarketPrice.scraped_at)

    # Add secondary sort by id for deterministic ordering when primary sort values are equal
    if sort_order == "asc":
        query = query.order_by(sort_column, col(MarketPrice.id))
    else:
        query = query.order_by(desc(sort_column), col(MarketPrice.id).desc())

    # Apply pagination - fetch limit+1 to determine hasMore
    query = query.offset(offset).limit(limit + 1)

    results = session.execute(query).all()

    # Check if there are more results
    has_more = len(results) > limit
    if has_more:
        results = results[:limit]  # Trim to requested limit

    # Get unique card IDs to batch fetch floor prices and VWAP
    card_ids = list(set(listing.card_id for listing, _ in results))
    floor_by_variant_map: dict[int, dict[str, float]] = {}
    floor_price_map: dict[int, float] = {}
    vwap_map: dict[int, float] = {}

    if card_ids:
        # Single CTE query for both floor prices by variant AND VWAP
        # Much faster than calling FloorPriceService.get_floor_prices_batch()
        floor_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        vwap_cutoff = datetime.now(timezone.utc) - timedelta(days=30)

        combined_query = text("""
            WITH floor_by_variant AS (
                SELECT
                    card_id,
                    LOWER(COALESCE(NULLIF(product_subtype, ''), treatment, 'unknown')) as variant,
                    ROUND(AVG(price)::numeric, 2) as floor_price
                FROM (
                    SELECT card_id, product_subtype, treatment, price,
                           ROW_NUMBER() OVER (
                               PARTITION BY card_id, COALESCE(NULLIF(product_subtype, ''), treatment, 'unknown')
                               ORDER BY price ASC
                           ) as rn
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                      AND listing_type = 'sold'
                      AND is_bulk_lot = FALSE
                      AND COALESCE(sold_date, scraped_at) >= :floor_cutoff
                ) ranked
                WHERE rn <= 4
                GROUP BY card_id, LOWER(COALESCE(NULLIF(product_subtype, ''), treatment, 'unknown'))
            ),
            vwap AS (
                SELECT card_id, ROUND(AVG(price)::numeric, 2) as vwap
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                  AND listing_type = 'sold'
                  AND is_bulk_lot = FALSE
                  AND COALESCE(sold_date, scraped_at) >= :vwap_cutoff
                GROUP BY card_id
            )
            SELECT 'floor' as query_type, card_id, variant as key, floor_price as value FROM floor_by_variant
            UNION ALL
            SELECT 'vwap' as query_type, card_id, NULL as key, vwap as value FROM vwap
        """)

        combined_results = session.execute(
            combined_query,
            {
                "card_ids": card_ids,
                "floor_cutoff": floor_cutoff,
                "vwap_cutoff": vwap_cutoff,
            },
        ).all()

        # Parse results into maps
        for query_type, card_id, key, value in combined_results:
            if value is None:
                continue
            if query_type == "floor":
                if card_id not in floor_by_variant_map:
                    floor_by_variant_map[card_id] = {}
                floor_by_variant_map[card_id][key] = float(value)
            elif query_type == "vwap":
                vwap_map[card_id] = float(value)

        # Build overall floor map (cheapest variant per card)
        for card_id, variants in floor_by_variant_map.items():
            floor_price_map[card_id] = min(variants.values())

    # Format results
    listings = []
    for listing, card in results:
        card_name = card.name
        card_slug = card.slug
        card_product_type = card.product_type
        card_image_url = card.image_url
        # Get treatment-specific floor price if available
        # Determine variant key: use product_subtype for sealed, treatment for singles
        # Use lowercase for case-insensitive matching
        raw_variant = listing.product_subtype if listing.product_subtype else listing.treatment
        variant_key = raw_variant.lower().strip() if raw_variant else "unknown"
        card_variants = floor_by_variant_map.get(listing.card_id, {})
        # Only use treatment-specific floor - don't fall back to other variants
        # This prevents comparing a Classic Paper listing to a Stonefoil floor
        variant_floor = card_variants.get(variant_key)
        floor_price = variant_floor  # No fallback - must match treatment

        listings.append(
            {
                "id": listing.id,
                "card_id": listing.card_id,
                "card_name": card_name,
                "card_slug": card_slug,
                "card_image_url": card_image_url,
                "product_type": card_product_type or "Single",
                "title": listing.title,
                "price": listing.price,
                "floor_price": floor_price,
                "vwap": vwap_map.get(listing.card_id),
                "platform": listing.platform,
                "treatment": listing.treatment,
                "listing_type": listing.listing_type,
                "listing_format": listing.listing_format,  # auction, buy_it_now, best_offer
                "condition": listing.condition,
                "bid_count": listing.bid_count,
                "seller_name": listing.seller_name,
                "seller_feedback_score": listing.seller_feedback_score,
                "seller_feedback_percent": listing.seller_feedback_percent,
                "shipping_cost": listing.shipping_cost,
                "grading": listing.grading,
                "traits": listing.traits,
                "url": listing.url,
                "image_url": listing.image_url,
                "sold_date": listing.sold_date.isoformat() if listing.sold_date else None,
                "scraped_at": listing.scraped_at.isoformat() if listing.scraped_at else None,
                "listed_at": listing.listed_at.isoformat() if listing.listed_at else None,
            }
        )

    # Log slow queries for performance monitoring
    log_query_time(f"listings(type={listing_type}, platform={platform})", start_time)

    result = {
        "items": listings,
        "total": total,  # None - COUNT skipped for performance
        "offset": offset,
        "limit": limit,
        "hasMore": has_more,  # Determined by fetching limit+1
    }

    # Cache the result for 2 minutes
    set_market_cache(cache_key, result)

    return JSONResponse(content=result, headers={"X-Cache": "MISS"})


# ============== LISTING REPORTS ==============

from pydantic import BaseModel


class ListingReportCreate(BaseModel):
    listing_id: int
    card_id: int
    reason: str  # 'wrong_price', 'fake_listing', 'duplicate', 'wrong_card', 'other'
    notes: Optional[str] = None
    listing_title: Optional[str] = None
    listing_price: Optional[float] = None
    listing_url: Optional[str] = None


@router.post("/reports")
def create_listing_report(
    report: ListingReportCreate,
    session: Session = Depends(get_session),
) -> Any:
    """
    Submit a report for an incorrect, fake, or duplicate listing.
    """
    from app.models.market import ListingReport

    # Verify the listing exists
    listing = session.get(MarketPrice, report.listing_id)
    if not listing:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="Listing not found")

    # Create the report
    db_report = ListingReport(
        listing_id=report.listing_id,
        card_id=report.card_id,
        reason=report.reason,
        notes=report.notes,
        listing_title=report.listing_title or listing.title,
        listing_price=report.listing_price or listing.price,
        listing_url=report.listing_url or listing.url,
    )
    session.add(db_report)
    session.commit()
    session.refresh(db_report)

    return {
        "id": db_report.id,
        "listing_id": db_report.listing_id,
        "reason": db_report.reason,
        "status": db_report.status,
        "created_at": db_report.created_at,
        "message": "Report submitted successfully",
    }


@router.get("/reports")
def get_listing_reports(
    session: Session = Depends(get_session),
    status: Optional[str] = Query(default=None),
    limit: int = Query(default=50, le=200),
) -> Any:
    """
    Get listing reports (for admin review).
    """
    from app.models.market import ListingReport

    query = select(ListingReport).order_by(desc(ListingReport.created_at))

    if status:
        query = query.where(ListingReport.status == status)

    query = query.limit(limit)
    reports = session.execute(query).scalars().all()

    return [
        {
            "id": r.id,
            "listing_id": r.listing_id,
            "card_id": r.card_id,
            "reason": r.reason,
            "notes": r.notes,
            "listing_title": r.listing_title,
            "listing_price": r.listing_price,
            "listing_url": r.listing_url,
            "status": r.status,
            "created_at": r.created_at,
        }
        for r in reports
    ]
