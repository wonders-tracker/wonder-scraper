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
    time_period: Optional[str] = Query(default="30d", pattern="^(7d|30d|90d|all)$"),
) -> Any:
    """
    Get robust market overview statistics with temporal data.
    """
    # Calculate time cutoff
    time_cutoffs = {
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
    floor_price_map = {}
    if card_ids:
        try:
            from sqlalchemy import text
            period_start = cutoff_time if cutoff_time else datetime.utcnow() - timedelta(hours=24)

            # Use parameterized queries to prevent SQL injection
            # Use COALESCE(sold_date, scraped_at) to include sales with NULL sold_date
            query = text("""
                SELECT DISTINCT ON (card_id) card_id, price, treatment, COALESCE(sold_date, scraped_at) as effective_date
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                ORDER BY card_id, COALESCE(sold_date, scraped_at) DESC
            """)
            results = session.execute(query, {"card_ids": card_ids}).all()
            last_sale_map = {row[0]: {'price': row[1], 'treatment': row[2], 'date': row[3]} for row in results}

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
            oldest_results = session.execute(oldest_sale_query, {"card_ids": card_ids, "period_start": period_start}).all()
            oldest_sale_map = {row[0]: {'price': row[1], 'date': row[2]} for row in oldest_results}

            # Count sales in period for each card
            sales_count_query = text("""
                SELECT card_id, COUNT(*) as sale_count, COUNT(DISTINCT DATE(COALESCE(sold_date, scraped_at))) as unique_days
                FROM marketprice
                WHERE card_id = ANY(:card_ids) AND listing_type = 'sold'
                AND COALESCE(sold_date, scraped_at) >= :period_start
                GROUP BY card_id
            """)
            sales_count_results = session.execute(sales_count_query, {"card_ids": card_ids, "period_start": period_start}).all()
            sales_count_map = {row[0]: {'count': row[1], 'unique_days': row[2]} for row in sales_count_results}

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
        last_price = last_sale_data['price'] if last_sale_data else None
        
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
        if last_price and floor_price and floor_price > 0 and sales_stats and sales_stats['count'] >= 2:
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
                
        # Deal Rating Delta
        deal_delta = 0.0
        if last_price and latest_snap and latest_snap.avg_price > 0:
             deal_delta = ((last_price - latest_snap.avg_price) / latest_snap.avg_price) * 100

        # Use actual sales count from MarketPrice (more accurate than snapshot volume)
        period_volume = sales_stats['count'] if sales_stats else 0

        overview_data.append({
            "id": card.id,
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
            "market_cap": (last_price or 0) * period_volume
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
