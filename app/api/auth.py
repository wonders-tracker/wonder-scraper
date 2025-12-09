from datetime import timedelta, datetime
from typing import Any
import httpx
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status, BackgroundTasks
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.rate_limit import rate_limiter, get_client_ip
from app.db import get_session
from app.models.user import User
from app.services.email import send_welcome_email, send_password_reset_email
from pydantic import BaseModel

router = APIRouter()

class Token(BaseModel):
    access_token: str
    token_type: str

class UserCreate(BaseModel):
    email: str
    password: str

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
COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = 60 * 60 * 24 * 7  # 7 days
COOKIE_SECURE = True  # Set to False for local dev without HTTPS
COOKIE_SAMESITE = "lax"


def set_auth_cookie(response: Response, token: str):
    """Set httpOnly auth cookie."""
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite=COOKIE_SAMESITE,
        path="/",
    )


def clear_auth_cookie(response: Response):
    """Clear auth cookie."""
    response.delete_cookie(key=COOKIE_NAME, path="/")


@router.post("/login")
def login_access_token(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session)
) -> Any:
    # Rate limiting: 5 attempts per minute, lockout after 5 failures
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=5, window_seconds=60)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Please try again in {retry_after} seconds.",
            headers={"Retry-After": str(retry_after)}
        )

    rate_limiter.record_request(ip)

    user = session.query(User).filter(User.email == form_data.username).first()
    if not user or not security.verify_password(form_data.password, user.hashed_password):
        # Record failed attempt for account lockout
        is_locked, remaining = rate_limiter.record_failed_login(ip)
        if is_locked:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Account locked due to too many failed attempts. Try again in {remaining} seconds.",
                headers={"Retry-After": str(remaining)}
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
    user.last_login = datetime.utcnow()
    session.add(user)
    session.commit()

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    token = create_access_token(user.email, expires_delta=access_token_expires)

    # Return token AND set cookie for persistence
    response = JSONResponse(content={
        "access_token": token,
        "token_type": "bearer",
    })
    set_auth_cookie(response, token)
    return response


@router.post("/logout")
def logout(response: Response):
    """Clear auth cookie."""
    resp = JSONResponse(content={"message": "Logged out successfully"})
    clear_auth_cookie(resp)
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
    request: Request,
    user_in: UserCreate,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
) -> Any:
    # Rate limiting: 3 registrations per hour per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=3, window_seconds=3600)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )

    rate_limiter.record_request(ip)

    user = session.query(User).filter(User.email == user_in.email).first()
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
        is_superuser=False
    )
    session.add(new_user)
    session.commit()
    session.refresh(new_user)

    # Send welcome email in background
    background_tasks.add_task(send_welcome_email, new_user.email)

    return new_user

@router.get("/discord/login")
def login_discord():
    """
    Redirects the user to the Discord OAuth2 authorization page.
    """
    return {
        "url": f"https://discord.com/oauth2/authorize?client_id={settings.DISCORD_CLIENT_ID}&redirect_uri={settings.DISCORD_REDIRECT_URI}&response_type=code&scope=identify%20email"
    }

@router.get("/discord/callback")
async def callback_discord(code: str, session: Session = Depends(get_session)):
    """
    Callback endpoint for Discord OAuth2.
    Exchanges code for token, gets user info, creates/logs in user.
    """
    async with httpx.AsyncClient() as client:
        # Exchange code for token
        data = {
            "client_id": settings.DISCORD_CLIENT_ID,
            "client_secret": settings.DISCORD_CLIENT_SECRET,
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": settings.DISCORD_REDIRECT_URI
        }
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        
        try:
            r = await client.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
            r.raise_for_status()
            token_data = r.json()
            access_token = token_data["access_token"]
        except httpx.HTTPStatusError as e:
             raise HTTPException(status_code=400, detail=f"Failed to authenticate with Discord: {e.response.text}")

        # Get User Info
        headers = {"Authorization": f"Bearer {access_token}"}
        try:
            r = await client.get("https://discord.com/api/users/@me", headers=headers)
            r.raise_for_status()
            discord_user = r.json()
        except httpx.HTTPStatusError as e:
             raise HTTPException(status_code=400, detail="Failed to fetch Discord user info")
        
        discord_id = discord_user["id"]
        email = discord_user.get("email")
        username = discord_user.get("username")
        discriminator = discord_user.get("discriminator")
        handle = f"{username}#{discriminator}" if discriminator and discriminator != "0" else username

        # Find or Create User
        # Check by discord_id
        user = session.exec(select(User).where(User.discord_id == discord_id)).first()
        
        if not user and email:
             # Check by email
             user = session.exec(select(User).where(User.email == email)).first()
             if user:
                 # Link account and update last login
                 user.discord_id = discord_id
                 user.discord_handle = handle
                 user.last_login = datetime.utcnow()
                 session.add(user)
                 session.commit()
                 session.refresh(user)
        
        if not user:
            # Create new user
            random_pw = secrets.token_urlsafe(32)
            user = User(
                email=email or f"{discord_id}@discord.placeholder", # Fallback if no email
                hashed_password=security.get_password_hash(random_pw),
                is_active=True,
                discord_id=discord_id,
                discord_handle=handle,
                last_login=datetime.utcnow()
            )
            session.add(user)
            session.commit()
            session.refresh(user)
        else:
            # Update last login for existing user
            user.last_login = datetime.utcnow()
            session.add(user)
            session.commit()

        # Create JWT
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token = create_access_token(user.email, expires_delta=access_token_expires)

        # Redirect to Frontend with cookie set
        frontend_url = f"{settings.FRONTEND_URL}/auth/callback"
        response = RedirectResponse(f"{frontend_url}?token={token}")
        set_auth_cookie(response, token)
        return response


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    request: Request,
    body: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    session: Session = Depends(get_session)
) -> Any:
    """
    Send password reset email.
    Always returns success to prevent email enumeration.
    """
    # Rate limiting: 5 requests per hour per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=5, window_seconds=3600)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )

    rate_limiter.record_request(ip)

    user = session.query(User).filter(User.email == body.email).first()

    if user:
        # Generate secure token
        reset_token = secrets.token_urlsafe(32)
        user.password_reset_token = reset_token
        user.password_reset_expires = datetime.utcnow() + timedelta(hours=1)
        session.add(user)
        session.commit()

        # Send email in background
        background_tasks.add_task(send_password_reset_email, user.email, reset_token)

    # Always return success to prevent email enumeration
    return {"message": "If an account exists with this email, you will receive a password reset link."}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(
    request: Request,
    body: ResetPasswordRequest,
    session: Session = Depends(get_session)
) -> Any:
    """
    Reset password using token from email.
    """
    # Rate limiting: 10 attempts per hour per IP
    ip = get_client_ip(request)
    is_limited, retry_after = rate_limiter.is_rate_limited(ip, max_requests=10, window_seconds=3600)

    if is_limited:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many reset attempts. Please try again later.",
            headers={"Retry-After": str(retry_after)}
        )

    rate_limiter.record_request(ip)

    # Validate password
    if len(body.new_password) < 8:
        raise HTTPException(
            status_code=400,
            detail="Password must be at least 8 characters long.",
        )

    # Find user by reset token
    user = session.query(User).filter(User.password_reset_token == body.token).first()

    if not user:
        raise HTTPException(
            status_code=400,
            detail="Invalid or expired reset token.",
        )

    # Check if token is expired
    if user.password_reset_expires and user.password_reset_expires < datetime.utcnow():
        # Clear expired token
        user.password_reset_token = None
        user.password_reset_expires = None
        session.add(user)
        session.commit()
        raise HTTPException(
            status_code=400,
            detail="Reset token has expired. Please request a new one.",
        )

    # Update password
    user.hashed_password = security.get_password_hash(body.new_password)
    user.password_reset_token = None
    user.password_reset_expires = None
    session.add(user)
    session.commit()

    return {"message": "Password has been reset successfully. You can now log in."}
