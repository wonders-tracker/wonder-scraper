from typing import Any, Optional, cast
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
from app.models.market import MarketSnapshot, MarketPrice

router = APIRouter()
logger = logging.getLogger(__name__)

# Thread-safe cache with TTL (2 min for market data - it changes frequently)
_market_cache = TTLCache(maxsize=50, ttl=120)
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
    Cached for 2 minutes to improve performance.
    """
    # Check cache first
    cache_key = f"market_overview_{time_period}"
    cached = get_market_cache(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})

    # Calculate time cutoff
    time_cutoffs = {
        "1h": timedelta(hours=1),
        "24h": timedelta(days=1),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None,
    }
    cutoff_delta = time_cutoffs.get(time_period)
    cutoff_time = datetime.now(timezone.utc) - cutoff_delta if cutoff_delta else None

    # Fetch all cards
    cards = session.execute(select(Card)).scalars().all()
    if not cards:
        return []

    card_ids = [c.id for c in cards]

    # Batch fetch snapshots
    snapshot_query = select(MarketSnapshot).where(col(MarketSnapshot.card_id).in_(card_ids))
    if cutoff_time:
        snapshot_query = snapshot_query.where(col(MarketSnapshot.timestamp) >= cutoff_time)
    snapshot_query = snapshot_query.order_by(col(MarketSnapshot.card_id), col(MarketSnapshot.timestamp).desc())
    all_snapshots = session.execute(snapshot_query).scalars().all()

    snapshots_by_card = {}
    for snap in all_snapshots:
        if snap.card_id not in snapshots_by_card:
            snapshots_by_card[snap.card_id] = []
        snapshots_by_card[snap.card_id].append(snap)

    # Batch fetch actual LAST SALE price (Postgres DISTINCT ON)
    last_sale_map = {}
    vwap_map = {}
    sales_count_map = {}
    floor_price_map = {}
    if card_ids:
        try:
            from sqlalchemy import text

            period_start = cutoff_time if cutoff_time else datetime.now(timezone.utc) - timedelta(hours=24)

            # Use parameterized queries to prevent SQL injection
            # Use COALESCE(sold_date, scraped_at) to include sales with NULL sold_date
            query = text("""
                SELECT DISTINCT ON (card_id) card_id, price, treatment, COALESCE(sold_date, scraped_at) as effective_date
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                ORDER BY card_id, COALESCE(sold_date, scraped_at) DESC
            """)
            results = session.execute(query, {"card_ids": card_ids}).all()
            last_sale_map = {row[0]: {"price": row[1], "treatment": row[2], "date": row[3]} for row in results}

            # Calculate VWAP with proper parameter binding
            # Use COALESCE(sold_date, scraped_at) as fallback when sold_date is NULL
            if cutoff_time:
                vwap_query = text("""
                    SELECT card_id, AVG(price) as vwap
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    AND COALESCE(sold_date, scraped_at) >= :cutoff_time
                    GROUP BY card_id
                """)
                vwap_results = session.execute(vwap_query, {"card_ids": card_ids, "cutoff_time": cutoff_time}).all()
            else:
                vwap_query = text("""
                    SELECT card_id, AVG(price) as vwap
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    GROUP BY card_id
                """)
                vwap_results = session.execute(vwap_query, {"card_ids": card_ids}).all()
            vwap_map = {row[0]: row[1] for row in vwap_results}

            # Get oldest sale in period for delta calculation
            # Use COALESCE(sold_date, scraped_at) as fallback when sold_date is NULL
            oldest_sale_query = text("""
                SELECT DISTINCT ON (card_id) card_id, price, COALESCE(sold_date, scraped_at) as effective_date
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                AND COALESCE(sold_date, scraped_at) >= :period_start
                ORDER BY card_id, COALESCE(sold_date, scraped_at) ASC
            """)
            oldest_results = session.execute(
                oldest_sale_query, {"card_ids": card_ids, "period_start": period_start}
            ).all()
            {row[0]: {"price": row[1], "date": row[2]} for row in oldest_results}

            # Count sales in period for each card AND calculate total dollar volume
            sales_count_query = text("""
                SELECT card_id,
                       COUNT(*) as sale_count,
                       COUNT(DISTINCT DATE(COALESCE(sold_date, scraped_at))) as unique_days,
                       SUM(price) as total_value
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                AND COALESCE(sold_date, scraped_at) >= :period_start
                GROUP BY card_id
            """)
            sales_count_results = session.execute(
                sales_count_query, {"card_ids": card_ids, "period_start": period_start}
            ).all()
            sales_count_map = {row[0]: {"count": row[1], "unique_days": row[2], "total_value": float(row[3]) if row[3] else 0} for row in sales_count_results}

            # Calculate floor prices (avg of 4 lowest sales per card in period)
            floor_query = text("""
                SELECT card_id, AVG(price) as floor_price
                FROM (
                    SELECT card_id, price,
                           ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY price ASC) as rn
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                      AND listing_type = 'sold'
                      AND COALESCE(sold_date, scraped_at) >= :period_start
                ) ranked
                WHERE rn <= 4
                GROUP BY card_id
            """)
            floor_results = session.execute(floor_query, {"card_ids": card_ids, "period_start": period_start}).all()
            floor_price_map = {row[0]: round(float(row[1]), 2) for row in floor_results}

        except Exception as e:
            print(f"Error fetching last sales: {e}")

    overview_data = []
    for card in cards:
        card_snaps = snapshots_by_card.get(card.id, [])
        latest_snap = card_snaps[0] if card_snaps else None
        oldest_snap = card_snaps[-1] if card_snaps else None

        last_sale_data = last_sale_map.get(card.id)
        last_price = last_sale_data["price"] if last_sale_data else None

        if last_price is None and latest_snap:
            last_price = latest_snap.avg_price

        # Get VWAP
        vwap = vwap_map.get(card.id)
        effective_price = vwap if vwap else (latest_snap.avg_price if latest_snap else 0.0)

        # Market Trend Delta - Compare last sale to VWAP (more stable than oldest vs newest)
        # This shows if the most recent sale was above or below the period average
        avg_delta = 0.0
        sales_stats = sales_count_map.get(card.id)
        floor_price = floor_price_map.get(card.id)

        # Primary method: Compare last sale to floor price (shows premium/discount to floor)
        if last_price and floor_price and floor_price > 0 and sales_stats and sales_stats["count"] >= 2:
            avg_delta = ((last_price - floor_price) / floor_price) * 100
            # Cap extreme values at ±200% to filter outliers
            avg_delta = max(-200, min(200, avg_delta))
        # Fallback: Compare last sale to VWAP
        elif last_price and vwap and vwap > 0:
            avg_delta = ((last_price - vwap) / vwap) * 100
            avg_delta = max(-200, min(200, avg_delta))
        # Last fallback: snapshot comparison
        elif latest_snap and oldest_snap and oldest_snap.avg_price > 0 and latest_snap.id != oldest_snap.id:
            avg_delta = ((latest_snap.avg_price - oldest_snap.avg_price) / oldest_snap.avg_price) * 100
            avg_delta = max(-200, min(200, avg_delta))

        # Deal Rating Delta - compare last sale to VWAP (more stable than snapshot avg)
        deal_delta = 0.0
        # Use VWAP for comparison as it's more accurate than snapshot avg_price
        comparison_price = (
            vwap if vwap and vwap > 0 else (latest_snap.avg_price if latest_snap and latest_snap.avg_price > 0 else 0)
        )
        if last_price and comparison_price > 0:
            deal_delta = ((last_price - comparison_price) / comparison_price) * 100
            # Cap at ±100% to avoid extreme outliers
            deal_delta = max(-100, min(100, deal_delta))

        # Use actual sales count from MarketPrice (more accurate than snapshot volume)
        period_volume = sales_stats["count"] if sales_stats else 0
        # Total dollar volume = sum of all sale prices in period
        total_dollar_volume = sales_stats["total_value"] if sales_stats else 0

        overview_data.append(
            {
                "id": card.id,
                "slug": card.slug if hasattr(card, "slug") else None,
                "name": card.name,
                "set_name": card.set_name,
                "rarity_id": card.rarity_id,
                "latest_price": last_price or 0.0,
                "avg_price": latest_snap.avg_price if latest_snap else 0.0,
                "vwap": effective_price,
                "floor_price": floor_price_map.get(card.id),  # Avg of 4 lowest sales
                "volume_period": period_volume,
                "volume_change": 0,  # TODO: Calculate from previous period if needed
                "price_delta_period": avg_delta,
                "deal_rating": deal_delta,
                "dollar_volume": total_dollar_volume,  # Total $ traded in period
            }
        )

    # Cache the result
    set_market_cache(cache_key, overview_data)

    return JSONResponse(content=overview_data, headers={"X-Cache": "MISS"})


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
    """
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
                func.coalesce(
                    MarketPrice.sold_date,
                    MarketPrice.listed_at,
                    MarketPrice.scraped_at
                ) >= cutoff_time
            )

    # Apply price range filters
    if min_price is not None:
        query = query.where(MarketPrice.price >= min_price)
    if max_price is not None:
        query = query.where(MarketPrice.price <= max_price)

    # Apply search filter
    if search:
        search_pattern = f"%{search}%"
        query = query.where(
            or_(
                col(MarketPrice.title).ilike(search_pattern),
                col(Card.name).ilike(search_pattern),
            )
        )

    # Get total count before pagination
    count_query = select(func.count()).select_from(query.subquery())
    total = session.execute(count_query).one()

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

    # Apply pagination
    query = query.offset(offset).limit(limit)

    results = session.execute(query).all()

    # Get unique card IDs to batch fetch floor prices and VWAP
    card_ids = list(set(listing.card_id for listing, _ in results))
    floor_price_map = {}
    vwap_map = {}

    if card_ids:
        # Batch calculate floor prices per variant (avg of 4 lowest sales)
        # Uses treatment for singles, product_subtype for sealed
        # NOTE: Floor price always uses 90-day lookback regardless of time_period filter
        # This ensures we have enough sales data for meaningful floor calculations
        # IMPORTANT: Use LOWER() for case-insensitive matching
        floor_cutoff = datetime.now(timezone.utc) - timedelta(days=90)
        floor_by_variant_query = text("""
            SELECT card_id, variant, AVG(price) as floor_price
            FROM (
                SELECT card_id,
                       LOWER(COALESCE(
                           NULLIF(product_subtype, ''),
                           treatment,
                           'unknown'
                       )) as variant,
                       price,
                       ROW_NUMBER() OVER (
                           PARTITION BY card_id,
                               LOWER(COALESCE(
                                   NULLIF(product_subtype, ''),
                                   treatment,
                                   'unknown'
                               ))
                           ORDER BY price ASC
                       ) as rn
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                  AND listing_type = 'sold'
                  AND COALESCE(sold_date, scraped_at) >= :cutoff
            ) ranked
            WHERE rn <= 4
            GROUP BY card_id, variant
        """)
        floor_results = session.execute(floor_by_variant_query, {"card_ids": card_ids, "cutoff": floor_cutoff}).all()
        # Build nested map: {card_id: {variant_lower: price}}
        floor_by_variant_map = {}
        for row in floor_results:
            card_id, variant, price = row[0], row[1], round(float(row[2]), 2)
            if card_id not in floor_by_variant_map:
                floor_by_variant_map[card_id] = {}
            # Store with lowercase key for case-insensitive lookup
            floor_by_variant_map[card_id][variant.lower() if variant else 'unknown'] = price
        # Also build overall floor map (cheapest variant)
        for card_id, variants in floor_by_variant_map.items():
            floor_price_map[card_id] = min(variants.values())

        # Batch calculate VWAP (avg of all sold prices in 30d) as fallback
        vwap_query = text("""
            SELECT card_id, AVG(price) as vwap
            FROM marketprice
            WHERE card_id = ANY(:card_ids)
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
            GROUP BY card_id
        """)
        vwap_results = session.execute(vwap_query, {"card_ids": card_ids, "cutoff": floor_cutoff}).all()
        vwap_map = {row[0]: round(float(row[1]), 2) for row in vwap_results}

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
        variant_key = raw_variant.lower().strip() if raw_variant else 'unknown'
        card_variants = floor_by_variant_map.get(listing.card_id, {})
        # Only use treatment-specific floor - don't fall back to other variants
        # This prevents comparing a Classic Paper listing to a Stonefoil floor
        variant_floor = card_variants.get(variant_key)
        floor_price = variant_floor  # No fallback - must match treatment

        listings.append({
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
        })

    # Log slow queries for performance monitoring
    log_query_time(f"listings(type={listing_type}, platform={platform})", start_time)

    return {
        "items": listings,
        "total": total,
        "offset": offset,
        "limit": limit,
        "hasMore": offset + len(listings) < total,
    }


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
