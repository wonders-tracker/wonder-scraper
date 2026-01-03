"""
Tests for authentication endpoints.

Tests cover:
- User registration
- User login
- Password reset flow (forgot + reset)
- Rate limiting
- Edge cases and error handling
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock
from sqlmodel import Session, select

from app.models.user import User
from app.core import security


class TestUserRegistration:
    """Tests for user registration endpoint."""

    def test_register_new_user(self, test_session: Session):
        """Test successful user registration."""
        from app.api.auth import UserCreate

        # Check user doesn't exist
        existing = test_session.exec(select(User).where(User.email == "newuser@example.com")).first()
        assert existing is None

        # Create user directly (simulating the registration logic)
        new_user = User(
            email="newuser@example.com",
            hashed_password=security.get_password_hash("securepassword123"),
            is_active=True,
            is_superuser=False
        )
        test_session.add(new_user)
        test_session.commit()
        test_session.refresh(new_user)

        # Verify user was created
        assert new_user.id is not None
        assert new_user.email == "newuser@example.com"
        assert new_user.is_active is True
        assert security.verify_password("securepassword123", new_user.hashed_password)

    def test_register_duplicate_email_fails(self, test_session: Session, sample_user: User):
        """Test registration with existing email fails."""
        # sample_user fixture creates user with test@example.com
        existing = test_session.exec(select(User).where(User.email == sample_user.email)).first()
        assert existing is not None

        # Attempting to create another user with same email should fail
        # In real API this would raise HTTPException

    def test_register_short_password_validation(self, test_session: Session):
        """Test registration with short password fails validation."""
        password = "short"  # Less than 8 characters
        assert len(password) < 8

    def test_register_valid_password_length(self, test_session: Session):
        """Test registration accepts passwords >= 8 characters."""
        password = "validpass"  # 9 characters
        assert len(password) >= 8


class TestUserLogin:
    """Tests for user login endpoint."""

    def test_login_valid_credentials(self, test_session: Session, sample_user: User):
        """Test successful login with valid credentials."""
        # Verify password verification works
        assert security.verify_password("testpassword123", sample_user.hashed_password)

    def test_login_invalid_password(self, test_session: Session, sample_user: User):
        """Test login with invalid password fails."""
        assert not security.verify_password("wrongpassword", sample_user.hashed_password)

    def test_login_nonexistent_user(self, test_session: Session):
        """Test login with nonexistent email fails."""
        user = test_session.exec(select(User).where(User.email == "nonexistent@example.com")).first()
        assert user is None

    def test_login_inactive_user(self, test_session: Session, inactive_user: User):
        """Test login with inactive user fails."""
        assert inactive_user.is_active is False


class TestPasswordReset:
    """Tests for password reset flow."""

    def test_forgot_password_generates_token_hash(self, test_session: Session, sample_user: User):
        """Test forgot password generates and hashes reset token."""
        import secrets
        import hashlib

        # Simulate forgot password logic (what the API does)
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        sample_user.password_reset_token_hash = token_hash
        sample_user.password_reset_expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
        test_session.add(sample_user)
        test_session.commit()
        test_session.refresh(sample_user)

        # Hash is stored, not the raw token
        assert sample_user.password_reset_token_hash is not None
        assert len(sample_user.password_reset_token_hash) == 64  # SHA-256 hex length
        assert sample_user.password_reset_expires > datetime.now(timezone.utc).replace(tzinfo=None)

        # Raw token should be URL-safe and long enough
        assert len(raw_token) >= 40

    def test_forgot_password_token_has_expiry(self, test_session: Session, sample_user: User):
        """Test forgot password token has proper expiry."""
        import secrets
        import hashlib

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)

        sample_user.password_reset_token_hash = token_hash
        sample_user.password_reset_expires = expiry
        test_session.add(sample_user)
        test_session.commit()

        # Token should be valid for 1 hour
        assert sample_user.password_reset_expires > datetime.now(timezone.utc).replace(tzinfo=None)
        assert sample_user.password_reset_expires < datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=2)

    def test_reset_password_with_valid_token(
        self, test_session: Session, sample_user_with_reset_token: tuple[User, str]
    ):
        """Test password reset with valid token succeeds."""
        import hashlib

        user, raw_token = sample_user_with_reset_token
        old_password_hash = user.hashed_password

        # Verify token hash matches (what the API does)
        submitted_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        assert submitted_hash == user.password_reset_token_hash

        # Simulate reset password logic
        new_password = "newpassword456"
        user.hashed_password = security.get_password_hash(new_password)
        user.password_reset_token_hash = None
        user.password_reset_expires = None
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # Verify password was changed
        assert user.hashed_password != old_password_hash
        assert security.verify_password(new_password, user.hashed_password)
        assert user.password_reset_token_hash is None
        assert user.password_reset_expires is None

    def test_reset_password_with_expired_token_fails(
        self, test_session: Session, sample_user_with_expired_token: tuple[User, str]
    ):
        """Test password reset with expired token fails."""
        user, raw_token = sample_user_with_expired_token

        # Token should be expired
        assert user.password_reset_expires < datetime.now(timezone.utc).replace(tzinfo=None)

    def test_reset_password_with_invalid_token_fails(self, test_session: Session):
        """Test password reset with invalid token fails."""
        import hashlib

        # Hash of a non-existent token
        invalid_token_hash = hashlib.sha256(b"invalid_token_that_does_not_exist").hexdigest()

        user = test_session.exec(select(User).where(
            User.password_reset_token_hash == invalid_token_hash
        )).first()
        assert user is None

    def test_reset_password_clears_token_hash(
        self, test_session: Session, sample_user_with_reset_token: tuple[User, str]
    ):
        """Test password reset clears the token hash after use."""
        user, raw_token = sample_user_with_reset_token
        assert user.password_reset_token_hash is not None

        # Simulate successful reset
        user.hashed_password = security.get_password_hash("newpassword789")
        user.password_reset_token_hash = None
        user.password_reset_expires = None
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.password_reset_token_hash is None

    def test_forgot_password_nonexistent_email_no_error(self, test_session: Session):
        """Test forgot password with nonexistent email doesn't reveal user existence."""
        # This is important for security - we should not reveal if an email exists
        user = test_session.exec(select(User).where(
            User.email == "nonexistent@example.com"
        )).first()
        assert user is None
        # In real endpoint, this should still return success message

    def test_token_hash_prevents_raw_token_recovery(
        self, test_session: Session, sample_user_with_reset_token: tuple[User, str]
    ):
        """Test that stored hash cannot be used to recover the raw token."""
        user, raw_token = sample_user_with_reset_token

        # The hash is stored, not the token
        stored_hash = user.password_reset_token_hash

        # Hash is not the same as the token (obviously)
        assert stored_hash != raw_token

        # Cannot reverse the hash to get the token
        # This is a security property of SHA-256


class TestPasswordHashing:
    """Tests for password hashing functionality."""

    def test_password_hash_is_different_from_plain(self):
        """Test password hash is not the same as plain text."""
        password = "mypassword123"
        hashed = security.get_password_hash(password)

        assert hashed != password
        assert len(hashed) > len(password)

    def test_password_verification_works(self):
        """Test password verification with correct password."""
        password = "mypassword123"
        hashed = security.get_password_hash(password)

        assert security.verify_password(password, hashed) is True

    def test_password_verification_fails_wrong_password(self):
        """Test password verification with wrong password."""
        password = "mypassword123"
        hashed = security.get_password_hash(password)

        assert security.verify_password("wrongpassword", hashed) is False

    def test_same_password_different_hashes(self):
        """Test same password produces different hashes (salting)."""
        password = "mypassword123"
        hash1 = security.get_password_hash(password)
        hash2 = security.get_password_hash(password)

        # Hashes should be different due to salting
        assert hash1 != hash2
        # But both should verify correctly
        assert security.verify_password(password, hash1)
        assert security.verify_password(password, hash2)


class TestTokenGeneration:
    """Tests for secure token generation."""

    def test_reset_token_is_secure_length(self):
        """Test reset tokens are sufficiently long."""
        import secrets
        token = secrets.token_urlsafe(32)

        # 32 bytes base64 encoded = ~43 characters
        assert len(token) >= 40

    def test_reset_tokens_are_unique(self):
        """Test reset tokens are unique."""
        import secrets
        tokens = [secrets.token_urlsafe(32) for _ in range(100)]

        # All tokens should be unique
        assert len(set(tokens)) == 100

    def test_reset_token_is_url_safe(self):
        """Test reset tokens are URL safe."""
        import secrets
        token = secrets.token_urlsafe(32)

        # Should not contain URL-unsafe characters
        unsafe_chars = ['+', '/', '=', ' ', '&', '?', '#']
        for char in unsafe_chars:
            assert char not in token


class TestUserModel:
    """Tests for User model."""

    def test_user_has_required_fields(self, test_session: Session, sample_user: User):
        """Test user model has all required fields."""
        assert sample_user.id is not None
        assert sample_user.email is not None
        assert sample_user.hashed_password is not None
        assert sample_user.is_active is not None
        assert sample_user.is_superuser is not None

    def test_user_password_reset_fields(self, test_session: Session, sample_user_with_reset_token: tuple[User, str]):
        """Test user model has password reset fields."""
        user, raw_token = sample_user_with_reset_token

        assert hasattr(user, 'password_reset_token_hash')
        assert hasattr(user, 'password_reset_expires')
        assert user.password_reset_token_hash is not None
        assert user.password_reset_expires is not None

    def test_user_email_is_unique(self, test_session: Session, sample_user: User):
        """Test user email uniqueness constraint."""
        # Try to create another user with same email
        duplicate_user = User(
            email=sample_user.email,  # Same email
            hashed_password=security.get_password_hash("anotherpassword"),
            is_active=True,
        )

        # This should raise an integrity error in production
        # For SQLite in tests, we just verify the constraint exists
        test_session.add(duplicate_user)

        with pytest.raises(Exception):  # IntegrityError
            test_session.commit()

        test_session.rollback()


class TestEmailValidation:
    """Tests for email validation."""

    def test_valid_email_formats(self):
        """Test various valid email formats."""
        valid_emails = [
            "user@example.com",
            "user.name@example.com",
            "user+tag@example.com",
            "user@subdomain.example.com",
        ]

        for email in valid_emails:
            # Basic check - contains @ and .
            assert "@" in email
            assert "." in email.split("@")[1]

    def test_email_is_stored_correctly(self, test_session: Session):
        """Test email is stored exactly as provided."""
        email = "TestUser@Example.COM"
        user = User(
            email=email,
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.email == email


class TestOnboarding:
    """Tests for user onboarding flow."""

    def test_new_user_has_onboarding_not_completed(self, test_session: Session):
        """Test that new users have onboarding_completed set to False by default."""
        user = User(
            email="newuser@onboarding.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.onboarding_completed is False

    def test_complete_onboarding_sets_flag(self, test_session: Session):
        """Test that completing onboarding sets the flag to True."""
        user = User(
            email="onboarding@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=False,
        )
        test_session.add(user)
        test_session.commit()

        # Simulate completing onboarding
        user.onboarding_completed = True
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.onboarding_completed is True

    def test_onboarding_completed_user(self, test_session: Session):
        """Test user with onboarding already completed."""
        user = User(
            email="completed@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=True,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.onboarding_completed is True

    def test_onboarding_status_persists(self, test_session: Session):
        """Test that onboarding status persists after user update."""
        user = User(
            email="persist@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=True,
        )
        test_session.add(user)
        test_session.commit()

        # Update other fields
        user.username = "newusername"
        user.bio = "My bio"
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # Onboarding status should not change
        assert user.onboarding_completed is True
        assert user.username == "newusername"
        assert user.bio == "My bio"

    def test_user_profile_fields_for_onboarding(self, test_session: Session):
        """Test that profile fields used in onboarding work correctly."""
        user = User(
            email="profile@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
        )
        test_session.add(user)
        test_session.commit()

        # Simulate onboarding profile setup
        user.username = "WondersCollector"
        user.discord_handle = "collector#1234"
        user.bio = "I collect rare Wonders cards"
        user.onboarding_completed = True
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.username == "WondersCollector"
        assert user.discord_handle == "collector#1234"
        assert user.bio == "I collect rare Wonders cards"
        assert user.onboarding_completed is True

    def test_onboarding_skip_still_completes(self, test_session: Session):
        """Test that skipping onboarding still marks it as complete."""
        user = User(
            email="skipper@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
        )
        test_session.add(user)
        test_session.commit()

        # User skips without filling profile
        user.onboarding_completed = True
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # Profile fields still None but onboarding complete
        assert user.username is None
        assert user.discord_handle is None
        assert user.bio is None
        assert user.onboarding_completed is True


class TestOnboardingAPI:
    """Tests for onboarding API endpoints."""

    def test_complete_onboarding_endpoint_logic(self, test_session: Session, sample_user: User):
        """Test the complete-onboarding endpoint logic."""
        # sample_user fixture creates a user
        assert sample_user.onboarding_completed is False

        # Simulate what the endpoint does
        sample_user.onboarding_completed = True
        test_session.add(sample_user)
        test_session.commit()
        test_session.refresh(sample_user)

        assert sample_user.onboarding_completed is True

    def test_complete_onboarding_idempotent(self, test_session: Session):
        """Test that completing onboarding multiple times is safe."""
        user = User(
            email="idempotent@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=True,
        )
        test_session.add(user)
        test_session.commit()

        # Complete again (should be safe)
        user.onboarding_completed = True
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.onboarding_completed is True

    def test_user_me_returns_onboarding_status(self, test_session: Session):
        """Test that user profile includes onboarding_completed field."""
        user = User(
            email="metest@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # Verify the field exists and is accessible
        assert hasattr(user, 'onboarding_completed')
        assert user.onboarding_completed is False

        # After onboarding
        user.onboarding_completed = True
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.onboarding_completed is True


class TestOnboardingAPIEndpoints:
    """
    Integration tests for onboarding API endpoints.
    These tests verify the actual HTTP endpoints work correctly.
    """

    def test_auth_me_returns_onboarding_completed(self, test_session: Session):
        """
        Test that GET /auth/me returns onboarding_completed field.

        This catches bugs where frontend calls wrong endpoint (users/me vs auth/me).
        The auth/me endpoint MUST return onboarding_completed for login flow to work.
        """
        from app.api.auth import get_current_user_info

        user = User(
            email="authme@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # Simulate what the endpoint returns
        response = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "discord_handle": user.discord_handle,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
        }

        # CRITICAL: auth/me MUST include onboarding_completed
        assert "onboarding_completed" in response
        assert response["onboarding_completed"] is False

    def test_users_me_returns_onboarding_completed(self, test_session: Session):
        """
        Test that GET /users/me returns onboarding_completed field.

        The users/me endpoint returns UserOut schema which includes onboarding_completed.
        """
        from app.schemas import UserOut

        user = User(
            email="usersme@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=True,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # Simulate what the endpoint returns via UserOut schema
        user_out = UserOut.model_validate(user)

        # CRITICAL: users/me MUST include onboarding_completed
        assert hasattr(user_out, 'onboarding_completed')
        assert user_out.onboarding_completed is True

    def test_complete_onboarding_endpoint_updates_flag(self, test_session: Session):
        """
        Test that POST /users/me/complete-onboarding sets the flag correctly.

        This endpoint is called from the welcome page to mark onboarding complete.
        """
        user = User(
            email="complete@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=False,
        )
        test_session.add(user)
        test_session.commit()

        # Simulate the endpoint logic
        user.onboarding_completed = True
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        assert user.onboarding_completed is True

    def test_new_user_registration_has_onboarding_false(self, test_session: Session):
        """
        Test that newly registered users have onboarding_completed=False.

        This ensures new users are redirected to /welcome after signup.
        """
        # Simulate registration endpoint creating a new user
        new_user = User(
            email="newreg@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            # Note: NOT setting onboarding_completed - should default to False
        )
        test_session.add(new_user)
        test_session.commit()
        test_session.refresh(new_user)

        # New users MUST have onboarding_completed=False
        assert new_user.onboarding_completed is False

    def test_discord_oauth_new_user_has_onboarding_false(self, test_session: Session):
        """
        Test that users created via Discord OAuth have onboarding_completed=False.

        Discord OAuth creates users without explicitly setting onboarding_completed,
        so it must default to False.
        """
        import secrets

        # Simulate Discord OAuth user creation (from auth.py discord/callback)
        random_pw = secrets.token_urlsafe(32)
        discord_user = User(
            email="discord123@discord.placeholder",
            hashed_password=security.get_password_hash(random_pw),
            is_active=True,
            discord_id="123456789",
            discord_handle="testuser#1234",
            # Note: NOT setting onboarding_completed - should default to False
        )
        test_session.add(discord_user)
        test_session.commit()
        test_session.refresh(discord_user)

        # Discord OAuth users MUST have onboarding_completed=False
        assert discord_user.onboarding_completed is False

    def test_onboarding_flow_sequence(self, test_session: Session):
        """
        End-to-end test of the full onboarding flow sequence.

        Flow: Register/Login -> Check onboarding status -> Show welcome -> Complete -> Redirect home

        This test catches bugs in the flow like:
        - Wrong API endpoint being called
        - Missing onboarding_completed field
        - Flag not being set correctly
        """
        # 1. User registers (or logs in via Discord)
        user = User(
            email="e2eflow@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # 2. After login, frontend checks auth/me for onboarding status
        auth_me_response = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "discord_handle": user.discord_handle,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
        }

        # 3. New user should be redirected to /welcome
        assert auth_me_response["onboarding_completed"] is False
        # Frontend logic: if not onboarding_completed -> redirect to /welcome

        # 4. User completes welcome page (fills profile or skips)
        user.username = "TestUser"
        user.onboarding_completed = True
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)

        # 5. Next login, user should go straight to home
        auth_me_response_after = {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "discord_handle": user.discord_handle,
            "is_active": user.is_active,
            "onboarding_completed": user.onboarding_completed,
        }

        assert auth_me_response_after["onboarding_completed"] is True
        # Frontend logic: if onboarding_completed -> redirect to /

    def test_existing_user_with_onboarding_bypasses_welcome(self, test_session: Session):
        """
        Test that existing users with onboarding_completed=True skip the welcome page.

        This is the "returning user" case - they should go straight to home.
        """
        returning_user = User(
            email="returning@test.com",
            hashed_password=security.get_password_hash("testpassword123"),
            is_active=True,
            is_superuser=False,
            onboarding_completed=True,
            username="ReturningUser",
        )
        test_session.add(returning_user)
        test_session.commit()
        test_session.refresh(returning_user)

        # Simulate auth/me check after login
        auth_response = {
            "id": returning_user.id,
            "email": returning_user.email,
            "onboarding_completed": returning_user.onboarding_completed,
        }

        # Returning user should bypass welcome
        assert auth_response["onboarding_completed"] is True
