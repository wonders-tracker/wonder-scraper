"""
Request timing middleware for performance monitoring.

Measures total request duration, logs slow requests, and adds X-Response-Time header.
Low overhead design suitable for production use.
"""

import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.perf_metrics import perf_metrics, SLOW_REQUEST_THRESHOLD_MS

logger = logging.getLogger(__name__)


# Paths to exclude from detailed timing (health checks, static files)
EXCLUDED_PATHS = frozenset({
    "/health",
    "/health/detailed",
    "/health/mode",
    "/health/metrics",
    "/health/circuits",
    "/health/performance",
    "/favicon.ico",
    "/robots.txt",
})


def _normalize_endpoint(path: str, method: str) -> str:
    """
    Normalize endpoint path for grouping.

    Replaces numeric IDs with {id} to group requests like:
    - /api/v1/cards/123 -> /api/v1/cards/{id}
    - /api/v1/portfolio/456/holdings -> /api/v1/portfolio/{id}/holdings

    This prevents metric explosion from unique IDs.
    """
    parts = path.rstrip("/").split("/")
    normalized_parts = []

    for part in parts:
        # Replace numeric IDs with placeholder
        if part.isdigit():
            normalized_parts.append("{id}")
        # Replace UUIDs with placeholder
        elif len(part) == 36 and part.count("-") == 4:
            normalized_parts.append("{uuid}")
        else:
            normalized_parts.append(part)

    normalized_path = "/".join(normalized_parts) or "/"
    return f"{method} {normalized_path}"


class TimingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that times requests and records performance metrics.

    Features:
    - Measures total request duration
    - Logs slow requests (>500ms by default)
    - Adds X-Response-Time header to responses
    - Records timing data to perf_metrics collector
    - Low overhead (simple time.perf_counter())
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Skip excluded paths
        path = request.url.path
        if path in EXCLUDED_PATHS:
            return await call_next(request)

        # Start timing
        start_time = time.perf_counter()

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration_seconds = time.perf_counter() - start_time
        duration_ms = duration_seconds * 1000

        # Add response header
        response.headers["X-Response-Time"] = f"{duration_ms:.2f}ms"

        # Normalize endpoint for metrics grouping
        endpoint = _normalize_endpoint(path, request.method)

        # Record to metrics collector
        perf_metrics.record(endpoint, duration_ms)

        # Log slow requests
        if duration_ms > SLOW_REQUEST_THRESHOLD_MS:
            client_ip = request.client.host if request.client else "unknown"
            logger.warning(
                "Slow request: %s %s completed in %.2fms (client: %s, status: %s)",
                request.method,
                path,
                duration_ms,
                client_ip,
                response.status_code,
            )

        return response


__all__ = ["TimingMiddleware"]
