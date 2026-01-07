"""
Auth configuration validation tests.

These tests ensure auth configuration is correct to prevent cookie/domain mismatches
that break authentication flows (like the Discord OAuth redirect URI issue).

Run standalone: pytest tests/test_auth_config.py -v
"""

import os
from urllib.parse import urlparse

import pytest


class TestAuthConfigValidation:
    """Validate auth-related configuration for correctness."""

    def test_discord_redirect_uri_matches_frontend_domain(self):
        """
        CRITICAL: Discord redirect URI must use the same domain as FRONTEND_URL.

        If these don't match, cookies set during OAuth callback won't be sent
        to the frontend, breaking authentication.

        BAD:  DISCORD_REDIRECT_URI=https://backend.railway.app/api/v1/auth/discord/callback
              FRONTEND_URL=https://wonderstracker.com
              -> Cookies set on backend.railway.app, frontend on wonderstracker.com = FAIL

        GOOD: DISCORD_REDIRECT_URI=https://wonderstracker.com/api/v1/auth/discord/callback
              FRONTEND_URL=https://wonderstracker.com
              -> Cookies set on wonderstracker.com, frontend on wonderstracker.com = OK
        """
        from app.core.config import settings

        # Skip if running in CI without proper env vars (localhost defaults are fine)
        if settings.FRONTEND_URL.startswith("http://localhost"):
            pytest.skip("Skipping domain validation for local development")

        frontend_domain = urlparse(settings.FRONTEND_URL).netloc
        redirect_domain = urlparse(settings.DISCORD_REDIRECT_URI).netloc

        assert frontend_domain == redirect_domain, (
            f"DISCORD_REDIRECT_URI domain ({redirect_domain}) must match "
            f"FRONTEND_URL domain ({frontend_domain}). "
            f"Mismatched domains cause auth cookies to fail. "
            f"Set DISCORD_REDIRECT_URI=https://{frontend_domain}/api/v1/auth/discord/callback"
        )

    def test_discord_redirect_uri_uses_https_in_production(self):
        """Redirect URI must use HTTPS in production to prevent token interception."""
        from app.core.config import settings

        if settings.FRONTEND_URL.startswith("http://localhost"):
            pytest.skip("Skipping HTTPS check for local development")

        parsed = urlparse(settings.DISCORD_REDIRECT_URI)
        assert parsed.scheme == "https", (
            f"DISCORD_REDIRECT_URI must use HTTPS in production, got: {parsed.scheme}"
        )

    def test_discord_redirect_uri_path_is_correct(self):
        """Redirect URI must point to the correct callback endpoint."""
        from app.core.config import settings

        parsed = urlparse(settings.DISCORD_REDIRECT_URI)
        expected_path = "/api/v1/auth/discord/callback"

        assert parsed.path == expected_path, (
            f"DISCORD_REDIRECT_URI path must be {expected_path}, got: {parsed.path}"
        )

    def test_frontend_url_uses_https_in_production(self):
        """Frontend URL must use HTTPS in production."""
        from app.core.config import settings

        if settings.FRONTEND_URL.startswith("http://localhost"):
            pytest.skip("Skipping HTTPS check for local development")

        parsed = urlparse(settings.FRONTEND_URL)
        assert parsed.scheme == "https", (
            f"FRONTEND_URL must use HTTPS in production, got: {parsed.scheme}"
        )

    def test_cookie_secure_enabled_in_production(self):
        """Cookies must be secure in production to prevent interception."""
        from app.core.config import settings

        if settings.FRONTEND_URL.startswith("http://localhost"):
            pytest.skip("Skipping secure cookie check for local development")

        assert settings.COOKIE_SECURE is True, (
            "COOKIE_SECURE must be True in production to prevent cookie interception"
        )

    def test_secret_key_is_set(self):
        """SECRET_KEY must be set for JWT signing."""
        from app.core.config import settings

        assert settings.SECRET_KEY, "SECRET_KEY must be set"

        # In CI/test environments, we use a shorter test key
        # In production, we validate length more strictly
        if settings.FRONTEND_URL.startswith("http://localhost"):
            assert len(settings.SECRET_KEY) >= 16, (
                "SECRET_KEY should be at least 16 characters even in test"
            )
        else:
            assert len(settings.SECRET_KEY) >= 32, (
                "SECRET_KEY should be at least 32 characters for production security"
            )

    def test_access_token_expiry_is_reasonable(self):
        """Access tokens should have short expiry for security."""
        from app.core.config import settings

        # Access tokens should expire within 1 hour max
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES <= 60, (
            f"ACCESS_TOKEN_EXPIRE_MINUTES ({settings.ACCESS_TOKEN_EXPIRE_MINUTES}) "
            "should be <= 60 minutes for security"
        )
        # But not too short to be annoying
        assert settings.ACCESS_TOKEN_EXPIRE_MINUTES >= 5, (
            f"ACCESS_TOKEN_EXPIRE_MINUTES ({settings.ACCESS_TOKEN_EXPIRE_MINUTES}) "
            "should be >= 5 minutes for usability"
        )

    def test_refresh_token_expiry_is_reasonable(self):
        """Refresh tokens should have reasonable expiry."""
        from app.core.config import settings

        # Refresh tokens should expire within 30 days
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS <= 30, (
            f"REFRESH_TOKEN_EXPIRE_DAYS ({settings.REFRESH_TOKEN_EXPIRE_DAYS}) "
            "should be <= 30 days for security"
        )
        # But at least 1 day
        assert settings.REFRESH_TOKEN_EXPIRE_DAYS >= 1, (
            f"REFRESH_TOKEN_EXPIRE_DAYS ({settings.REFRESH_TOKEN_EXPIRE_DAYS}) "
            "should be >= 1 day for usability"
        )


class TestAuthEndpointConfig:
    """Test auth endpoint configuration is correct."""

    def test_discord_login_returns_correct_redirect_uri(self):
        """The /auth/discord/login endpoint must return URI matching config."""
        from app.core.config import settings
        from app.api.auth import login_discord

        result = login_discord()

        assert "url" in result
        assert settings.DISCORD_REDIRECT_URI in result["url"], (
            f"Discord login URL must contain DISCORD_REDIRECT_URI. "
            f"Expected to find: {settings.DISCORD_REDIRECT_URI}"
        )
        assert settings.DISCORD_CLIENT_ID in result["url"], (
            f"Discord login URL must contain DISCORD_CLIENT_ID"
        )


def validate_production_auth_config(base_url: str) -> dict:
    """
    Validate auth configuration for a running environment.

    This can be called from CI to validate staging/production.
    Returns dict with validation results.
    """
    import httpx

    results = {
        "valid": True,
        "checks": [],
        "errors": []
    }

    try:
        # Get Discord login URL from the API
        response = httpx.get(f"{base_url}/api/v1/auth/discord/login", timeout=10)
        response.raise_for_status()
        data = response.json()

        discord_url = data.get("url", "")

        # Extract redirect_uri from Discord URL
        from urllib.parse import parse_qs, urlparse
        parsed = urlparse(discord_url)
        params = parse_qs(parsed.query)
        redirect_uri = params.get("redirect_uri", [""])[0]

        # Check 1: Redirect URI should NOT point to Railway backend
        if "railway.app" in redirect_uri and "railway.app" not in base_url:
            results["valid"] = False
            results["errors"].append(
                f"CRITICAL: redirect_uri points to Railway ({redirect_uri}) "
                f"but should match frontend domain"
            )
        else:
            results["checks"].append("redirect_uri domain: OK")

        # Check 2: Redirect URI should use HTTPS
        if not redirect_uri.startswith("https://"):
            results["valid"] = False
            results["errors"].append(f"redirect_uri must use HTTPS: {redirect_uri}")
        else:
            results["checks"].append("redirect_uri HTTPS: OK")

        # Check 3: Redirect URI path should be correct
        if "/api/v1/auth/discord/callback" not in redirect_uri:
            results["valid"] = False
            results["errors"].append(f"redirect_uri has wrong path: {redirect_uri}")
        else:
            results["checks"].append("redirect_uri path: OK")

    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"Failed to validate: {e}")

    return results


if __name__ == "__main__":
    # Allow running standalone for quick validation
    import sys

    if len(sys.argv) > 1:
        base_url = sys.argv[1]
        print(f"Validating auth config for: {base_url}")
        results = validate_production_auth_config(base_url)

        print("\nChecks passed:")
        for check in results["checks"]:
            print(f"  ✓ {check}")

        if results["errors"]:
            print("\nErrors found:")
            for error in results["errors"]:
                print(f"  ✗ {error}")
            sys.exit(1)
        else:
            print("\n✓ All auth configuration checks passed")
            sys.exit(0)
    else:
        print("Usage: python tests/test_auth_config.py <base_url>")
        print("Example: python tests/test_auth_config.py https://wonder-scraper-staging.up.railway.app")
