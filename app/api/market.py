from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query, HTTPException, Request
from sqlmodel import Session, select, func, desc
from datetime import datetime, timedelta

from app.api import deps
from app.db import get_session
from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice
from app.services.price_calculator import PriceCalculator

router = APIRouter()

@router.get("/treatments")
def read_treatments(
    session: Session = Depends(get_session),
) -> Any:
    """
    Get price floors by treatment.
    """
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
    results = session.exec(query).all()
    return [{"name": row[0], "min_price": float(row[1]), "count": int(row[2])} for row in results]

@router.get("/overview")
def read_market_overview(
    session: Session = Depends(get_session),
    time_period: Optional[str] = Query(default="24h", regex="^(24h|7d|30d|90d|all)$"),
) -> Any:
    """
    Get robust market overview statistics with temporal data.
    """
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
    
    # Fetch all cards
    cards = session.exec(select(Card)).all()
    if not cards:
        return []
    
    card_ids = [c.id for c in cards]
    
    # Batch fetch snapshots
    snapshot_query = select(MarketSnapshot).where(MarketSnapshot.card_id.in_(card_ids))
    if cutoff_time:
        snapshot_query = snapshot_query.where(MarketSnapshot.timestamp >= cutoff_time)
    snapshot_query = snapshot_query.order_by(MarketSnapshot.card_id, desc(MarketSnapshot.timestamp))
    all_snapshots = session.exec(snapshot_query).all()
    
    snapshots_by_card = {}
    for snap in all_snapshots:
        if snap.card_id not in snapshots_by_card:
            snapshots_by_card[snap.card_id] = []
        snapshots_by_card[snap.card_id].append(snap)
        
    # Batch fetch actual LAST SALE price (Postgres DISTINCT ON)
    last_sale_map = {}
    vwap_map = {}
    oldest_sale_map = {}
    sales_count_map = {}
    if card_ids:
        try:
            from sqlalchemy import text
            id_list = ", ".join(str(cid) for cid in card_ids)
            period_start = cutoff_time if cutoff_time else datetime.utcnow() - timedelta(hours=24)

            query = text(f"""
                SELECT DISTINCT ON (card_id) card_id, price, treatment, sold_date
                FROM marketprice
                WHERE card_id IN ({id_list}) AND listing_type = 'sold'
                ORDER BY card_id, sold_date DESC NULLS LAST
            """)
            results = session.exec(query).all()
            last_sale_map = {row[0]: {'price': row[1], 'treatment': row[2], 'date': row[3]} for row in results}

            # Calculate VWAP
            vwap_query = text(f"""
                SELECT card_id, AVG(price) as vwap
                FROM marketprice
                WHERE card_id IN ({id_list})
                AND listing_type = 'sold'
                {f"AND sold_date >= '{cutoff_time}'" if cutoff_time else ""}
                GROUP BY card_id
            """)
            vwap_results = session.exec(vwap_query).all()
            vwap_map = {row[0]: row[1] for row in vwap_results}

            # Get oldest sale in period for delta calculation
            # Also get sale counts to validate minimum data requirements
            oldest_sale_query = text(f"""
                SELECT DISTINCT ON (card_id) card_id, price, sold_date
                FROM marketprice
                WHERE card_id IN ({id_list}) AND listing_type = 'sold'
                AND sold_date >= '{period_start}'
                ORDER BY card_id, sold_date ASC
            """)
            oldest_results = session.exec(oldest_sale_query).all()
            oldest_sale_map = {row[0]: {'price': row[1], 'date': row[2]} for row in oldest_results}

            # Count sales in period for each card
            sales_count_query = text(f"""
                SELECT card_id, COUNT(*) as sale_count, COUNT(DISTINCT DATE(sold_date)) as unique_days
                FROM marketprice
                WHERE card_id IN ({id_list}) AND listing_type = 'sold'
                AND sold_date >= '{period_start}'
                GROUP BY card_id
            """)
            sales_count_results = session.exec(sales_count_query).all()
            sales_count_map = {row[0]: {'count': row[1], 'unique_days': row[2]} for row in sales_count_results}

        except Exception as e:
            print(f"Error fetching last sales: {e}")

    overview_data = []
    for card in cards:
        card_snaps = snapshots_by_card.get(card.id, [])
        latest_snap = card_snaps[0] if card_snaps else None
        oldest_snap = card_snaps[-1] if card_snaps else None
        
        last_sale_data = last_sale_map.get(card.id)
        last_price = last_sale_data['price'] if last_sale_data else None
        
        if last_price is None and latest_snap:
            last_price = latest_snap.avg_price
            
        # Get VWAP
        vwap = vwap_map.get(card.id)
        effective_price = vwap if vwap else (latest_snap.avg_price if latest_snap else 0.0)
            
        # Market Trend Delta - Use batch-fetched oldest sale with validation
        avg_delta = 0.0
        oldest_sale_data = oldest_sale_map.get(card.id)
        sales_stats = sales_count_map.get(card.id)
        last_sale_data_full = last_sale_map.get(card.id)

        # Require minimum data: at least 2 sales on different days
        if (oldest_sale_data and last_sale_data_full and sales_stats and
            sales_stats['count'] >= 2 and sales_stats['unique_days'] >= 2):

            oldest_price = oldest_sale_data['price']
            oldest_date = oldest_sale_data['date']
            newest_date = last_sale_data_full.get('date') if isinstance(last_sale_data_full, dict) else None

            # Only calculate if we have different dates and valid prices
            if oldest_price > 0 and last_price and last_price > 0:
                # Ensure the sales are actually from different times
                if newest_date and oldest_date and newest_date > oldest_date:
                    avg_delta = ((last_price - oldest_price) / oldest_price) * 100

        # Fallback to snapshot comparison if sales data insufficient
        if avg_delta == 0.0 and latest_snap and oldest_snap and oldest_snap.avg_price > 0 and latest_snap.id != oldest_snap.id:
            avg_delta = ((latest_snap.avg_price - oldest_snap.avg_price) / oldest_snap.avg_price) * 100
                
        # Deal Rating Delta
        deal_delta = 0.0
        if last_price and latest_snap and latest_snap.avg_price > 0:
             deal_delta = ((last_price - latest_snap.avg_price) / latest_snap.avg_price) * 100

        overview_data.append({
            "id": card.id,
            "name": card.name,
            "set_name": card.set_name,
            "rarity_id": card.rarity_id,
            "latest_price": last_price or 0.0,
            "avg_price": latest_snap.avg_price if latest_snap else 0.0,
            "vwap": effective_price,
            "volume_period": latest_snap.volume if latest_snap else 0, 
            "volume_change": (latest_snap.volume - oldest_snap.volume) if (latest_snap and oldest_snap) else 0,
            "price_delta_period": avg_delta,
            "deal_rating": deal_delta,
            "market_cap": (last_price or 0) * (latest_snap.volume if latest_snap else 0)
        })
        
    return overview_data

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
    query = select(MarketPrice, Card.name, Card.id).join(Card).where(MarketPrice.listing_type == "sold").order_by(desc(MarketPrice.sold_date)).limit(limit)
    results = session.exec(query).all()
    
    activity_data = []
    for sale, card_name, card_id in results:
        activity_data.append({
            "card_id": card_id,
            "card_name": card_name,
            "price": sale.price,
            "date": sale.sold_date,
            "treatment": sale.treatment,
            "platform": sale.platform
        })

    return activity_data


# ============================================================================
# Advanced Price Tracking Endpoints
# ============================================================================

@router.get("/floor")
async def read_floor_prices(
    request: Request,
    session: Session = Depends(get_session),
    product_type: str = Query(default="Single"),
    period: str = Query(default="30d", regex="^(1d|3d|7d|14d|30d|90d|all)$"),
    min_sales: int = Query(default=3, ge=1),
) -> Any:
    """
    Get floor prices by rarity, treatment, and combination.

    Rate limit: 30/minute per IP

    Returns comprehensive floor price data for market analysis.
    """
    calc = PriceCalculator(session)

    by_rarity = calc.calculate_floor_by_rarity(
        rarity_id=None,
        period=period,
        product_type=product_type
    )

    by_treatment = calc.calculate_floor_by_treatment(
        treatment=None,
        period=period,
        product_type=product_type
    )

    by_combination = calc.calculate_floor_by_combination(
        period=period,
        product_type=product_type,
        min_sales=min_sales
    )

    return {
        "product_type": product_type,
        "period": period,
        "by_rarity": by_rarity,
        "by_treatment": by_treatment,
        "by_combination": by_combination
    }


@router.get("/time-series")
def read_time_series(
    session: Session = Depends(get_session),
    card_id: Optional[int] = Query(default=None),
    product_type: Optional[str] = Query(default=None),
    interval: str = Query(default="1d", regex="^(1d|1w|1m)$"),
    period: str = Query(default="30d", regex="^(7d|14d|30d|90d|1y)$"),
) -> Any:
    """
    Get time-series price data with VWAP, volume, and floor prices.

    Use card_id for specific card or product_type for aggregate data.
    """
    if not card_id and not product_type:
        raise HTTPException(
            status_code=400,
            detail="Either card_id or product_type must be specified"
        )

    calc = PriceCalculator(session)

    data = calc.get_time_series(
        card_id=card_id,
        interval=interval,
        period=period,
        product_type=product_type
    )

    return {
        "card_id": card_id,
        "product_type": product_type,
        "interval": interval,
        "period": period,
        "data": data
    }


@router.get("/bid-ask")
def read_bid_ask_spreads(
    session: Session = Depends(get_session),
    product_type: str = Query(default="Single"),
    limit: int = Query(default=50, le=200),
) -> Any:
    """
    Get current bid/ask spreads and price-to-sale ratios.

    Useful for finding arbitrage opportunities and market inefficiencies.
    """
    # Get cards with active listings
    cards = session.exec(
        select(Card)
        .where(Card.product_type == product_type)
        .limit(limit)
    ).all()

    calc = PriceCalculator(session)
    results = []

    for card in cards:
        spread = calc.calculate_bid_ask_spread(card.id)
        p2s = calc.calculate_price_to_sale(card.id, "30d")

        if spread and spread["lowest_ask"] > 0:
            results.append({
                "card_id": card.id,
                "name": card.name,
                "set_name": card.set_name,
                "lowest_ask": spread["lowest_ask"],
                "highest_bid": spread["highest_bid"],
                "spread_amount": spread["spread_amount"],
                "spread_percent": spread["spread_percent"],
                "price_to_sale": p2s
            })

    # Sort by spread percent descending (highest spreads first)
    results.sort(key=lambda x: x["spread_percent"], reverse=True)

    return {
        "product_type": product_type,
        "count": len(results),
        "cards": results
    }


@router.get("/metrics/{card_id}")
def read_comprehensive_metrics(
    card_id: int,
    session: Session = Depends(get_session),
    period: str = Query(default="30d", regex="^(1d|3d|7d|14d|30d|90d|all)$"),
) -> Any:
    """
    Get all calculated price metrics for a specific card.

    Includes VWAP, EMA, price deltas, bid/ask spread, and price-to-sale ratio.
    """
    # Verify card exists
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    calc = PriceCalculator(session)
    metrics = calc.get_comprehensive_metrics(card_id, period)

    # Get latest snapshot for context
    snapshot = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.card_id == card_id)
        .order_by(MarketSnapshot.timestamp.desc())
    ).first()

    return {
        "card_id": card_id,
        "name": card.name,
        "set_name": card.set_name,
        "product_type": card.product_type,
        "period": period,
        # Snapshot data
        "min_price": snapshot.min_price if snapshot else None,
        "max_price": snapshot.max_price if snapshot else None,
        "avg_price": snapshot.avg_price if snapshot else None,
        "volume": snapshot.volume if snapshot else 0,
        "lowest_ask": snapshot.lowest_ask if snapshot else None,
        "highest_bid": snapshot.highest_bid if snapshot else None,
        "inventory": snapshot.inventory if snapshot else 0,
        # Calculated metrics
        **metrics
    }
