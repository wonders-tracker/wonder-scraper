from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class Rarity(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)

class Card(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    rarity_id: Optional[int] = Field(default=None, foreign_key="rarity.id")
    
    # Metadata
    set_name: str = Field(default="Wonders of the First", index=True)
    product_type: str = Field(default="Single") # Single, Box, Pack, Lot
    created_at: datetime = Field(default_factory=datetime.utcnow)

