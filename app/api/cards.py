from typing import Any, List, Optional
import json
import hashlib
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session, select, func, desc
from datetime import datetime, timedelta

from app.api import deps
from app.db import get_session
from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice
from app.schemas import CardOut, MarketSnapshotOut, MarketPriceOut

router = APIRouter()

# Simple in-memory cache
_cache = {}
_cache_ttl = {}

def get_cache_key(endpoint: str, **params) -> str:
    """Generate cache key from endpoint and params."""
    param_str = json.dumps(params, sort_keys=True)
    return hashlib.md5(f"{endpoint}:{param_str}".encode()).hexdigest()

def get_cached(key: str) -> Optional[Any]:
    """Get cached response if not expired."""
    import time
    if key in _cache and key in _cache_ttl:
        if time.time() < _cache_ttl[key]:
            return _cache[key]
        else:
            # Expired, clean up
            del _cache[key]
            del _cache_ttl[key]
    return None

def set_cache(key: str, value: Any, ttl: int = 300):
    """Set cache with TTL (default 5 minutes)."""
    import time
    _cache[key] = value
    _cache_ttl[key] = time.time() + ttl

@router.get("/", response_model=List[CardOut])
def read_cards(
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    time_period: Optional[str] = Query(default="24h", regex="^(24h|7d|30d|90d|all)$"),
    product_type: Optional[str] = Query(default=None, description="Filter by product type (e.g., Single, Box, Pack)"),
) -> Any:
    """
    Retrieve cards with latest market data - OPTIMIZED with caching.
    Single batch query instead of N+1 + 5-minute cache.
    """
    # Check cache first
    cache_key = get_cache_key("cards", skip=skip, limit=limit, search=search or "", time_period=time_period, product_type=product_type or "")
    cached = get_cached(cache_key)
    if cached:
        return JSONResponse(content=cached, headers={"X-Cache": "HIT"})
    # Calculate time cutoff
    time_cutoffs = {
        "24h": timedelta(hours=24),
        "7d": timedelta(days=7),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }
    cutoff_delta = time_cutoffs.get(time_period)
    cutoff_time = datetime.utcnow() - cutoff_delta if cutoff_delta else None
    
    # Single query to get cards
    card_query = select(Card)
    if search:
        card_query = card_query.where(Card.name.ilike(f"%{search}%"))
    if product_type:
        # Case-insensitive match for better UX
        card_query = card_query.where(Card.product_type.ilike(product_type))
        
    card_query = card_query.offset(skip).limit(limit)
    cards = session.exec(card_query).all()
    
    if not cards:
        return []
    
    # Batch fetch ALL snapshots for these cards in ONE query
    card_ids = [c.id for c in cards]
    snapshot_query = select(MarketSnapshot).where(MarketSnapshot.card_id.in_(card_ids))
    if cutoff_time:
        snapshot_query = snapshot_query.where(MarketSnapshot.timestamp >= cutoff_time)
    snapshot_query = snapshot_query.order_by(MarketSnapshot.card_id, desc(MarketSnapshot.timestamp))
    all_snapshots = session.exec(snapshot_query).all()
    
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
    rarities = session.exec(select(Rarity)).all()
    rarity_map = {r.id: r.name for r in rarities}
    
    # Batch fetch actual LAST SALE price (Postgres DISTINCT ON)
    last_sale_map = {}
    vwap_map = {}
    prev_price_map = {} # Price N hours ago
    active_stats_map = {}  # Computed from MarketPrice for fresh lowest_ask/inventory

    if card_ids:
        try:
            from sqlalchemy import text

            # Use parameterized queries to prevent SQL injection
            # PostgreSQL ANY() syntax for array parameters
            # Filter out NULL sold_date to ensure valid last sale data
            query = text("""
                SELECT DISTINCT ON (card_id) card_id, price, treatment
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                AND listing_type = 'sold'
                AND sold_date IS NOT NULL
                ORDER BY card_id, sold_date DESC
            """)
            results = session.execute(query, {"card_ids": card_ids}).all()
            last_sale_map = {row[0]: {'price': row[1], 'treatment': row[2]} for row in results}

            # Calculate VWAP with proper parameter binding
            # Always filter out NULL sold_date to avoid including invalid records
            if cutoff_time:
                vwap_query = text("""
                    SELECT card_id, AVG(price) as vwap
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    AND sold_date IS NOT NULL
                    AND sold_date >= :cutoff_time
                    GROUP BY card_id
                """)
                vwap_results = session.execute(vwap_query, {"card_ids": card_ids, "cutoff_time": cutoff_time}).all()
            else:
                vwap_query = text("""
                    SELECT card_id, AVG(price) as vwap
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
                    AND sold_date IS NOT NULL
                    GROUP BY card_id
                """)
                vwap_results = session.execute(vwap_query, {"card_ids": card_ids}).all()
            vwap_map = {row[0]: row[1] for row in vwap_results}

            # Fetch LIVE active listing stats (lowest_ask, inventory) from MarketPrice
            # This ensures fresh data even when snapshots are stale
            active_stats_query = text("""
                SELECT card_id, MIN(price) as lowest_ask, COUNT(*) as inventory
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                AND listing_type = 'active'
                GROUP BY card_id
            """)
            active_stats_results = session.execute(active_stats_query, {"card_ids": card_ids}).all()
            active_stats_map = {row[0]: {'lowest_ask': row[1], 'inventory': row[2]} for row in active_stats_results}

            # Fetch Previous Sale Price (oldest sale overall for trend comparison)
            # Compare most recent sale vs oldest recorded sale to show all-time trend
            # Filter out NULL sold_date to ensure valid ordering
            prev_price_query = text("""
                SELECT DISTINCT ON (card_id) card_id, price
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                AND listing_type = 'sold'
                AND sold_date IS NOT NULL
                ORDER BY card_id, sold_date ASC
            """)
            prev_results = session.execute(prev_price_query, {"card_ids": card_ids}).all()
            prev_price_map = {row[0]: row[1] for row in prev_results}

        except Exception as e:
            print(f"Error fetching sales data: {e}")
    
    # Build results
    results = []
    for card in cards:
        card_snaps = snapshots_by_card.get(card.id, [])
        latest_snap = card_snaps[0] if card_snaps else None
        oldest_snap = card_snaps[-1] if card_snaps else None # Oldest in the time window
        
        # Use actual last sale if available, otherwise fallback to avg
        last_sale_data = last_sale_map.get(card.id)
        last_price = last_sale_data['price'] if last_sale_data else None
        last_treatment = last_sale_data['treatment'] if last_sale_data else None
        
        if last_price is None and latest_snap:
            last_price = latest_snap.avg_price
            
        # Get VWAP
        vwap = vwap_map.get(card.id)
        
        # 1. Market Trend Delta (Sales-based)
        avg_delta = 0.0
        
        # Strategy A: Use actual sales delta (Current vs Prev Close) - Most Accurate
        prev_close = prev_price_map.get(card.id)
        if last_price and prev_close and prev_close > 0:
             avg_delta = ((last_price - prev_close) / prev_close) * 100
             
        # Strategy B: Fallback to Snapshot Delta (if sales gap is too large or missing)
        elif latest_snap and oldest_snap and oldest_snap.avg_price > 0:
            if latest_snap.id != oldest_snap.id:
                avg_delta = ((latest_snap.avg_price - oldest_snap.avg_price) / oldest_snap.avg_price) * 100

                
        # 2. Deal Rating Delta (Last Sale vs Current Avg Price)
        deal_delta = 0.0
        if last_price and latest_snap and latest_snap.avg_price > 0:
             deal_delta = ((last_price - latest_snap.avg_price) / latest_snap.avg_price) * 100
        
        # Get LIVE active stats from MarketPrice (preferred), fallback to snapshot only if None
        # Use explicit None check since 0 is valid (no active listings)
        live_active = active_stats_map.get(card.id, {})
        live_lowest = live_active.get('lowest_ask')
        live_inv = live_active.get('inventory')
        lowest_ask = live_lowest if live_lowest is not None else (latest_snap.lowest_ask if latest_snap else None)
        inventory = live_inv if live_inv is not None else (latest_snap.inventory if latest_snap else 0)

        c_out = CardOut(
            id=card.id,
            name=card.name,
            set_name=card.set_name,
            rarity_id=card.rarity_id,
            rarity_name=rarity_map.get(card.rarity_id, "Unknown"),
            latest_price=last_price,
            volume_30d=latest_snap.volume if latest_snap else 0,
            price_delta_24h=avg_delta, # Now reflects Market Trend (Avg Price)
            last_sale_diff=deal_delta, # Now reflects Deal Rating (Last Sale vs Avg)
            last_sale_treatment=last_treatment, # Added treatment
            lowest_ask=lowest_ask,  # Use LIVE data from MarketPrice
            inventory=inventory,    # Use LIVE data from MarketPrice
            product_type=card.product_type if hasattr(card, 'product_type') else "Single",
            max_price=latest_snap.max_price if latest_snap else None,
            avg_price=latest_snap.avg_price if latest_snap else None,
            vwap=vwap if vwap else (latest_snap.avg_price if latest_snap else None),
            last_updated=latest_snap.timestamp if latest_snap else None # Add last_updated from snapshot
        )
        results.append(c_out)
    
    # Convert to dict for caching
    results_dict = [r.model_dump(mode='json') for r in results]
    set_cache(cache_key, results_dict, ttl=300)  # 5 minutes
    
    return JSONResponse(content=results_dict, headers={"X-Cache": "MISS"})

def get_card_by_id_or_slug(session: Session, card_identifier: str) -> Card:
    """Resolve card by ID (numeric) or slug (string)."""
    # Try numeric ID first
    if card_identifier.isdigit():
        card = session.get(Card, int(card_identifier))
        if card:
            return card
    # Try slug lookup
    card = session.exec(select(Card).where(Card.slug == card_identifier)).first()
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
    stmt = select(MarketSnapshot).where(MarketSnapshot.card_id == card.id).order_by(desc(MarketSnapshot.timestamp)).limit(50)
    snapshots = session.exec(stmt).all()
    
    latest_snap = snapshots[0] if snapshots else None
    # Rough approximation for "oldest in recent history" since we don't have time_period param here easily
    # Let's just take the last one fetched (up to 50 snapshots ago)
    oldest_snap = snapshots[-1] if snapshots else None
    
    # Fetch actual last sale
    last_sale = session.exec(
        select(MarketPrice)
        .where(MarketPrice.card_id == card.id, MarketPrice.listing_type == "sold")
        .order_by(desc(MarketPrice.sold_date))
        .limit(1)
    ).first()
    
    real_price = last_sale.price if last_sale else (latest_snap.avg_price if latest_snap else None)
    real_treatment = last_sale.treatment if last_sale else None
    
    # Calculate VWAP and 30-day volume for single card
    vwap = None
    prev_close = None
    volume_30d = 0
    try:
        from sqlalchemy import text
        cutoff_30d = datetime.utcnow() - timedelta(days=30)

        # Get VWAP and volume in one query
        stats_q = text("""
            SELECT AVG(price), COUNT(*) FROM marketprice
            WHERE card_id = :cid AND listing_type = 'sold' AND sold_date >= :cutoff
        """)
        stats_res = session.execute(stats_q, {"cid": card.id, "cutoff": cutoff_30d}).first()
        if stats_res:
            vwap = stats_res[0]
            volume_30d = stats_res[1] or 0

        # Fetch Prev Close (30 days ago for trend calculation)
        prev_q = text("""
            SELECT price FROM marketprice
            WHERE card_id = :cid AND listing_type = 'sold' AND sold_date < :cutoff
            ORDER BY sold_date DESC LIMIT 1
        """)
        prev_res = session.execute(prev_q, {"cid": card.id, "cutoff": cutoff_30d}).first()
        prev_close = prev_res[0] if prev_res else None

    except Exception:
        pass

    # 1. Market Trend Delta
    avg_delta = 0.0
    
    # Strategy A: Sales-based Delta
    if real_price and prev_close and prev_close > 0:
        avg_delta = ((real_price - prev_close) / prev_close) * 100
        
    # Strategy B: Snapshot Fallback
    elif latest_snap and oldest_snap and oldest_snap.avg_price > 0 and latest_snap.id != oldest_snap.id:
        avg_delta = ((latest_snap.avg_price - oldest_snap.avg_price) / oldest_snap.avg_price) * 100
            
    # 2. Deal Rating Delta
    deal_delta = 0.0
    if real_price and latest_snap and latest_snap.avg_price > 0:
        deal_delta = ((real_price - latest_snap.avg_price) / latest_snap.avg_price) * 100

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

    c_out = CardOut(
        id=card.id,
        slug=card.slug,  # Include slug for SEO-friendly URLs
        name=card.name,
        set_name=card.set_name,
        rarity_id=card.rarity_id,
        rarity_name=rarity_name,
        latest_price=real_price,
        volume_30d=volume_30d,  # 30-day volume from MarketPrice
        price_delta_24h=avg_delta,
        last_sale_diff=deal_delta,
        last_sale_treatment=real_treatment,
        lowest_ask=lowest_ask,  # Use LIVE data from MarketPrice
        inventory=inventory,    # Use LIVE data from MarketPrice
        product_type=card.product_type if hasattr(card, 'product_type') else "Single",
        max_price=latest_snap.max_price if latest_snap else None,
        avg_price=latest_snap.avg_price if latest_snap else None,
        vwap=vwap if vwap else (latest_snap.avg_price if latest_snap else None),
        last_updated=latest_snap.timestamp if latest_snap else None # Add last_updated from snapshot
    )
    
    # Cache result
    result_dict = c_out.model_dump(mode='json')
    set_cache(cache_key, result_dict, ttl=300)
    
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
    statement = select(MarketSnapshot).where(MarketSnapshot.card_id == card.id).order_by(MarketSnapshot.timestamp.desc())
    snapshot = session.exec(statement).first()

    if not snapshot:
        raise HTTPException(status_code=404, detail="Market data not found for this card")

    return snapshot

@router.get("/{card_id}/history", response_model=List[MarketPriceOut])
def read_sales_history(
    card_id: str,  # Accept string to support both ID and slug
    session: Session = Depends(get_session),
    limit: int = 50,
) -> Any:
    """
    Get sales history (individual sold listings).
    """
    card = get_card_by_id_or_slug(session, card_id)
    statement = select(MarketPrice).where(
        MarketPrice.card_id == card.id,
        MarketPrice.listing_type == "sold"
    ).order_by(desc(MarketPrice.sold_date)).limit(limit)
    prices = session.exec(statement).all()
    return prices

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
    statement = select(MarketPrice).where(
        MarketPrice.card_id == card.id,
        MarketPrice.listing_type == "active"
    ).order_by(desc(MarketPrice.scraped_at)).limit(limit)
    active = session.exec(statement).all()
    return active


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

    cutoff = datetime.utcnow() - timedelta(days=days)

    statement = select(MarketSnapshot).where(
        MarketSnapshot.card_id == card.id,
        MarketSnapshot.timestamp >= cutoff
    ).order_by(desc(MarketSnapshot.timestamp)).limit(limit)

    snapshots = session.exec(statement).all()
    return snapshots
