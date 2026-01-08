"""
Tests for JWT token utilities.

Tests cover:
- Access token creation and validation
- Refresh token creation with rotation
- Token decoding and expiry handling
- Token hash generation
"""

from datetime import datetime, timedelta, timezone
import jwt

from app.core.jwt import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_token_expiry,
    is_token_expired,
    hash_token_jti,
)
from app.core.config import settings


class TestAccessToken:
    """Tests for access token creation and validation."""

    def test_create_access_token_basic(self):
        """Test creating a basic access token."""
        token = create_access_token("user123")

        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0

    def test_access_token_contains_subject(self):
        """Test that access token contains the subject."""
        subject = "user123"
        token = create_access_token(subject)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == subject

    def test_access_token_has_correct_type(self):
        """Test that access token has type 'access'."""
        token = create_access_token("user123")

        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "access"

    def test_access_token_has_expiry(self):
        """Test that access token has expiry time."""
        token = create_access_token("user123")

        payload = decode_token(token)
        assert payload is not None
        assert "exp" in payload

    def test_access_token_custom_expiry(self):
        """Test access token with custom expiry delta."""
        custom_delta = timedelta(hours=1)
        token = create_access_token("user123", expires_delta=custom_delta)

        expiry = get_token_expiry(token)
        assert expiry is not None
        # Should be approximately 1 hour from now (within 1 minute tolerance)
        expected = datetime.now(timezone.utc) + custom_delta
        assert abs((expiry - expected).total_seconds()) < 60

    def test_access_token_default_expiry(self):
        """Test access token has default expiry from settings."""
        token = create_access_token("user123")

        expiry = get_token_expiry(token)
        assert expiry is not None
        expected = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        # Within 1 minute tolerance
        assert abs((expiry - expected).total_seconds()) < 60

    def test_access_token_with_non_string_subject(self):
        """Test that non-string subjects are converted to strings."""
        token = create_access_token(12345)

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "12345"


class TestRefreshToken:
    """Tests for refresh token creation and rotation."""

    def test_create_refresh_token_returns_tuple(self):
        """Test that refresh token creation returns token and hash."""
        result = create_refresh_token("user123")

        assert isinstance(result, tuple)
        assert len(result) == 2
        token, token_hash = result
        assert isinstance(token, str)
        assert isinstance(token_hash, str)

    def test_refresh_token_contains_subject(self):
        """Test that refresh token contains the subject."""
        token, _ = create_refresh_token("user123")

        payload = decode_token(token)
        assert payload is not None
        assert payload["sub"] == "user123"

    def test_refresh_token_has_correct_type(self):
        """Test that refresh token has type 'refresh'."""
        token, _ = create_refresh_token("user123")

        payload = decode_token(token)
        assert payload is not None
        assert payload["type"] == "refresh"

    def test_refresh_token_has_jti(self):
        """Test that refresh token has a unique JTI."""
        token, _ = create_refresh_token("user123")

        payload = decode_token(token)
        assert payload is not None
        assert "jti" in payload
        assert len(payload["jti"]) > 0

    def test_refresh_token_hash_matches_jti(self):
        """Test that token hash corresponds to the JTI."""
        token, token_hash = create_refresh_token("user123")

        payload = decode_token(token)
        assert payload is not None
        jti = payload["jti"]

        # Hash the JTI and compare
        expected_hash = hash_token_jti(jti)
        assert token_hash == expected_hash

    def test_refresh_tokens_have_unique_jtis(self):
        """Test that different refresh tokens have unique JTIs."""
        _, hash1 = create_refresh_token("user123")
        _, hash2 = create_refresh_token("user123")

        assert hash1 != hash2

    def test_refresh_token_custom_expiry(self):
        """Test refresh token with custom expiry delta."""
        custom_delta = timedelta(days=30)
        token, _ = create_refresh_token("user123", expires_delta=custom_delta)

        expiry = get_token_expiry(token)
        assert expiry is not None
        expected = datetime.now(timezone.utc) + custom_delta
        assert abs((expiry - expected).total_seconds()) < 60

    def test_refresh_token_default_expiry(self):
        """Test refresh token has default expiry from settings."""
        token, _ = create_refresh_token("user123")

        expiry = get_token_expiry(token)
        assert expiry is not None
        expected = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        assert abs((expiry - expected).total_seconds()) < 60


class TestDecodeToken:
    """Tests for token decoding."""

    def test_decode_valid_token(self):
        """Test decoding a valid token."""
        token = create_access_token("user123")

        payload = decode_token(token)

        assert payload is not None
        assert payload["sub"] == "user123"

    def test_decode_expired_token(self):
        """Test decoding an expired token returns None."""
        # Create a token that expires immediately
        token = create_access_token("user123", expires_delta=timedelta(seconds=-1))

        payload = decode_token(token)

        assert payload is None

    def test_decode_invalid_token(self):
        """Test decoding an invalid token returns None."""
        payload = decode_token("invalid.token.here")

        assert payload is None

    def test_decode_tampered_token(self):
        """Test decoding a tampered token returns None."""
        token = create_access_token("user123")
        # Tamper with the token
        tampered = token[:-10] + "0000000000"

        payload = decode_token(tampered)

        assert payload is None

    def test_decode_wrong_signature_token(self):
        """Test decoding a token with wrong signature returns None."""
        # Create a token with a different secret
        to_encode = {
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
            "sub": "user123",
            "type": "access",
        }
        token = jwt.encode(to_encode, "wrong_secret", algorithm="HS256")

        payload = decode_token(token)

        assert payload is None


class TestGetTokenExpiry:
    """Tests for get_token_expiry function."""

    def test_get_expiry_valid_token(self):
        """Test getting expiry from valid token."""
        token = create_access_token("user123")

        expiry = get_token_expiry(token)

        assert expiry is not None
        assert isinstance(expiry, datetime)
        assert expiry.tzinfo is not None

    def test_get_expiry_expired_token(self):
        """Test getting expiry from expired token still works."""
        # Create an expired token
        to_encode = {
            "exp": datetime.now(timezone.utc) - timedelta(hours=1),
            "sub": "user123",
        }
        token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

        # get_token_expiry doesn't verify signature, so it should return the expiry
        expiry = get_token_expiry(token)

        assert expiry is not None
        assert expiry < datetime.now(timezone.utc)

    def test_get_expiry_invalid_token(self):
        """Test getting expiry from invalid token returns None."""
        expiry = get_token_expiry("not.a.valid.token")

        assert expiry is None

    def test_get_expiry_token_without_exp(self):
        """Test getting expiry from token without exp claim returns None."""
        # Manually create a token without exp claim
        # PyJWT doesn't require exp by default
        to_encode = {"sub": "user123"}
        token = jwt.encode(
            to_encode,
            settings.SECRET_KEY,
            algorithm=settings.ALGORITHM,
        )

        expiry = get_token_expiry(token)

        assert expiry is None


class TestIsTokenExpired:
    """Tests for is_token_expired function."""

    def test_valid_token_not_expired(self):
        """Test that a fresh token is not expired."""
        token = create_access_token("user123")

        assert is_token_expired(token) is False

    def test_expired_token_is_expired(self):
        """Test that an expired token is detected."""
        # Create an already-expired token
        token = create_access_token("user123", expires_delta=timedelta(seconds=-1))

        assert is_token_expired(token) is True

    def test_invalid_token_is_considered_expired(self):
        """Test that invalid token is considered expired."""
        assert is_token_expired("invalid.token") is True


class TestHashTokenJti:
    """Tests for hash_token_jti function."""

    def test_hash_returns_hex_string(self):
        """Test that hash returns a hex string."""
        jti = "test-jti-value"

        result = hash_token_jti(jti)

        assert isinstance(result, str)
        # SHA256 hex is 64 characters
        assert len(result) == 64
        # Should be valid hex
        int(result, 16)

    def test_same_jti_produces_same_hash(self):
        """Test that same JTI produces same hash."""
        jti = "consistent-jti"

        hash1 = hash_token_jti(jti)
        hash2 = hash_token_jti(jti)

        assert hash1 == hash2

    def test_different_jtis_produce_different_hashes(self):
        """Test that different JTIs produce different hashes."""
        hash1 = hash_token_jti("jti-one")
        hash2 = hash_token_jti("jti-two")

        assert hash1 != hash2
