"""
API Metering Middleware stub.

This file provides a pass-through middleware when the saas/ module is not available.
In OSS deployments, requests pass through without metering.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

try:
    from saas.middleware.metering import APIMeteringMiddleware, METERED_PREFIXES, EXCLUDED_PATHS
    METERING_AVAILABLE = True
    logger.info("SaaS metering module loaded")
except ImportError:
    METERING_AVAILABLE = False
    logger.info("SaaS module not available - API metering disabled")

    # Stub constants for compatibility
    METERED_PREFIXES = []
    EXCLUDED_PATHS = []

    class APIMeteringMiddleware(BaseHTTPMiddleware):
        """
        Stub middleware that passes requests through without metering.
        Used when saas/ module is not available.
        """

        async def dispatch(self, request, call_next):
            # Pass through without metering
            return await call_next(request)


__all__ = ["APIMeteringMiddleware", "METERING_AVAILABLE", "METERED_PREFIXES", "EXCLUDED_PATHS"]
