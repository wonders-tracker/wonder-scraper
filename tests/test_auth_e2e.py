"""
End-to-end tests for authentication flows.

Tests complete user journeys through the auth system:
- Registration → Login → Access protected resource
- Login → Refresh → Continue session
- Password reset flow
- Logout and cookie clearing
"""

import pytest
import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from sqlmodel import Session, select
from unittest.mock import patch, MagicMock

from app.main import app
from app.db import get_session
from app.models.user import User
from app.core import security
from app.core.jwt import decode_token


@pytest.fixture
def client(test_session: Session):
    """Create test client with overridden database session."""
    def get_test_session():
        yield test_session

    app.dependency_overrides[get_session] = get_test_session
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture
def registered_user(test_session: Session) -> tuple[User, str]:
    """Create a registered user with known password."""
    password = "securepassword123"
    user = User(
        email="e2e@test.com",
        hashed_password=security.get_password_hash(password),
        is_active=True,
        is_superuser=False,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user, password


class TestRegistrationFlow:
    """E2E tests for user registration."""

    def test_register_creates_user(self, client: TestClient, test_session: Session):
        """Registration should create user and return user data."""
        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "newuser@test.com",
                "password": "validpassword123"
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should return user data
        assert "id" in data
        assert data["email"] == "newuser@test.com"
        assert data["is_active"] is True

    def test_register_then_login_returns_tokens(self, client: TestClient, test_session: Session):
        """After registration, login should return tokens."""
        # Register
        register_response = client.post(
            "/api/v1/auth/register",
            json={
                "email": "reglogin@test.com",
                "password": "validpassword123"
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        assert register_response.status_code == 200

        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "reglogin@test.com",
                "password": "validpassword123",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert login_response.status_code == 200
        data = login_response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_duplicate_email_rejected(self, client: TestClient, registered_user: tuple[User, str]):
        """Duplicate email registration should fail."""
        user, _ = registered_user

        response = client.post(
            "/api/v1/auth/register",
            json={
                "email": user.email,
                "password": "anotherpassword123"
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()


class TestLoginFlow:
    """E2E tests for user login."""

    def test_login_returns_tokens_and_sets_cookies(
        self, client: TestClient, registered_user: tuple[User, str]
    ):
        """Login should return access token and set refresh cookie."""
        user, password = registered_user

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": user.email,
                "password": password,
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert response.status_code == 200
        data = response.json()

        # Should return access token
        assert "access_token" in data
        assert data["token_type"] == "bearer"

        # Access token should be valid JWT
        payload = decode_token(data["access_token"])
        assert payload is not None
        assert payload.get("sub") == user.email
        assert payload.get("type") == "access"

        # Should set refresh token cookie
        assert "refresh_token" in response.cookies

    def test_login_with_wrong_password_fails(
        self, client: TestClient, registered_user: tuple[User, str]
    ):
        """Login with wrong password should fail with 400."""
        user, _ = registered_user

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": user.email,
                "password": "wrongpassword",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        # API returns 400 for invalid credentials (not 401)
        assert response.status_code == 400
        assert "incorrect" in response.json()["detail"].lower()

    def test_login_with_nonexistent_email_fails(self, client: TestClient):
        """Login with nonexistent email should fail with 400."""
        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": "doesnotexist@test.com",
                "password": "anypassword",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        # API returns 400 for invalid credentials
        assert response.status_code == 400


class TestRefreshFlow:
    """E2E tests for token refresh."""

    def test_refresh_returns_new_access_token(
        self, client: TestClient, registered_user: tuple[User, str]
    ):
        """Refresh should return a valid access token."""
        user, password = registered_user

        # First login to get refresh token
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": password},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        assert login_response.status_code == 200

        # Get the refresh token from cookies
        refresh_token = login_response.cookies.get("refresh_token")
        assert refresh_token is not None, "Login should set refresh_token cookie"

        # Use refresh token to get new access token
        # Manually set cookie since TestClient may not handle path-scoped cookies correctly
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
                "Cookie": f"refresh_token={refresh_token}",
            },
        )

        assert refresh_response.status_code == 200
        new_access = refresh_response.json()["access_token"]

        # New token should be valid and for the same user
        payload = decode_token(new_access)
        assert payload is not None
        assert payload.get("sub") == user.email
        assert payload.get("type") == "access"

        # Token should have proper structure
        assert new_access.count(".") == 2  # JWT has 3 parts

    def test_refresh_rotates_refresh_token(
        self, client: TestClient, registered_user: tuple[User, str]
    ):
        """Refresh should rotate the refresh token (cookie changes)."""
        user, password = registered_user

        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": password},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        original_refresh = login_response.cookies.get("refresh_token")
        assert original_refresh is not None

        # Refresh with explicit cookie header
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
                "Cookie": f"refresh_token={original_refresh}",
            },
        )

        assert refresh_response.status_code == 200
        new_refresh = refresh_response.cookies.get("refresh_token")

        # Refresh token should be rotated
        assert new_refresh is not None
        assert new_refresh != original_refresh

    def test_refresh_without_cookie_fails(self, client: TestClient):
        """Refresh without refresh token cookie should fail."""
        response = client.post(
            "/api/v1/auth/refresh",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            },
        )

        assert response.status_code == 401


class TestProtectedResourceAccess:
    """E2E tests for accessing protected resources."""

    def test_access_protected_with_valid_token(
        self, client: TestClient, registered_user: tuple[User, str]
    ):
        """Should access protected resource with valid access token."""
        user, password = registered_user

        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": password},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        access_token = login_response.json()["access_token"]

        # Access protected endpoint (auth/me)
        me_response = client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert me_response.status_code == 200
        data = me_response.json()
        assert data["email"] == user.email

    def test_access_protected_without_token_fails(self, client: TestClient):
        """Should fail to access protected resource without token."""
        response = client.get(
            "/api/v1/auth/me",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert response.status_code == 401


class TestLogoutFlow:
    """E2E tests for logout."""

    def test_logout_clears_cookies(
        self, client: TestClient, registered_user: tuple[User, str]
    ):
        """Logout should clear auth cookies."""
        user, password = registered_user

        # Login
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": user.email, "password": password},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        access_token = login_response.json()["access_token"]

        # Logout
        logout_response = client.post(
            "/api/v1/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token}",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            },
            cookies=login_response.cookies,
        )

        assert logout_response.status_code == 200

        # Cookies should be cleared (max_age=0 or deleted)
        set_cookies = logout_response.headers.get_list("set-cookie")
        for cookie in set_cookies:
            if "refresh_token" in cookie or "access_token" in cookie:
                # Cookie should be expired/deleted (contains max-age=0 or expires in past)
                cookie_lower = cookie.lower()
                assert "max-age=0" in cookie_lower or 'expires=' in cookie_lower


class TestPasswordResetFlow:
    """E2E tests for password reset."""

    def test_forgot_password_accepts_valid_email(
        self, client: TestClient, registered_user: tuple[User, str]
    ):
        """Forgot password should accept valid email (security: same response for invalid)."""
        user, _ = registered_user

        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": user.email},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        # Should always return 200 to not leak user existence
        assert response.status_code == 200

    def test_forgot_password_accepts_invalid_email(self, client: TestClient):
        """Forgot password should accept invalid email (no user enumeration)."""
        response = client.post(
            "/api/v1/auth/forgot-password",
            json={"email": "nonexistent@test.com"},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        # Should return 200 even for non-existent email (security)
        assert response.status_code == 200

    def test_reset_password_with_valid_token(
        self, test_session: Session, client: TestClient
    ):
        """Reset password should work with valid token."""
        # Create user with reset token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        user = User(
            email="resetflow@test.com",
            hashed_password=security.get_password_hash("oldpassword123"),
            is_active=True,
            password_reset_token_hash=token_hash,
            password_reset_expires=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
        )
        test_session.add(user)
        test_session.commit()

        # Reset password
        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "newpassword456"
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert response.status_code == 200

        # Verify password was changed
        test_session.refresh(user)
        assert security.verify_password("newpassword456", user.hashed_password)

        # Token should be cleared
        assert user.password_reset_token_hash is None

    def test_reset_password_with_expired_token_fails(
        self, test_session: Session, client: TestClient
    ):
        """Reset password should fail with expired token."""
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        user = User(
            email="expiredflow@test.com",
            hashed_password=security.get_password_hash("oldpassword123"),
            is_active=True,
            password_reset_token_hash=token_hash,
            password_reset_expires=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),  # Expired
        )
        test_session.add(user)
        test_session.commit()

        response = client.post(
            "/api/v1/auth/reset-password",
            json={
                "token": raw_token,
                "new_password": "newpassword456"
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        assert response.status_code == 400
        assert "expired" in response.json()["detail"].lower()


class TestInactiveUserFlow:
    """E2E tests for inactive user handling."""

    def test_inactive_user_cannot_login(self, test_session: Session, client: TestClient):
        """Inactive users should not be able to login."""
        user = User(
            email="inactive_login@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=False,
        )
        test_session.add(user)
        test_session.commit()

        response = client.post(
            "/api/v1/auth/login",
            data={
                "username": user.email,
                "password": "testpassword123",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )

        # API returns 400 for inactive user
        assert response.status_code == 400
        assert "inactive" in response.json()["detail"].lower()


class TestCompleteUserJourney:
    """E2E test for complete user journey."""

    def test_register_login_access_refresh_logout(self, client: TestClient, test_session: Session):
        """Complete user journey: register → login → access → refresh → logout."""
        email = "journey@test.com"
        password = "journeypassword123"

        # 1. Register
        register_response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "password": password},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        assert register_response.status_code == 200
        assert register_response.json()["email"] == email

        # 2. Login to get tokens
        login_response = client.post(
            "/api/v1/auth/login",
            data={"username": email, "password": password},
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        assert login_response.status_code == 200
        access_token_1 = login_response.json()["access_token"]
        refresh_token_1 = login_response.cookies.get("refresh_token")

        # 3. Access protected resource
        me_response_1 = client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {access_token_1}",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        assert me_response_1.status_code == 200
        assert me_response_1.json()["email"] == email

        # 4. Refresh token (with explicit cookie header)
        refresh_response = client.post(
            "/api/v1/auth/refresh",
            headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
                "Cookie": f"refresh_token={refresh_token_1}",
            },
        )
        assert refresh_response.status_code == 200
        access_token_2 = refresh_response.json()["access_token"]
        refresh_token_2 = refresh_response.cookies.get("refresh_token")

        # New token should work
        me_response_2 = client.get(
            "/api/v1/auth/me",
            headers={
                "Authorization": f"Bearer {access_token_2}",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
            }
        )
        assert me_response_2.status_code == 200

        # 5. Logout (with explicit cookie header)
        logout_response = client.post(
            "/api/v1/auth/logout",
            headers={
                "Authorization": f"Bearer {access_token_2}",
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
                "Accept-Language": "en-US",
                "Accept-Encoding": "gzip",
                "Cookie": f"refresh_token={refresh_token_2}",
            },
        )
        assert logout_response.status_code == 200
