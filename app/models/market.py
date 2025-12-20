from typing import Optional, List, Dict, Any
from sqlmodel import Field, SQLModel
from sqlalchemy import Index, Column
from sqlalchemy.types import JSON
from datetime import datetime, timezone

from app.core.typing import utc_now


class MarketSnapshot(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id", index=True)

    # Sold Data
    min_price: float
    max_price: float
    avg_price: float
    volume: int = Field(default=0)

    # Active Data (New)
    lowest_ask: Optional[float] = None
    highest_bid: Optional[float] = None  # eBay auctions only
    inventory: Optional[int] = None  # Count of active listings

    # Last Sale Data
    last_sale_price: Optional[float] = None
    last_sale_date: Optional[datetime] = None

    platform: str = Field(default="ebay")  # 'ebay', 'opensea'

    timestamp: datetime = Field(default_factory=utc_now, index=True)

    # Composite index for common query pattern: card_id + timestamp ORDER BY
    __table_args__ = (Index("ix_marketsnapshot_card_timestamp", "card_id", "timestamp"),)


class MarketPrice(SQLModel, table=True):
    """Individual raw price data points (optional, for detailed history)"""

    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    price: float
    title: str
    sold_date: Optional[datetime] = None
    listing_type: str = Field(default="sold")  # 'sold' or 'active'
    treatment: str = Field(default="Classic Paper")  # Classic Paper, Foil, Serialized, etc.
    bid_count: int = Field(default=0)  # Number of bids (for auctions)
    listing_format: Optional[str] = Field(default=None)  # 'auction', 'buy_it_now', 'best_offer', None if unknown
    external_id: Optional[str] = Field(default=None, index=True)  # Unique ID from source (e.g., eBay item ID)
    url: Optional[str] = Field(default=None)  # Link to the listing
    image_url: Optional[str] = Field(default=None)  # Link to listing image
    description: Optional[str] = Field(default=None)  # Short description or specifics
    platform: str = Field(default="ebay")  # 'ebay', 'opensea', 'tcgplayer', etc.

    # Product classification for boxes/packs/lots
    # Subtypes: 'Collector Booster Box', 'Play Bundle', 'Collector Pack', 'Play Pack',
    #           'Starter Set', 'Serialized Advantage', 'Case', 'Silver Pack', etc.
    product_subtype: Optional[str] = Field(default=None, index=True)

    # Quantity: Number of units in this listing (e.g., 'Lot of 4' = 4, '5ct' = 5)
    quantity: int = Field(default=1)

    # Seller Info
    seller_name: Optional[str] = Field(default=None, index=True)  # Seller username
    seller_feedback_score: Optional[int] = Field(default=None)  # Feedback count (e.g., 1234)
    seller_feedback_percent: Optional[float] = Field(default=None)  # Positive feedback % (e.g., 99.5)

    # Listing Details
    condition: Optional[str] = Field(default=None)  # "New", "Like New", "Used", etc.
    shipping_cost: Optional[float] = Field(default=None)  # Shipping price (0 = free)

    # Grading (for slabbed cards)
    # Format: "PSA 10", "BGS 9.5", "TAG 10", "CGC 9.8", null for raw
    grading: Optional[str] = Field(default=None, index=True)

    # NFT Traits (for OpenSea/Blokpax listings)
    # Format: [{"trait_type": "Hierarchy", "value": "Spell"}, {"trait_type": "Artist", "value": "Romall Smith"}, ...]
    traits: Optional[List[Dict[str, Any]]] = Field(default=None, sa_column=Column(JSON))

    scraped_at: datetime = Field(default_factory=utc_now)

    # When listing was first seen (for active->sold tracking)
    # Set once when listing first appears, preserved when it sells
    listed_at: Optional[datetime] = Field(default=None, index=True)

    # Composite indexes for FMP queries
    __table_args__ = (
        # For FMP: card_id + listing_type + sold_date queries
        Index("ix_marketprice_card_listing_sold", "card_id", "listing_type", "sold_date"),
        # For treatment queries
        Index("ix_marketprice_card_treatment", "card_id", "treatment"),
        # For listing type + sold_date range scans
        Index("ix_marketprice_listing_sold", "listing_type", "sold_date"),
    )


class ListingReport(SQLModel, table=True):
    """User-submitted reports for incorrect/fake/duplicate listings"""

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: int = Field(foreign_key="marketprice.id", index=True)
    card_id: int = Field(foreign_key="card.id", index=True)

    # Report details
    reason: str  # 'wrong_price', 'fake_listing', 'duplicate', 'wrong_card', 'other'
    notes: Optional[str] = Field(default=None)

    # Listing context (snapshot at time of report)
    listing_title: Optional[str] = Field(default=None)
    listing_price: Optional[float] = Field(default=None)
    listing_url: Optional[str] = Field(default=None)

    # Status tracking
    status: str = Field(default="pending")  # 'pending', 'reviewed', 'resolved', 'dismissed'
    resolution_notes: Optional[str] = Field(default=None)
    resolved_at: Optional[datetime] = Field(default=None)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)


class Report(SQLModel, table=True):
    """Stored CSV reports for market data exports."""

    id: Optional[int] = Field(default=None, primary_key=True)
    filename: str = Field(index=True)
    report_type: str = Field(index=True)  # 'daily', 'weekly', 'monthly'
    content: str  # CSV content stored as text
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
