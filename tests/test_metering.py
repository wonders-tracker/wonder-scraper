"""
Tests for API usage metering middleware.

Tests cover:
- Path matching for metered endpoints
- Exclusion logic
- User detection and customer ID handling
- Async usage event sending
- Error handling
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from starlette.testclient import TestClient
from starlette.requests import Request
from starlette.responses import Response

from app.middleware.metering import APIMeteringMiddleware, METERED_PREFIXES, EXCLUDED_PATHS


class TestPathMatching:
    """Tests for path matching logic."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance for testing."""
        return APIMeteringMiddleware(app=MagicMock())

    def test_should_meter_cards_endpoint(self, middleware):
        """Test cards endpoints are metered."""
        assert middleware._should_meter("/api/v1/cards/123") is True
        assert middleware._should_meter("/api/v1/cards") is True
        assert middleware._should_meter("/api/v1/cards/123/prices") is True

    def test_should_meter_market_endpoint(self, middleware):
        """Test market endpoints are metered."""
        assert middleware._should_meter("/api/v1/market") is True
        assert middleware._should_meter("/api/v1/market/snapshot") is True

    def test_should_meter_blokpax_endpoint(self, middleware):
        """Test blokpax endpoints are metered."""
        assert middleware._should_meter("/api/v1/blokpax/listings") is True

    def test_excludes_cards_search(self, middleware):
        """Test cards search is excluded from metering."""
        assert middleware._should_meter("/api/v1/cards/search") is False
        assert middleware._should_meter("/api/v1/cards/search?q=test") is False

    def test_excludes_billing_endpoints(self, middleware):
        """Test billing endpoints are excluded."""
        assert middleware._should_meter("/api/v1/billing") is False
        assert middleware._should_meter("/api/v1/billing/checkout") is False
        assert middleware._should_meter("/api/v1/billing/portal") is False

    def test_excludes_webhooks(self, middleware):
        """Test webhook endpoints are excluded."""
        assert middleware._should_meter("/api/v1/webhooks") is False
        assert middleware._should_meter("/api/v1/webhooks/polar") is False

    def test_excludes_auth_endpoints(self, middleware):
        """Test auth endpoints are excluded."""
        assert middleware._should_meter("/api/v1/auth") is False
        assert middleware._should_meter("/api/v1/auth/login") is False

    def test_excludes_users_endpoints(self, middleware):
        """Test users endpoints are excluded."""
        assert middleware._should_meter("/api/v1/users") is False
        assert middleware._should_meter("/api/v1/users/me") is False

    def test_excludes_analytics_endpoints(self, middleware):
        """Test analytics endpoints are excluded."""
        assert middleware._should_meter("/api/v1/analytics") is False

    def test_non_metered_paths(self, middleware):
        """Test paths that shouldn't be metered."""
        assert middleware._should_meter("/api/v1/unknown") is False
        assert middleware._should_meter("/") is False
        assert middleware._should_meter("/health") is False
        assert middleware._should_meter("/docs") is False

    def test_exclusion_takes_priority(self, middleware):
        """Test exclusions are checked before metered prefixes."""
        # cards/search starts with /api/v1/cards (metered) but should be excluded
        assert middleware._should_meter("/api/v1/cards/search") is False


class TestMiddlewareDispatch:
    """Tests for middleware dispatch behavior."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        async def mock_app(scope, receive, send):
            pass
        return APIMeteringMiddleware(app=mock_app)

    @pytest.mark.asyncio
    async def test_dispatch_successful_request_meters(self, middleware):
        """Test successful requests to metered endpoints trigger metering."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/cards/123"
        mock_request.method = "GET"

        mock_user = MagicMock()
        mock_user.polar_customer_id = "cust_abc123"
        mock_request.state = MagicMock()
        mock_request.state.user = mock_user

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        with patch.object(middleware, '_send_usage_event', new_callable=AsyncMock) as mock_send:
            with patch('asyncio.create_task') as mock_create_task:
                result = await middleware.dispatch(mock_request, mock_call_next)

                # Verify task was created for sending usage event
                mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_dispatch_error_response_skips_metering(self, middleware):
        """Test error responses don't trigger metering."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/cards/123"
        mock_request.method = "GET"
        mock_request.state = MagicMock()

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 404

        async def mock_call_next(request):
            return mock_response

        with patch('asyncio.create_task') as mock_create_task:
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Should not create task for error responses
            mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_no_user_skips_metering(self, middleware):
        """Test requests without user don't trigger metering."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/cards/123"
        mock_request.method = "GET"
        mock_request.state = MagicMock()
        mock_request.state.user = None

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        with patch('asyncio.create_task') as mock_create_task:
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Should not create task when no user
            mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_user_no_customer_id_skips_metering(self, middleware):
        """Test requests from users without customer ID don't trigger metering."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/cards/123"
        mock_request.method = "GET"

        mock_user = MagicMock()
        mock_user.polar_customer_id = None  # No customer ID
        mock_request.state = MagicMock()
        mock_request.state.user = mock_user

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        with patch('asyncio.create_task') as mock_create_task:
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Should not create task when no customer ID
            mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_dispatch_excluded_path_skips_metering(self, middleware):
        """Test excluded paths don't trigger metering."""
        mock_request = MagicMock(spec=Request)
        mock_request.url.path = "/api/v1/cards/search"
        mock_request.method = "GET"
        mock_request.state = MagicMock()

        mock_response = MagicMock(spec=Response)
        mock_response.status_code = 200

        async def mock_call_next(request):
            return mock_response

        with patch('asyncio.create_task') as mock_create_task:
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Should not create task for excluded paths
            mock_create_task.assert_not_called()


class TestUsageEventSending:
    """Tests for usage event sending."""

    @pytest.fixture
    def middleware(self):
        """Create middleware instance."""
        return APIMeteringMiddleware(app=MagicMock())

    @pytest.mark.asyncio
    async def test_send_usage_event_success(self, middleware):
        """Test successful usage event sending."""
        with patch('app.services.polar.ingest_usage_event', new_callable=AsyncMock) as mock_ingest:
            await middleware._send_usage_event(
                customer_id="cust_123",
                endpoint="/api/v1/cards/456",
                method="GET"
            )

            mock_ingest.assert_called_once_with(
                customer_id="cust_123",
                event_name="api_request",
                metadata={
                    "endpoint": "/api/v1/cards/456",
                    "method": "GET",
                    "requests": 1
                }
            )

    @pytest.mark.asyncio
    async def test_send_usage_event_handles_exception(self, middleware):
        """Test usage event sending handles exceptions gracefully."""
        with patch('app.services.polar.ingest_usage_event', new_callable=AsyncMock) as mock_ingest:
            mock_ingest.side_effect = Exception("Network error")

            # Should not raise exception
            await middleware._send_usage_event(
                customer_id="cust_123",
                endpoint="/api/v1/cards/456",
                method="GET"
            )


class TestMeteredPrefixesConfig:
    """Tests for metered prefixes configuration."""

    def test_metered_prefixes_includes_cards(self):
        """Test cards prefix is in metered prefixes."""
        assert "/api/v1/cards" in METERED_PREFIXES

    def test_metered_prefixes_includes_market(self):
        """Test market prefix is in metered prefixes."""
        assert "/api/v1/market" in METERED_PREFIXES

    def test_metered_prefixes_includes_blokpax(self):
        """Test blokpax prefix is in metered prefixes."""
        assert "/api/v1/blokpax" in METERED_PREFIXES


class TestExcludedPathsConfig:
    """Tests for excluded paths configuration."""

    def test_excluded_paths_includes_search(self):
        """Test search is excluded."""
        assert "/api/v1/cards/search" in EXCLUDED_PATHS

    def test_excluded_paths_includes_billing(self):
        """Test billing is excluded."""
        assert "/api/v1/billing" in EXCLUDED_PATHS

    def test_excluded_paths_includes_webhooks(self):
        """Test webhooks is excluded."""
        assert "/api/v1/webhooks" in EXCLUDED_PATHS

    def test_excluded_paths_includes_auth(self):
        """Test auth is excluded."""
        assert "/api/v1/auth" in EXCLUDED_PATHS

    def test_excluded_paths_includes_users(self):
        """Test users is excluded."""
        assert "/api/v1/users" in EXCLUDED_PATHS

    def test_excluded_paths_includes_analytics(self):
        """Test analytics is excluded."""
        assert "/api/v1/analytics" in EXCLUDED_PATHS
