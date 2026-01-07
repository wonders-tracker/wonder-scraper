"""
JWT token utilities with refresh token rotation.

Token Strategy:
- Access tokens: Short-lived (15 min), sent in response body
- Refresh tokens: Long-lived (7 days), stored in httpOnly cookie only
- On each refresh, a new refresh token is issued (rotation)
- Logout clears the cookie; access token expires naturally
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
import secrets
import hashlib
import jwt
from app.core.config import settings


TokenType = Literal["access", "refresh"]


def create_access_token(subject: str | Any, expires_delta: timedelta | None = None) -> str:
    """Create a short-lived access token."""
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "access",
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(subject: str | Any, expires_delta: timedelta | None = None) -> tuple[str, str]:
    """
    Create a refresh token with rotation support.

    Returns:
        tuple: (token_string, token_hash) - hash is stored in DB for validation
    """
    if expires_delta:
        expire = datetime.now(timezone.utc) + expires_delta
    else:
        expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)

    # Add a unique jti (JWT ID) for token rotation tracking
    jti = secrets.token_urlsafe(32)

    to_encode = {
        "exp": expire,
        "sub": str(subject),
        "type": "refresh",
        "jti": jti,
        "iat": datetime.now(timezone.utc),
    }
    token = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    token_hash = hashlib.sha256(jti.encode()).hexdigest()

    return token, token_hash


def decode_token(token: str) -> Optional[dict]:
    """
    Decode and validate a JWT token.

    Returns:
        dict with token payload if valid, None if invalid/expired
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


def get_token_expiry(token: str) -> Optional[datetime]:
    """Get the expiration time of a token without full validation."""
    try:
        # Decode without verification to get expiry
        payload = jwt.decode(token, options={"verify_signature": False})
        exp = payload.get("exp")
        if exp:
            return datetime.fromtimestamp(exp, tz=timezone.utc)
        return None
    except jwt.InvalidTokenError:
        return None


def is_token_expired(token: str) -> bool:
    """Check if a token is expired."""
    expiry = get_token_expiry(token)
    if expiry is None:
        return True
    return datetime.now(timezone.utc) > expiry


def hash_token_jti(jti: str) -> str:
    """Hash a token's JTI for storage/comparison."""
    return hashlib.sha256(jti.encode()).hexdigest()
