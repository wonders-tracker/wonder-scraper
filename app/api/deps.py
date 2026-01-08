from typing import Optional, Tuple
import threading

from cachetools import TTLCache
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer, APIKeyHeader

from pydantic import BaseModel
from sqlmodel import Session, select
from datetime import datetime, timezone

from app.db import get_session
from app.models.user import User
from app.models.api_key import APIKey
from app.core.config import settings
from app.core.anti_scraping import api_key_limiter
from app.core.jwt import decode_token

# Cookie name for auth token
COOKIE_NAME = "access_token"

# User cache: Reduces DB lookups for authenticated requests
# TTL of 30 seconds - balances freshness with performance
_user_cache: TTLCache = TTLCache(maxsize=100, ttl=30)
_user_cache_lock = threading.Lock()

# API Key header name
API_KEY_HEADER = "X-API-Key"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/login", auto_error=False)
api_key_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


class TokenData(BaseModel):
    email: Optional[str] = None


def get_token_from_request(request: Request, header_token: Optional[str] = None) -> Optional[str]:
    """
    Extract token from Authorization header or cookie.
    Priority: Header > Cookie
    """
    # First try header (from OAuth2PasswordBearer)
    if header_token:
        return header_token

    # Then try cookie
    cookie_token = request.cookies.get(COOKIE_NAME)
    if cookie_token:
        return cookie_token

    return None


def _get_cached_user(email: str, session: Session) -> Optional[User]:
    """Get user from cache or database."""
    with _user_cache_lock:
        cached = _user_cache.get(email)
        if cached is not None:
            return cached

    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        with _user_cache_lock:
            _user_cache[email] = user

    return user


def get_current_user(
    request: Request, header_token: Optional[str] = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    """
    Get current user from JWT token (header or cookie).
    Only accepts access tokens, not refresh tokens.
    Uses a 30-second cache to reduce DB lookups.
    """
    token = get_token_from_request(request, header_token)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if not payload:
        raise credentials_exception

    # Only accept access tokens (not refresh tokens)
    token_type = payload.get("type")
    if token_type and token_type != "access":
        raise credentials_exception

    email = payload.get("sub")
    if email is None or not isinstance(email, str):
        raise credentials_exception

    # Use cached user lookup (30s TTL)
    user = _get_cached_user(email, session)
    if user is None:
        raise credentials_exception
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is disabled",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


def get_current_user_optional(
    request: Request, header_token: Optional[str] = Depends(oauth2_scheme), session: Session = Depends(get_session)
) -> Optional[User]:
    """
    Get current user if authenticated, otherwise return None.
    Useful for endpoints that work for both authenticated and anonymous users.
    Uses cached user lookup for performance.
    """
    token = get_token_from_request(request, header_token)

    if not token:
        return None

    payload = decode_token(token)
    if not payload:
        return None

    # Only accept access tokens
    token_type = payload.get("type")
    if token_type and token_type != "access":
        return None

    email = payload.get("sub")
    if email is None or not isinstance(email, str):
        return None

    # Use cached user lookup (30s TTL)
    return _get_cached_user(email, session)


def get_current_superuser(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Get current user and verify they are a superuser.
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


# ============== API KEY AUTHENTICATION ==============


def validate_api_key(
    request: Request,
    api_key: Optional[str] = Depends(api_key_header),
    session: Session = Depends(get_session),
) -> Optional[Tuple[APIKey, User]]:
    """
    Validate API key from X-API-Key header.
    Returns (api_key, user) tuple or None if no key provided.
    """
    if not api_key:
        return None

    # Hash the key for lookup
    key_hash = APIKey.hash_key(api_key)

    # Find the API key
    db_key = session.exec(select(APIKey).where(APIKey.key_hash == key_hash)).first()

    if not db_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    # Check if key is active
    if not db_key.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key is disabled",
        )

    # Check if key is expired
    if db_key.expires_at and db_key.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
        )

    # Auto-reset daily counter at midnight UTC
    now = datetime.now(timezone.utc)
    today = now.date()
    if db_key.last_reset_date is None or db_key.last_reset_date.date() < today:
        db_key.requests_today = 0
        db_key.last_reset_date = now
        session.add(db_key)
        session.flush()  # Persist reset before rate limit check

    # Check rate limits
    allowed, reason = api_key_limiter.check_limit(
        key_hash,
        per_minute=db_key.rate_limit_per_minute,
        per_day=db_key.rate_limit_per_day,
    )

    if not allowed:
        if reason == "daily_limit":
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Daily API limit exceeded. Limit resets at midnight UTC.",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please slow down.",
                headers={"Retry-After": "60"},
            )

    # Record the request
    api_key_limiter.record_request(key_hash)

    # Update usage stats
    db_key.requests_today += 1
    db_key.requests_total += 1
    db_key.last_used_at = datetime.now(timezone.utc)
    session.add(db_key)
    session.commit()

    # Get the user
    user = session.get(User, db_key.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key owner account is inactive",
        )

    return db_key, user


def require_api_key(
    api_key_data: Optional[Tuple[APIKey, User]] = Depends(validate_api_key),
) -> Tuple[APIKey, User]:
    """
    Require a valid API key. Raises 401 if not provided.
    Use this dependency for endpoints that REQUIRE API key access.
    """
    if not api_key_data:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required. Get your key at /api/v1/users/api-keys",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key_data


# ============== PROTECTED DATA ACCESS ==============


def get_data_access(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
    api_key_data: Optional[Tuple[APIKey, User]] = Depends(validate_api_key),
    session: Session = Depends(get_session),
) -> User:
    """
    Require either JWT authentication OR API key for data access.
    This is the dependency for protected data endpoints.

    Priority: API Key > JWT Cookie > JWT Header
    """
    # Try API key first (programmatic access)
    if api_key_data:
        return api_key_data[1]  # Return the user

    # Try JWT (browser/app access)
    token = get_token_from_request(request, header_token)

    if token:
        payload = decode_token(token)
        if payload:
            # Only accept access tokens
            token_type = payload.get("type")
            if not token_type or token_type == "access":
                email = payload.get("sub")
                if email and isinstance(email, str):
                    user = session.exec(select(User).where(User.email == email)).first()
                    if user and user.is_active:
                        return user

    # No valid auth found
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required. Please log in or provide an API key.",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_data_access_optional(
    request: Request,
    header_token: Optional[str] = Depends(oauth2_scheme),
    api_key_data: Optional[Tuple[APIKey, User]] = Depends(validate_api_key),
    session: Session = Depends(get_session),
) -> Optional[User]:
    """
    Optional data access - returns user if authenticated, None otherwise.
    Use this for endpoints that have different behavior for auth vs anon users.
    """
    # Try API key first
    if api_key_data:
        return api_key_data[1]

    # Try JWT
    token = get_token_from_request(request, header_token)

    if token:
        payload = decode_token(token)
        if payload:
            # Only accept access tokens
            token_type = payload.get("type")
            if not token_type or token_type == "access":
                email = payload.get("sub")
                if email and isinstance(email, str):
                    user = session.exec(select(User).where(User.email == email)).first()
                    if user and user.is_active:
                        return user

    return None
