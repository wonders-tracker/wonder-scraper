"""
Structured logging configuration using structlog.

Provides JSON-formatted logs for production (searchable/aggregatable)
and human-readable colored output for development.

Usage:
    from app.core.logging_config import get_logger

    logger = get_logger(__name__)
    logger.info("user logged in", user_id=123, email="user@example.com")

Output in production (JSON):
    {"event": "user logged in", "user_id": 123, "email": "user@example.com",
     "timestamp": "2024-01-01T12:00:00Z", "level": "info", "logger": "app.api.auth"}

Output in development (colored):
    2024-01-01 12:00:00 [info     ] user logged in    user_id=123 email=user@example.com
"""

import logging
import os
import sys
from typing import Any

import structlog

# Determine environment
IS_PRODUCTION = os.getenv("RAILWAY_ENVIRONMENT") is not None
IS_TEST = "pytest" in sys.modules


def configure_logging() -> None:
    """Configure structlog with appropriate processors for the environment."""

    # Shared processors for all environments
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    if IS_PRODUCTION:
        # Production: JSON output for log aggregation
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: colored, human-readable output
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=not IS_TEST),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging to use structlog
    # This captures logs from third-party libraries
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )

    # Reduce noise from chatty libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.WARNING)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        A structlog bound logger with JSON/console output based on environment
    """
    return structlog.get_logger(name)


# Configure on import
configure_logging()
