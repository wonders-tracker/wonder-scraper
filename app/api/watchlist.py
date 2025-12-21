"""
Watchlist / Price Alert API Endpoints
"""

from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import datetime, timezone

from app.api import deps
from app.db import get_session
from app.models.user import User
from app.models.card import Card
from app.models.watchlist import Watchlist, EmailPreferences

router = APIRouter()


# ============== SCHEMAS ==============


class WatchlistCreate(BaseModel):
    card_id: int
    alert_enabled: bool = True
    alert_type: str = "below"  # 'above', 'below', 'any'
    target_price: Optional[float] = None
    treatment: Optional[str] = None
    notify_email: bool = True
    notes: Optional[str] = None


class WatchlistUpdate(BaseModel):
    alert_enabled: Optional[bool] = None
    alert_type: Optional[str] = None
    target_price: Optional[float] = None
    treatment: Optional[str] = None
    notify_email: Optional[bool] = None
    notes: Optional[str] = None


class WatchlistOut(BaseModel):
    id: int
    card_id: int
    alert_enabled: bool
    alert_type: str
    target_price: Optional[float]
    treatment: Optional[str]
    notify_email: bool
    notes: Optional[str]
    created_at: datetime

    # Card details for display
    card_name: Optional[str] = None
    card_set: Optional[str] = None
    card_slug: Optional[str] = None
    current_price: Optional[float] = None

    model_config = {"from_attributes": True}


class EmailPreferencesUpdate(BaseModel):
    daily_digest: Optional[bool] = None
    weekly_report: Optional[bool] = None
    portfolio_summary: Optional[bool] = None
    price_alerts: Optional[bool] = None
    new_listings: Optional[bool] = None
    digest_hour: Optional[int] = None
    digest_day: Optional[int] = None


class EmailPreferencesOut(BaseModel):
    daily_digest: bool
    weekly_report: bool
    portfolio_summary: bool
    price_alerts: bool
    new_listings: bool
    digest_hour: int
    digest_day: int

    model_config = {"from_attributes": True}


# ============== WATCHLIST ENDPOINTS ==============


@router.get("", response_model=List[WatchlistOut])
def get_watchlist(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Get user's watchlist with card details."""
    items = session.exec(select(Watchlist).where(Watchlist.user_id == current_user.id)).all()

    result = []
    for item in items:
        card = session.get(Card, item.card_id)
        out = WatchlistOut.model_validate(item)
        if card:
            out.card_name = card.name
            out.card_set = card.set_name
            out.card_slug = card.slug
            out.current_price = getattr(card, "floor_price", None)  # floor_price is computed, not on model
        result.append(out)

    return result


@router.post("", response_model=WatchlistOut)
def add_to_watchlist(
    item_in: WatchlistCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Add a card to watchlist."""
    # Check if card exists
    card = session.get(Card, item_in.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if already watching
    existing = session.exec(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.card_id == item_in.card_id)
    ).first()

    if existing:
        raise HTTPException(status_code=400, detail="Card already in watchlist")

    # Create watchlist entry
    db_item = Watchlist(user_id=current_user.id, **item_in.model_dump())
    session.add(db_item)
    session.commit()
    session.refresh(db_item)

    out = WatchlistOut.model_validate(db_item)
    out.card_name = card.name
    out.card_set = card.set_name
    out.card_slug = card.slug
    out.current_price = getattr(card, "floor_price", None)

    return out


@router.get("/{card_id}", response_model=Optional[WatchlistOut])
def get_watchlist_item(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Check if user is watching a specific card."""
    item = session.exec(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.card_id == card_id)
    ).first()

    if not item:
        return None

    card = session.get(Card, card_id)
    out = WatchlistOut.model_validate(item)
    if card:
        out.card_name = card.name
        out.card_set = card.set_name
        out.card_slug = card.slug
        out.current_price = getattr(card, "floor_price", None)

    return out


@router.put("/{card_id}", response_model=WatchlistOut)
def update_watchlist_item(
    card_id: int,
    item_in: WatchlistUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Update watchlist settings for a card."""
    item = session.exec(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.card_id == card_id)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Card not in watchlist")

    update_data = item_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(item, key, value)

    item.updated_at = datetime.now(timezone.utc)
    session.add(item)
    session.commit()
    session.refresh(item)

    card = session.get(Card, card_id)
    out = WatchlistOut.model_validate(item)
    if card:
        out.card_name = card.name
        out.card_set = card.set_name
        out.card_slug = card.slug
        out.current_price = getattr(card, "floor_price", None)

    return out


@router.delete("/{card_id}")
def remove_from_watchlist(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Remove a card from watchlist."""
    item = session.exec(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.card_id == card_id)
    ).first()

    if not item:
        raise HTTPException(status_code=404, detail="Card not in watchlist")

    session.delete(item)
    session.commit()

    return {"message": "Removed from watchlist", "card_id": card_id}


# ============== EMAIL PREFERENCES ==============


@router.get("/preferences/email", response_model=EmailPreferencesOut)
def get_email_preferences(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Get user's email notification preferences."""
    prefs = session.exec(select(EmailPreferences).where(EmailPreferences.user_id == current_user.id)).first()

    if not prefs:
        # Return defaults
        return EmailPreferencesOut(
            daily_digest=False,
            weekly_report=True,
            portfolio_summary=True,
            price_alerts=True,
            new_listings=False,
            digest_hour=9,
            digest_day=0,
        )

    return EmailPreferencesOut.model_validate(prefs)


@router.put("/preferences/email", response_model=EmailPreferencesOut)
def update_email_preferences(
    prefs_in: EmailPreferencesUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Update user's email notification preferences."""
    prefs = session.exec(select(EmailPreferences).where(EmailPreferences.user_id == current_user.id)).first()

    if not prefs:
        # Create new preferences
        prefs = EmailPreferences(user_id=current_user.id)

    update_data = prefs_in.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(prefs, key, value)

    prefs.updated_at = datetime.now(timezone.utc)
    session.add(prefs)
    session.commit()
    session.refresh(prefs)

    return EmailPreferencesOut.model_validate(prefs)


# ============== QUICK TOGGLE (for split button) ==============


@router.post("/{card_id}/toggle")
def toggle_watchlist(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Toggle watching a card (add/remove). For quick button actions."""
    # Check if card exists
    card = session.get(Card, card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check if already watching
    existing = session.exec(
        select(Watchlist).where(Watchlist.user_id == current_user.id, Watchlist.card_id == card_id)
    ).first()

    if existing:
        # Remove from watchlist
        session.delete(existing)
        session.commit()
        return {"watching": False, "card_id": card_id}
    else:
        # Add to watchlist with defaults
        db_item = Watchlist(
            user_id=current_user.id, card_id=card_id, alert_enabled=True, alert_type="below", notify_email=True
        )
        session.add(db_item)
        session.commit()
        return {"watching": True, "card_id": card_id}
