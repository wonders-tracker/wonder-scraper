from typing import Any, List, Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select, func, desc
from datetime import datetime, timedelta

from app.api import deps
from app.db import get_session
from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice

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
            period_start = cutoff_time if cutoff_time else datetime.utcnow() - timedelta(hours=24)

            # Use parameterized queries to prevent SQL injection
            query = text("""
                SELECT DISTINCT ON (card_id) card_id, price, treatment, sold_date
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                ORDER BY card_id, sold_date DESC NULLS LAST
            """)
            results = session.execute(query, {"card_ids": card_ids}).all()
            last_sale_map = {row[0]: {'price': row[1], 'treatment': row[2], 'date': row[3]} for row in results}

            # Calculate VWAP with proper parameter binding
            if cutoff_time:
                vwap_query = text("""
                    SELECT card_id, AVG(price) as vwap
                    FROM marketprice
                    WHERE card_id = ANY(:card_ids)
                    AND listing_type = 'sold'
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
                    GROUP BY card_id
                """)
                vwap_results = session.execute(vwap_query, {"card_ids": card_ids}).all()
            vwap_map = {row[0]: row[1] for row in vwap_results}

            # Get oldest sale in period for delta calculation
            oldest_sale_query = text("""
                SELECT DISTINCT ON (card_id) card_id, price, sold_date
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                AND sold_date >= :period_start
                ORDER BY card_id, sold_date ASC
            """)
            oldest_results = session.execute(oldest_sale_query, {"card_ids": card_ids, "period_start": period_start}).all()
            oldest_sale_map = {row[0]: {'price': row[1], 'date': row[2]} for row in oldest_results}

            # Count sales in period for each card
            sales_count_query = text("""
                SELECT card_id, COUNT(*) as sale_count, COUNT(DISTINCT DATE(sold_date)) as unique_days
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                AND sold_date >= :period_start
                GROUP BY card_id
            """)
            sales_count_results = session.execute(sales_count_query, {"card_ids": card_ids, "period_start": period_start}).all()
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
