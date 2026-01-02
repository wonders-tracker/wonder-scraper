"""Database utilities for handling transient connection failures.

Neon serverless PostgreSQL can drop connections unexpectedly, especially
during long-running operations or when the database scales down.
This module provides retry logic to handle these transient failures.
"""

import asyncio
import functools
import logging
from typing import TypeVar, Callable, Any, ParamSpec
from sqlmodel import Session
from sqlalchemy import text
from sqlalchemy.exc import (
    OperationalError,
    DisconnectionError,
    InterfaceError,
)

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")

# Errors that indicate a transient connection failure (worth retrying)
TRANSIENT_ERRORS = (
    "server closed the connection unexpectedly",
    "connection refused",
    "connection reset by peer",
    "SSL connection has been closed unexpectedly",
    "terminating connection due to administrator command",
    "connection timed out",
    "could not connect to server",
    "the database system is starting up",
    "the database system is shutting down",
)


def is_transient_error(error: Exception) -> bool:
    """Check if an error is a transient connection failure."""
    error_msg = str(error).lower()
    return any(msg in error_msg for msg in TRANSIENT_ERRORS)


def db_retry(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    exponential: bool = True,
) -> Callable[[Callable[P, T]], Callable[P, T]]:
    """
    Decorator that retries a database operation on transient connection failures.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential: Use exponential backoff if True
    """

    def decorator(func: Callable[P, T]) -> Callable[P, T]:
        func_name = getattr(func, "__name__", "unknown")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)  # type: ignore[arg-type]
                except (OperationalError, DisconnectionError, InterfaceError) as e:
                    last_error = e
                    if not is_transient_error(e) or attempt >= max_retries:
                        raise

                    delay = min(
                        base_delay * (2**attempt if exponential else 1),
                        max_delay,
                    )
                    logger.warning(
                        f"[DB Retry] {func_name} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    import time

                    time.sleep(delay)

            if last_error:
                raise last_error
            raise RuntimeError("Unexpected state in db_retry")

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            last_error: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)  # type: ignore[arg-type]
                    if asyncio.iscoroutine(result):
                        return await result  # type: ignore[misc]
                    return result  # type: ignore[return-value]
                except (OperationalError, DisconnectionError, InterfaceError) as e:
                    last_error = e
                    if not is_transient_error(e) or attempt >= max_retries:
                        raise

                    delay = min(
                        base_delay * (2**attempt if exponential else 1),
                        max_delay,
                    )
                    logger.warning(
                        f"[DB Retry] {func_name} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)

            if last_error:
                raise last_error
            raise RuntimeError("Unexpected state in db_retry")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore[return-value]
        return sync_wrapper  # type: ignore[return-value]

    return decorator


def execute_with_retry(
    engine,
    operation: Callable[[Session], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """
    Execute a database operation with automatic retry on transient failures.

    Args:
        engine: SQLAlchemy engine
        operation: Function that takes a Session and returns a result
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries

    Returns:
        The result of the operation

    Example:
        def update_card(session):
            card = session.get(Card, card_id)
            card.name = "New Name"
            session.commit()
            return card

        result = execute_with_retry(engine, update_card)
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            with Session(engine) as session:
                return operation(session)
        except (OperationalError, DisconnectionError, InterfaceError) as e:
            last_error = e
            if not is_transient_error(e) or attempt >= max_retries:
                raise

            delay = base_delay * (2**attempt)
            logger.warning(
                f"[DB Retry] Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            import time

            time.sleep(delay)

    raise last_error  # type: ignore


async def execute_with_retry_async(
    engine,
    operation: Callable[[Session], T],
    max_retries: int = 3,
    base_delay: float = 1.0,
) -> T:
    """
    Async version of execute_with_retry.
    Note: The operation itself is sync (SQLModel sessions are sync),
    but the retry delays are async.
    """
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            with Session(engine) as session:
                return operation(session)
        except (OperationalError, DisconnectionError, InterfaceError) as e:
            last_error = e
            if not is_transient_error(e) or attempt >= max_retries:
                raise

            delay = base_delay * (2**attempt)
            logger.warning(
                f"[DB Retry] Operation failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)

    raise last_error  # type: ignore


def check_db_connection(engine) -> bool:  # type: ignore[type-arg]
    """
    Check if database connection is healthy.
    Returns True if connection is good, False otherwise.
    """
    try:
        with Session(engine) as session:
            session.execute(text("SELECT 1"))
            return True
    except Exception as e:
        logger.error(f"[DB Health] Connection check failed: {e}")
        return False
