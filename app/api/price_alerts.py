"""
Price Alerts API - User-defined price alerts for cards

Endpoints for creating, listing, and managing price alerts.
"""

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select

from app.api import deps
from app.core.typing import ensure_int
from app.db import get_session
from app.models.card import Card
from app.models.price_alert import (
    PriceAlert,
    PriceAlertCreate,
    PriceAlertRead,
    PriceAlertUpdate,
    AlertStatus,
)
from app.models.user import User
from app.services.floor_price import get_floor_price_service

router = APIRouter()


@router.post("/", response_model=PriceAlertRead)
def create_price_alert(
    alert_in: PriceAlertCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new price alert for a card.
    """
    # Check if card exists
    card = session.get(Card, alert_in.card_id)
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    # Check for duplicate active alerts
    existing = session.exec(
        select(PriceAlert)
        .where(PriceAlert.user_id == current_user.id)
        .where(PriceAlert.card_id == alert_in.card_id)
        .where(PriceAlert.status == AlertStatus.ACTIVE)
        .where(PriceAlert.alert_type == alert_in.alert_type)
    ).first()

    if existing:
        raise HTTPException(
            status_code=400,
            detail=f"You already have an active '{alert_in.alert_type.value}' alert for this card"
        )

    # Get current price for reference
    floor_service = get_floor_price_service(session)
    floor_result = floor_service.get_floor_price(alert_in.card_id, days=30)
    current_price = floor_result.price

    # Create the alert
    alert = PriceAlert(
        user_id=ensure_int(current_user.id),
        card_id=alert_in.card_id,
        target_price=alert_in.target_price,
        alert_type=alert_in.alert_type,
        treatment=alert_in.treatment,
        expires_at=alert_in.expires_at,
        price_at_creation=current_price,
        status=AlertStatus.ACTIVE,
    )
    session.add(alert)
    session.commit()
    session.refresh(alert)

    return PriceAlertRead(
        id=ensure_int(alert.id),
        user_id=alert.user_id,
        card_id=alert.card_id,
        target_price=alert.target_price,
        alert_type=alert.alert_type,
        treatment=alert.treatment,
        status=alert.status,
        price_at_creation=alert.price_at_creation,
        triggered_at=alert.triggered_at,
        triggered_price=alert.triggered_price,
        created_at=alert.created_at,
        expires_at=alert.expires_at,
        notification_sent=alert.notification_sent,
    )


@router.get("/", response_model=List[PriceAlertRead])
def list_price_alerts(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
    status: Optional[AlertStatus] = Query(default=None, description="Filter by status"),
    card_id: Optional[int] = Query(default=None, description="Filter by card ID"),
    limit: int = Query(default=50, le=100, description="Max alerts to return"),
) -> Any:
    """
    List all price alerts for the current user.
    """
    query = select(PriceAlert).where(PriceAlert.user_id == current_user.id)

    if status:
        query = query.where(PriceAlert.status == status)
    if card_id:
        query = query.where(PriceAlert.card_id == card_id)

    query = query.order_by(PriceAlert.created_at.desc()).limit(limit)
    alerts = session.exec(query).all()

    return [
        PriceAlertRead(
            id=ensure_int(a.id),
            user_id=a.user_id,
            card_id=a.card_id,
            target_price=a.target_price,
            alert_type=a.alert_type,
            treatment=a.treatment,
            status=a.status,
            price_at_creation=a.price_at_creation,
            triggered_at=a.triggered_at,
            triggered_price=a.triggered_price,
            created_at=a.created_at,
            expires_at=a.expires_at,
            notification_sent=a.notification_sent,
        )
        for a in alerts
    ]


@router.get("/{alert_id}", response_model=PriceAlertRead)
def get_price_alert(
    alert_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get a specific price alert.
    """
    alert = session.get(PriceAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    return PriceAlertRead(
        id=ensure_int(alert.id),
        user_id=alert.user_id,
        card_id=alert.card_id,
        target_price=alert.target_price,
        alert_type=alert.alert_type,
        treatment=alert.treatment,
        status=alert.status,
        price_at_creation=alert.price_at_creation,
        triggered_at=alert.triggered_at,
        triggered_price=alert.triggered_price,
        created_at=alert.created_at,
        expires_at=alert.expires_at,
        notification_sent=alert.notification_sent,
    )


@router.patch("/{alert_id}", response_model=PriceAlertRead)
def update_price_alert(
    alert_id: int,
    alert_in: PriceAlertUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update a price alert (target price, type, or cancel it).
    """
    alert = session.get(PriceAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Only allow updates on active alerts
    if alert.status != AlertStatus.ACTIVE:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot update alert with status '{alert.status.value}'"
        )

    # Apply updates
    update_data = alert_in.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(alert, field, value)

    session.add(alert)
    session.commit()
    session.refresh(alert)

    return PriceAlertRead(
        id=ensure_int(alert.id),
        user_id=alert.user_id,
        card_id=alert.card_id,
        target_price=alert.target_price,
        alert_type=alert.alert_type,
        treatment=alert.treatment,
        status=alert.status,
        price_at_creation=alert.price_at_creation,
        triggered_at=alert.triggered_at,
        triggered_price=alert.triggered_price,
        created_at=alert.created_at,
        expires_at=alert.expires_at,
        notification_sent=alert.notification_sent,
    )


@router.delete("/{alert_id}")
def delete_price_alert(
    alert_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Cancel/delete a price alert.
    """
    alert = session.get(PriceAlert, alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    if alert.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")

    # Soft delete by setting status to cancelled
    alert.status = AlertStatus.CANCELLED
    session.add(alert)
    session.commit()

    return {"message": "Alert cancelled"}


@router.get("/card/{card_id}", response_model=List[PriceAlertRead])
def get_alerts_for_card(
    card_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get all active alerts for a specific card.
    """
    alerts = session.exec(
        select(PriceAlert)
        .where(PriceAlert.user_id == current_user.id)
        .where(PriceAlert.card_id == card_id)
        .where(PriceAlert.status == AlertStatus.ACTIVE)
    ).all()

    return [
        PriceAlertRead(
            id=ensure_int(a.id),
            user_id=a.user_id,
            card_id=a.card_id,
            target_price=a.target_price,
            alert_type=a.alert_type,
            treatment=a.treatment,
            status=a.status,
            price_at_creation=a.price_at_creation,
            triggered_at=a.triggered_at,
            triggered_price=a.triggered_price,
            created_at=a.created_at,
            expires_at=a.expires_at,
            notification_sent=a.notification_sent,
        )
        for a in alerts
    ]
