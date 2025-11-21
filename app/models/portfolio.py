from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

class PortfolioItem(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    
    quantity: int = Field(default=1)
    purchase_price: float = Field(default=0.0)
    acquired_at: datetime = Field(default_factory=datetime.utcnow)

