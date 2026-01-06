"""
Tests for anti-scraping protection system.
"""

from unittest.mock import MagicMock


class TestAntiScrapingMiddleware:
    """Test the anti-scraping middleware detection capabilities."""

    def test_bot_user_agent_detection(self):
        """Test that common bot user agents are detected."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)

        # These should be detected as bots
        bot_agents = [
            "python-requests/2.28.0",
            "curl/7.84.0",
            "wget/1.21",
            "Googlebot/2.1",
            "Baiduspider/2.0",
            "AhrefsBot/7.0",
            "SemrushBot/7",
            "python-urllib/3.9",
            "",  # Empty UA
        ]

        for agent in bot_agents:
            assert middleware._is_bot_user_agent(agent), f"Should detect '{agent}' as bot"

        # These should NOT be detected as bots
        real_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15",
        ]

        for agent in real_agents:
            assert not middleware._is_bot_user_agent(agent), f"Should NOT detect '{agent}' as bot"

    def test_headless_browser_detection(self):
        """Test detection of headless browsers."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)

        # Create mock requests with different characteristics

        # Headless Chrome - should be detected
        headless_request = MagicMock()
        headless_request.headers = {
            "user-agent": "Mozilla/5.0 (X11; Linux x86_64) HeadlessChrome/91.0.4472.124",
            "accept": "text/html",
            "accept-language": "en-US",
            "accept-encoding": "gzip",
        }

        is_headless, reason = middleware._is_headless_browser(headless_request)
        assert is_headless, "Should detect HeadlessChrome"
        assert "headless" in reason.lower()

        # Puppeteer in UA
        puppeteer_request = MagicMock()
        puppeteer_request.headers = {
            "user-agent": "Mozilla/5.0 Puppeteer/13.0.0",
            "accept": "text/html",
            "accept-language": "en",
            "accept-encoding": "gzip",
        }

        is_headless, reason = middleware._is_headless_browser(puppeteer_request)
        assert is_headless, "Should detect Puppeteer"

        # Missing headers - suspicious
        missing_headers_request = MagicMock()
        missing_headers_request.headers = {
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/91.0",
            # Missing accept, accept-language, accept-encoding
        }

        is_headless, reason = middleware._is_headless_browser(missing_headers_request)
        assert is_headless, "Should detect missing browser headers"
        assert "missing_headers" in reason

        # Real browser - should NOT be detected
        real_browser_request = MagicMock()
        real_browser_request.headers = {
            "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "accept-language": "en-US,en;q=0.5",
            "accept-encoding": "gzip, deflate, br",
        }

        is_headless, reason = middleware._is_headless_browser(real_browser_request)
        assert not is_headless, "Should NOT detect real browser as headless"

    def test_rate_limiting(self):
        """Test IP-based rate limiting (per-minute limit)."""
        from app.core.anti_scraping import AntiScrapingMiddleware
        import time

        middleware = AntiScrapingMiddleware(app=None, enabled=True)

        test_ip = "192.168.1.100"

        # Simulate requests spread over time (to avoid burst limit)
        # The burst limit is 10 req/5sec, so we need to space them out
        # For testing, we'll manipulate the timestamps directly

        # Add 60 requests with old timestamps (outside burst window but inside minute window)
        base_time = time.time() - 30  # 30 seconds ago
        for i in range(60):
            middleware._requests[test_ip].append((base_time + i * 0.5, "/api/v1/cards"))

        # Now the 61st request should be rate limited (per-minute limit)
        is_limited, retry_after = middleware._check_rate_limit(test_ip, "/api/v1/cards")
        assert is_limited, "Should be rate limited after 60 requests in a minute"
        assert retry_after > 0, "Should have retry-after value"

    def test_burst_detection(self):
        """Test burst request detection (too many requests too fast)."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)

        test_ip = "10.0.0.50"

        # Simulate 10 rapid requests in under 5 seconds
        for i in range(10):
            is_limited, _ = middleware._check_rate_limit(test_ip, "/api/v1/market")
            if i < 10:
                assert not is_limited, f"Request {i+1} should not be limited yet"
            middleware._record_request(test_ip, "/api/v1/market")

        # 11th request should be blocked by burst limit
        is_limited, retry_after = middleware._check_rate_limit(test_ip, "/api/v1/market")
        assert is_limited, "Burst should trigger rate limit"

    def test_fingerprint_generation(self):
        """Test browser fingerprint generation."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)

        request1 = MagicMock()
        request1.headers = {
            "user-agent": "Mozilla/5.0 Chrome/91",
            "accept-language": "en-US",
            "accept-encoding": "gzip",
            "accept": "text/html",
        }

        request2 = MagicMock()
        request2.headers = {
            "user-agent": "Mozilla/5.0 Firefox/89",
            "accept-language": "de-DE",
            "accept-encoding": "gzip",
            "accept": "text/html",
        }

        fp1 = middleware._get_fingerprint(request1)
        fp2 = middleware._get_fingerprint(request2)

        # Different browsers should have different fingerprints
        assert fp1 != fp2, "Different browsers should have different fingerprints"

        # Same browser should have same fingerprint
        fp1_again = middleware._get_fingerprint(request1)
        assert fp1 == fp1_again, "Same browser should have same fingerprint"

    def test_path_protection(self):
        """Test that correct paths are protected."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)

        # Protected paths - note: exact match /api/v1/cards is allowed (root),
        # but subpaths like /api/v1/cards/123 are protected
        protected = [
            "/api/v1/cards/123",
            "/api/v1/cards/dragon-fire/history",
            "/api/v1/market/overview",
            "/api/v1/market/treatments",
            "/api/v1/blokpax/sales",
            "/api/v1/blokpax/storefronts",
        ]

        for path in protected:
            assert middleware._is_protected_path(path), f"'{path}' should be protected"

        # NOT protected paths (allowed list or outside protected prefixes)
        allowed = [
            "/",
            "/api/v1/auth/login",
            "/api/v1/auth/register",
            "/api/v1/portfolio/me",
            "/api/v1/admin/users",
            "/docs",
        ]

        for path in allowed:
            assert not middleware._is_protected_path(path), f"'{path}' should NOT be protected"


class TestAPIKeyRateLimiter:
    """Test the API key rate limiter."""

    def test_per_minute_limit(self):
        """Test per-minute rate limiting for API keys."""
        from app.core.anti_scraping import APIKeyRateLimiter

        limiter = APIKeyRateLimiter()
        test_key = "test_key_hash_123"

        # First 60 requests should pass
        for i in range(60):
            allowed, reason = limiter.check_limit(test_key, per_minute=60, per_day=10000)
            assert allowed, f"Request {i+1} should be allowed"
            limiter.record_request(test_key)

        # 61st should fail
        allowed, reason = limiter.check_limit(test_key, per_minute=60, per_day=10000)
        assert not allowed, "61st request should be denied"
        assert reason == "minute_limit"

    def test_per_day_limit(self):
        """Test per-day rate limiting for API keys."""
        from app.core.anti_scraping import APIKeyRateLimiter

        limiter = APIKeyRateLimiter()
        test_key = "test_key_hash_456"

        # Set up 100 requests already made today
        limiter._day_requests[test_key] = 99
        limiter._day_start[test_key] = 99999999999  # Far future

        # Next request should pass (at 99)
        allowed, _ = limiter.check_limit(test_key, per_minute=1000, per_day=100)
        assert allowed

        limiter.record_request(test_key)

        # Now at 100 - should be denied
        allowed, reason = limiter.check_limit(test_key, per_minute=1000, per_day=100)
        assert not allowed
        assert reason == "daily_limit"


class TestAPIKeyModel:
    """Test the API key model."""

    def test_key_generation(self):
        """Test API key generation format."""
        from app.models.api_key import APIKey

        key = APIKey.generate_key()

        assert key.startswith("wt_"), "Key should start with 'wt_' prefix"
        assert len(key) > 30, "Key should be long enough for security"

    def test_key_hashing(self):
        """Test API key hashing."""
        from app.models.api_key import APIKey

        key = "wt_test_key_12345"
        hash1 = APIKey.hash_key(key)
        hash2 = APIKey.hash_key(key)

        assert hash1 == hash2, "Same key should produce same hash"
        assert len(hash1) == 64, "SHA256 hash should be 64 characters"
        assert key not in hash1, "Hash should not contain original key"

    def test_key_prefix_extraction(self):
        """Test key prefix extraction."""
        from app.models.api_key import APIKey

        key = "wt_abc123xyz"
        prefix = APIKey.get_prefix(key)

        # Prefix is first 11 chars for wt_ keys
        assert len(prefix) == 11, "Prefix should be 11 chars for wt_ keys"
        assert prefix == "wt_abc123xy", "Prefix should be first 11 chars"
        assert key.startswith(prefix), "Key should start with prefix"
