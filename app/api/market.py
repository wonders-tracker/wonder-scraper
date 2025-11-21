from typing import Any, List
from fastapi import APIRouter, Depends
from sqlmodel import Session, select, func, desc

from app.api import deps
from app.db import get_session
from app.models.card import Card
from app.models.market import MarketSnapshot

router = APIRouter()

@router.get("/overview")
def read_market_overview(
    session: Session = Depends(get_session),
) -> Any:
    """
    Get optimized market overview statistics.
    Returns a list of cards with their latest market snapshot data.
    """
    # We want to fetch all cards and their LATEST market snapshot.
    # In SQLModel/SQLAlchemy, a window function or distinct on is efficient, 
    # but for simplicity and compatibility, we'll fetch all snapshots that are the "latest" per card.
    
    # Optimized Query: Join Card with MarketSnapshot
    # We use a subquery or just distinct(card_id) order by timestamp desc if supported,
    # but distinct on is Postgres specific. 
    
    # Strategy: Fetch all cards + their latest snapshot in one go.
    # Since we have 427 cards, we can just fetch the latest snapshot for each.
    
    # Let's use a subquery to find max id (or timestamp) per card_id
    # subq = select(func.max(MarketSnapshot.id)).group_by(MarketSnapshot.card_id)
    
    # Actually, joining Card and MarketSnapshot where MarketSnapshot is the latest is standard.
    # For now, to ensure it's "instant", we will just query Card and join the latest Snapshot.
    
    # Postgres DISTINCT ON is fastest:
    stmt = select(Card, MarketSnapshot).join(MarketSnapshot, isouter=True).distinct(Card.id).order_by(Card.id, desc(MarketSnapshot.timestamp))
    
    results = session.exec(stmt).all()
    
    overview_data = []
    for card, snapshot in results:
        overview_data.append({
            "id": card.id,
            "name": card.name,
            "set_name": card.set_name,
            "rarity_id": card.rarity_id,
            "latest_price": snapshot.avg_price if snapshot else 0.0,
            "volume_24h": snapshot.volume if snapshot else 0,
            "price_delta_24h": 0.0, # Placeholder for speed
            "market_cap": (snapshot.avg_price if snapshot else 0) * (snapshot.volume if snapshot else 0)
        })
        
    return overview_data
