from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, desc
from datetime import datetime, timedelta

from app.api import deps
from app.db import get_session
from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice
from app.schemas import CardOut, MarketSnapshotOut, MarketPriceOut

router = APIRouter()

@router.get("/", response_model=List[CardOut])
def read_cards(
    session: Session = Depends(get_session),
    skip: int = 0,
    limit: int = 100,
    search: Optional[str] = None,
    time_period: Optional[str] = Query(default="24h", regex="^(24h|7d|30d|90d|all)$"),
) -> Any:
    """
    Retrieve cards with latest market data - OPTIMIZED for Neon.
    Single batch query instead of N+1.
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
    
    # Single query to get cards
    card_query = select(Card)
    if search:
        card_query = card_query.where(Card.name.ilike(f"%{search}%"))
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
        if len(snapshots_by_card[snap.card_id]) < 2:  # Only need latest 2
            snapshots_by_card[snap.card_id].append(snap)
    
    # Batch fetch rarities
    rarities = session.exec(select(Rarity)).all()
    rarity_map = {r.id: r.name for r in rarities}
    
    # Build results
    results = []
    for card in cards:
        card_snaps = snapshots_by_card.get(card.id, [])
        latest_snap = card_snaps[0] if len(card_snaps) > 0 else None
        prev_snap = card_snaps[1] if len(card_snaps) > 1 else None
        
        delta = 0.0
        if latest_snap and prev_snap and prev_snap.avg_price > 0:
            delta = ((latest_snap.avg_price - prev_snap.avg_price) / prev_snap.avg_price) * 100
        
        c_out = CardOut(
            id=card.id,
            name=card.name,
            set_name=card.set_name,
            rarity_id=card.rarity_id,
            rarity_name=rarity_map.get(card.rarity_id, "Unknown"),
            latest_price=latest_snap.avg_price if latest_snap else None,
            volume_24h=latest_snap.volume if latest_snap else 0,
            price_delta_24h=delta if latest_snap else None,
            lowest_ask=latest_snap.lowest_ask if latest_snap else None,
            inventory=latest_snap.inventory if latest_snap else 0,
            product_type=card.product_type if hasattr(card, 'product_type') else "Single",
            max_price=latest_snap.max_price if latest_snap else None
        )
        results.append(c_out)
    
    return results

@router.get("/{card_id}", response_model=CardOut)
def read_card(
    card_id: int,
    session: Session = Depends(get_session),
) -> Any:
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    
    # Fetch rarity name
    rarity_name = "Unknown"
    if card.rarity_id:
        rarity = session.get(Rarity, card.rarity_id)
        if rarity:
            rarity_name = rarity.name
    
    # Fetch latest 2 snapshots to calculate delta
    stmt = select(MarketSnapshot).where(MarketSnapshot.card_id == card_id).order_by(desc(MarketSnapshot.timestamp)).limit(2)
    snapshots = session.exec(stmt).all()
    
    latest_snap = snapshots[0] if snapshots else None
    prev_snap = snapshots[1] if len(snapshots) > 1 else None
    
    delta = 0.0
    if latest_snap and prev_snap and prev_snap.avg_price > 0:
        delta = ((latest_snap.avg_price - prev_snap.avg_price) / prev_snap.avg_price) * 100
            
    c_out = CardOut(
        id=card.id,
        name=card.name,
        set_name=card.set_name,
        rarity_id=card.rarity_id,
        rarity_name=rarity_name,
        latest_price=latest_snap.avg_price if latest_snap else None,
        volume_24h=latest_snap.volume if latest_snap else 0,
        price_delta_24h=delta if latest_snap else None,
        lowest_ask=latest_snap.lowest_ask if latest_snap else None,
        inventory=latest_snap.inventory if latest_snap else 0,
        product_type=card.product_type if hasattr(card, 'product_type') else "Single",
        max_price=latest_snap.max_price if latest_snap else None
    )
    
    return c_out

@router.get("/{card_id}/market", response_model=Optional[MarketSnapshotOut])
def read_market_data(
    card_id: int,
    session: Session = Depends(get_session),
) -> Any:
    """
    Get latest market snapshot for a card.
    """
    statement = select(MarketSnapshot).where(MarketSnapshot.card_id == card_id).order_by(MarketSnapshot.timestamp.desc())
    snapshot = session.exec(statement).first()
    
    if not snapshot:
        raise HTTPException(status_code=404, detail="Market data not found for this card")
        
    return snapshot

@router.get("/{card_id}/history", response_model=List[MarketPriceOut])
def read_sales_history(
    card_id: int,
    session: Session = Depends(get_session),
    limit: int = 50,
) -> Any:
    """
    Get sales history (individual sold listings).
    """
    statement = select(MarketPrice).where(
        MarketPrice.card_id == card_id,
        MarketPrice.listing_type == "sold"
    ).order_by(desc(MarketPrice.sold_date)).limit(limit)
    prices = session.exec(statement).all()
    return prices

@router.get("/{card_id}/active", response_model=List[MarketPriceOut])
def read_active_listings(
    card_id: int,
    session: Session = Depends(get_session),
    limit: int = 50,
) -> Any:
    """
    Get active listings for a card.
    """
    statement = select(MarketPrice).where(
        MarketPrice.card_id == card_id,
        MarketPrice.listing_type == "active"
    ).order_by(desc(MarketPrice.scraped_at)).limit(limit)
    active = session.exec(statement).all()
    return active
