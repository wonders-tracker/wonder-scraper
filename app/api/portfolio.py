from typing import Any, List
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from app.api import deps
from app.db import get_session
from app.models.portfolio import PortfolioItem
from app.models.card import Card
from app.models.market import MarketSnapshot
from app.models.user import User
from app.schemas import PortfolioItemCreate, PortfolioItemOut

router = APIRouter()

@router.post("/", response_model=PortfolioItemOut)
def create_portfolio_item(
    item_in: PortfolioItemCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Add a card to the user's portfolio.
    """
    # Check if card exists
    card = session.get(Card, item_in.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    item = PortfolioItem(
        user_id=current_user.id,
        card_id=item_in.card_id,
        quantity=item_in.quantity,
        purchase_price=item_in.purchase_price
    )
    session.add(item)
    session.commit()
    session.refresh(item)
    
    # Return with card details (basic)
    return PortfolioItemOut(
        id=item.id,
        user_id=item.user_id,
        card_id=item.card_id,
        quantity=item.quantity,
        purchase_price=item.purchase_price,
        acquired_at=item.acquired_at,
        card_name=card.name,
        card_set=card.set_name
    )

@router.get("/", response_model=List[PortfolioItemOut])
def read_portfolio(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Retrieve user's portfolio with calculated stats.
    """
    stmt = select(PortfolioItem).where(PortfolioItem.user_id == current_user.id)
    items = session.exec(stmt).all()
    
    results = []
    for item in items:
        # Fetch Card Info
        card = session.get(Card, item.card_id)
        
        # Fetch Latest Market Price
        market_stmt = select(MarketSnapshot).where(MarketSnapshot.card_id == item.card_id).order_by(MarketSnapshot.timestamp.desc())
        market_snap = session.exec(market_stmt).first()
        current_price = market_snap.avg_price if market_snap else 0.0
        
        current_value = current_price * item.quantity
        cost_basis = item.purchase_price * item.quantity
        gain_loss = current_value - cost_basis
        gain_loss_percent = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0.0
        
        out = PortfolioItemOut(
            id=item.id,
            user_id=item.user_id,
            card_id=item.card_id,
            quantity=item.quantity,
            purchase_price=item.purchase_price,
            acquired_at=item.acquired_at,
            card_name=card.name if card else "Unknown",
            card_set=card.set_name if card else "",
            current_market_price=current_price,
            current_value=current_value,
            gain_loss=gain_loss,
            gain_loss_percent=gain_loss_percent
        )
        results.append(out)
        
    return results

@router.delete("/{item_id}", response_model=PortfolioItemOut)
def delete_portfolio_item(
    item_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Remove an item from the portfolio.
    """
    item = session.get(PortfolioItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
        
    session.delete(item)
    session.commit()
    
    # Return valid Pydantic model instead of just item object
    # Since the object is deleted, we can't access lazy loaded fields easily, 
    # but we have what we need in the object before deletion or just basic fields.
    # Simpler to return basic info.
    return PortfolioItemOut(
        id=item.id,
        user_id=item.user_id,
        card_id=item.card_id,
        quantity=item.quantity,
        purchase_price=item.purchase_price,
        acquired_at=item.acquired_at
    )

