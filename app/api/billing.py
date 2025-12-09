"""
Billing API endpoints for Polar subscription management.
"""
import logging
from typing import Literal
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, select

from app.db import get_session
from app.models.user import User
from app.api.deps import get_current_user, get_current_superuser
from app.core.config import settings
from app.core.rate_limit import rate_limiter, get_client_ip
from app.services.polar import create_checkout_session, get_customer_portal_url

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout")
async def create_checkout(
    request: Request,
    product: Literal["pro", "api"] = "pro",
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Create a Polar checkout session for subscription.

    Args:
        product: "pro" for Pro Access ($49.95/mo) or "api" for API Access (pay-per-request)

    Returns the checkout URL to redirect the user to.
    """
    # Rate limiting: 5 checkout attempts per minute per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=5, window_seconds=60)
    if is_limited:
        logger.warning("Checkout rate limited", extra={"ip": ip, "user_email": user.email})
        raise HTTPException(
            status_code=429,
            detail="Too many checkout attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )
    rate_limiter.record_request(ip)

    # Check if user already has active subscription
    if user.is_pro:
        raise HTTPException(
            status_code=400,
            detail="You already have an active subscription"
        )

    # Select product ID based on type
    if product == "api":
        product_id = settings.POLAR_API_PRODUCT_ID
    else:
        product_id = settings.POLAR_PRO_PRODUCT_ID

    if not product_id:
        raise HTTPException(
            status_code=500,
            detail=f"Product {product} not configured"
        )

    # Use configured success URL or fallback to frontend profile
    success_url = settings.POLAR_SUCCESS_URL or f"{settings.FRONTEND_URL}/profile?upgraded=true&checkout_id={{CHECKOUT_ID}}"

    checkout_url = await create_checkout_session(
        product_id=product_id,
        customer_email=user.email,
        success_url=success_url,
        metadata={"user_id": str(user.id), "product_type": product}
    )

    return {"checkout_url": checkout_url}


@router.get("/portal")
async def get_billing_portal(
    user: User = Depends(get_current_user)
):
    """
    Get the Polar customer portal URL for managing subscription.
    """
    if not user.polar_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No subscription found. Please subscribe first."
        )

    portal_url = await get_customer_portal_url(user.polar_customer_id)

    return {"portal_url": portal_url}


@router.get("/status")
async def get_subscription_status(
    user: User = Depends(get_current_user)
):
    """
    Get current subscription status for the user.
    """
    return {
        "tier": user.subscription_tier,
        "status": user.subscription_status,
        "product_type": user.subscription_product_type,
        "is_pro": user.is_pro,
        "is_api_subscriber": user.is_api_subscriber,
        "has_api_access": user.has_api_access,
        "api_access_requested": user.api_access_requested,
        "api_access_approved": user.api_access_approved,
        "current_period_end": user.subscription_current_period_end.isoformat() if user.subscription_current_period_end else None
    }


# ============ API Access Request Flow ============

@router.post("/api-access/request")
async def request_api_access(
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session)
):
    """
    Request API access. Admin will review and approve.
    """
    if user.has_api_access:
        raise HTTPException(status_code=400, detail="You already have API access")

    if user.api_access_requested:
        raise HTTPException(status_code=400, detail="You have already requested API access. Please wait for approval.")

    user.api_access_requested = True
    user.api_access_requested_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()

    logger.info("API access requested", extra={"user_email": user.email})
    return {"message": "API access request submitted. You will receive an email once approved."}


@router.get("/api-access/requests")
async def list_api_access_requests(
    admin: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """
    List all pending API access requests. Admin only.
    """
    users = session.exec(
        select(User).where(
            User.api_access_requested == True,
            User.api_access_approved == False
        )
    ).all()

    return [
        {
            "id": u.id,
            "email": u.email,
            "username": u.username,
            "discord_handle": u.discord_handle,
            "requested_at": u.api_access_requested_at.isoformat() if u.api_access_requested_at else None,
            "created_at": u.created_at.isoformat() if u.created_at else None
        }
        for u in users
    ]


@router.post("/api-access/approve/{user_id}")
async def approve_api_access(
    user_id: int,
    admin: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """
    Approve a user's API access request and send them an email with checkout link.
    Admin only.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    if not user.api_access_requested:
        raise HTTPException(status_code=400, detail="User has not requested API access")

    if user.api_access_approved:
        raise HTTPException(status_code=400, detail="User already approved")

    # Mark as approved
    user.api_access_approved = True
    user.api_access_approved_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()

    # Send approval email with checkout link
    try:
        from app.services.email import send_api_access_approved_email
        await send_api_access_approved_email(user.email, user.username or user.email.split('@')[0])
        logger.info("API access approval email sent", extra={"user_email": user.email})
    except Exception as e:
        logger.exception("Failed to send API access approval email", extra={"user_email": user.email})

    return {"message": f"API access approved for {user.email}. Email sent."}


@router.post("/api-access/deny/{user_id}")
async def deny_api_access(
    user_id: int,
    admin: User = Depends(get_current_superuser),
    session: Session = Depends(get_session)
):
    """
    Deny a user's API access request. Admin only.
    """
    user = session.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Reset request status
    user.api_access_requested = False
    user.api_access_requested_at = None
    session.add(user)
    session.commit()

    return {"message": f"API access request denied for {user.email}"}
