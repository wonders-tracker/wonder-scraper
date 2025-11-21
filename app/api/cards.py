from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, desc

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
    current_user = Depends(deps.get_current_user)
) -> Any:
    """
    Retrieve cards with latest market data.
    """
    query = select(Card)
    if search:
        query = query.where(Card.name.ilike(f"%{search}%"))
    
    query = query.offset(skip).limit(limit)
    cards = session.exec(query).all()
    
    results = []
    for card in cards:
        # Fetch latest 2 snapshots to calculate delta
        stmt = select(MarketSnapshot).where(MarketSnapshot.card_id == card.id).order_by(desc(MarketSnapshot.timestamp)).limit(2)
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
            latest_price=latest_snap.avg_price if latest_snap else None,
            volume_24h=latest_snap.volume if latest_snap else 0,
            price_delta_24h=delta if latest_snap else None,
            lowest_ask=latest_snap.lowest_ask if latest_snap else None,
            inventory=latest_snap.inventory if latest_snap else 0
        )
        results.append(c_out)
    
    return results

@router.get("/{card_id}", response_model=CardOut)
def read_card(
    card_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(deps.get_current_user)
) -> Any:
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    return card

@router.get("/{card_id}/market", response_model=Optional[MarketSnapshotOut])
def read_market_data(
    card_id: int,
    session: Session = Depends(get_session),
    current_user = Depends(deps.get_current_user)
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
    current_user = Depends(deps.get_current_user)
) -> Any:
    """
    Get sales history (individual sold listings).
    """
    statement = select(MarketPrice).where(MarketPrice.card_id == card_id).order_by(desc(MarketPrice.sold_date)).limit(limit)
    prices = session.exec(statement).all()
    return prices
