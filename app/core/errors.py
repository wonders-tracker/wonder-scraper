"""
Unified error handling with Sentry integration.

Provides centralized exception handling with:
- Automatic Sentry error tracking (when configured)
- Structured logging with context enrichment
- Custom fingerprinting for error grouping
- Graceful degradation when Sentry unavailable

Usage:
    # Capture an exception
    capture_exception(exc, context={"card_id": 123})

    # Capture a message (non-exception event)
    capture_message("Parse failed for title", level="warning")

    # Context manager for operations
    with ErrorHandler("scrape_ebay", card_name="Dragonmaster Cai"):
        scrape_card(...)
"""

from typing import Optional, Any, Dict
from datetime import datetime, timezone
from contextlib import contextmanager
import structlog

from app.core.context import get_request_id, get_user_id, get_context_dict

logger = structlog.get_logger(__name__)

__all__ = [
    "init_sentry",
    "capture_exception",
    "capture_message",
    "ErrorHandler",
    "is_sentry_enabled",
]

# Lazy-loaded Sentry SDK (optional dependency)
_sentry_initialized: bool = False
_sentry_dsn: Optional[str] = None


def init_sentry(
    dsn: str,
    environment: str = "production",
    traces_sample_rate: float = 0.1,
    release: Optional[str] = None,
) -> bool:
    """
    Initialize Sentry SDK for error tracking.

    Args:
        dsn: Sentry DSN (from project settings)
        environment: Environment name (production, staging, development)
        traces_sample_rate: Percentage of transactions to trace (0.0-1.0)
        release: Release version (defaults to RAILWAY_GIT_COMMIT_SHA)

    Returns:
        True if initialization successful, False otherwise
    """
    global _sentry_initialized, _sentry_dsn

    if not dsn:
        logger.info("Sentry disabled (no DSN provided)")
        return False

    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        import logging
        import os

        # Get release from Railway environment if not provided
        if not release:
            release = os.environ.get("RAILWAY_GIT_COMMIT_SHA")

        sentry_sdk.init(
            dsn=dsn,
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            release=release,
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(
                    level=logging.INFO,
                    event_level=logging.ERROR,
                ),
            ],
            # Don't send errors for these exceptions
            ignore_errors=[
                KeyboardInterrupt,
                SystemExit,
            ],
            # Filter out health check transactions
            traces_sampler=_traces_sampler,
            # Add tags to all events
            before_send=_before_send,
        )

        _sentry_initialized = True
        _sentry_dsn = dsn
        logger.info(
            "Sentry initialized",
            environment=environment,
            traces_sample_rate=traces_sample_rate,
            release=release,
        )
        return True

    except ImportError:
        logger.warning("Sentry SDK not installed, error tracking disabled")
        return False
    except Exception as e:
        logger.error("Failed to initialize Sentry", error=str(e))
        return False


def _traces_sampler(sampling_context: Dict[str, Any]) -> float:
    """Custom sampler to filter out health check transactions."""
    # Get the transaction name or path
    transaction_name = sampling_context.get("transaction_context", {}).get("name", "")
    parent = sampling_context.get("parent_sampled")

    # Always inherit parent's decision if available
    if parent is not None:
        return float(parent)

    # Don't trace health checks
    if "/health" in transaction_name:
        return 0.0

    # Default sample rate (will be overridden by traces_sample_rate)
    return 0.1


def _before_send(event: Dict[str, Any], hint: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Process event before sending to Sentry."""
    # Filter out health check errors
    if "request" in event:
        url = event["request"].get("url", "")
        if "/health" in url:
            return None

    # Add request context if available
    request_id = get_request_id()
    if request_id:
        event.setdefault("tags", {})["request_id"] = request_id

    user_id = get_user_id()
    if user_id:
        event.setdefault("user", {})["id"] = str(user_id)

    return event


def is_sentry_enabled() -> bool:
    """Check if Sentry is initialized and available."""
    return _sentry_initialized


def capture_exception(
    exc: BaseException,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error",
    fingerprint: Optional[list[str]] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Capture an exception with Sentry and structured logging.

    Args:
        exc: Exception to capture
        context: Additional context dict (e.g., {"card_id": 123})
        level: Severity level (debug, info, warning, error, fatal)
        fingerprint: Custom grouping fingerprint for Sentry
        tags: Additional tags for filtering in Sentry

    Returns:
        Sentry event ID (for user error reports) or None if not sent
    """
    # Enrich context with request info
    enriched_context = {
        **get_context_dict(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "error_type": type(exc).__name__,
        **(context or {}),
    }

    # Log with structlog (always, even without Sentry)
    logger.error(
        "Exception captured",
        exc_info=exc,
        **enriched_context,
    )

    # Send to Sentry if available
    if _sentry_initialized:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                # Add context
                for key, value in enriched_context.items():
                    if value is not None:
                        scope.set_extra(key, value)

                # Add tags
                if tags:
                    for key, value in tags.items():
                        scope.set_tag(key, value)

                # Set custom fingerprint for grouping
                if fingerprint:
                    scope.fingerprint = fingerprint

                # Set level
                scope.level = level

                # Capture exception
                event_id = sentry_sdk.capture_exception(exc)
                return event_id
        except Exception as e:
            logger.warning("Failed to send exception to Sentry", error=str(e))

    return None


def capture_message(
    message: str,
    level: str = "info",
    context: Optional[Dict[str, Any]] = None,
    tags: Optional[Dict[str, str]] = None,
) -> Optional[str]:
    """
    Capture a message with Sentry (for non-exception events).

    Useful for:
    - Parse failures (silent errors that don't raise exceptions)
    - Business logic warnings
    - Performance degradation alerts
    - Circuit breaker state changes

    Args:
        message: Message to capture
        level: Severity level (debug, info, warning, error, fatal)
        context: Additional context dict
        tags: Additional tags for filtering

    Returns:
        Sentry event ID or None if not sent
    """
    enriched_context = {
        **get_context_dict(),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **(context or {}),
    }

    # Log with structlog
    log_func = getattr(logger, level, logger.info)
    log_func(message, **enriched_context)

    # Send to Sentry if available
    if _sentry_initialized:
        try:
            import sentry_sdk

            with sentry_sdk.push_scope() as scope:
                for key, value in enriched_context.items():
                    if value is not None:
                        scope.set_extra(key, value)

                if tags:
                    for key, value in tags.items():
                        scope.set_tag(key, value)

                scope.level = level
                event_id = sentry_sdk.capture_message(message, level=level)
                return event_id
        except Exception as e:
            logger.warning("Failed to send message to Sentry", error=str(e))

    return None


class ErrorHandler:
    """
    Context manager for handling errors with automatic capture.

    Provides a clean pattern for wrapping operations that might fail,
    with automatic Sentry capture and optional suppression.

    Usage:
        # Suppress and capture errors
        with ErrorHandler("scrape_ebay", card_name="Dragonmaster Cai"):
            scrape_card(...)

        # Re-raise after capturing
        with ErrorHandler("process_payment", reraise=True):
            charge_card(...)

        # Don't capture (logging only)
        with ErrorHandler("cleanup", capture=False):
            cleanup_temp_files()

    Args:
        operation: Name of the operation (for grouping in Sentry)
        context: Additional context dict
        capture: Whether to send to Sentry (default: True)
        reraise: Whether to re-raise exception (default: False)
        fingerprint: Custom fingerprint for Sentry grouping
    """

    def __init__(
        self,
        operation: str,
        context: Optional[Dict[str, Any]] = None,
        capture: bool = True,
        reraise: bool = False,
        fingerprint: Optional[list[str]] = None,
    ):
        self.operation = operation
        self.context = context or {}
        self.capture = capture
        self.reraise = reraise
        self.fingerprint = fingerprint or [operation]
        self.event_id: Optional[str] = None

    def __enter__(self) -> "ErrorHandler":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_val is not None:
            if self.capture:
                self.event_id = capture_exception(
                    exc_val,
                    context={
                        "operation": self.operation,
                        **self.context,
                    },
                    fingerprint=self.fingerprint + [type(exc_val).__name__],
                )

            # Return True to suppress exception (unless reraise=True)
            return not self.reraise

        return False


@contextmanager
def error_boundary(operation: str, **context):
    """
    Simplified error boundary for common use case.

    Captures and suppresses errors, logging with context.

    Usage:
        with error_boundary("parse_price", raw_price=price_text):
            return float(price_text)
    """
    handler = ErrorHandler(operation, context=context, capture=True, reraise=False)
    with handler:
        yield handler
