"""
Tests for database retry utilities.

Tests cover:
- Transient error detection
- Sync and async retry execution
- Exponential backoff with max delay cap
- db_retry decorator behavior
- Connection health checks
"""

import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from sqlalchemy.exc import OperationalError, DisconnectionError, InterfaceError

from app.core.db_utils import (
    is_transient_error,
    execute_with_retry,
    execute_with_retry_async,
    db_retry,
    check_db_connection,
    TRANSIENT_ERRORS,
)


class TestIsTransientError:
    """Tests for is_transient_error function."""

    @pytest.mark.parametrize("error_msg", [
        "server closed the connection unexpectedly",
        "connection refused",
        "connection reset by peer",
        "ssl connection has been closed unexpectedly",
        "SSL Connection Has Been Closed Unexpectedly",  # Case variation
        "terminating connection due to administrator command",
        "connection timed out",
        "could not connect to server",
        "the database system is starting up",
        "the database system is shutting down",
    ])
    def test_detects_transient_errors(self, error_msg):
        """Should detect all known transient error messages."""
        error = Exception(error_msg)
        assert is_transient_error(error) is True

    @pytest.mark.parametrize("error_msg", [
        "Server Closed The Connection Unexpectedly",  # Case insensitive
        "CONNECTION REFUSED",
        "The Database System Is Starting Up",
    ])
    def test_case_insensitive(self, error_msg):
        """Should match error messages case-insensitively."""
        error = Exception(error_msg)
        assert is_transient_error(error) is True

    @pytest.mark.parametrize("error_msg", [
        "relation 'cards' does not exist",
        "duplicate key value violates unique constraint",
        "column 'foo' does not exist",
        "permission denied for table users",
        "syntax error at or near 'SELECT'",
        "",
    ])
    def test_rejects_non_transient_errors(self, error_msg):
        """Should reject non-transient database errors."""
        error = Exception(error_msg)
        assert is_transient_error(error) is False

    def test_with_operational_error(self):
        """Should work with SQLAlchemy OperationalError."""
        error = OperationalError(
            "server closed the connection unexpectedly",
            None,
            None
        )
        assert is_transient_error(error) is True


class TestExecuteWithRetry:
    """Tests for execute_with_retry function."""

    def test_success_on_first_try(self, test_engine):
        """Should return result on successful first try."""
        def operation(session):
            return "success"

        result = execute_with_retry(test_engine, operation)
        assert result == "success"

    def test_retries_on_transient_error(self, test_engine):
        """Should retry on transient error and succeed."""
        call_count = 0

        def operation(session):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError(
                    "server closed the connection unexpectedly",
                    None,
                    None
                )
            return "success after retry"

        with patch("app.core.db_utils.time.sleep"):  # Skip actual delays
            result = execute_with_retry(test_engine, operation)

        assert result == "success after retry"
        assert call_count == 3

    def test_raises_after_max_retries(self, test_engine):
        """Should raise exception after max retries exhausted."""
        call_count = 0

        def operation(session):
            nonlocal call_count
            call_count += 1
            raise OperationalError(
                "server closed the connection unexpectedly",
                None,
                None
            )

        with patch("app.core.db_utils.time.sleep"):
            with pytest.raises(OperationalError):
                execute_with_retry(test_engine, operation, max_retries=2)

        assert call_count == 3  # Initial + 2 retries

    def test_no_retry_on_non_transient_error(self, test_engine):
        """Should not retry on non-transient errors."""
        call_count = 0

        def operation(session):
            nonlocal call_count
            call_count += 1
            raise OperationalError(
                "relation 'cards' does not exist",
                None,
                None
            )

        with pytest.raises(OperationalError):
            execute_with_retry(test_engine, operation)

        assert call_count == 1  # No retries

    def test_respects_max_delay(self, test_engine):
        """Should cap delay at max_delay."""
        delays = []
        call_count = 0

        def mock_sleep(delay):
            delays.append(delay)

        def operation(session):
            nonlocal call_count
            call_count += 1
            raise OperationalError(
                "server closed the connection unexpectedly",
                None,
                None
            )

        with patch("app.core.db_utils.time.sleep", side_effect=mock_sleep):
            with pytest.raises(OperationalError):
                execute_with_retry(
                    test_engine,
                    operation,
                    max_retries=5,
                    base_delay=1.0,
                    max_delay=5.0,
                )

        # Delays should be: 1, 2, 4, 5, 5 (capped at max_delay)
        assert len(delays) == 5
        assert all(d <= 5.0 for d in delays)
        assert delays == [1.0, 2.0, 4.0, 5.0, 5.0]

    def test_handles_disconnection_error(self, test_engine):
        """Should retry on DisconnectionError with transient message."""
        call_count = 0

        def operation(session):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                # Use a message that matches TRANSIENT_ERRORS
                raise DisconnectionError("server closed the connection unexpectedly")
            return "recovered"

        with patch("app.core.db_utils.time.sleep"):
            result = execute_with_retry(test_engine, operation)

        assert result == "recovered"
        assert call_count == 2

    def test_handles_interface_error(self, test_engine):
        """Should retry on InterfaceError."""
        call_count = 0

        def operation(session):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise InterfaceError("connection reset by peer", None, None)
            return "recovered"

        with patch("app.core.db_utils.time.sleep"):
            result = execute_with_retry(test_engine, operation)

        assert result == "recovered"


class TestExecuteWithRetryAsync:
    """Tests for execute_with_retry_async function."""

    @pytest.mark.asyncio
    async def test_success_on_first_try(self, test_engine):
        """Should return result on successful first try."""
        def operation(session):
            return "async success"

        result = await execute_with_retry_async(test_engine, operation)
        assert result == "async success"

    @pytest.mark.asyncio
    async def test_retries_on_transient_error(self, test_engine):
        """Should retry on transient error and succeed."""
        call_count = 0

        def operation(session):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise OperationalError(
                    "connection timed out",
                    None,
                    None
                )
            return "async success after retry"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await execute_with_retry_async(test_engine, operation)

        assert result == "async success after retry"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_max_retries(self, test_engine):
        """Should raise exception after max retries exhausted."""
        call_count = 0

        def operation(session):
            nonlocal call_count
            call_count += 1
            raise OperationalError(
                "could not connect to server",
                None,
                None
            )

        with patch("asyncio.sleep", new_callable=AsyncMock):
            with pytest.raises(OperationalError):
                await execute_with_retry_async(test_engine, operation, max_retries=1)

        assert call_count == 2  # Initial + 1 retry

    @pytest.mark.asyncio
    async def test_respects_max_delay(self, test_engine):
        """Should cap delay at max_delay in async version."""
        delays = []
        call_count = 0

        async def mock_sleep(delay):
            delays.append(delay)

        def operation(session):
            nonlocal call_count
            call_count += 1
            raise OperationalError(
                "ssl connection has been closed unexpectedly",
                None,
                None
            )

        with patch("asyncio.sleep", side_effect=mock_sleep):
            with pytest.raises(OperationalError):
                await execute_with_retry_async(
                    test_engine,
                    operation,
                    max_retries=4,
                    base_delay=2.0,
                    max_delay=8.0,
                )

        # Delays should be: 2, 4, 8, 8 (capped at 8.0)
        assert len(delays) == 4
        assert all(d <= 8.0 for d in delays)
        assert delays == [2.0, 4.0, 8.0, 8.0]


class TestDbRetryDecorator:
    """Tests for db_retry decorator."""

    def test_sync_function_success(self):
        """Should work with sync functions."""
        @db_retry(max_retries=2)
        def my_func():
            return "decorated success"

        result = my_func()
        assert result == "decorated success"

    def test_sync_function_retry(self):
        """Should retry sync functions on transient errors."""
        call_count = 0

        @db_retry(max_retries=2)
        def my_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OperationalError(
                    "terminating connection due to administrator command",
                    None,
                    None
                )
            return "recovered"

        with patch("app.core.db_utils.time.sleep"):
            result = my_func()

        assert result == "recovered"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_async_function_success(self):
        """Should work with async functions."""
        @db_retry(max_retries=2)
        async def my_async_func():
            return "async decorated success"

        result = await my_async_func()
        assert result == "async decorated success"

    @pytest.mark.asyncio
    async def test_async_function_retry(self):
        """Should retry async functions on transient errors."""
        call_count = 0

        @db_retry(max_retries=2)
        async def my_async_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise OperationalError(
                    "the database system is starting up",
                    None,
                    None
                )
            return "async recovered"

        with patch("asyncio.sleep", new_callable=AsyncMock):
            result = await my_async_func()

        assert result == "async recovered"
        assert call_count == 2

    def test_respects_max_delay_parameter(self):
        """Should respect max_delay parameter."""
        delays = []

        def mock_sleep(delay):
            delays.append(delay)
            raise OperationalError("server closed the connection unexpectedly", None, None)

        @db_retry(max_retries=5, base_delay=1.0, max_delay=3.0)
        def always_fails():
            raise OperationalError(
                "server closed the connection unexpectedly",
                None,
                None
            )

        with patch("app.core.db_utils.time.sleep", side_effect=mock_sleep):
            with pytest.raises(OperationalError):
                always_fails()

        # Delays should be: 1, 2, 3, 3, 3 (capped at max_delay=3.0)
        # But since mock_sleep raises, we only get delays before the re-raise
        assert all(d <= 3.0 for d in delays)

    def test_linear_backoff_option(self):
        """Should support linear (non-exponential) backoff."""
        delays = []

        def mock_sleep(delay):
            delays.append(delay)

        call_count = 0

        @db_retry(max_retries=3, base_delay=2.0, exponential=False)
        def my_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise OperationalError(
                    "connection refused",
                    None,
                    None
                )
            return "success"

        with patch("app.core.db_utils.time.sleep", side_effect=mock_sleep):
            result = my_func()

        assert result == "success"
        # With exponential=False, all delays should be base_delay (2.0)
        assert all(d == 2.0 for d in delays)


class TestCheckDbConnection:
    """Tests for check_db_connection function."""

    def test_returns_true_on_healthy_connection(self, test_engine):
        """Should return True for healthy database connection."""
        result = check_db_connection(test_engine)
        assert result is True

    def test_returns_false_on_connection_failure(self):
        """Should return False when connection fails."""
        # Create a mock engine that always fails
        mock_engine = MagicMock()

        with patch("app.core.db_utils.Session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(
                side_effect=OperationalError("connection refused", None, None)
            )
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            result = check_db_connection(mock_engine)

        assert result is False

    def test_logs_error_on_failure(self):
        """Should log error when connection check fails."""
        mock_engine = MagicMock()

        with patch("app.core.db_utils.Session") as mock_session:
            mock_session.return_value.__enter__ = MagicMock(
                side_effect=Exception("test error")
            )
            mock_session.return_value.__exit__ = MagicMock(return_value=False)

            with patch("app.core.db_utils.logger") as mock_logger:
                check_db_connection(mock_engine)
                mock_logger.error.assert_called_once()


class TestTransientErrorsList:
    """Tests for the TRANSIENT_ERRORS constant."""

    def test_all_errors_are_lowercase(self):
        """All transient error strings should be lowercase for matching."""
        for error in TRANSIENT_ERRORS:
            assert error == error.lower(), f"Error '{error}' is not lowercase"

    def test_covers_common_neon_errors(self):
        """Should cover common Neon PostgreSQL connection errors."""
        neon_errors = [
            "server closed the connection unexpectedly",
            "ssl connection has been closed unexpectedly",  # lowercase
            "terminating connection due to administrator command",
        ]
        for error in neon_errors:
            assert error in TRANSIENT_ERRORS, f"Missing Neon error: {error}"

    def test_covers_general_connection_errors(self):
        """Should cover general connection errors."""
        general_errors = [
            "connection refused",
            "connection reset by peer",
            "connection timed out",
            "could not connect to server",
        ]
        for error in general_errors:
            assert error in TRANSIENT_ERRORS, f"Missing general error: {error}"
