"""
Polar.sh integration stub.

This file provides graceful fallbacks when the saas/ module is not available.
In OSS deployments (without saas/ submodule), these functions are no-ops.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

try:
    from saas.services.polar import (
        get_polar_client,
        create_checkout_session,
        get_customer_portal_url,
        ingest_usage_event,
    )

    POLAR_AVAILABLE = True
except ImportError:
    POLAR_AVAILABLE = False
    logger.info("SaaS module not available - Polar integration disabled")

    def get_polar_client():
        """Stub: Polar client not available."""
        raise NotImplementedError("Polar integration requires saas/ module")

    async def create_checkout_session(
        product_id: str, customer_email: str, success_url: str, metadata: Optional[dict] = None
    ) -> str:
        """Stub: Checkout not available in OSS version."""
        raise NotImplementedError("Billing requires saas/ module")

    async def get_customer_portal_url(customer_id: str) -> str:
        """Stub: Customer portal not available in OSS version."""
        raise NotImplementedError("Billing requires saas/ module")

    async def ingest_usage_event(customer_id: str, event_name: str, metadata: Optional[dict] = None) -> None:
        """Stub: Usage metering not available - silent no-op."""
        pass  # Silent no-op for metering


__all__ = [
    "POLAR_AVAILABLE",
    "get_polar_client",
    "create_checkout_session",
    "get_customer_portal_url",
    "ingest_usage_event",
]
