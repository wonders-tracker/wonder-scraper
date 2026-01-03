"""
Analytics API endpoints for tracking page views and events.
"""

import hashlib
from typing import Optional, Dict, Any
from fastapi import APIRouter, Request, Depends
from pydantic import BaseModel
from sqlmodel import Session
from user_agents import parse as parse_ua

from app.db import get_session
from app.api import deps
from app.models.user import User
from app.models.analytics import PageView, AnalyticsEvent

router = APIRouter()


class PageViewRequest(BaseModel):
    path: str
    referrer: Optional[str] = None
    session_id: Optional[str] = None


class EventRequest(BaseModel):
    event_name: str
    properties: Optional[Dict[str, Any]] = None
    session_id: Optional[str] = None


def get_device_type(user_agent_string: str) -> str:
    """Parse user agent to determine device type."""
    try:
        ua = parse_ua(user_agent_string)
        if ua.is_mobile:
            return "mobile"
        elif ua.is_tablet:
            return "tablet"
        else:
            return "desktop"
    except (ValueError, AttributeError, TypeError):
        # user-agents library can raise these when parsing malformed UA strings
        return "unknown"


def hash_ip(ip: str) -> str:
    """Hash IP address for privacy."""
    return hashlib.sha256(ip.encode()).hexdigest()[:16]


@router.post("/pageview")
async def track_pageview(
    data: PageViewRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(deps.get_current_user_optional),
):
    """Track a page view."""
    user_agent = request.headers.get("user-agent", "")

    # Get client IP (handle proxies)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    pageview = PageView(
        path=data.path,
        user_id=current_user.id if current_user else None,
        session_id=data.session_id,
        referrer=data.referrer,
        user_agent=user_agent[:500] if user_agent else None,
        ip_hash=hash_ip(client_ip),
        device_type=get_device_type(user_agent),
    )

    session.add(pageview)
    session.commit()

    return {"status": "ok"}


@router.post("/event")
async def track_event(
    data: EventRequest,
    request: Request,
    session: Session = Depends(get_session),
    current_user: Optional[User] = Depends(deps.get_current_user_optional),
):
    """Track a custom analytics event."""
    # Get client IP (handle proxies)
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        client_ip = forwarded_for.split(",")[0].strip()
    else:
        client_ip = request.client.host if request.client else "unknown"

    # Extract common properties for easier querying
    props = data.properties or {}
    card_id = props.get("card_id")
    card_name = props.get("card_name")
    platform = props.get("platform")

    event = AnalyticsEvent(
        event_name=data.event_name,
        user_id=current_user.id if current_user else None,
        session_id=data.session_id,
        ip_hash=hash_ip(client_ip),
        properties=props,
        card_id=int(card_id) if card_id else None,
        card_name=str(card_name)[:255] if card_name else None,
        platform=str(platform)[:50] if platform else None,
    )

    session.add(event)
    session.commit()

    return {"status": "ok"}
