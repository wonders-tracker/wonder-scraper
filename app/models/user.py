from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str
    is_active: bool = Field(default=True)
    is_superuser: bool = Field(default=False)
    has_api_access: bool = Field(default=False)  # Must be granted by admin
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Profile Fields
    username: Optional[str] = Field(default=None, nullable=True)
    discord_handle: Optional[str] = Field(default=None, nullable=True)
    discord_id: Optional[str] = Field(default=None, nullable=True, sa_column_kwargs={"unique": True})
    bio: Optional[str] = Field(default=None, nullable=True)

    # Password Reset
    password_reset_token: Optional[str] = Field(default=None, nullable=True, index=True)
    password_reset_expires: Optional[datetime] = Field(default=None, nullable=True)
