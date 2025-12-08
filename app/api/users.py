from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from pydantic import BaseModel
from datetime import datetime

from app.api import deps
from app.db import get_session
from app.models.user import User
from app.models.api_key import APIKey
from app.schemas import UserOut, UserUpdate

router = APIRouter()

@router.get("/me", response_model=UserOut)
def read_user_me(
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Get current user profile.
    """
    return UserOut.model_validate(current_user)

@router.put("/me", response_model=UserOut)
def update_user_me(
    user_in: UserUpdate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Update current user profile.
    """
    user_data = user_in.model_dump(exclude_unset=True)
    for key, value in user_data.items():
        setattr(current_user, key, value)

    session.add(current_user)
    session.commit()
    session.refresh(current_user)
    return UserOut.model_validate(current_user)


# ============== API KEY MANAGEMENT ==============

class APIKeyCreate(BaseModel):
    name: str = "Default"


class APIKeyOut(BaseModel):
    id: int
    key_prefix: str
    name: str
    is_active: bool
    rate_limit_per_minute: int
    rate_limit_per_day: int
    requests_today: int
    requests_total: int
    last_used_at: Optional[datetime]
    created_at: datetime
    expires_at: Optional[datetime]

    model_config = {"from_attributes": True}


class APIKeyCreated(APIKeyOut):
    """Response when creating a new API key - includes the actual key (shown only once)."""
    key: str  # The actual API key - only shown on creation!


@router.get("/api-keys", response_model=List[APIKeyOut])
def list_api_keys(
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    List all API keys for the current user.
    Note: The actual key values are NOT returned - only the prefix for identification.
    """
    keys = session.exec(
        select(APIKey).where(APIKey.user_id == current_user.id)
    ).all()
    return [APIKeyOut.model_validate(k) for k in keys]


@router.post("/api-keys", response_model=APIKeyCreated)
def create_api_key(
    key_in: APIKeyCreate,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Create a new API key.

    IMPORTANT: The key is only shown ONCE in this response. Store it securely!
    If you lose it, you'll need to create a new one.

    Usage:
    - Include the key in requests as: `X-API-Key: wt_your_key_here`
    - Rate limits: 60 requests/minute, 10,000 requests/day
    """
    # Check if user has API access (superusers always have access)
    if not current_user.is_superuser and not current_user.has_api_access:
        raise HTTPException(
            status_code=403,
            detail="API access not granted. Please request access from the API page."
        )

    # Limit to 5 keys per user
    existing_count = len(session.exec(
        select(APIKey).where(APIKey.user_id == current_user.id)
    ).all())

    if existing_count >= 5:
        raise HTTPException(
            status_code=400,
            detail="Maximum of 5 API keys per user. Delete an existing key first."
        )

    # Generate the key
    raw_key = APIKey.generate_key()

    # Create the DB record
    db_key = APIKey(
        user_id=current_user.id,
        key_hash=APIKey.hash_key(raw_key),
        key_prefix=APIKey.get_prefix(raw_key),
        name=key_in.name,
        is_active=True,
        rate_limit_per_minute=60,
        rate_limit_per_day=10000,
    )

    session.add(db_key)
    session.commit()
    session.refresh(db_key)

    # Return with the actual key (only time it's shown!)
    response = APIKeyCreated.model_validate(db_key)
    response.key = raw_key
    return response


@router.delete("/api-keys/{key_id}")
def delete_api_key(
    key_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Delete an API key.
    """
    db_key = session.get(APIKey, key_id)

    if not db_key:
        raise HTTPException(status_code=404, detail="API key not found")

    if db_key.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your API key")

    session.delete(db_key)
    session.commit()

    return {"message": "API key deleted", "key_prefix": db_key.key_prefix}


@router.put("/api-keys/{key_id}/toggle")
def toggle_api_key(
    key_id: int,
    session: Session = Depends(get_session),
    current_user: User = Depends(deps.get_current_user),
) -> Any:
    """
    Enable or disable an API key.
    """
    db_key = session.get(APIKey, key_id)

    if not db_key:
        raise HTTPException(status_code=404, detail="API key not found")

    if db_key.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not your API key")

    db_key.is_active = not db_key.is_active
    session.add(db_key)
    session.commit()
    session.refresh(db_key)

    status = "enabled" if db_key.is_active else "disabled"
    return {"message": f"API key {status}", "is_active": db_key.is_active}


# ============== API ACCESS REQUEST ==============

class APIAccessRequest(BaseModel):
    name: str
    email: str
    company: Optional[str] = None
    use_case: str


@router.post("/request-api-access")
def request_api_access(
    request: APIAccessRequest,
) -> Any:
    """
    Submit a request for API access.
    Sends email notification to admin.
    """
    from app.services.email import send_api_access_request_email

    # Send email to admin
    email_sent = send_api_access_request_email(
        requester_email=request.email,
        requester_name=request.name,
        use_case=request.use_case,
        company=request.company
    )

    if not email_sent:
        # Still return success to user, but log internally
        print(f"[API] Access request from {request.email} - email not configured")

    return {
        "message": "Your API access request has been submitted. We'll review it and get back to you soon.",
        "email": request.email
    }

