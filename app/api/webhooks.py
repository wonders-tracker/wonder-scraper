"""
Webhooks API stub.

This file provides a fallback router when the saas/ module is not available.
In OSS deployments, webhook endpoints return 501 Not Implemented.
"""

import logging
from fastapi import APIRouter, HTTPException, Request

logger = logging.getLogger(__name__)

try:
    from saas.api.webhooks import router, verify_polar_signature
    WEBHOOKS_AVAILABLE = True
    logger.info("SaaS webhooks module loaded")
except ImportError:
    WEBHOOKS_AVAILABLE = False
    logger.info("SaaS module not available - webhook endpoints disabled")

    # Create stub router
    router = APIRouter()

    def verify_polar_signature(payload: bytes, signature: str, secret: str) -> bool:
        """Stub: Always returns False when saas/ not available."""
        return False

    @router.post("/webhooks/polar")
    async def polar_webhook(request: Request):
        """Polar webhooks not available in OSS version."""
        raise HTTPException(
            status_code=501,
            detail="Webhook handling requires the saas/ module"
        )


# Re-export for backwards compatibility with existing code
__all__ = ["router", "WEBHOOKS_AVAILABLE", "verify_polar_signature"]
