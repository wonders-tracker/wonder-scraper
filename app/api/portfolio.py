from typing import Any, List, Optional
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, func, desc

from app.api import deps
from app.db import get_session
from app.models.portfolio import PortfolioItem, PortfolioCard
from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice
from app.models.user import User
from app.schemas import (
    PortfolioItemCreate,
    PortfolioItemOut,
    PortfolioItemUpdate,
    PortfolioCardCreate,
    PortfolioCardBatchCreate,
    PortfolioCardUpdate,
    PortfolioCardOut,
    PortfolioSummary,
)


def get_live_market_price(session: Session, card_id: int) -> float:
    """
    Get live market price for a card, preferring actual data over snapshots.
    Priority: 1) Latest sold price, 2) Live lowest_ask, 3) Snapshot avg_price
    """
    # Try to get most recent sold price
    last_sale = session.exec(
        select(MarketPrice.price)
        .where(MarketPrice.card_id == card_id)
        .where(MarketPrice.listing_type == "sold")
        .order_by(desc(MarketPrice.sold_date))
        .limit(1)
    ).first()
    if last_sale:
        return last_sale

    # Fallback to live lowest_ask from active listings
    live_ask = session.exec(
        select(func.min(MarketPrice.price))
        .where(MarketPrice.card_id == card_id)
        .where(MarketPrice.listing_type == "active")
    ).first()
    if live_ask:
        return live_ask

    # Final fallback to snapshot avg_price
    snapshot = session.exec(
        select(MarketSnapshot)
        .where(MarketSnapshot.card_id == card_id)
        .order_by(desc(MarketSnapshot.timestamp), desc(MarketSnapshot.id))
        .limit(1)
    ).first()
    return snapshot.avg_price if snapshot and snapshot.avg_price else 0.0


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
        purchase_price=item_in.purchase_price,
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
        card_set=card.set_name,
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

        # Get LIVE market price (prefers recent sale > lowest_ask > snapshot)
        current_price = get_live_market_price(session, item.card_id)

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
            gain_loss_percent=gain_loss_percent,
        )
        results.append(out)

    return results


@router.put("/{item_id}", response_model=PortfolioItemOut)
def update_portfolio_item(
    item_id: int,
    item_in: PortfolioItemUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a portfolio item's quantity or purchase price.
    """
    item = session.get(PortfolioItem, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Portfolio item not found")
    if item.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update fields if provided
    if item_in.quantity is not None:
        item.quantity = item_in.quantity
    if item_in.purchase_price is not None:
        item.purchase_price = item_in.purchase_price
    if item_in.acquired_at is not None:
        item.acquired_at = item_in.acquired_at

    session.add(item)
    session.commit()
    session.refresh(item)

    # Get card details
    card = session.get(Card, item.card_id)

    # Get LIVE market price (prefers recent sale > lowest_ask > snapshot)
    current_price = get_live_market_price(session, item.card_id)

    current_value = current_price * item.quantity
    cost_basis = item.purchase_price * item.quantity
    gain_loss = current_value - cost_basis
    gain_loss_percent = (gain_loss / cost_basis * 100) if cost_basis > 0 else 0.0

    return PortfolioItemOut(
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
        gain_loss_percent=gain_loss_percent,
    )


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
        acquired_at=item.acquired_at,
    )


# =============================================================================
# NEW PORTFOLIO CARD ENDPOINTS (Individual card tracking)
# =============================================================================


def get_treatment_market_price(session: Session, card_id: int, treatment: str) -> float:
    """
    Get market price for a specific card + treatment combination.
    Falls back to card-level price if treatment-specific not available.
    """
    # Try to get treatment-specific VWAP (last 30 days)
    cutoff = datetime.utcnow() - timedelta(days=30)

    treatment_avg = session.exec(
        select(func.avg(MarketPrice.price))
        .where(MarketPrice.card_id == card_id)
        .where(MarketPrice.treatment == treatment)
        .where(MarketPrice.listing_type == "sold")
        .where(MarketPrice.sold_date >= cutoff)
    ).first()

    if treatment_avg and treatment_avg > 0:
        return float(treatment_avg)

    # Fallback: Get most recent sale for this treatment (any time)
    last_treatment_sale = session.exec(
        select(MarketPrice.price)
        .where(MarketPrice.card_id == card_id)
        .where(MarketPrice.treatment == treatment)
        .where(MarketPrice.listing_type == "sold")
        .order_by(desc(MarketPrice.sold_date))
        .limit(1)
    ).first()

    if last_treatment_sale:
        return float(last_treatment_sale)

    # Final fallback: Use card-level price (any treatment)
    return get_live_market_price(session, card_id)


def build_portfolio_card_out(
    session: Session, card: PortfolioCard, db_card: Card, rarity: Optional[Rarity]
) -> PortfolioCardOut:
    """Build PortfolioCardOut with market data."""
    market_price = get_treatment_market_price(session, card.card_id, card.treatment)
    profit_loss = market_price - card.purchase_price if market_price else None
    profit_loss_pct = (
        (profit_loss / card.purchase_price * 100) if profit_loss is not None and card.purchase_price > 0 else None
    )

    return PortfolioCardOut(
        id=card.id,
        user_id=card.user_id,
        card_id=card.card_id,
        treatment=card.treatment,
        source=card.source,
        purchase_price=card.purchase_price,
        purchase_date=card.purchase_date,
        grading=card.grading,
        notes=card.notes,
        created_at=card.created_at,
        updated_at=card.updated_at,
        # Card details
        card_name=db_card.name if db_card else "Unknown",
        card_set=db_card.set_name if db_card else "",
        card_slug=db_card.slug if db_card else None,
        rarity_name=rarity.name if rarity else None,
        product_type=db_card.product_type if db_card else None,
        # Market data
        market_price=market_price,
        profit_loss=profit_loss,
        profit_loss_percent=profit_loss_pct,
    )


@router.post("/cards", response_model=PortfolioCardOut)
def create_portfolio_card(
    card_in: PortfolioCardCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Add a single card to the user's portfolio with treatment/source details.
    """
    # Validate card exists
    db_card = session.get(Card, card_in.card_id)
    if not db_card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Validate purchase price
    if card_in.purchase_price < 0:
        raise HTTPException(status_code=400, detail="Purchase price cannot be negative")

    card = PortfolioCard(
        user_id=current_user.id,
        card_id=card_in.card_id,
        treatment=card_in.treatment,
        source=card_in.source,
        purchase_price=card_in.purchase_price,
        purchase_date=card_in.purchase_date.date() if card_in.purchase_date else None,
        grading=card_in.grading,
        notes=card_in.notes,
    )
    session.add(card)
    session.commit()
    session.refresh(card)

    rarity = session.get(Rarity, db_card.rarity_id) if db_card.rarity_id else None
    return build_portfolio_card_out(session, card, db_card, rarity)


@router.post("/cards/batch", response_model=List[PortfolioCardOut])
def create_portfolio_cards_batch(
    batch_in: PortfolioCardBatchCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Add multiple cards to the portfolio at once (split entry mode).
    All cards are added atomically - if one fails, none are added.
    Max 100 cards per request.
    """
    if len(batch_in.cards) > 100:
        raise HTTPException(status_code=400, detail="Maximum 100 cards per batch")

    if len(batch_in.cards) == 0:
        raise HTTPException(status_code=400, detail="At least one card required")

    # Validate all cards first
    card_ids = set(c.card_id for c in batch_in.cards)
    db_cards = {c.id: c for c in session.exec(select(Card).where(Card.id.in_(card_ids))).all()}

    for i, card_in in enumerate(batch_in.cards):
        if card_in.card_id not in db_cards:
            raise HTTPException(status_code=400, detail=f"Card at index {i}: Card ID {card_in.card_id} not found")
        if card_in.purchase_price < 0:
            raise HTTPException(status_code=400, detail=f"Card at index {i}: Purchase price cannot be negative")

    # Create all cards
    created_cards = []
    for card_in in batch_in.cards:
        card = PortfolioCard(
            user_id=current_user.id,
            card_id=card_in.card_id,
            treatment=card_in.treatment,
            source=card_in.source,
            purchase_price=card_in.purchase_price,
            purchase_date=card_in.purchase_date.date() if card_in.purchase_date else None,
            grading=card_in.grading,
            notes=card_in.notes,
        )
        session.add(card)
        created_cards.append(card)

    session.commit()

    # Refresh and build response
    results = []
    for card in created_cards:
        session.refresh(card)
        db_card = db_cards[card.card_id]
        rarity = session.get(Rarity, db_card.rarity_id) if db_card.rarity_id else None
        results.append(build_portfolio_card_out(session, card, db_card, rarity))

    return results


@router.get("/cards", response_model=List[PortfolioCardOut])
def read_portfolio_cards(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    treatment: Optional[str] = Query(default=None, description="Filter by treatment"),
    source: Optional[str] = Query(default=None, description="Filter by source"),
    graded: Optional[bool] = Query(default=None, description="Filter graded (true) or raw (false)"),
    card_id: Optional[int] = Query(default=None, description="Filter by specific card"),
) -> Any:
    """
    Get all portfolio cards for the current user with optional filters.
    """
    query = (
        select(PortfolioCard).where(PortfolioCard.user_id == current_user.id).where(PortfolioCard.deleted_at.is_(None))
    )

    if treatment:
        query = query.where(PortfolioCard.treatment == treatment)
    if source:
        query = query.where(PortfolioCard.source == source)
    if graded is not None:
        if graded:
            query = query.where(PortfolioCard.grading.isnot(None))
        else:
            query = query.where(PortfolioCard.grading.is_(None))
    if card_id:
        query = query.where(PortfolioCard.card_id == card_id)

    query = query.order_by(desc(PortfolioCard.created_at))
    cards = session.exec(query).all()

    # Batch fetch card details
    card_ids = set(c.card_id for c in cards)
    db_cards = {c.id: c for c in session.exec(select(Card).where(Card.id.in_(card_ids))).all()} if card_ids else {}

    # Batch fetch rarities
    rarity_ids = set(c.rarity_id for c in db_cards.values() if c.rarity_id)
    rarities = (
        {r.id: r for r in session.exec(select(Rarity).where(Rarity.id.in_(rarity_ids))).all()} if rarity_ids else {}
    )

    results = []
    for card in cards:
        db_card = db_cards.get(card.card_id)
        rarity = rarities.get(db_card.rarity_id) if db_card and db_card.rarity_id else None
        results.append(build_portfolio_card_out(session, card, db_card, rarity))

    return results


@router.get("/cards/summary", response_model=PortfolioSummary)
def read_portfolio_summary(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get portfolio summary statistics.
    """
    cards = session.exec(
        select(PortfolioCard).where(PortfolioCard.user_id == current_user.id).where(PortfolioCard.deleted_at.is_(None))
    ).all()

    total_cards = len(cards)
    total_cost_basis = sum(c.purchase_price for c in cards)

    # Calculate market values
    total_market_value = 0.0
    by_treatment = {}
    by_source = {}

    for card in cards:
        market_price = get_treatment_market_price(session, card.card_id, card.treatment)
        total_market_value += market_price

        # Aggregate by treatment
        if card.treatment not in by_treatment:
            by_treatment[card.treatment] = {"count": 0, "cost": 0.0, "value": 0.0}
        by_treatment[card.treatment]["count"] += 1
        by_treatment[card.treatment]["cost"] += card.purchase_price
        by_treatment[card.treatment]["value"] += market_price

        # Aggregate by source
        if card.source not in by_source:
            by_source[card.source] = {"count": 0, "cost": 0.0, "value": 0.0}
        by_source[card.source]["count"] += 1
        by_source[card.source]["cost"] += card.purchase_price
        by_source[card.source]["value"] += market_price

    total_profit_loss = total_market_value - total_cost_basis
    total_profit_loss_percent = (total_profit_loss / total_cost_basis * 100) if total_cost_basis > 0 else 0.0

    return PortfolioSummary(
        total_cards=total_cards,
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        total_profit_loss=total_profit_loss,
        total_profit_loss_percent=total_profit_loss_percent,
        by_treatment=by_treatment,
        by_source=by_source,
    )


@router.get("/cards/{card_id}", response_model=PortfolioCardOut)
def read_portfolio_card(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a single portfolio card by ID.
    """
    card = session.get(PortfolioCard, card_id)
    if not card or card.deleted_at:
        raise HTTPException(status_code=404, detail="Portfolio card not found")
    if card.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    db_card = session.get(Card, card.card_id)
    rarity = session.get(Rarity, db_card.rarity_id) if db_card and db_card.rarity_id else None
    return build_portfolio_card_out(session, card, db_card, rarity)


@router.patch("/cards/{card_id}", response_model=PortfolioCardOut)
def update_portfolio_card(
    card_id: int,
    card_in: PortfolioCardUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a portfolio card's details.
    """
    card = session.get(PortfolioCard, card_id)
    if not card or card.deleted_at:
        raise HTTPException(status_code=404, detail="Portfolio card not found")
    if card.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Update fields if provided
    if card_in.treatment is not None:
        card.treatment = card_in.treatment
    if card_in.source is not None:
        card.source = card_in.source
    if card_in.purchase_price is not None:
        if card_in.purchase_price < 0:
            raise HTTPException(status_code=400, detail="Purchase price cannot be negative")
        card.purchase_price = card_in.purchase_price
    if card_in.purchase_date is not None:
        card.purchase_date = card_in.purchase_date.date() if card_in.purchase_date else None
    if card_in.grading is not None:
        card.grading = card_in.grading if card_in.grading else None
    if card_in.notes is not None:
        card.notes = card_in.notes if card_in.notes else None

    card.updated_at = datetime.utcnow()
    session.add(card)
    session.commit()
    session.refresh(card)

    db_card = session.get(Card, card.card_id)
    rarity = session.get(Rarity, db_card.rarity_id) if db_card and db_card.rarity_id else None
    return build_portfolio_card_out(session, card, db_card, rarity)


@router.delete("/cards/{card_id}", response_model=PortfolioCardOut)
def delete_portfolio_card(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Soft-delete a portfolio card.
    """
    card = session.get(PortfolioCard, card_id)
    if not card or card.deleted_at:
        raise HTTPException(status_code=404, detail="Portfolio card not found")
    if card.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Soft delete
    card.deleted_at = datetime.utcnow()
    session.add(card)
    session.commit()
    session.refresh(card)

    db_card = session.get(Card, card.card_id)
    rarity = session.get(Rarity, db_card.rarity_id) if db_card and db_card.rarity_id else None
    return build_portfolio_card_out(session, card, db_card, rarity)


@router.get("/treatments", response_model=List[str])
def get_available_treatments(
    session: Session = Depends(get_session),
) -> Any:
    """
    Get list of all treatments found in market data.
    """
    from sqlalchemy import text

    result = session.execute(
        text("""
        SELECT DISTINCT treatment
        FROM marketprice
        WHERE treatment IS NOT NULL
        ORDER BY treatment
    """)
    )
    return [row[0] for row in result]


@router.get("/sources", response_model=List[str])
def get_available_sources() -> Any:
    """
    Get list of valid purchase sources.
    """
    return ["eBay", "Blokpax", "TCGPlayer", "LGS", "Trade", "Pack Pull", "Other"]


@router.get("/cards/history/value")
def get_portfolio_value_history(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    days: int = Query(default=30, ge=7, le=365, description="Number of days of history"),
) -> Any:
    """
    Get portfolio value history over time.
    Returns daily portfolio value based on cards owned at each date.
    """
    from sqlalchemy import text

    # Get all user's portfolio cards (including purchase dates)
    cards = session.exec(
        select(PortfolioCard).where(PortfolioCard.user_id == current_user.id).where(PortfolioCard.deleted_at.is_(None))
    ).all()

    if not cards:
        return {"history": [], "cost_basis_history": []}

    # Build date range
    end_date = datetime.utcnow().date()
    start_date = end_date - timedelta(days=days)

    # Get unique card_ids
    card_ids = list(set(c.card_id for c in cards))

    # Get historical prices for all cards - use daily VWAP from sold listings
    # This query gets the average sold price per card per day
    price_query = text("""
        SELECT
            card_id,
            DATE(COALESCE(sold_date, scraped_at)) as sale_date,
            AVG(price) as avg_price
        FROM marketprice
        WHERE card_id = ANY(:card_ids)
          AND listing_type = 'sold'
          AND COALESCE(sold_date, scraped_at) >= :start_date
        GROUP BY card_id, DATE(COALESCE(sold_date, scraped_at))
        ORDER BY card_id, sale_date
    """)

    price_results = session.execute(price_query, {"card_ids": card_ids, "start_date": start_date}).all()

    # Build price lookup: {card_id: {date: price}}
    price_by_card_date = {}
    for row in price_results:
        cid, sale_date, avg_price = row
        if cid not in price_by_card_date:
            price_by_card_date[cid] = {}
        price_by_card_date[cid][sale_date] = float(avg_price)

    # Get current prices as fallback
    current_prices = {}
    for card in cards:
        current_prices[card.card_id] = get_treatment_market_price(session, card.card_id, card.treatment)

    # Calculate daily portfolio value
    history = []
    cost_basis_history = []
    current_date = start_date

    while current_date <= end_date:
        daily_value = 0.0
        daily_cost = 0.0

        for card in cards:
            # Check if card was owned on this date
            card_purchase_date = card.purchase_date
            if card_purchase_date and card_purchase_date > current_date:
                continue  # Card not yet purchased

            # Add cost basis
            daily_cost += card.purchase_price

            # Get price for this card on this date
            card_prices = price_by_card_date.get(card.card_id, {})

            # Find the most recent price on or before current_date
            price = None
            for d in sorted(card_prices.keys(), reverse=True):
                if d <= current_date:
                    price = card_prices[d]
                    break

            # If no historical price, use current price
            if price is None:
                price = current_prices.get(card.card_id, card.purchase_price)

            daily_value += price

        history.append({"date": current_date.isoformat(), "value": round(daily_value, 2)})
        cost_basis_history.append({"date": current_date.isoformat(), "value": round(daily_cost, 2)})

        current_date += timedelta(days=1)

    return {"history": history, "cost_basis_history": cost_basis_history}
