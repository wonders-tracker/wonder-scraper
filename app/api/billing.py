"""
Billing API stub.

This file provides a fallback router when the saas/ module is not available.
In OSS deployments, billing endpoints return 501 Not Implemented.
"""

import logging
from fastapi import APIRouter, HTTPException

logger = logging.getLogger(__name__)

try:
    from saas.api.billing import router

    BILLING_AVAILABLE = True
    logger.info("SaaS billing module loaded")
except ImportError:
    BILLING_AVAILABLE = False
    logger.info("SaaS module not available - billing endpoints disabled")

    # Create stub router with disabled endpoints
    router = APIRouter()

    @router.get("/billing/status")
    async def billing_status():
        """Billing not available in OSS version."""
        return {"available": False, "message": "Billing features require the saas/ module"}

    @router.post("/billing/checkout")
    async def create_checkout():
        """Checkout not available in OSS version."""
        raise HTTPException(status_code=501, detail="Billing features are not available in the open-source version")

    @router.get("/billing/portal")
    async def get_portal():
        """Portal not available in OSS version."""
        raise HTTPException(status_code=501, detail="Billing features are not available in the open-source version")


__all__ = ["router", "BILLING_AVAILABLE"]
