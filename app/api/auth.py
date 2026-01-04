"""
Authentication endpoints with refresh token rotation.

Security features:
- Short-lived access tokens (15 min) in response body
- Long-lived refresh tokens (7 days) in httpOnly cookie only
- Refresh token rotation on each use
- Hashed reset tokens
- Discord OAuth with transaction handling
- CSRF protection via SameSite cookies
"""

from datetime import timedelta, datetime, timezone
from typing import Any
import httpx
import secrets
import hashlib

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.jwt import create_access_token, create_refresh_token, decode_token, hash_token_jti
from app.core.rate_limit import rate_limiter, get_client_ip
from app.db import get_session
from app.models.user import User
from app.services.email import send_welcome_email, send_password_reset_email
from pydantic import BaseModel, EmailStr, field_validator

router = APIRouter()


class Token(BaseModel):
    access_token: str
    token_type: str
    expires_in: int  # seconds until expiry


class UserCreate(BaseModel):
    email: EmailStr  # Validates email format
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        """Normalize email to lowercase."""
        return v.lower().strip()


class UserResponse(BaseModel):
    id: int
    email: str
    is_active: bool


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class MessageResponse(BaseModel):
    message: str


# Cookie settings
ACCESS_COOKIE_NAME = "access_token"  # Short-lived, for backwards compat
REFRESH_COOKIE_NAME = "refresh_token"  # Long-lived, httpOnly
COOKIE_SECURE = settings.COOKIE_SECURE
COOKIE_SAMESITE = "lax"


def _hash_token(token: str) -> str:
    """Hash a token for secure storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def set_auth_cookies(response: Response, access_token: str, refresh_token: str):
    """Set both access and refresh token cookies."""
    # Access token cookie (short-lived, 15 min)
    response.set_cookie(
        key=ACCESS_COOKIE_NAME,
        value=access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )
    # Refresh token cookie (long-lived, 7 days)
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/api/v1/auth",  # Only sent to auth endpoints
    )


def clear_auth_cookies(response: Response):
    """Clear all auth cookies."""
    response.delete_cookie(key=ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=REFRESH_COOKIE_NAME, path="/api/v1/auth")


def _create_token_response(user: User, session: Session) -> JSONResponse:
    """Create tokens and return JSON response with cookies set."""
    # Create access token
    access_token = create_access_token(user.email)

    # Create refresh token and store hash
    refresh_token, refresh_hash = create_refresh_token(user.email)
    user.refresh_token_hash = refresh_hash
    session.add(user)
    session.commit()

    # Build response
    response = JSONResponse(
        content={
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        }
    )
    set_auth_cookies(response, access_token, refresh_token)
    return response


@router.post("/login")
def login_access_token(
    request: Request, form_data: OAuth2PasswordRequestForm = Depends(), session: Session = Depends(get_session)
) -> Any:
    """Login with email/password, returns access token and sets refresh cookie."""
    # Rate limiting: 5 attempts per minute, lockout after 5 failures
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=5, window_seconds=60)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)},
        )

    rate_limiter.record_request(ip)

    user = session.exec(select(User).where(User.email == form_data.username)).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        # Record failed attempt for account lockout
        is_locked, remaining = rate_limiter.record_failed_login(ip)
        if is_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked due to too many failed attempts. Try again in {remaining} seconds.",
                headers={"Retry-After": str(remaining)},
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Incorrect email or password",
        )

    if not user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")

    # Clear failed attempts on successful login
    rate_limiter.record_successful_login(ip)

    # Update last login timestamp
    user.last_login = datetime.now(timezone.utc)

    return _create_token_response(user, session)


@router.post("/refresh")
def refresh_access_token(request: Request, session: Session = Depends(get_session)) -> Any:
    """
    Refresh the access token using the refresh token cookie.
    Implements token rotation - issues new refresh token on each use.
    """
    # Rate limiting: 30 refresh attempts per minute per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=30, window_seconds=60)
    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many refresh attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )
    rate_limiter.record_request(ip)

    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
        )

    # Decode and validate refresh token
    payload = decode_token(refresh_token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    email = payload.get("sub")
    jti = payload.get("jti")

    if not email or not jti:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Find user with row lock to prevent race conditions
    user = session.exec(select(User).where(User.email == email).with_for_update()).first()
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    # Verify the refresh token matches stored hash (rotation check)
    token_hash = hash_token_jti(jti)
    if user.refresh_token_hash != token_hash:
        # Token doesn't match - possible token reuse attack
        # Invalidate all tokens for this user
        user.refresh_token_hash = None
        session.add(user)
        session.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has been revoked",
        )

    # Token is valid - issue new tokens (rotation)
    return _create_token_response(user, session)


@router.post("/logout")
def logout(request: Request, response: Response, session: Session = Depends(get_session)):
    """Clear auth cookies and invalidate refresh token."""
    resp = JSONResponse(content={"message": "Logged out successfully"})
    clear_auth_cookies(resp)

    # Try to invalidate refresh token in DB
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        payload = decode_token(refresh_token)
        if payload:
            email = payload.get("sub")
            if email:
                user = session.exec(select(User).where(User.email == email)).first()
                if user:
                    user.refresh_token_hash = None
                    session.add(user)
                    session.commit()

    return resp


@router.get("/me")
def get_current_user_info(
    request: Request,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """Get current user info from token (header or cookie)."""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "discord_handle": current_user.discord_handle,
        "is_active": current_user.is_active,
        "is_superuser": current_user.is_superuser,
        "onboarding_completed": current_user.onboarding_completed,
        "subscription_tier": current_user.subscription_tier,
        "is_pro": current_user.is_pro,
    }


@router.post("/register", response_model=UserResponse)
def register_user(
    request: Request, user_in: UserCreate, background_tasks: BackgroundTasks, session: Session = Depends(get_session)
) -> Any:
    # Rate limiting: 3 registrations per hour per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=3, window_seconds=3600)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    rate_limiter.record_request(ip)

    user = session.exec(select(User).where(User.email == user_in.email)).first()
    if user:
        raise HTTPException(
            status_code=400,
            detail="The user with this email already exists in the system.",
        )

    # Password validation
    if len(user_in.password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )

    new_user = User(
        email=user_in.email,
        hashed_password=security.get_password_hash(user_in.password),
        is_active=True,
        is_superuser=False,
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # Send welcome email in background
    background_tasks.add_task(send_welcome_email, new_user.email)

    return new_user


@router.get("/discord/login")
def login_discord():
    """Redirects the user to the Discord OAuth2 authorization page."""
    return {
        "url": f"https://discord.com/oauth2/authorize?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_REDIRECT_URI}&response_type=code&scope=identify%20email"
    }


@router.get("/discord/callback")
async def callback_discord(code: str, session: Session = Depends(get_session)):
    """
    Callback endpoint for Discord OAuth2.
    Exchanges code for token, gets user info, creates/logs in user.
    Uses transaction handling to prevent race conditions.
    """
    async with httpx.AsyncClient() as client:
        # Exchange code for token
        data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.DISCORD_REDIRECT_URI,
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}

        try:
            r = await client.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
            r.raise_for_status()
            token_data = r.json()
            discord_access_token = token_data["access_token"]
        except httpx.HTTPStatusError as e:
            raise HTTPException(status_code=400, detail=f"Failed to authenticate with Discord: {e.response.text}")

        # Get User Info
        headers = {"Authorization": f"Bearer {discord_access_token}"}
        try:
            r = await client.get("https://discord.com/api/users/@me", headers=headers)
            r.raise_for_status()
            discord_user = r.json()
        except httpx.HTTPStatusError:
            raise HTTPException(status_code=400, detail="Failed to fetch Discord user info")

        discord_id = discord_user["id"]
        email = discord_user.get("email")
        username = discord_user.get("username")
        discriminator = discord_user.get("discriminator")
        handle = f"{username}#{discriminator}" if discriminator and discriminator != "0" else username

        # Find or Create User with proper transaction handling
        # Use SELECT FOR UPDATE to prevent race conditions
        user = session.exec(select(User).where(User.discord_id == discord_id).with_for_update()).first()

        if not user and email:
            # Check by email with lock
            user = session.exec(select(User).where(User.email == email).with_for_update()).first()
            if user:
                # Link Discord account to existing user
                user.discord_id = discord_id
                user.discord_handle = handle
                user.last_login = datetime.now(timezone.utc)

        if not user:
            # Create new user
            random_pw = secrets.token_urlsafe(32)
            user = User(
                email=email or f"{discord_id}@discord.placeholder",
                hashed_password=security.get_password_hash(random_pw),
                is_active=True,
                discord_id=discord_id,
                discord_handle=handle,
                last_login=datetime.now(timezone.utc),
            )
            session.add(user)
        else:
            # Update last login for existing user
            user.last_login = datetime.now(timezone.utc)
            session.add(user)

        # Create tokens
        access_token = create_access_token(user.email)
        refresh_token, refresh_hash = create_refresh_token(user.email)
        user.refresh_token_hash = refresh_hash
        session.commit()
        session.refresh(user)

        # Redirect to Frontend with cookies only (no token in URL)
        frontend_url = f"{settings.FRONTEND_URL}/auth/callback"
        response = RedirectResponse(frontend_url)
        set_auth_cookies(response, access_token, refresh_token)
        return response


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session),
) -> Any:
    """
    Send password reset email.
    Always returns success to prevent email enumeration.
    Token is hashed before storage.
    """
    # Rate limiting: 5 requests per hour per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=5, window_seconds=3600)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    rate_limiter.record_request(ip)

    user = session.exec(select(User).where(User.email == body.email)).first()

    if user:
        # Generate secure token and hash it for storage
        reset_token = secrets.token_urlsafe(32)
        user.password_reset_token_hash = _hash_token(reset_token)
        user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
        session.add(user)
        session.commit()

        # Send email with the raw token (not hash) in background
        background_tasks.add_task(send_password_reset_email, user.email, reset_token)

    # Always return success to prevent email enumeration
    return {"message": "If an account exists with this email, you will receive a password reset link."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(request: Request, body: ResetPasswordRequest, session: Session = Depends(get_session)) -> Any:
    """
    Reset password using token from email.
    Token is hashed for comparison.
    """
    # Rate limiting: 10 attempts per hour per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=10, window_seconds=3600)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)},
        )

    rate_limiter.record_request(ip)

    # Validate password
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )

    # Hash the provided token and find user by hash
    token_hash = _hash_token(body.token)
    user = session.exec(select(User).where(User.password_reset_token_hash == token_hash)).first()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token.",
        )

    # Check if token is expired (database stores naive UTC datetimes)
    now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
    if user.password_reset_expires and user.password_reset_expires < now_utc:
        # Clear expired token
        user.password_reset_token_hash = None
        user.password_reset_expires = None
        session.add(user)
        session.commit()
        raise HTTPException(
            status_code=400,
            detail="Reset token has expired. Please request a new one.",
        )

    # Update password and clear reset token
    user.hashed_password = security.get_password_hash(body.new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires = None
    # Also invalidate any existing refresh tokens
    user.refresh_token_hash = None
    session.add(user)
    session.commit()

    return {"message": "Password has been reset successfully. You can now log in."}
