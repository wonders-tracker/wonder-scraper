from datetime import timedelta
from typing import Any
import httpx
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.api import deps
from app.core import security
from app.core.config import settings
from app.core.jwt import create_access_token
from app.core.rate_limit import rate_limiter, get_client_ip
from app.db import get_session
from app.models.user import User
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

@router.post("/login", response_model=Token)
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

    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return {
        "access_token": create_access_token(user.email, expires_delta=access_token_expires),
        "token_type": "bearer",
    }

@router.post("/register", response_model=UserResponse)
def register_user(
    request: Request,
    user_in: UserCreate,
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
                 # Link account
                 user.discord_id = discord_id
                 user.discord_handle = handle
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
                discord_handle=handle
            )
            session.add(user)
            session.commit()
            session.refresh(user)

        # Create JWT
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        token = create_access_token(user.email, expires_delta=access_token_expires)
        
        # Redirect to Frontend
        # Using configured frontend URL
        frontend_url = f"{settings.FRONTEND_URL}/auth/callback"
        return RedirectResponse(f"{frontend_url}?token={token}")
