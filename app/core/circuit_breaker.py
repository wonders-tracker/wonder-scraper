from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass, field
from threading import Lock
from typing import Any, Callable, Dict, Optional
import logging

logger = logging.getLogger(__name__)

# Type alias for notification callback - return value is ignored
StateChangeCallback = Callable[[str, str, str], Any]  # (name, old_state, new_state)

# Global notification callback - set by application on startup
_notification_callback: Optional[StateChangeCallback] = None


def set_notification_callback(callback: StateChangeCallback) -> None:
    """Set the global notification callback for circuit breaker state changes."""
    global _notification_callback
    _notification_callback = callback


def _notify_state_change(name: str, old_state: str, new_state: str) -> None:
    """Notify about state change if callback is registered."""
    if _notification_callback:
        try:
            _notification_callback(name, old_state, new_state)
        except Exception as e:
            logger.error(f"Circuit breaker notification failed: {e}")


def _persist_state(name: str, state: str, failure_count: int, last_failure_at: Optional[datetime]) -> None:
    """Persist circuit breaker state to database (async-safe, non-blocking)."""
    try:
        # Import here to avoid circular imports
        from sqlmodel import Session, select
        from app.db import engine
        from app.models.circuit_breaker_state import CircuitBreakerState

        with Session(engine) as session:
            db_state = session.exec(select(CircuitBreakerState).where(CircuitBreakerState.name == name)).first()

            if db_state:
                db_state.state = state
                db_state.failure_count = failure_count
                db_state.last_failure_at = last_failure_at
                db_state.updated_at = datetime.now(timezone.utc)
            else:
                db_state = CircuitBreakerState(
                    name=name,
                    state=state,
                    failure_count=failure_count,
                    last_failure_at=last_failure_at,
                )
            session.add(db_state)
            session.commit()
    except Exception as e:
        # Don't let persistence failures break the circuit breaker
        logger.warning(f"Failed to persist circuit breaker state for {name}: {e}")


def _load_state(name: str) -> Optional[Dict[str, Any]]:
    """Load circuit breaker state from database."""
    try:
        from sqlmodel import Session, select
        from app.db import engine
        from app.models.circuit_breaker_state import CircuitBreakerState

        with Session(engine) as session:
            db_state = session.exec(select(CircuitBreakerState).where(CircuitBreakerState.name == name)).first()

            if db_state:
                return {
                    "state": db_state.state,
                    "failure_count": db_state.failure_count,
                    "last_failure_at": db_state.last_failure_at,
                }
    except Exception as e:
        logger.warning(f"Failed to load circuit breaker state for {name}: {e}")
    return None


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    half_open_max_calls: int = 3
    persist: bool = True  # Persist state to database

    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: datetime | None = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: Lock = field(default_factory=Lock, init=False)

    def __post_init__(self):
        """Restore state from database if persistence is enabled."""
        if self.persist:
            saved = _load_state(self.name)
            if saved:
                state_str = saved.get("state", "closed")
                try:
                    self._state = CircuitState(state_str)
                except ValueError:
                    self._state = CircuitState.CLOSED
                self._failure_count = saved.get("failure_count", 0)
                self._last_failure_time = saved.get("last_failure_at")
                logger.info(f"Circuit {self.name}: restored state={self._state.value}, failures={self._failure_count}")

    def _persist(self) -> None:
        """Persist current state to database."""
        if self.persist:
            _persist_state(
                self.name,
                self._state.value,
                self._failure_count,
                self._last_failure_time,
            )

    @property
    def state(self) -> CircuitState:
        """Return current state. Use allow_request() for state transitions."""
        return self._state

    def _check_recovery_transition(self) -> bool:
        """Check if circuit should transition from OPEN to HALF_OPEN.

        Must be called while holding self._lock.
        Returns True if state changed (for persistence).
        """
        if self._state == CircuitState.OPEN and self._last_failure_time:
            elapsed = (datetime.now(timezone.utc) - self._last_failure_time).total_seconds()
            if elapsed >= self.recovery_timeout:
                old_state = self._state.value
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0
                logger.info(f"Circuit {self.name}: OPEN -> HALF_OPEN")
                _notify_state_change(self.name, old_state, self._state.value)
                return True
        return False

    def record_success(self):
        state_changed = False
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    old_state = self._state.value
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED")
                    _notify_state_change(self.name, old_state, self._state.value)
                    state_changed = True
            else:
                self._failure_count = 0
        # Persist outside lock to avoid holding lock during DB operation
        if state_changed:
            self._persist()

    def record_failure(self):
        state_changed = False
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(timezone.utc)

            if self._state == CircuitState.HALF_OPEN:
                old_state = self._state.value
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (failure during recovery)")
                _notify_state_change(self.name, old_state, self._state.value)
                state_changed = True
            elif self._failure_count >= self.failure_threshold:
                old_state = self._state.value
                self._state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name}: CLOSED -> OPEN (threshold reached)")
                _notify_state_change(self.name, old_state, self._state.value)
                state_changed = True
        # Persist outside lock to avoid holding lock during DB operation
        if state_changed:
            self._persist()

    def allow_request(self) -> bool:
        state_changed = False
        with self._lock:
            # Check for recovery transition while holding the lock
            state_changed = self._check_recovery_transition()

            if self._state == CircuitState.CLOSED:
                result = True
            elif self._state == CircuitState.OPEN:
                result = False
            else:  # HALF_OPEN
                self._half_open_calls += 1
                result = self._half_open_calls <= self.half_open_max_calls
        # Persist outside lock
        if state_changed:
            self._persist()
        return result


class CircuitBreakerRegistry:
    _breakers: Dict[str, CircuitBreaker] = {}

    @classmethod
    def get(cls, name: str, **kwargs) -> CircuitBreaker:
        if name not in cls._breakers:
            cls._breakers[name] = CircuitBreaker(name=name, **kwargs)
        return cls._breakers[name]

    @classmethod
    def get_all_states(cls) -> Dict[str, str]:
        return {name: cb.state.value for name, cb in cls._breakers.items()}
