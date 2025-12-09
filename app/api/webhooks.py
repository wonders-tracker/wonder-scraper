"""
Webhook handlers for external services (Polar, etc.)
"""
import hmac
import hashlib
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlmodel import Session, select

from app.db import get_session
from app.models.user import User
from app.models.webhook_event import WebhookEvent
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


def is_event_processed(event_id: str, session: Session) -> bool:
    """Check if a webhook event has already been processed."""
    existing = session.exec(
        select(WebhookEvent).where(WebhookEvent.event_id == event_id)
    ).first()
    return existing is not None


def record_event(
    event_id: str,
    event_type: str,
    session: Session,
    user_id: int | None = None,
    subscription_id: str | None = None,
    status: str = "processed",
    error_message: str | None = None
) -> WebhookEvent:
    """Record a processed webhook event."""
    event = WebhookEvent(
        event_id=event_id,
        event_type=event_type,
        source="polar",
        user_id=user_id,
        subscription_id=subscription_id,
        status=status,
        error_message=error_message
    )
    session.add(event)
    session.commit()
    return event


def verify_polar_signature(payload: bytes, signature: str, secret: str) -> bool:
    """
    Verify Polar webhook signature using Standard Webhooks spec.
    """
    if not signature or not secret:
        return False

    # Standard Webhooks format: "v1,timestamp,signature"
    try:
        parts = signature.split(",")
        if len(parts) < 3:
            return False

        timestamp = parts[1]
        received_sig = parts[2]

        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, received_sig)
    except Exception:
        return False


@router.post("/polar")
async def polar_webhook(
    request: Request,
    session: Session = Depends(get_session)
):
    """
    Handle Polar webhook events for subscription lifecycle.

    Events handled:
    - subscription.created: New subscription
    - subscription.active: Subscription activated/renewed
    - subscription.updated: Subscription modified
    - subscription.canceled: User canceled (still active until period end)
    - subscription.revoked: Subscription ended
    - checkout.created: Checkout started
    - checkout.updated: Checkout completed/updated
    """
    # Get raw body for signature verification
    body = await request.body()

    # Verify webhook signature
    signature = request.headers.get("webhook-signature", "")
    if settings.POLAR_WEBHOOK_SECRET and not verify_polar_signature(
        body, signature, settings.POLAR_WEBHOOK_SECRET
    ):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    event_type = payload.get("type")
    data = payload.get("data", {})

    # Generate unique event ID from payload
    # Polar includes an ID in the data, but we also include event type for uniqueness
    data_id = data.get("id", "")
    event_id = f"{event_type}:{data_id}"

    logger.info("Polar webhook received", extra={"event_type": event_type, "event_id": event_id})

    # Check for duplicate event (idempotency)
    if is_event_processed(event_id, session):
        logger.info("Duplicate webhook event, skipping", extra={"event_id": event_id})
        return {"status": "ok", "message": "already processed"}

    # Process the event
    user_id = None
    subscription_id = data.get("id")
    error_message = None
    status = "processed"

    try:
        if event_type == "subscription.active":
            user_id = await handle_subscription_active(data, session)

        elif event_type == "subscription.created":
            user_id = await handle_subscription_created(data, session)

        elif event_type == "subscription.updated":
            user_id = await handle_subscription_updated(data, session)

        elif event_type == "subscription.canceled":
            user_id = await handle_subscription_canceled(data, session)

        elif event_type == "subscription.revoked":
            user_id = await handle_subscription_revoked(data, session)

        elif event_type == "checkout.updated":
            checkout_status = data.get("status")
            if checkout_status == "succeeded":
                logger.info("Checkout succeeded", extra={"checkout_id": data.get("id")})

    except Exception as e:
        logger.exception("Failed to process webhook event", extra={"event_id": event_id})
        error_message = str(e)
        status = "failed"

    # Record the event for idempotency
    record_event(
        event_id=event_id,
        event_type=event_type,
        session=session,
        user_id=user_id,
        subscription_id=subscription_id,
        status=status,
        error_message=error_message
    )

    return {"status": "ok"}


async def handle_subscription_created(data: dict, session: Session) -> int | None:
    """Handle new subscription creation. Returns user_id if found."""
    user = await find_user_from_subscription(data, session)
    if not user:
        logger.warning("User not found for subscription", extra={"subscription_id": data.get("id")})
        return None

    # Extract product type from metadata
    metadata = data.get("metadata", {})
    product_type = metadata.get("product_type", "pro")  # Default to pro for backwards compat

    user.subscription_id = data.get("id")
    user.polar_customer_id = data.get("customer_id")
    user.subscription_status = data.get("status")
    user.subscription_product_type = product_type

    session.add(user)
    session.commit()
    logger.info("Subscription created", extra={"user_email": user.email, "product_type": product_type})
    return user.id


async def handle_subscription_active(data: dict, session: Session) -> int | None:
    """Handle subscription activation - upgrade user based on product type. Returns user_id if found."""
    user = await find_user_from_subscription(data, session)
    if not user:
        logger.warning("User not found for subscription activation", extra={"subscription_id": data.get("id")})
        return None

    # Determine product type from metadata or existing user data
    metadata = data.get("metadata", {})
    product_type = metadata.get("product_type") or user.subscription_product_type or "pro"

    # Set tier based on product type
    if product_type == "api":
        user.subscription_tier = "api"
        user.has_api_access = True
    else:
        user.subscription_tier = "pro"
        user.has_api_access = True  # Pro includes API access

    user.subscription_status = "active"
    user.subscription_id = data.get("id")
    user.polar_customer_id = data.get("customer_id")
    user.subscription_product_type = product_type

    # Set period end if available
    current_period_end = data.get("current_period_end")
    if current_period_end:
        user.subscription_current_period_end = datetime.fromisoformat(
            current_period_end.replace("Z", "+00:00")
        )

    session.add(user)
    session.commit()
    logger.info(
        "Subscription activated",
        extra={"user_email": user.email, "tier": user.subscription_tier, "product_type": product_type}
    )
    return user.id


async def handle_subscription_updated(data: dict, session: Session) -> int | None:
    """Handle subscription updates. Returns user_id if found."""
    subscription_id = data.get("id")
    user = session.exec(
        select(User).where(User.subscription_id == subscription_id)
    ).first()

    if not user:
        logger.warning("User not found for subscription update", extra={"subscription_id": subscription_id})
        return None

    user.subscription_status = data.get("status")

    current_period_end = data.get("current_period_end")
    if current_period_end:
        user.subscription_current_period_end = datetime.fromisoformat(
            current_period_end.replace("Z", "+00:00")
        )

    session.add(user)
    session.commit()
    logger.info("Subscription updated", extra={"user_email": user.email, "status": user.subscription_status})
    return user.id


async def handle_subscription_canceled(data: dict, session: Session) -> int | None:
    """Handle subscription cancellation (still active until period end). Returns user_id if found."""
    subscription_id = data.get("id")
    user = session.exec(
        select(User).where(User.subscription_id == subscription_id)
    ).first()

    if not user:
        logger.warning("User not found for subscription cancel", extra={"subscription_id": subscription_id})
        return None

    user.subscription_status = "canceled"
    # Keep tier as current until period ends

    session.add(user)
    session.commit()
    logger.info(
        "Subscription canceled",
        extra={"user_email": user.email, "tier": user.subscription_tier, "period_end": str(user.subscription_current_period_end)}
    )
    return user.id


async def handle_subscription_revoked(data: dict, session: Session) -> int | None:
    """Handle subscription revocation - downgrade to free. Returns user_id if found."""
    subscription_id = data.get("id")
    user = session.exec(
        select(User).where(User.subscription_id == subscription_id)
    ).first()

    if not user:
        logger.warning("User not found for subscription revoke", extra={"subscription_id": subscription_id})
        return None

    previous_tier = user.subscription_tier
    user.subscription_tier = "free"
    user.subscription_status = None
    user.has_api_access = False
    user.subscription_current_period_end = None
    user.subscription_product_type = None

    session.add(user)
    session.commit()
    logger.info("Subscription revoked", extra={"user_email": user.email, "previous_tier": previous_tier})
    return user.id


async def find_user_from_subscription(data: dict, session: Session) -> User | None:
    """Find user from subscription data using metadata or customer email."""
    # Try metadata first (contains user_id from checkout)
    metadata = data.get("metadata", {})
    user_id = metadata.get("user_id")

    if user_id:
        user = session.get(User, int(user_id))
        if user:
            return user

    # Try by existing subscription_id
    subscription_id = data.get("id")
    user = session.exec(
        select(User).where(User.subscription_id == subscription_id)
    ).first()
    if user:
        return user

    # Try by polar_customer_id
    customer_id = data.get("customer_id")
    if customer_id:
        user = session.exec(
            select(User).where(User.polar_customer_id == customer_id)
        ).first()
        if user:
            return user

    # Try by customer email
    customer = data.get("customer", {})
    customer_email = customer.get("email")
    if customer_email:
        user = session.exec(
            select(User).where(User.email == customer_email)
        ).first()
        if user:
            return user

    return None
