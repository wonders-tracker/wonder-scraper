"""
Tests for circuit breaker functionality.

Tests cover:
1. State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
2. Core methods (record_success, record_failure, allow_request)
3. CircuitBreakerRegistry (get, get_all_states)
4. Edge cases (recovery timeout, half_open max calls)
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock

from app.core.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
)


class TestCircuitState:
    """Tests for CircuitState enum."""

    def test_circuit_states_exist(self):
        """Verify all expected circuit states are defined."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"

    def test_state_count(self):
        """Verify there are exactly 3 states."""
        assert len(CircuitState) == 3


class TestCircuitBreakerInitialization:
    """Tests for CircuitBreaker initialization."""

    def test_default_initialization(self):
        """Test that CircuitBreaker initializes with correct defaults."""
        cb = CircuitBreaker(name="test", persist=False)

        assert cb.name == "test"
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 60.0
        assert cb.half_open_max_calls == 3
        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._success_count == 0
        assert cb._last_failure_time is None
        assert cb._half_open_calls == 0

    def test_custom_initialization(self):
        """Test that CircuitBreaker accepts custom parameters."""
        cb = CircuitBreaker(
            name="custom",
            failure_threshold=10,
            recovery_timeout=120.0,
            half_open_max_calls=5,
        )

        assert cb.name == "custom"
        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 120.0
        assert cb.half_open_max_calls == 5

    def test_starts_in_closed_state(self):
        """Test that CircuitBreaker starts in CLOSED state."""
        cb = CircuitBreaker(name="test", persist=False)
        assert cb.state == CircuitState.CLOSED


class TestStateTransitions:
    """Tests for circuit breaker state transitions."""

    def test_closed_to_open_after_failure_threshold(self):
        """Test CLOSED -> OPEN after failure_threshold failures."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=3)

        # Record failures below threshold
        cb.record_failure()
        cb.record_failure()
        assert cb._state == CircuitState.CLOSED

        # Third failure should open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

    def test_open_to_half_open_after_recovery_timeout(self):
        """Test OPEN -> HALF_OPEN after recovery_timeout via allow_request."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, recovery_timeout=60.0)

        # Open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # Mock time to be past recovery timeout
        past_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb._last_failure_time = past_time

        # allow_request should trigger recovery check and transition
        result = cb.allow_request()
        assert cb._state == CircuitState.HALF_OPEN
        assert result is True  # First call in HALF_OPEN should be allowed

    def test_half_open_to_closed_after_successful_calls(self):
        """Test HALF_OPEN -> CLOSED after successful calls."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, half_open_max_calls=3)

        # Open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # Transition to HALF_OPEN via allow_request
        past_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb._last_failure_time = past_time
        cb.allow_request()  # Trigger transition

        assert cb._state == CircuitState.HALF_OPEN

        # Record successful calls
        cb.record_success()
        cb.record_success()
        assert cb._state == CircuitState.HALF_OPEN

        # Third success should close the circuit
        cb.record_success()
        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0
        assert cb._success_count == 0

    def test_half_open_to_open_on_failure_during_recovery(self):
        """Test HALF_OPEN -> OPEN on failure during recovery."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1)

        # Open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # Transition to HALF_OPEN via allow_request
        past_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb._last_failure_time = past_time
        cb.allow_request()

        assert cb._state == CircuitState.HALF_OPEN

        # Record a failure - should go back to OPEN
        cb.record_failure()
        assert cb._state == CircuitState.OPEN


class TestRecordSuccess:
    """Tests for record_success method."""

    def test_record_success_resets_failure_count(self):
        """Test that record_success resets failure count when CLOSED."""
        cb = CircuitBreaker(name="test_success_reset", failure_threshold=5, persist=False)

        # Accumulate some failures (but not enough to open)
        cb.record_failure()
        cb.record_failure()
        assert cb._failure_count == 2

        # Success should reset the count
        cb.record_success()
        assert cb._failure_count == 0

    def test_record_success_in_half_open_increments_success_count(self):
        """Test that record_success in HALF_OPEN increments success count."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, half_open_max_calls=3)

        # Get to HALF_OPEN state via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb.allow_request()

        assert cb._state == CircuitState.HALF_OPEN
        assert cb._success_count == 0

        cb.record_success()
        assert cb._success_count == 1

        cb.record_success()
        assert cb._success_count == 2

    def test_record_success_in_closed_does_not_change_success_count(self):
        """Test that record_success in CLOSED doesn't track success count."""
        cb = CircuitBreaker(name="test", persist=False)

        cb.record_success()
        cb.record_success()

        # Success count is only tracked in HALF_OPEN state
        assert cb._success_count == 0


class TestRecordFailure:
    """Tests for record_failure method."""

    def test_record_failure_increments_count(self):
        """Test that record_failure increments failure count."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=10)

        assert cb._failure_count == 0

        cb.record_failure()
        assert cb._failure_count == 1

        cb.record_failure()
        assert cb._failure_count == 2

        cb.record_failure()
        assert cb._failure_count == 3

    def test_record_failure_sets_last_failure_time(self):
        """Test that record_failure sets last_failure_time."""
        cb = CircuitBreaker(name="test", persist=False)

        assert cb._last_failure_time is None

        cb.record_failure()

        assert cb._last_failure_time is not None
        assert isinstance(cb._last_failure_time, datetime)

        # Should be recent (within last second)
        time_diff = (datetime.now(timezone.utc) - cb._last_failure_time).total_seconds()
        assert time_diff < 1.0

    def test_record_failure_opens_circuit_at_threshold(self):
        """Test that circuit opens when failure threshold is reached."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=3)

        cb.record_failure()
        assert cb._state == CircuitState.CLOSED

        cb.record_failure()
        assert cb._state == CircuitState.CLOSED

        cb.record_failure()
        assert cb._state == CircuitState.OPEN


class TestAllowRequest:
    """Tests for allow_request method."""

    def test_allow_request_when_closed(self):
        """Test that requests are allowed when circuit is CLOSED."""
        cb = CircuitBreaker(name="test", persist=False)

        assert cb._state == CircuitState.CLOSED
        assert cb.allow_request() is True

        # Multiple requests should all be allowed
        for _ in range(10):
            assert cb.allow_request() is True

    def test_allow_request_when_open(self):
        """Test that requests are blocked when circuit is OPEN."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1)

        # Open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # Requests should be blocked
        assert cb.allow_request() is False
        assert cb.allow_request() is False

    def test_allow_request_when_half_open(self):
        """Test that limited requests are allowed when circuit is HALF_OPEN."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, half_open_max_calls=3)

        # Get to HALF_OPEN state via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)

        # First call triggers transition and is allowed
        assert cb.allow_request() is True
        assert cb._state == CircuitState.HALF_OPEN
        assert cb._half_open_calls == 1

        # 2nd and 3rd requests should be allowed
        assert cb.allow_request() is True
        assert cb.allow_request() is True

        # 4th request should be blocked
        assert cb.allow_request() is False

    def test_allow_request_triggers_state_transition(self):
        """Test that allow_request can trigger OPEN -> HALF_OPEN transition."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, recovery_timeout=60.0)

        # Open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # Set time past recovery timeout
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)

        # allow_request should trigger state check and transition
        result = cb.allow_request()

        assert cb._state == CircuitState.HALF_OPEN
        assert result is True


class TestCircuitBreakerRegistry:
    """Tests for CircuitBreakerRegistry."""

    def setup_method(self):
        """Clear the registry before each test."""
        CircuitBreakerRegistry._breakers = {}

    def test_registry_creates_new_breaker(self):
        """Test that registry creates new breaker when name doesn't exist."""
        cb = CircuitBreakerRegistry.get("new_breaker")

        assert cb is not None
        assert cb.name == "new_breaker"
        assert isinstance(cb, CircuitBreaker)

    def test_registry_returns_existing_breaker(self):
        """Test that registry returns existing breaker for same name."""
        cb1 = CircuitBreakerRegistry.get("same_name")
        cb2 = CircuitBreakerRegistry.get("same_name")

        assert cb1 is cb2

    def test_registry_creates_separate_breakers(self):
        """Test that different names create different breakers."""
        cb1 = CircuitBreakerRegistry.get("breaker_1")
        cb2 = CircuitBreakerRegistry.get("breaker_2")

        assert cb1 is not cb2
        assert cb1.name == "breaker_1"
        assert cb2.name == "breaker_2"

    def test_registry_passes_kwargs_on_creation(self):
        """Test that registry passes kwargs when creating new breaker."""
        cb = CircuitBreakerRegistry.get(
            "custom_breaker",
            failure_threshold=10,
            recovery_timeout=120.0,
            half_open_max_calls=5,
        )

        assert cb.failure_threshold == 10
        assert cb.recovery_timeout == 120.0
        assert cb.half_open_max_calls == 5

    def test_registry_ignores_kwargs_for_existing_breaker(self):
        """Test that registry ignores kwargs for existing breaker."""
        cb1 = CircuitBreakerRegistry.get("test", failure_threshold=5)
        cb2 = CircuitBreakerRegistry.get("test", failure_threshold=10)

        # Should return same breaker with original settings
        assert cb1 is cb2
        assert cb2.failure_threshold == 5  # Original value, not 10

    def test_get_all_states(self):
        """Test that get_all_states returns all breaker states."""
        # Create multiple breakers in different states
        cb1 = CircuitBreakerRegistry.get("closed_breaker")
        cb2 = CircuitBreakerRegistry.get("open_breaker", failure_threshold=1)
        cb2.record_failure()  # Open it

        states = CircuitBreakerRegistry.get_all_states()

        assert states["closed_breaker"] == "closed"
        assert states["open_breaker"] == "open"

    def test_get_all_states_empty_registry(self):
        """Test get_all_states with empty registry."""
        states = CircuitBreakerRegistry.get_all_states()
        assert states == {}


class TestRecoveryTimeoutTransition:
    """Tests for recovery timeout behavior."""

    def test_recovery_timeout_transition(self):
        """Test that state transitions exactly at recovery timeout."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, recovery_timeout=30.0)

        # Open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # Set time just before recovery timeout (29 seconds)
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=29)
        assert cb.allow_request() is False  # Still open
        assert cb._state == CircuitState.OPEN

        # Set time at recovery timeout (30 seconds)
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=30)
        assert cb.allow_request() is True  # Should transition
        assert cb._state == CircuitState.HALF_OPEN

    def test_recovery_timeout_resets_half_open_calls(self):
        """Test that transitioning to HALF_OPEN resets half_open_calls counter."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, recovery_timeout=60.0)

        # Open the circuit
        cb.record_failure()
        cb._half_open_calls = 5  # Simulate some leftover state

        # Trigger OPEN -> HALF_OPEN transition via allow_request
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb.allow_request()

        assert cb._state == CircuitState.HALF_OPEN
        # half_open_calls gets reset to 0, then incremented to 1 by allow_request
        assert cb._half_open_calls == 1

    def test_no_transition_without_last_failure_time(self):
        """Test that OPEN state doesn't transition if last_failure_time is None."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1)

        # Manually set state to OPEN without recording failure
        cb._state = CircuitState.OPEN
        cb._last_failure_time = None

        # Should stay OPEN (no transition possible without timestamp)
        assert cb.allow_request() is False
        assert cb._state == CircuitState.OPEN


class TestHalfOpenMaxCallsLimit:
    """Tests for half_open_max_calls behavior."""

    def test_half_open_max_calls_limit(self):
        """Test that HALF_OPEN state limits number of allowed calls."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, half_open_max_calls=2)

        # Get to HALF_OPEN via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)

        # First call triggers transition and is call #1
        assert cb.allow_request() is True
        assert cb._half_open_calls == 1

        # Second call
        assert cb.allow_request() is True
        assert cb._half_open_calls == 2

        # 3rd call blocked
        assert cb.allow_request() is False
        assert cb._half_open_calls == 3  # Still incremented but returned False

    def test_half_open_max_calls_with_different_values(self):
        """Test HALF_OPEN with various max_calls settings."""
        for max_calls in [1, 3, 5, 10]:
            cb = CircuitBreaker(name=f"test_{max_calls}", failure_threshold=1, half_open_max_calls=max_calls)

            # Get to HALF_OPEN via allow_request
            cb.record_failure()
            cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)

            # Should allow exactly max_calls requests
            for i in range(max_calls):
                assert cb.allow_request() is True, f"Call {i+1} should be allowed"

            # Next call should be blocked
            assert cb.allow_request() is False


class TestThreadSafety:
    """Tests for thread safety mechanisms."""

    def test_has_lock(self):
        """Test that CircuitBreaker has a lock for thread safety."""
        cb = CircuitBreaker(name="test", persist=False)
        assert hasattr(cb, "_lock")

    def test_record_success_uses_lock(self):
        """Test that record_success acquires the lock."""
        cb = CircuitBreaker(name="test", persist=False)

        # Mock the lock to verify it's used
        with patch.object(cb, "_lock") as mock_lock:
            mock_lock.__enter__ = MagicMock(return_value=None)
            mock_lock.__exit__ = MagicMock(return_value=False)

            cb.record_success()

            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_record_failure_uses_lock(self):
        """Test that record_failure acquires the lock."""
        cb = CircuitBreaker(name="test", persist=False)

        with patch.object(cb, "_lock") as mock_lock:
            mock_lock.__enter__ = MagicMock(return_value=None)
            mock_lock.__exit__ = MagicMock(return_value=False)

            cb.record_failure()

            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()

    def test_allow_request_uses_lock(self):
        """Test that allow_request acquires the lock."""
        cb = CircuitBreaker(name="test", persist=False)

        with patch.object(cb, "_lock") as mock_lock:
            mock_lock.__enter__ = MagicMock(return_value=None)
            mock_lock.__exit__ = MagicMock(return_value=False)

            cb.allow_request()

            mock_lock.__enter__.assert_called_once()
            mock_lock.__exit__.assert_called_once()


class TestLogging:
    """Tests for logging behavior."""

    def test_logs_closed_to_open_transition(self):
        """Test that CLOSED -> OPEN transition is logged."""
        cb = CircuitBreaker(name="test_log", persist=False, failure_threshold=1)

        with patch("app.core.circuit_breaker.logger") as mock_logger:
            cb.record_failure()

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "test_log" in call_args
            assert "CLOSED -> OPEN" in call_args

    def test_logs_half_open_to_open_transition(self):
        """Test that HALF_OPEN -> OPEN transition is logged."""
        cb = CircuitBreaker(name="test_log", persist=False, failure_threshold=1)

        # Get to HALF_OPEN via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb.allow_request()

        with patch("app.core.circuit_breaker.logger") as mock_logger:
            cb.record_failure()

            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args[0][0]
            assert "test_log" in call_args
            assert "HALF_OPEN -> OPEN" in call_args

    def test_logs_half_open_to_closed_transition(self):
        """Test that HALF_OPEN -> CLOSED transition is logged."""
        cb = CircuitBreaker(name="test_log", failure_threshold=1, half_open_max_calls=1)

        # Get to HALF_OPEN via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb.allow_request()

        with patch("app.core.circuit_breaker.logger") as mock_logger:
            cb.record_success()

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_log" in call_args
            assert "HALF_OPEN -> CLOSED" in call_args

    def test_logs_open_to_half_open_transition(self):
        """Test that OPEN -> HALF_OPEN transition is logged."""
        cb = CircuitBreaker(name="test_log", persist=False, failure_threshold=1)

        # Open the circuit
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)

        with patch("app.core.circuit_breaker.logger") as mock_logger:
            # allow_request triggers the recovery transition
            cb.allow_request()

            mock_logger.info.assert_called_once()
            call_args = mock_logger.info.call_args[0][0]
            assert "test_log" in call_args
            assert "OPEN -> HALF_OPEN" in call_args


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_failure_threshold_of_one(self):
        """Test circuit breaker with failure_threshold of 1."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1)

        assert cb._state == CircuitState.CLOSED
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

    def test_half_open_max_calls_of_one(self):
        """Test circuit breaker with half_open_max_calls of 1."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, half_open_max_calls=1)

        # Get to HALF_OPEN via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)

        # First call triggers transition and is allowed
        assert cb.allow_request() is True
        assert cb._state == CircuitState.HALF_OPEN

        # Second call blocked
        assert cb.allow_request() is False

        # One success should close it (reset half_open_calls first)
        cb._half_open_calls = 0
        cb.record_success()
        assert cb._state == CircuitState.CLOSED

    def test_very_short_recovery_timeout(self):
        """Test circuit breaker with very short recovery timeout."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, recovery_timeout=0.001)

        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # With such a short timeout, should transition almost immediately
        import time

        time.sleep(0.01)

        # allow_request checks recovery transition
        result = cb.allow_request()
        assert cb._state == CircuitState.HALF_OPEN
        assert result is True

    def test_rapid_state_changes(self):
        """Test rapid open/close cycles."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, half_open_max_calls=1)

        for _ in range(5):
            # CLOSED -> OPEN
            cb.record_failure()
            assert cb._state == CircuitState.OPEN

            # OPEN -> HALF_OPEN (via allow_request)
            cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
            cb.allow_request()
            assert cb._state == CircuitState.HALF_OPEN

            # HALF_OPEN -> CLOSED
            cb.record_success()
            assert cb._state == CircuitState.CLOSED

    def test_success_before_any_failure(self):
        """Test that success with no prior failures works correctly."""
        cb = CircuitBreaker(name="test", persist=False)

        cb.record_success()
        cb.record_success()

        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_multiple_successes_in_half_open(self):
        """Test multiple successes needed to close in HALF_OPEN."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, half_open_max_calls=5)

        # Get to HALF_OPEN via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb.allow_request()

        assert cb._state == CircuitState.HALF_OPEN

        # Record 4 successes - should still be HALF_OPEN
        for _ in range(4):
            cb.record_success()
            assert cb._state == CircuitState.HALF_OPEN

        # 5th success should close it
        cb.record_success()
        assert cb._state == CircuitState.CLOSED

    def test_registry_with_many_breakers(self):
        """Test registry with many circuit breakers."""
        # Clear registry first
        CircuitBreakerRegistry._breakers = {}

        # Create many breakers
        for i in range(100):
            cb = CircuitBreakerRegistry.get(f"breaker_{i}")
            assert cb.name == f"breaker_{i}"

        # Verify all are tracked
        states = CircuitBreakerRegistry.get_all_states()
        assert len(states) == 100

    def test_state_property_is_idempotent_in_closed(self):
        """Test that accessing state property doesn't change CLOSED state."""
        cb = CircuitBreaker(name="test", persist=False)

        # Access state multiple times
        for _ in range(10):
            assert cb.state == CircuitState.CLOSED

    def test_state_property_is_idempotent_in_half_open(self):
        """Test that accessing state property doesn't change HALF_OPEN state."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1)

        # Get to HALF_OPEN via allow_request
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb.allow_request()

        assert cb._state == CircuitState.HALF_OPEN

        # Access state property multiple times - should stay HALF_OPEN
        for _ in range(10):
            assert cb.state == CircuitState.HALF_OPEN

    def test_check_recovery_transition_private_method(self):
        """Test the _check_recovery_transition private method."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1, recovery_timeout=60.0)

        # Open the circuit
        cb.record_failure()
        assert cb._state == CircuitState.OPEN

        # Set time past recovery timeout
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)

        # Call _check_recovery_transition directly (must hold lock)
        with cb._lock:
            cb._check_recovery_transition()

        assert cb._state == CircuitState.HALF_OPEN
        assert cb._half_open_calls == 0

    def test_check_recovery_transition_does_nothing_when_closed(self):
        """Test that _check_recovery_transition does nothing when CLOSED."""
        cb = CircuitBreaker(name="test", persist=False)

        # Call when CLOSED
        with cb._lock:
            cb._check_recovery_transition()

        assert cb._state == CircuitState.CLOSED

    def test_check_recovery_transition_does_nothing_when_half_open(self):
        """Test that _check_recovery_transition does nothing when HALF_OPEN."""
        cb = CircuitBreaker(name="test", persist=False, failure_threshold=1)

        # Get to HALF_OPEN
        cb.record_failure()
        cb._last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=61)
        cb.allow_request()

        assert cb._state == CircuitState.HALF_OPEN

        # Call _check_recovery_transition - should do nothing
        with cb._lock:
            cb._check_recovery_transition()

        assert cb._state == CircuitState.HALF_OPEN
