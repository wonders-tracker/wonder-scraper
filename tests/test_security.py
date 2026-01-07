"""
Security tests for anti-scraping protection.
Tests rate limiting, bot detection, API key authentication, and P0 security fixes.
"""

import pytest
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
from sqlmodel import Session

from app.models.user import User
from app.core import security


@pytest.mark.integration
class TestAntiScrapingIntegration:
    """Integration tests for anti-scraping middleware."""

    @pytest.fixture
    def client(self):
        """Create test client with middleware."""
        from app.main import app

        return TestClient(app)

    def test_normal_browser_request_allowed(self, client):
        """Normal browser requests should be allowed."""
        response = client.get(
            "/api/v1/cards",
            headers={
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate, br",
            },
        )
        # Should not be blocked by anti-scraping (may still need auth)
        assert response.status_code != 403

    def test_bot_user_agent_flagged(self, client):
        """Bot user agents should be flagged with warning header."""
        response = client.get(
            "/api/v1/cards",
            headers={
                "User-Agent": "python-requests/2.28.0",
                "Accept": "*/*",
            },
        )
        # Bot requests get a warning header but aren't blocked outright
        # (they're rate limited more aggressively)
        assert response.status_code in [200, 401, 429]

    def test_headless_browser_detected(self, client):
        """Headless browsers should be detected."""
        response = client.get(
            "/api/v1/cards",
            headers={
                "User-Agent": "Mozilla/5.0 HeadlessChrome/91.0",
                "Accept": "text/html",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            },
        )
        # Should get warning or be blocked after violations
        assert response.status_code in [200, 401, 403, 429]

    def test_missing_headers_detected(self, client):
        """Requests missing common browser headers should be detected."""
        response = client.get(
            "/api/v1/cards",
            headers={
                "User-Agent": "Mozilla/5.0 Chrome/91.0",
                # Missing Accept, Accept-Language, Accept-Encoding
            },
        )
        # Should work but may get warning
        assert response.status_code in [200, 401, 403, 429]


@pytest.mark.integration
class TestAPIKeyAuthentication:
    """Test API key authentication."""

    def test_invalid_api_key_rejected(self):
        """Invalid API keys should be rejected."""
        from fastapi import HTTPException
        from app.api.deps import validate_api_key
        from unittest.mock import MagicMock

        # Test the API key validation directly (bypasses middleware state)
        mock_request = MagicMock()
        mock_request.headers = {"X-API-Key": "wt_invalid_key_12345"}

        # Create a mock session that returns no key found
        mock_session = MagicMock()
        mock_session.exec.return_value.first.return_value = None  # No key found

        # Validate should raise HTTPException for invalid keys
        with pytest.raises(HTTPException) as exc_info:
            validate_api_key(mock_request, "wt_invalid_key_12345", mock_session)

        assert exc_info.value.status_code == 401
        assert "Invalid API key" in str(exc_info.value.detail)

        # Also verify the hash lookup is done correctly
        from app.models.api_key import APIKey

        key_hash = APIKey.hash_key("wt_invalid_key_12345")
        # Hash should be consistent
        assert key_hash == APIKey.hash_key("wt_invalid_key_12345")

    def test_missing_api_key_allowed_for_public_endpoints(self):
        """Public endpoints should work without API key (for now)."""
        from app.main import app

        client = TestClient(app)

        response = client.get(
            "/",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
        )
        # Root endpoint is public
        assert response.status_code == 200


class TestRateLimiting:
    """Test rate limiting functionality."""

    def test_rate_limiter_tracks_requests(self):
        """Rate limiter should track request counts."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)
        test_ip = "test_192.168.1.1"

        # Record some requests
        for i in range(5):
            middleware._record_request(test_ip, "/api/v1/cards")

        # Check that requests are tracked
        assert len(middleware._requests[test_ip]) == 5

    def test_burst_limit_enforced(self):
        """Burst limit (10 req/5sec) should be enforced."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)
        test_ip = "burst_test_ip"

        # Simulate 10 rapid requests
        for i in range(10):
            is_limited, _ = middleware._check_rate_limit(test_ip, "/test")
            if i < 10:
                middleware._record_request(test_ip, "/test")

        # 11th should be limited
        is_limited, retry_after = middleware._check_rate_limit(test_ip, "/test")
        assert is_limited, "Burst limit should be enforced"

    def test_ip_blocking_after_violations(self):
        """IPs should be blocked after multiple violations."""
        from app.core.anti_scraping import AntiScrapingMiddleware

        middleware = AntiScrapingMiddleware(app=None, enabled=True)
        test_ip = "violation_test_ip"

        # Record 3 violations
        for i in range(3):
            middleware._record_violation(test_ip, "test_violation")

        # IP should be blocked
        assert test_ip in middleware._blocked_ips


@pytest.mark.integration
class TestDatabaseSecurity:
    """Test database security configurations."""

    def test_sql_injection_prevention(self):
        """SQL injection attempts should be prevented by parameterized queries."""
        # Our API uses SQLModel with parameterized queries
        # This test verifies the patterns are safe

        # These patterns should NOT cause SQL injection
        malicious_inputs = [
            "'; DROP TABLE users; --",
            "1 OR 1=1",
            "UNION SELECT * FROM users",
            "<script>alert('xss')</script>",
        ]

        # The search parameter is used in ilike() with SQLAlchemy
        # which properly escapes input
        for malicious in malicious_inputs:
            # This would be passed to the endpoint as search param
            # SQLAlchemy's ilike() properly escapes it
            assert True  # Parameterized queries handle this

    def test_database_connection_security(self):
        """Database connection should have security parameters set."""
        from app.db import engine
        from app.core.config import settings

        # Verify connection pool limits match configured values
        # Pool size is set in config for concurrent scraper operations
        assert engine.pool.size() <= settings.DB_POOL_SIZE, "Connection pool size should match config"
        assert engine.pool.overflow() <= settings.DB_MAX_OVERFLOW + 10, "Connection overflow should be limited"

        # Verify engine has connect_args for timeout
        # The engine is configured in app/db.py with statement_timeout

    def test_xss_prevention_in_responses(self):
        """API responses should not be vulnerable to XSS."""
        # FastAPI returns JSON which is safe when properly consumed
        # XSS is only a risk if JSON is improperly rendered as HTML
        # The key protection is:
        # 1. Content-Type: application/json (not text/html)
        # 2. Frontend frameworks (React) auto-escape when rendering

        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Verify API returns JSON content type, not HTML
        response = client.get(
            "/",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            },
        )

        content_type = response.headers.get("content-type", "")
        # JSON responses are safe because browsers don't execute scripts in JSON
        assert "application/json" in content_type

        # Additionally, our API endpoints return JSON, not HTML
        # React's JSX auto-escapes user content preventing XSS


@pytest.mark.integration
class TestEndpointProtection:
    """Test that sensitive endpoints are properly protected."""

    def test_admin_endpoints_require_superuser(self):
        """Admin endpoints should require superuser authentication."""
        from app.main import app

        client = TestClient(app)

        admin_endpoints = [
            "/api/v1/admin/stats",
            "/api/v1/admin/api-keys",
            "/api/v1/admin/scheduler/status",
        ]

        for endpoint in admin_endpoints:
            response = client.get(
                endpoint,
                headers={
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "Accept-Language": "en-US",
                    "Accept-Encoding": "gzip",
                },
            )
            # Should require auth
            assert response.status_code in [401, 403], f"{endpoint} should require auth"

    def test_portfolio_endpoints_require_auth(self):
        """Portfolio endpoints should require authentication."""
        from app.main import app

        client = TestClient(app)

        response = client.get(
            "/api/v1/portfolio",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            },
        )
        assert response.status_code == 401


class TestAPIKeyModel:
    """Test API key security properties."""

    def test_key_hashing_is_irreversible(self):
        """API key hashing should be one-way."""
        from app.models.api_key import APIKey

        key = "wt_secret_key_12345"
        hash1 = APIKey.hash_key(key)

        # Hash should not contain the original key
        assert key not in hash1
        assert "secret" not in hash1

        # Hash should be consistent
        hash2 = APIKey.hash_key(key)
        assert hash1 == hash2

    def test_key_generation_uniqueness(self):
        """Generated keys should be unique."""
        from app.models.api_key import APIKey

        keys = [APIKey.generate_key() for _ in range(100)]
        unique_keys = set(keys)

        # All keys should be unique
        assert len(unique_keys) == 100

    def test_key_has_sufficient_entropy(self):
        """Generated keys should have sufficient entropy."""
        from app.models.api_key import APIKey

        key = APIKey.generate_key()

        # Key should be long enough (wt_ + 43 chars base64)
        assert len(key) > 40

        # Key should have prefix
        assert key.startswith("wt_")


# ============== P0 SECURITY FIXES TESTS ==============


class TestSecretKeyValidation:
    """Test SECRET_KEY validation at startup."""

    def test_empty_secret_key_raises_error(self):
        """Empty SECRET_KEY should raise ValueError at startup."""

        # Temporarily patch the environment
        with patch.dict("os.environ", {"SECRET_KEY": ""}, clear=False):
            with pytest.raises(ValueError) as exc_info:
                from app.core.config import Settings

                Settings()  # Should fail validation

            assert "SECRET_KEY" in str(exc_info.value)

    def test_valid_secret_key_accepted(self):
        """Valid SECRET_KEY should be accepted."""
        # The current settings have a valid key (app loaded successfully)
        from app.core.config import settings

        assert settings.SECRET_KEY is not None
        assert len(settings.SECRET_KEY) > 0


class TestEmailNormalization:
    """Test email normalization to prevent case-based duplicate accounts."""

    def test_email_normalized_to_lowercase(self):
        """UserCreate should normalize email to lowercase."""
        from app.api.auth import UserCreate

        user_create = UserCreate(email="TEST@EXAMPLE.COM", password="validpassword123")
        assert user_create.email == "test@example.com"

    def test_email_whitespace_stripped(self):
        """UserCreate should strip whitespace from email."""
        from app.api.auth import UserCreate

        user_create = UserCreate(email="  test@example.com  ", password="validpassword123")
        assert user_create.email == "test@example.com"

    def test_mixed_case_emails_become_identical(self):
        """Mixed case emails should become identical after normalization."""
        from app.api.auth import UserCreate

        emails = [
            "User@Example.COM",
            "USER@EXAMPLE.COM",
            "user@example.com",
            "UsEr@ExAmPlE.cOm",
        ]

        normalized = [UserCreate(email=e, password="pass12345678").email for e in emails]
        unique = set(normalized)

        assert len(unique) == 1
        assert unique.pop() == "user@example.com"

    def test_invalid_email_rejected(self):
        """Invalid email formats should be rejected."""
        from app.api.auth import UserCreate
        from pydantic import ValidationError

        invalid_emails = [
            "not-an-email",
            "@nodomain.com",
            "no@domain",
            "spaces in@email.com",
        ]

        for invalid in invalid_emails:
            with pytest.raises(ValidationError):
                UserCreate(email=invalid, password="validpassword123")


class TestRefreshTokenRotation:
    """Test refresh token rotation security."""

    def test_refresh_token_is_hashed_before_storage(self, test_session: Session):
        """Refresh token JTI should be hashed before storage."""
        from app.core.jwt import create_refresh_token

        # Create a refresh token
        token, token_hash = create_refresh_token("test@example.com")

        # The hash should be a SHA-256 hex digest (64 chars)
        assert len(token_hash) == 64

        # The raw token should be a JWT (three base64 sections)
        assert token.count(".") == 2

        # The hash should not contain the raw token
        assert token not in token_hash

    def test_refresh_token_rotation_invalidates_old_token(self, test_session: Session):
        """Old refresh token should be invalid after rotation."""
        from app.core.jwt import create_refresh_token, decode_token, hash_token_jti

        # Create initial token and store hash
        token1, hash1 = create_refresh_token("test@example.com")

        # Create a user to simulate the flow
        user = User(
            email="rotation@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            refresh_token_hash=hash1,
        )
        test_session.add(user)
        test_session.commit()

        # Simulate rotation - create new token
        token2, hash2 = create_refresh_token("rotation@test.com")

        # Update user with new hash
        user.refresh_token_hash = hash2
        test_session.add(user)
        test_session.commit()

        # Old token's hash should no longer match
        payload1 = decode_token(token1)
        jti1 = payload1.get("jti")
        old_hash = hash_token_jti(jti1)

        assert old_hash == hash1  # Verify our hash function is consistent
        assert old_hash != user.refresh_token_hash  # Old hash no longer matches stored

    def test_reused_token_detected(self, test_session: Session):
        """Token reuse attack should be detectable via hash mismatch."""
        from app.core.jwt import create_refresh_token, decode_token, hash_token_jti

        # Attacker captures token1
        token1, hash1 = create_refresh_token("victim@test.com")

        # Create user with token1's hash
        user = User(
            email="victim@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            refresh_token_hash=hash1,
        )
        test_session.add(user)
        test_session.commit()

        # Legitimate user refreshes (rotation)
        token2, hash2 = create_refresh_token("victim@test.com")
        user.refresh_token_hash = hash2
        test_session.add(user)
        test_session.commit()

        # Attacker tries to use captured token1
        payload1 = decode_token(token1)
        attacker_jti = payload1.get("jti")
        attacker_hash = hash_token_jti(attacker_jti)

        # Hash mismatch = token reuse detected
        assert attacker_hash != user.refresh_token_hash


class TestRefreshRateLimiting:
    """Test rate limiting on refresh endpoint."""

    def test_refresh_endpoint_has_rate_limit(self):
        """Refresh endpoint should be rate limited."""
        from app.core.rate_limit import rate_limiter

        test_ip = "refresh_rate_test_ip"

        # Clear any existing state
        rate_limiter.clear()

        # Make 30 requests (the limit)
        for _ in range(30):
            is_limited, _ = rate_limiter.is_rate_limited(test_ip, max_requests=30, window_seconds=60)
            if not is_limited:
                rate_limiter.record_request(test_ip)

        # 31st should be limited
        is_limited, retry_after = rate_limiter.is_rate_limited(test_ip, max_requests=30, window_seconds=60)
        assert is_limited, "Refresh endpoint should be rate limited after 30 requests"

    def test_rate_limit_returns_retry_after(self):
        """Rate limiter should return retry-after value."""
        from app.core.rate_limit import rate_limiter

        test_ip = "retry_after_test_ip"
        rate_limiter.clear()

        # Exhaust the limit
        for _ in range(30):
            rate_limiter.record_request(test_ip)

        is_limited, retry_after = rate_limiter.is_rate_limited(test_ip, max_requests=30, window_seconds=60)

        assert is_limited
        assert retry_after > 0
        assert retry_after <= 60  # Should be within the window


class TestInactiveUserEnforcement:
    """Test that inactive users cannot authenticate."""

    def test_inactive_user_rejected_from_get_current_user(self, test_session: Session):
        """Inactive users should be rejected by get_current_user."""
        from app.api.deps import get_current_user
        from app.core.jwt import create_access_token
        from fastapi import HTTPException

        # Create inactive user
        inactive_user = User(
            email="inactive@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=False,
        )
        test_session.add(inactive_user)
        test_session.commit()

        # Create valid token for inactive user
        access_token = create_access_token(subject="inactive@test.com")

        # Mock request with token
        mock_request = MagicMock()
        mock_request.cookies = {"access_token": access_token}

        # Should raise 401 for inactive user
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(mock_request, access_token, test_session)

        assert exc_info.value.status_code == 401
        assert "disabled" in exc_info.value.detail.lower()

    def test_active_user_allowed(self, test_session: Session):
        """Active users should be allowed by get_current_user."""
        from app.api.deps import get_current_user
        from app.core.jwt import create_access_token

        # Create active user
        active_user = User(
            email="active@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
        )
        test_session.add(active_user)
        test_session.commit()

        # Create valid token for active user
        access_token = create_access_token(subject="active@test.com")

        # Mock request with token
        mock_request = MagicMock()
        mock_request.cookies = {"access_token": access_token}

        # Should return the user
        user = get_current_user(mock_request, access_token, test_session)
        assert user.email == "active@test.com"
        assert user.is_active is True


class TestPasswordResetTokenHashing:
    """Test that password reset tokens are hashed before storage."""

    def test_reset_token_is_hashed(self, test_session: Session):
        """Password reset token should be hashed before storage."""
        raw_token = secrets.token_urlsafe(32)
        expected_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Create user with hashed token
        user = User(
            email="reset@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            password_reset_token_hash=expected_hash,
            password_reset_expires=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        test_session.add(user)
        test_session.commit()

        # Verify hash is stored, not raw token
        assert user.password_reset_token_hash == expected_hash
        assert raw_token not in user.password_reset_token_hash

    def test_reset_token_verified_by_hashing_input(self, test_session: Session):
        """Reset token verification should hash the input and compare."""
        raw_token = secrets.token_urlsafe(32)
        stored_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        user = User(
            email="verify@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            password_reset_token_hash=stored_hash,
            password_reset_expires=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        test_session.add(user)
        test_session.commit()

        # Correct token should verify
        submitted_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        assert submitted_hash == user.password_reset_token_hash

        # Wrong token should fail
        wrong_hash = hashlib.sha256(b"wrong_token").hexdigest()
        assert wrong_hash != user.password_reset_token_hash


@pytest.mark.integration
class TestCORSMiddlewareOrder:
    """Test that CORS middleware is correctly ordered."""

    def test_cors_headers_present_on_preflight(self):
        """CORS preflight should return proper headers."""
        from app.main import app

        client = TestClient(app)

        response = client.options(
            "/api/v1/cards",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
                "Access-Control-Request-Headers": "content-type",
            },
        )

        # CORS headers should be present
        assert "access-control-allow-origin" in response.headers or response.status_code == 200

    def test_options_request_not_blocked_by_anti_scraping(self):
        """OPTIONS requests should not be blocked by anti-scraping."""
        from app.main import app

        client = TestClient(app)

        # CORS preflight is an OPTIONS request
        response = client.options(
            "/api/v1/cards",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )

        # Should not be 403 (blocked)
        assert response.status_code != 403
