"""
Request context middleware for observability.

Injects request_id, correlation_id into every request for:
- Log correlation (find all logs for a request)
- Error tracking (group errors by request)
- Distributed tracing (follow requests across services)

Also tracks performance metrics (latency, status codes).

Headers:
- X-Request-ID: Unique ID for this request (generated if not provided)
- X-Correlation-ID: ID spanning multiple services (passed through)
"""

import re
import time
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.context import (
    set_request_id,
    get_request_id,
    set_correlation_id,
    get_correlation_id,
    generate_request_id,
    clear_context,
)
from app.core.perf_metrics import perf_metrics

logger = structlog.get_logger(__name__)

# Request ID validation to prevent log injection attacks
MAX_ID_LENGTH = 64
SAFE_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]+$")


def _validate_id(value: Optional[str]) -> Optional[str]:
    """
    Validate and sanitize request/correlation IDs.

    Returns None if invalid (will use generated ID instead).
    Protects against:
    - Log injection (control characters, newlines)
    - Excessive length causing log bloat
    - Special characters that could break log parsing
    """
    if not value:
        return None
    if len(value) > MAX_ID_LENGTH:
        return None
    if not SAFE_ID_PATTERN.match(value):
        return None
    return value


class RequestContextMiddleware(BaseHTTPMiddleware):
    """
    Middleware that manages request context for observability.

    Features:
    - Extracts X-Request-ID from headers or generates one
    - Extracts X-Correlation-ID for distributed tracing
    - Binds context to structlog for automatic log enrichment
    - Adds request_id to response headers for client debugging
    - Cleans up context after request completes

    Order: Should be early in middleware chain (after CORS, before auth)
    """

    async def dispatch(self, request: Request, call_next) -> Response:
        # Extract or generate request ID (with validation to prevent log injection)
        provided_id = _validate_id(request.headers.get("X-Request-ID"))
        request_id = provided_id or generate_request_id()
        set_request_id(request_id)

        # Store in request state for access in route handlers
        request.state.request_id = request_id

        # Extract correlation ID (for tracing across services)
        correlation_id = _validate_id(request.headers.get("X-Correlation-ID"))
        if correlation_id:
            set_correlation_id(correlation_id)

        # Bind to structlog for automatic inclusion in all logs
        # This makes every log message include request_id automatically
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            correlation_id=correlation_id,
            path=request.url.path,
            method=request.method,
        )

        # Start timing for performance metrics
        start_time = time.perf_counter()
        status_code = 500  # Default to error in case of exception

        try:
            response = await call_next(request)
            status_code = response.status_code

            # Add request_id to response headers for client debugging
            response.headers["X-Request-ID"] = request_id
            if correlation_id:
                response.headers["X-Correlation-ID"] = correlation_id

            return response
        finally:
            # Record performance metrics (skip health checks to avoid noise)
            duration_ms = (time.perf_counter() - start_time) * 1000
            if not request.url.path.startswith("/health"):
                perf_metrics.record_request(
                    request.url.path, duration_ms, status_code
                )

            # Clean up context to prevent leaking to next request
            clear_context()
            structlog.contextvars.clear_contextvars()
