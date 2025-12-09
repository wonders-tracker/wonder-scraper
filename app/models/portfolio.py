from typing import Optional
from enum import Enum
from sqlmodel import Field, SQLModel, Index
from datetime import datetime, date


class PurchaseSource(str, Enum):
    """Where the card was purchased from."""

    EBAY = "eBay"
    BLOKPAX = "Blokpax"
    TCGPLAYER = "TCGPlayer"
    LGS = "LGS"  # Local Game Store
    TRADE = "Trade"
    PACK_PULL = "Pack Pull"
    OTHER = "Other"


class PortfolioCard(SQLModel, table=True):
    """
    Individual card tracking in user's portfolio.
    Each row represents ONE physical card with its specific details.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)

    # Card-specific details
    treatment: str = Field(default="Classic Paper", index=True)
    source: str = Field(default="Other", index=True)  # Where purchased
    purchase_price: float = Field(default=0.0)
    purchase_date: Optional[date] = Field(default=None, index=True)
    grading: Optional[str] = Field(default=None)  # e.g., "PSA 10", "BGS 9.5", null for raw
    notes: Optional[str] = Field(default=None)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    deleted_at: Optional[datetime] = Field(default=None, index=True)  # Soft delete

    __table_args__ = (
        Index("ix_portfoliocard_user_card", "user_id", "card_id"),
        Index("ix_portfoliocard_user_treatment", "user_id", "treatment"),
        Index("ix_portfoliocard_user_source", "user_id", "source"),
    )


# Legacy model - keep for backwards compatibility
class PortfolioItem(SQLModel, table=True):
    """
    Legacy quantity-based portfolio tracking.
    @deprecated: Use PortfolioCard for new implementations.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)

    quantity: int = Field(default=1)
    purchase_price: float = Field(default=0.0)
    acquired_at: datetime = Field(default_factory=datetime.utcnow)
