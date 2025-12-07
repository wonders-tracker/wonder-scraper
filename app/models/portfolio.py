from typing import Optional
from enum import Enum
from sqlmodel import Field, SQLModel
from sqlalchemy import Index
from datetime import datetime, date
from decimal import Decimal


class PurchaseSource(str, Enum):
    """Where the card was purchased from."""
    EBAY = "eBay"
    BLOKPAX = "Blokpax"
    TCGPLAYER = "TCGPlayer"
    LGS = "LGS"  # Local Game Store
    TRADE = "Trade"
    PACK_PULL = "Pack Pull"
    OTHER = "Other"


class PortfolioItem(SQLModel, table=True):
    """Legacy quantity-based portfolio model. Deprecated - use PortfolioCard instead."""
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)

    quantity: int = Field(default=1)
    purchase_price: float = Field(default=0.0)
    acquired_at: datetime = Field(default_factory=datetime.utcnow)


class PortfolioCard(SQLModel, table=True):
    """
    Individual card tracking in user's portfolio.
    Each row represents a single physical card with its specific attributes.
    """
    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)

    # Card-specific attributes
    treatment: str = Field(default="Classic Paper", index=True)  # Paper, Foil, Formless, Serialized, etc.
    source: str = Field(default="Other", index=True)  # Where purchased: eBay, Blokpax, TCGPlayer, LGS, Trade, Pack Pull, Other

    # Purchase details
    purchase_price: float = Field(default=0.0)  # Price paid per card
    purchase_date: Optional[date] = Field(default=None, index=True)  # When purchased

    # Grading (optional)
    grading: Optional[str] = Field(default=None)  # e.g., "PSA 10", "BGS 9.5", "CGC 9", or null for raw

    # Metadata
    notes: Optional[str] = Field(default=None)  # User notes about this card
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Soft delete support
    deleted_at: Optional[datetime] = Field(default=None, index=True)

    # Composite indexes for common queries
    __table_args__ = (
        Index('ix_portfoliocard_user_card', 'user_id', 'card_id'),
        Index('ix_portfoliocard_user_treatment', 'user_id', 'treatment'),
        Index('ix_portfoliocard_user_source', 'user_id', 'source'),
    )

