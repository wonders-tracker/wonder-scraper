"""
Blokpax-specific database models for tracking NFT assets, listings, and sales.
"""

from typing import Optional, List
from sqlmodel import Field, SQLModel, JSON, Column
from datetime import datetime


class BlokpaxStorefront(SQLModel, table=True):
    """
    Represents a Blokpax storefront/collection.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    slug: str = Field(index=True, unique=True)
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    network_id: int = Field(default=1)  # 1 = Ethereum, 137 = Polygon
    contract_address: Optional[str] = None

    # Stats (updated periodically)
    floor_price_bpx: Optional[float] = None
    floor_price_usd: Optional[float] = None
    total_tokens: int = Field(default=0)
    listed_count: int = Field(default=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BlokpaxAssetDB(SQLModel, table=True):
    """
    Represents an individual NFT asset on Blokpax.
    Links to our Card model for WOTF items.
    """

    __tablename__ = "blokpax_asset"

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, unique=True)  # Blokpax asset ID
    storefront_slug: str = Field(index=True)
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None

    # On-chain data
    network_id: int = Field(default=1)
    contract_address: str
    token_id: str

    # Ownership
    owner_count: int = Field(default=0)
    token_count: int = Field(default=1)

    # Traits stored as JSON
    traits: Optional[List] = Field(default=None, sa_column=Column(JSON))

    # Current floor listing
    floor_price_bpx: Optional[float] = None
    floor_price_usd: Optional[float] = None

    # Link to our Card model (if this is a WOTF item we track)
    card_id: Optional[int] = Field(default=None, foreign_key="card.id", index=True)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BlokpaxListing(SQLModel, table=True):
    """
    Represents an active listing on Blokpax.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, unique=True)  # Blokpax listing ID
    asset_id: str = Field(index=True)  # Blokpax asset ID

    price_bpx: float
    price_usd: float
    quantity: int = Field(default=1)

    seller_address: str = Field(index=True)
    status: str = Field(default="active")  # 'active', 'filled', 'cancelled'

    created_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class BlokpaxOffer(SQLModel, table=True):
    """
    Represents an offer on a Blokpax asset.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    external_id: str = Field(index=True, unique=True)  # Blokpax offer ID
    asset_id: str = Field(index=True)  # Blokpax asset ID

    price_bpx: float
    price_usd: float
    quantity: int = Field(default=1)

    buyer_address: str = Field(index=True)
    status: str = Field(default="open")  # 'open', 'filled', 'cancelled'

    created_at: Optional[datetime] = None
    scraped_at: datetime = Field(default_factory=datetime.utcnow)


class BlokpaxSale(SQLModel, table=True):
    """
    Represents a completed sale on Blokpax.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    listing_id: str = Field(index=True)  # Original listing ID
    asset_id: str = Field(index=True)
    asset_name: str

    price_bpx: float
    price_usd: float
    quantity: int = Field(default=1)

    seller_address: str
    buyer_address: str

    filled_at: datetime = Field(index=True)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)

    # Link to our Card model (if this is a WOTF item we track)
    card_id: Optional[int] = Field(default=None, foreign_key="card.id", index=True)


class BlokpaxSnapshot(SQLModel, table=True):
    """
    Point-in-time snapshot of storefront stats (like MarketSnapshot for eBay).
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    storefront_slug: str = Field(index=True)

    floor_price_bpx: Optional[float] = None
    floor_price_usd: Optional[float] = None
    bpx_price_usd: float  # BPX/USD rate at time of snapshot

    listed_count: int = Field(default=0)
    total_tokens: int = Field(default=0)

    # Sales volume in last 24h (optional, requires activity tracking)
    volume_24h_bpx: Optional[float] = None
    volume_24h_usd: Optional[float] = None
    sales_24h: int = Field(default=0)

    # Redemption tracking (for collector boxes)
    total_redeemed: int = Field(default=0)
    max_supply: int = Field(default=0)

    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BlokpaxRedemption(SQLModel, table=True):
    """
    Tracks individual redemption events from Blokpax activity feed.
    """

    id: Optional[int] = Field(default=None, primary_key=True)
    storefront_slug: str = Field(index=True)
    asset_id: str = Field(index=True)
    asset_name: str
    box_art: Optional[str] = None  # e.g. "Dragon", "First Form: Solfera"
    serial_number: Optional[str] = None  # e.g. "929/2699"
    redeemed_at: datetime = Field(index=True)
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
