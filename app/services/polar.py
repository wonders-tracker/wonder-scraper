"""
Polar.sh integration for subscription billing and usage metering.
"""
import logging
from typing import Optional
from polar_sdk import Polar
from app.core.config import settings

logger = logging.getLogger(__name__)


def get_polar_client() -> Polar:
    """Get configured Polar client."""
    return Polar(
        access_token=settings.POLAR_ACCESS_TOKEN,
        server="sandbox" if settings.POLAR_ENVIRONMENT == "sandbox" else None
    )


async def create_checkout_session(
    product_id: str,
    customer_email: str,
    success_url: str,
    metadata: Optional[dict] = None
) -> str:
    """
    Create a Polar checkout session.

    Returns the checkout URL to redirect the user to.
    """
    polar = get_polar_client()

    checkout = polar.checkouts.custom.create(
        product_id=product_id,
        customer_email=customer_email,
        success_url=success_url,
        metadata=metadata or {}
    )

    return checkout.url


async def get_customer_portal_url(customer_id: str) -> str:
    """Get the customer portal URL for managing subscription."""
    polar = get_polar_client()

    session = polar.customer_sessions.create(
        customer_id=customer_id
    )

    return session.customer_portal_url


async def ingest_usage_event(
    customer_id: str,
    event_name: str,
    metadata: Optional[dict] = None
) -> None:
    """
    Send a usage event to Polar for metering.

    Args:
        customer_id: Polar customer ID
        event_name: Event name (e.g., "api_request")
        metadata: Additional event data
    """
    if not customer_id or not settings.POLAR_ACCESS_TOKEN:
        return

    try:
        polar = get_polar_client()

        polar.events.ingest(
            events=[{
                "name": event_name,
                "external_customer_id": customer_id,
                "metadata": metadata or {}
            }]
        )
    except Exception as e:
        logger.exception("Failed to ingest usage event", extra={"customer_id": customer_id, "event_name": event_name})
