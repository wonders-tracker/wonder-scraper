"""
Request context middleware for observability.

Injects request_id, correlation_id into every request for:
- Log correlation (find all logs for a request)
- Error tracking (group errors by request)
- Distributed tracing (follow requests across services)

Also tracks performance metrics (latency, status codes) and samples
slow/error requests to the request_trace table for debugging.

Headers:
- X-Request-ID: Unique ID for this request (generated if not provided)
- X-Correlation-ID: ID spanning multiple services (passed through)
"""

import asyncio
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
    set_user_id,
    get_user_id,
    generate_request_id,
    clear_context,
)
from app.core.perf_metrics import perf_metrics
from app.core.config import settings

logger = structlog.get_logger(__name__)

# Threshold for sampling slow requests (ms)
SLOW_REQUEST_THRESHOLD_MS = 500.0

# Bounded semaphore for fire-and-forget trace writes
# Prevents thread pool exhaustion under heavy load
_trace_semaphore: Optional[asyncio.Semaphore] = None
_trace_dropped_count: int = 0

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


def _sample_request_trace_sync(
    request_id: str,
    correlation_id: Optional[str],
    user_id: Optional[int],
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Synchronous helper to persist request trace.
    Called from thread pool to avoid blocking event loop.
    """
    try:
        from sqlmodel import Session
        from app.db import engine
        from app.models.observability import RequestTrace

        with Session(engine) as session:
            trace = RequestTrace(
                request_id=request_id,
                correlation_id=correlation_id,
                method=method,
                path=path[:500],  # Truncate long paths
                status_code=status_code,
                duration_ms=duration_ms,
                user_id=user_id,
                error_type=error_type[:100] if error_type else None,
                error_message=error_message[:1000] if error_message else None,
            )
            session.add(trace)
            session.commit()

        logger.debug(
            "Request trace sampled",
            request_id=request_id,
            duration_ms=round(duration_ms, 1),
            status_code=status_code,
        )
    except Exception as e:
        # Fire-and-forget - log but don't fail
        logger.warning(
            "Failed to sample request trace",
            request_id=request_id,
            error=str(e),
        )


def _get_trace_semaphore() -> asyncio.Semaphore:
    """Get or create the bounded semaphore for trace writes."""
    global _trace_semaphore
    if _trace_semaphore is None:
        _trace_semaphore = asyncio.Semaphore(settings.TRACE_QUEUE_MAX_SIZE)
    return _trace_semaphore


async def _sample_request_trace(
    request_id: str,
    correlation_id: Optional[str],
    user_id: Optional[int],
    method: str,
    path: str,
    status_code: int,
    duration_ms: float,
    error_type: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    """
    Sample slow or error requests to the request_trace table.

    Uses thread pool executor to avoid blocking the event loop.
    Fire-and-forget - failures are logged but don't affect the request.

    Bounded queue: If more than TRACE_QUEUE_MAX_SIZE traces are pending,
    new traces are dropped to prevent thread pool exhaustion under load.
    """
    global _trace_dropped_count

    semaphore = _get_trace_semaphore()

    # Try to acquire semaphore without blocking
    # If queue is full, drop this trace (backpressure)
    if semaphore.locked():
        _trace_dropped_count += 1
        if _trace_dropped_count % 100 == 1:  # Log every 100th drop
            logger.warning(
                "Trace queue full, dropping request trace",
                request_id=request_id,
                dropped_total=_trace_dropped_count,
            )
        return

    async def _run_with_semaphore():
        async with semaphore:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(
                None,  # Default executor
                _sample_request_trace_sync,
                request_id,
                correlation_id,
                user_id,
                method,
                path,
                status_code,
                duration_ms,
                error_type,
                error_message,
            )

    # Fire-and-forget: schedule the task but don't await it
    asyncio.create_task(_run_with_semaphore())


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

                # Sample slow or error requests to request_trace table
                is_slow = duration_ms >= SLOW_REQUEST_THRESHOLD_MS
                is_error = status_code >= 500
                if is_slow or is_error:
                    # Get user_id before context cleanup
                    user_id = get_user_id()
                    # Fire-and-forget async trace (runs in thread pool)
                    await _sample_request_trace(
                        request_id=request_id,
                        correlation_id=correlation_id,
                        user_id=user_id,
                        method=request.method,
                        path=request.url.path,
                        status_code=status_code,
                        duration_ms=duration_ms,
                    )

            # Clean up context to prevent leaking to next request
            clear_context()
            structlog.contextvars.clear_contextvars()
