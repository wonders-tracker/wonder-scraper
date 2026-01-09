"""
Request context management for distributed tracing.

Provides request_id correlation across logs, metrics, and error tracking.
Uses contextvars for async-safe context propagation.

Usage:
    # In middleware (automatic)
    set_request_id(generate_request_id())

    # In business logic (read-only)
    logger.info("Processing", request_id=get_request_id())

    # In error handlers
    capture_exception(exc, context={"request_id": get_request_id()})
"""

from contextvars import ContextVar
from typing import Optional
import uuid

__all__ = [
    "set_request_id",
    "get_request_id",
    "generate_request_id",
    "set_user_id",
    "get_user_id",
    "set_correlation_id",
    "get_correlation_id",
    "clear_context",
    "get_context_dict",
]

# Context variables for request tracking (async-safe)
_request_id: ContextVar[Optional[str]] = ContextVar("request_id", default=None)
_user_id: ContextVar[Optional[int]] = ContextVar("user_id", default=None)
_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def generate_request_id() -> str:
    """
    Generate a new request ID.

    Format: req_{16 hex chars}
    Example: req_a1b2c3d4e5f6g7h8
    """
    return f"req_{uuid.uuid4().hex[:16]}"


def set_request_id(request_id: str) -> None:
    """Set request ID for current async context."""
    _request_id.set(request_id)


def get_request_id() -> Optional[str]:
    """Get request ID from current async context."""
    return _request_id.get()


def set_user_id(user_id: int) -> None:
    """Set user ID for current context (after auth)."""
    _user_id.set(user_id)


def get_user_id() -> Optional[int]:
    """Get user ID from current context."""
    return _user_id.get()


def set_correlation_id(correlation_id: str) -> None:
    """
    Set correlation ID for distributed tracing.

    Correlation ID spans multiple services/requests and is passed
    via X-Correlation-ID header for end-to-end tracing.
    """
    _correlation_id.set(correlation_id)


def get_correlation_id() -> Optional[str]:
    """Get correlation ID from current context."""
    return _correlation_id.get()


def clear_context() -> None:
    """
    Clear all context variables.

    Called at end of request to prevent context leaking.
    """
    _request_id.set(None)
    _user_id.set(None)
    _correlation_id.set(None)


def get_context_dict() -> dict:
    """
    Get all context variables as dict.

    Useful for enriching error reports or metrics.
    """
    return {
        "request_id": get_request_id(),
        "user_id": get_user_id(),
        "correlation_id": get_correlation_id(),
    }
