"""
API usage metering middleware for Polar billing.

Tracks API requests and sends usage events to Polar for metered billing.
"""
import asyncio
import logging
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger(__name__)


# Endpoints to meter (API data endpoints)
METERED_PREFIXES = [
    "/api/v1/cards",
    "/api/v1/market",
    "/api/v1/blokpax",
]

# Endpoints to exclude from metering
EXCLUDED_PATHS = [
    "/api/v1/cards/search",  # Search is free
    "/api/v1/billing",
    "/api/v1/webhooks",
    "/api/v1/auth",
    "/api/v1/users",
    "/api/v1/analytics",
]


class APIMeteringMiddleware(BaseHTTPMiddleware):
    """
    Middleware to track API usage and send events to Polar.

    Only meters requests from authenticated users with a Polar customer ID.
    Runs asynchronously to not block the response.
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        # Only meter successful API requests
        if response.status_code >= 400:
            return response

        # Check if this path should be metered
        path = request.url.path
        if not self._should_meter(path):
            return response

        # Get user from request state (set by auth dependency)
        user = getattr(request.state, "user", None)
        if not user or not getattr(user, "polar_customer_id", None):
            return response

        # Send usage event asynchronously (don't block response)
        asyncio.create_task(
            self._send_usage_event(
                customer_id=user.polar_customer_id,
                endpoint=path,
                method=request.method
            )
        )

        return response

    def _should_meter(self, path: str) -> bool:
        """Check if the request path should be metered."""
        # Check exclusions first
        for excluded in EXCLUDED_PATHS:
            if path.startswith(excluded):
                return False

        # Check if it matches a metered prefix
        for prefix in METERED_PREFIXES:
            if path.startswith(prefix):
                return True

        return False

    async def _send_usage_event(
        self,
        customer_id: str,
        endpoint: str,
        method: str
    ) -> None:
        """Send usage event to Polar (fire and forget)."""
        try:
            from app.services.polar import ingest_usage_event

            await ingest_usage_event(
                customer_id=customer_id,
                event_name="api_request",
                metadata={
                    "endpoint": endpoint,
                    "method": method,
                    "requests": 1
                }
            )
        except Exception as e:
            # Log but don't fail - metering shouldn't break the API
            logger.exception("Failed to send usage event", extra={"customer_id": customer_id, "endpoint": endpoint})
