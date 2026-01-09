"""
Tests for observability components.

Tests:
- Request context management
- Error handler with Sentry
- Health threshold checking
- Health check system
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.core.context import (
    set_request_id,
    get_request_id,
    generate_request_id,
    set_user_id,
    get_user_id,
    set_correlation_id,
    get_correlation_id,
    clear_context,
    get_context_dict,
)
from app.core.health_thresholds import (
    HealthThresholds,
    Threshold,
    check_threshold,
)
from app.core.errors import ErrorHandler, capture_exception, capture_message


class TestRequestContext:
    """Tests for request context management."""

    def test_generate_request_id_format(self):
        """Test request ID format: req_{16 hex chars}."""
        request_id = generate_request_id()
        assert request_id.startswith("req_")
        assert len(request_id) == 20  # req_ + 16 chars

    def test_request_id_context(self):
        """Test setting and getting request ID."""
        clear_context()
        assert get_request_id() is None

        set_request_id("req_test123")
        assert get_request_id() == "req_test123"

        clear_context()
        assert get_request_id() is None

    def test_user_id_context(self):
        """Test setting and getting user ID."""
        clear_context()
        assert get_user_id() is None

        set_user_id(42)
        assert get_user_id() == 42

        clear_context()
        assert get_user_id() is None

    def test_correlation_id_context(self):
        """Test setting and getting correlation ID."""
        clear_context()
        assert get_correlation_id() is None

        set_correlation_id("corr_abc123")
        assert get_correlation_id() == "corr_abc123"

        clear_context()
        assert get_correlation_id() is None

    def test_get_context_dict(self):
        """Test getting all context as dict."""
        clear_context()
        set_request_id("req_test")
        set_user_id(123)
        set_correlation_id("corr_test")

        context = get_context_dict()
        assert context["request_id"] == "req_test"
        assert context["user_id"] == 123
        assert context["correlation_id"] == "corr_test"

        clear_context()

    def test_clear_context(self):
        """Test clearing all context variables."""
        set_request_id("req_test")
        set_user_id(123)
        set_correlation_id("corr_test")

        clear_context()

        assert get_request_id() is None
        assert get_user_id() is None
        assert get_correlation_id() is None


class TestHealthThresholds:
    """Tests for health threshold checking."""

    def test_check_threshold_ok(self):
        """Test value below warning threshold."""
        threshold = Threshold(warning=0.3, critical=0.5)
        assert check_threshold(0.2, threshold) == "ok"

    def test_check_threshold_warning(self):
        """Test value at warning threshold."""
        threshold = Threshold(warning=0.3, critical=0.5)
        assert check_threshold(0.3, threshold) == "warning"
        assert check_threshold(0.4, threshold) == "warning"

    def test_check_threshold_critical(self):
        """Test value at critical threshold."""
        threshold = Threshold(warning=0.3, critical=0.5)
        assert check_threshold(0.5, threshold) == "critical"
        assert check_threshold(0.9, threshold) == "critical"

    def test_scraper_stale_hours_threshold(self):
        """Test scraper stale hours threshold values."""
        # Verify default thresholds (1h warn, 3h critical)
        assert HealthThresholds.SCRAPER_STALE_HOURS.warning == 1.0
        assert HealthThresholds.SCRAPER_STALE_HOURS.critical == 3.0

        assert check_threshold(0.5, HealthThresholds.SCRAPER_STALE_HOURS) == "ok"
        assert check_threshold(1.5, HealthThresholds.SCRAPER_STALE_HOURS) == "warning"
        assert check_threshold(4.0, HealthThresholds.SCRAPER_STALE_HOURS) == "critical"

    def test_api_slow_request_rate_threshold(self):
        """Test API slow request rate threshold."""
        # Verify default thresholds (10% warn, 30% critical)
        assert HealthThresholds.API_SLOW_REQUEST_RATE.warning == 0.1
        assert HealthThresholds.API_SLOW_REQUEST_RATE.critical == 0.3

    def test_threshold_str(self):
        """Test threshold string representation."""
        threshold = Threshold(warning=0.3, critical=0.5, unit="ratio", name="test")
        assert "test" in str(threshold)
        assert "0.3" in str(threshold)
        assert "0.5" in str(threshold)

    def test_get_all_thresholds(self):
        """Test getting all thresholds as dict."""
        all_thresholds = HealthThresholds.get_all()
        assert "SCRAPER_STALE_HOURS" in all_thresholds
        assert "API_SLOW_REQUEST_RATE" in all_thresholds
        assert isinstance(all_thresholds["SCRAPER_STALE_HOURS"], Threshold)


class TestErrorHandler:
    """Tests for error handler."""

    def test_error_handler_suppresses_exception(self):
        """Test ErrorHandler suppresses exceptions by default."""
        with ErrorHandler("test_operation"):
            raise ValueError("test error")

        # Should reach here without exception

    def test_error_handler_reraises_when_configured(self):
        """Test ErrorHandler re-raises when reraise=True."""
        with pytest.raises(ValueError):
            with ErrorHandler("test_operation", reraise=True):
                raise ValueError("test error")

    def test_error_handler_no_exception(self):
        """Test ErrorHandler with successful operation."""
        result = None
        with ErrorHandler("test_operation") as handler:
            result = "success"

        assert result == "success"
        assert handler.event_id is None  # No exception = no event

    def test_error_handler_context(self):
        """Test ErrorHandler with context."""
        handler = ErrorHandler(
            "test_operation",
            context={"card_id": 123},
            capture=False,  # Don't actually capture
        )

        assert handler.operation == "test_operation"
        assert handler.context == {"card_id": 123}

    def test_capture_exception_without_sentry(self):
        """Test capture_exception logs when Sentry not initialized."""
        # Should not raise, just log
        event_id = capture_exception(
            ValueError("test"),
            context={"test": True},
        )
        assert event_id is None  # Sentry not initialized

    def test_capture_message_without_sentry(self):
        """Test capture_message logs when Sentry not initialized."""
        event_id = capture_message(
            "test message",
            level="warning",
            context={"test": True},
        )
        assert event_id is None  # Sentry not initialized


class TestRequestContextMiddleware:
    """Tests for request context middleware."""

    @pytest.mark.asyncio
    async def test_middleware_generates_request_id(self):
        """Test middleware generates request ID if not provided."""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from app.middleware.context import RequestContextMiddleware
        from app.core.context import get_request_id

        async def homepage(request):
            return JSONResponse({"request_id": get_request_id()})

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(RequestContextMiddleware)

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert "X-Request-ID" in response.headers
        assert response.headers["X-Request-ID"].startswith("req_")

    @pytest.mark.asyncio
    async def test_middleware_uses_provided_request_id(self):
        """Test middleware uses X-Request-ID header if provided."""
        from starlette.testclient import TestClient
        from starlette.applications import Starlette
        from starlette.responses import JSONResponse
        from starlette.routing import Route
        from app.middleware.context import RequestContextMiddleware
        from app.core.context import get_request_id

        async def homepage(request):
            return JSONResponse({"request_id": get_request_id()})

        app = Starlette(routes=[Route("/", homepage)])
        app.add_middleware(RequestContextMiddleware)

        client = TestClient(app)
        response = client.get("/", headers={"X-Request-ID": "custom_id_123"})

        assert response.status_code == 200
        assert response.headers["X-Request-ID"] == "custom_id_123"
        data = response.json()
        assert data["request_id"] == "custom_id_123"


class TestHealthCheck:
    """Tests for unified health check (requires database)."""

    def test_check_database_health(self):
        """Test database health check."""
        from app.core.health_check import HealthCheck

        health = HealthCheck.check_database_health()

        assert "status" in health
        assert health["status"] in ["ok", "warning", "critical"]
        # Should have connection time if successful
        if health["status"] != "critical":
            assert "connection_time_ms" in health

    def test_check_performance_health(self):
        """Test performance health check."""
        from app.core.health_check import HealthCheck

        health = HealthCheck.check_performance_health()

        assert "status" in health
        assert health["status"] in ["ok", "warning", "critical"]
        assert "total_requests" in health

    def test_check_circuit_health(self):
        """Test circuit breaker health check."""
        from app.core.health_check import HealthCheck

        health = HealthCheck.check_circuit_health()

        assert "status" in health
        assert health["status"] in ["ok", "warning", "critical"]
        assert "total_circuits" in health


@pytest.mark.integration
class TestPersistentMetrics:
    """Integration tests for persistent metrics (requires database)."""

    def test_record_start_and_complete(self, integration_session):
        """Test recording job start and completion."""
        from app.core.metrics_persistent import PersistentMetricsStore

        metrics = PersistentMetricsStore()

        # Record start
        job_log_id = metrics.record_start("test_job", metadata={"test": True})

        # Record completion
        metrics.record_complete(
            "test_job",
            cards_processed=10,
            successful=8,
            failed=2,
            job_log_id=job_log_id,
        )

        # Check in-memory metrics
        last_run = metrics.get_last_run("test_job")
        assert last_run is not None
        assert last_run.successful == 8
        assert last_run.failed == 2

    def test_get_historical_job_runs(self, integration_session):
        """Test getting historical job runs."""
        from app.core.metrics_persistent import PersistentMetricsStore

        metrics = PersistentMetricsStore()

        # Record a few jobs
        for i in range(3):
            job_log_id = metrics.record_start("test_historical")
            metrics.record_complete(
                "test_historical",
                cards_processed=10,
                successful=10 - i,
                failed=i,
                job_log_id=job_log_id,
            )

        # Get historical runs
        history = metrics.get_historical_job_runs("test_historical", limit=10)
        assert len(history) >= 3


@pytest.mark.integration
class TestObservabilityModels:
    """Integration tests for observability database models."""

    def test_scraper_job_log_create(self, integration_session):
        """Test creating a scraper job log entry."""
        from app.models.observability import ScraperJobLog

        log = ScraperJobLog(
            job_name="test_job",
            started_at=datetime.now(timezone.utc),
            status="running",
        )
        integration_session.add(log)
        integration_session.commit()
        integration_session.refresh(log)

        assert log.id is not None
        assert log.job_name == "test_job"
        assert log.status == "running"

    def test_metrics_snapshot_create(self, integration_session):
        """Test creating a metrics snapshot."""
        from app.models.observability import MetricsSnapshot

        snapshot = MetricsSnapshot(
            metric_type="scraper",
            metric_name="ebay_update",
            metric_value={"success_rate": 0.95, "duration": 120},
        )
        integration_session.add(snapshot)
        integration_session.commit()
        integration_session.refresh(snapshot)

        assert snapshot.id is not None
        assert snapshot.metric_value["success_rate"] == 0.95

    def test_request_trace_create(self, integration_session):
        """Test creating a request trace."""
        import uuid
        from app.models.observability import RequestTrace

        # Use unique request_id to avoid conflicts with previous test runs
        unique_request_id = f"req_test_{uuid.uuid4().hex[:12]}"
        trace = RequestTrace(
            request_id=unique_request_id,
            method="GET",
            path="/api/v1/cards",
            status_code=200,
            duration_ms=150.5,
        )
        integration_session.add(trace)
        integration_session.commit()
        integration_session.refresh(trace)

        assert trace.id is not None
        assert trace.request_id == unique_request_id
        assert trace.duration_ms == 150.5
