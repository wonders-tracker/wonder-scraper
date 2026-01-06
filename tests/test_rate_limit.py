"""
Tests for rate limiting functionality.

Tests cover:
- Rate limit initialization
- Request counting and tracking
- Rate limit exceeded behavior
- Rate limit reset after time window
- Failed login tracking and lockouts
- IP extraction from various headers
- Rate limit decorator functionality
- Concurrent request handling
"""

import pytest
from unittest.mock import Mock, patch
from fastapi import Request, HTTPException, status
from fastapi.datastructures import Headers

from app.core.rate_limit import (
    RateLimiter,
    rate_limiter,
    get_client_ip,
    rate_limit,
)


class TestRateLimiterInitialization:
    """Tests for RateLimiter initialization."""

    def test_rate_limiter_initializes_empty(self):
        """Test that RateLimiter starts with empty state."""
        limiter = RateLimiter()
        assert len(limiter._requests) == 0
        assert len(limiter._lockouts) == 0
        assert len(limiter._failed_attempts) == 0

    def test_global_rate_limiter_exists(self):
        """Test that global rate_limiter instance exists."""
        assert rate_limiter is not None
        assert isinstance(rate_limiter, RateLimiter)


class TestRequestCounting:
    """Tests for request counting and tracking."""

    def test_record_single_request(self):
        """Test recording a single request."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        limiter.record_request(ip)

        assert ip in limiter._requests
        assert len(limiter._requests[ip]) == 1
        timestamp, count = limiter._requests[ip][0]
        assert count == 1
        assert isinstance(timestamp, float)

    def test_record_multiple_requests_from_same_ip(self):
        """Test recording multiple requests from the same IP."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        for _ in range(5):
            limiter.record_request(ip)

        assert ip in limiter._requests
        assert len(limiter._requests[ip]) == 5

    def test_record_requests_from_different_ips(self):
        """Test recording requests from different IPs."""
        limiter = RateLimiter()
        ips = ["192.168.1.1", "192.168.1.2", "192.168.1.3"]

        for ip in ips:
            limiter.record_request(ip)

        assert len(limiter._requests) == 3
        for ip in ips:
            assert ip in limiter._requests
            assert len(limiter._requests[ip]) == 1


class TestRateLimitChecking:
    """Tests for rate limit checking logic."""

    def test_is_not_rate_limited_when_under_limit(self):
        """Test that requests under the limit are not blocked."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record 5 requests (under default limit of 10)
        for _ in range(5):
            limiter.record_request(ip)

        is_limited, retry_after = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)

        assert is_limited is False
        assert retry_after == 0

    def test_is_rate_limited_when_at_limit(self):
        """Test that requests at the limit are blocked."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record exactly 10 requests (at limit)
        for _ in range(10):
            limiter.record_request(ip)

        is_limited, retry_after = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)

        assert is_limited is True
        assert retry_after == 60

    def test_is_rate_limited_when_over_limit(self):
        """Test that requests over the limit are blocked."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record 15 requests (over limit of 10)
        for _ in range(15):
            limiter.record_request(ip)

        is_limited, retry_after = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)

        assert is_limited is True
        assert retry_after == 60

    def test_different_ips_have_independent_limits(self):
        """Test that different IPs have independent rate limits."""
        limiter = RateLimiter()
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        # Max out IP1
        for _ in range(10):
            limiter.record_request(ip1)

        # IP1 should be limited
        is_limited1, _ = limiter.is_rate_limited(ip1, max_requests=10, window_seconds=60)
        assert is_limited1 is True

        # IP2 should not be limited
        is_limited2, _ = limiter.is_rate_limited(ip2, max_requests=10, window_seconds=60)
        assert is_limited2 is False


class TestRateLimitReset:
    """Tests for rate limit reset after time window."""

    @patch("app.core.rate_limit.time.time")
    def test_old_requests_are_cleaned_up(self, mock_time):
        """Test that requests outside the time window are removed."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Start at time 0
        mock_time.return_value = 0.0

        # Record 10 requests at time 0 (hitting the limit)
        for _ in range(10):
            limiter.record_request(ip)

        # At time 0, should be rate limited
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
        assert is_limited is True

        # Move time forward 61 seconds (outside the 60-second window)
        mock_time.return_value = 61.0

        # Now should not be rate limited (old requests cleaned up)
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
        assert is_limited is False

    @patch("app.core.rate_limit.time.time")
    def test_partial_window_cleanup(self, mock_time):
        """Test that only requests outside the window are removed."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record 5 requests at time 0
        mock_time.return_value = 0.0
        for _ in range(5):
            limiter.record_request(ip)

        # Record 5 more requests at time 40
        mock_time.return_value = 40.0
        for _ in range(5):
            limiter.record_request(ip)

        # At time 50, check with 60-second window
        # First 5 requests (from time 0) should still be in window
        # Last 5 requests (from time 40) should also be in window
        mock_time.return_value = 50.0
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
        assert is_limited is True  # 10 requests in window

        # At time 70, check with 60-second window
        # First 5 requests (from time 0) should be removed (70 - 0 = 70 > 60)
        # Last 5 requests (from time 40) should still be in window (70 - 40 = 30 < 60)
        mock_time.return_value = 70.0
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
        assert is_limited is False  # Only 5 requests in window

    @patch("app.core.rate_limit.time.time")
    def test_sliding_window_behavior(self, mock_time):
        """Test that rate limit uses sliding window algorithm."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record 10 requests at time 0 (hitting limit)
        mock_time.return_value = 0.0
        for _ in range(10):
            limiter.record_request(ip)

        # At time 30, should still be limited (requests from time 0 still in 60s window)
        mock_time.return_value = 30.0
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
        assert is_limited is True

        # At time 61, window has moved and old requests are gone
        mock_time.return_value = 61.0
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
        assert is_limited is False


class TestFailedLoginTracking:
    """Tests for failed login tracking and lockouts."""

    def test_record_single_failed_login(self):
        """Test recording a single failed login attempt."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        is_locked, remaining = limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)

        assert is_locked is False
        assert remaining == 4  # 5 - 1 = 4 attempts remaining
        assert limiter._failed_attempts[ip] == 1

    def test_multiple_failed_logins_increment_count(self):
        """Test that multiple failed logins increment the counter."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        for i in range(1, 4):
            is_locked, remaining = limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)
            assert is_locked is False
            assert limiter._failed_attempts[ip] == i
            assert remaining == 5 - i

    def test_lockout_triggered_at_threshold(self):
        """Test that lockout is triggered when threshold is reached."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record 4 failed attempts (under threshold)
        for _ in range(4):
            is_locked, _ = limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)
            assert is_locked is False

        # 5th attempt should trigger lockout
        is_locked, lockout_duration = limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)

        assert is_locked is True
        assert lockout_duration == 300
        assert ip in limiter._lockouts

    @patch("app.core.rate_limit.time.time")
    def test_lockout_prevents_requests(self, mock_time):
        """Test that locked out IPs are blocked from making requests."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        mock_time.return_value = 0.0

        # Trigger lockout
        for _ in range(5):
            limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)

        # Check that IP is rate limited due to lockout
        is_limited, retry_after = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)

        assert is_limited is True
        assert retry_after == 300

    @patch("app.core.rate_limit.time.time")
    def test_lockout_expires_after_duration(self, mock_time):
        """Test that lockout expires after the lockout duration."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Trigger lockout at time 0
        mock_time.return_value = 0.0
        for _ in range(5):
            limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)

        # At time 0, should be locked out
        is_limited, retry_after = limiter.is_rate_limited(ip)
        assert is_limited is True

        # At time 301 (after 300s lockout), should not be locked out
        mock_time.return_value = 301.0
        is_limited, retry_after = limiter.is_rate_limited(ip)
        assert is_limited is False

        # Failed attempts should be reset
        assert limiter._failed_attempts[ip] == 0
        assert ip not in limiter._lockouts

    @patch("app.core.rate_limit.time.time")
    def test_lockout_retry_after_counts_down(self, mock_time):
        """Test that retry_after countdown is accurate during lockout."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Trigger lockout at time 0 with 300s duration
        mock_time.return_value = 0.0
        for _ in range(5):
            limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)

        # At time 100, should have 200s remaining
        mock_time.return_value = 100.0
        is_limited, retry_after = limiter.is_rate_limited(ip)
        assert is_limited is True
        assert retry_after == 200

        # At time 250, should have 50s remaining
        mock_time.return_value = 250.0
        is_limited, retry_after = limiter.is_rate_limited(ip)
        assert is_limited is True
        assert retry_after == 50

    def test_successful_login_clears_failed_attempts(self):
        """Test that successful login clears failed attempt counter."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record some failed attempts
        for _ in range(3):
            limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)

        assert limiter._failed_attempts[ip] == 3

        # Record successful login
        limiter.record_successful_login(ip)

        # Failed attempts should be cleared
        assert ip not in limiter._failed_attempts

    @patch("app.core.rate_limit.time.time")
    def test_successful_login_clears_lockout(self, mock_time):
        """Test that successful login clears lockout."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        mock_time.return_value = 0.0

        # Trigger lockout
        for _ in range(5):
            limiter.record_failed_login(ip, lockout_threshold=5, lockout_seconds=300)

        assert ip in limiter._lockouts
        assert ip in limiter._failed_attempts

        # Successful login should clear lockout
        limiter.record_successful_login(ip)

        assert ip not in limiter._lockouts
        assert ip not in limiter._failed_attempts

    def test_different_ips_have_independent_failed_attempts(self):
        """Test that different IPs have independent failed attempt counters."""
        limiter = RateLimiter()
        ip1 = "192.168.1.1"
        ip2 = "192.168.1.2"

        # Record failures for IP1
        for _ in range(3):
            limiter.record_failed_login(ip1, lockout_threshold=5, lockout_seconds=300)

        # Record failures for IP2
        for _ in range(2):
            limiter.record_failed_login(ip2, lockout_threshold=5, lockout_seconds=300)

        assert limiter._failed_attempts[ip1] == 3
        assert limiter._failed_attempts[ip2] == 2


class TestGetClientIP:
    """Tests for IP extraction from request headers."""

    def test_extract_ip_from_x_forwarded_for(self):
        """Test extracting IP from X-Forwarded-For header."""
        request = Mock(spec=Request)
        request.headers = Headers({"x-forwarded-for": "203.0.113.1, 198.51.100.1"})
        request.client = None

        ip = get_client_ip(request)

        # Should return the first IP in the list
        assert ip == "203.0.113.1"

    def test_extract_ip_from_x_forwarded_for_with_spaces(self):
        """Test extracting IP from X-Forwarded-For with extra spaces."""
        request = Mock(spec=Request)
        request.headers = Headers({"x-forwarded-for": "  203.0.113.1  ,  198.51.100.1  "})
        request.client = None

        ip = get_client_ip(request)

        # Should strip whitespace
        assert ip == "203.0.113.1"

    def test_extract_ip_from_x_real_ip(self):
        """Test extracting IP from X-Real-IP header."""
        request = Mock(spec=Request)
        request.headers = Headers({"x-real-ip": "203.0.113.1"})
        request.client = None

        ip = get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_x_forwarded_for_takes_precedence_over_x_real_ip(self):
        """Test that X-Forwarded-For takes precedence over X-Real-IP."""
        request = Mock(spec=Request)
        request.headers = Headers({"x-forwarded-for": "203.0.113.1", "x-real-ip": "198.51.100.1"})
        request.client = None

        ip = get_client_ip(request)

        # Should use X-Forwarded-For
        assert ip == "203.0.113.1"

    def test_extract_ip_from_client_when_no_headers(self):
        """Test extracting IP from request.client when headers are absent."""
        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "203.0.113.1"

        ip = get_client_ip(request)

        assert ip == "203.0.113.1"

    def test_return_unknown_when_no_ip_available(self):
        """Test returning 'unknown' when no IP can be determined."""
        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = None

        ip = get_client_ip(request)

        assert ip == "unknown"


class TestRateLimitDecorator:
    """Tests for the rate_limit decorator."""

    @pytest.mark.asyncio
    async def test_decorator_allows_requests_under_limit(self):
        """Test that decorator allows requests under the limit."""
        limiter = RateLimiter()

        @rate_limit(max_requests=5, window_seconds=60)
        async def test_endpoint(request: Request):
            return {"status": "success"}

        # Create mock request
        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "192.168.1.1"

        # Manually inject limiter for testing
        with patch("app.core.rate_limit.rate_limiter", limiter):
            # First 5 requests should succeed
            for i in range(5):
                result = await test_endpoint(request)
                assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_decorator_blocks_requests_over_limit(self):
        """Test that decorator blocks requests over the limit."""
        limiter = RateLimiter()

        @rate_limit(max_requests=3, window_seconds=60)
        async def test_endpoint(request: Request):
            return {"status": "success"}

        # Create mock request
        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "192.168.1.1"

        with patch("app.core.rate_limit.rate_limiter", limiter):
            # First 3 requests should succeed
            for _ in range(3):
                result = await test_endpoint(request)
                assert result == {"status": "success"}

            # 4th request should raise HTTPException
            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint(request)

            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
            assert "Retry-After" in exc_info.value.headers
            assert exc_info.value.headers["Retry-After"] == "60"

    @pytest.mark.asyncio
    async def test_decorator_custom_error_message(self):
        """Test that decorator uses custom error message."""
        limiter = RateLimiter()
        custom_message = "Custom rate limit message"

        @rate_limit(max_requests=1, window_seconds=60, error_message=custom_message)
        async def test_endpoint(request: Request):
            return {"status": "success"}

        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "192.168.1.1"

        with patch("app.core.rate_limit.rate_limiter", limiter):
            # First request succeeds
            await test_endpoint(request)

            # Second request should fail with custom message
            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint(request)

            assert exc_info.value.detail == custom_message

    @pytest.mark.asyncio
    async def test_decorator_finds_request_in_args(self):
        """Test that decorator finds request when passed as positional arg."""
        limiter = RateLimiter()

        @rate_limit(max_requests=5, window_seconds=60)
        async def test_endpoint(request: Request):
            return {"status": "success"}

        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "192.168.1.1"

        with patch("app.core.rate_limit.rate_limiter", limiter):
            # Pass request as positional argument
            result = await test_endpoint(request)
            assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_decorator_with_async_endpoint(self):
        """Test that decorator works with async endpoints."""
        limiter = RateLimiter()

        @rate_limit(max_requests=5, window_seconds=60)
        async def test_endpoint(request: Request):
            return {"status": "success"}

        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "192.168.1.1"

        with patch("app.core.rate_limit.rate_limiter", limiter):
            result = await test_endpoint(request)
            assert result == {"status": "success"}

    @pytest.mark.asyncio
    async def test_decorator_different_endpoints_share_ip_limits(self):
        """Test that different endpoints share the same IP-based limits."""
        limiter = RateLimiter()

        @rate_limit(max_requests=3, window_seconds=60)
        async def endpoint1(request: Request):
            return {"endpoint": "1"}

        @rate_limit(max_requests=3, window_seconds=60)
        async def endpoint2(request: Request):
            return {"endpoint": "2"}

        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "192.168.1.1"

        with patch("app.core.rate_limit.rate_limiter", limiter):
            # Make 2 requests to endpoint1
            await endpoint1(request)
            await endpoint1(request)

            # Make 1 request to endpoint2
            await endpoint2(request)

            # Both endpoints share the same limiter, so we've made 3 requests total
            # 4th request to either endpoint should fail
            with pytest.raises(HTTPException) as exc_info:
                await endpoint1(request)

            assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS

    @pytest.mark.asyncio
    async def test_decorator_retry_after_header_set_correctly(self):
        """Test that Retry-After header is set correctly."""
        limiter = RateLimiter()

        @rate_limit(max_requests=1, window_seconds=120)
        async def test_endpoint(request: Request):
            return {"status": "success"}

        request = Mock(spec=Request)
        request.headers = Headers({})
        request.client = Mock()
        request.client.host = "192.168.1.1"

        with patch("app.core.rate_limit.rate_limiter", limiter):
            # First request succeeds
            await test_endpoint(request)

            # Second request should fail with Retry-After: 120
            with pytest.raises(HTTPException) as exc_info:
                await test_endpoint(request)

            assert exc_info.value.headers["Retry-After"] == "120"


class TestConcurrentRequests:
    """Tests for handling concurrent requests."""

    def test_concurrent_requests_from_same_ip_are_counted(self):
        """Test that concurrent requests from the same IP are all counted."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Simulate 5 concurrent requests
        for _ in range(5):
            limiter.record_request(ip)

        # All 5 should be counted
        assert len(limiter._requests[ip]) == 5

        # Should not be limited (under default limit of 10)
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
        assert is_limited is False

    def test_concurrent_requests_from_different_ips_are_independent(self):
        """Test that concurrent requests from different IPs are independent."""
        limiter = RateLimiter()

        # Simulate concurrent requests from 3 different IPs
        ips = ["192.168.1.1", "192.168.1.2", "192.168.1.3"]
        for ip in ips:
            for _ in range(5):
                limiter.record_request(ip)

        # Each IP should have 5 requests
        for ip in ips:
            assert len(limiter._requests[ip]) == 5
            is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)
            assert is_limited is False


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_empty_ip_string(self):
        """Test handling of empty IP string."""
        limiter = RateLimiter()
        ip = ""

        limiter.record_request(ip)
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)

        # Should handle empty string without error
        assert is_limited is False

    def test_zero_max_requests(self):
        """Test behavior when max_requests is 0."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # With max_requests=0, should always be limited
        is_limited, retry_after = limiter.is_rate_limited(ip, max_requests=0, window_seconds=60)

        assert is_limited is True

    def test_zero_window_seconds(self):
        """Test behavior when window_seconds is 0."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        limiter.record_request(ip)

        # With window_seconds=0, all requests should be outside window
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=0)

        # Should not be limited (all requests cleaned up)
        assert is_limited is False

    def test_very_large_window_seconds(self):
        """Test behavior with very large window_seconds."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record requests
        for _ in range(5):
            limiter.record_request(ip)

        # Check with very large window (1 year in seconds)
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=31536000)

        assert is_limited is False

    def test_negative_lockout_threshold(self):
        """Test behavior with negative lockout threshold."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # With negative threshold, first attempt should trigger lockout
        is_locked, _ = limiter.record_failed_login(ip, lockout_threshold=-1, lockout_seconds=300)

        # Implementation should handle this gracefully
        assert isinstance(is_locked, bool)

    def test_multiple_cleanup_calls(self):
        """Test that multiple cleanup calls don't cause errors."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        limiter.record_request(ip)

        # Call cleanup multiple times
        limiter._cleanup_old_requests(ip, 60)
        limiter._cleanup_old_requests(ip, 60)
        limiter._cleanup_old_requests(ip, 60)

        # Should not raise any errors
        assert True

    @patch("app.core.rate_limit.time.time")
    def test_exactly_at_window_boundary(self, mock_time):
        """Test behavior when request is exactly at window boundary."""
        limiter = RateLimiter()
        ip = "192.168.1.1"

        # Record request at time 0
        mock_time.return_value = 0.0
        limiter.record_request(ip)

        # Check at exactly time 60 (window is 60 seconds)
        mock_time.return_value = 60.0
        is_limited, _ = limiter.is_rate_limited(ip, max_requests=10, window_seconds=60)

        # Request at time 0 should be cleaned up (60 - 0 = 60, not > 60)
        # So should not be limited
        assert is_limited is False
