from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime
import re


def generate_slug(name: str) -> str:
    """Generate URL-friendly slug from card name."""
    # Convert to lowercase
    slug = name.lower()
    # Replace special characters with hyphens
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    # Remove leading/trailing hyphens
    slug = slug.strip("-")
    # Replace multiple hyphens with single
    slug = re.sub(r"-+", "-", slug)
    return slug


class Rarity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)


class Card(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    slug: Optional[str] = Field(default=None, index=True, unique=True)
    rarity_id: Optional[int] = Field(default=None, foreign_key="rarity.id")

    # Metadata
    set_name: str = Field(default="Wonders of the First", index=True)
    product_type: str = Field(default="Single")  # Single, Box, Pack, Bundle, Lot
    created_at: datetime = Field(default_factory=datetime.utcnow)
