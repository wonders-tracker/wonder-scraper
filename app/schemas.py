from typing import List, Optional
from pydantic import BaseModel, field_validator
from datetime import datetime, date


class MarketSnapshotBase(BaseModel):
    min_price: float
    max_price: float
    avg_price: float
    volume: int
    lowest_ask: Optional[float] = None
    highest_bid: Optional[float] = None
    inventory: Optional[int] = None
    timestamp: datetime


class MarketSnapshotOut(MarketSnapshotBase):
    id: int
    card_id: int

    model_config = {"from_attributes": True}


class MarketPriceBase(BaseModel):
    price: float
    title: str
    sold_date: Optional[datetime] = None
    listing_type: str
    treatment: Optional[str] = "Classic Paper"
    bid_count: Optional[int] = 0
    url: Optional[str] = None
    image_url: Optional[str] = None
    # Seller info
    seller_name: Optional[str] = None
    seller_feedback_score: Optional[int] = None
    seller_feedback_percent: Optional[float] = None
    # Listing details
    condition: Optional[str] = None
    shipping_cost: Optional[float] = None
    # Product classification (for boxes/packs/lots)
    product_subtype: Optional[str] = None
    quantity: int = 1
    scraped_at: datetime


class MarketPriceOut(MarketPriceBase):
    id: int
    card_id: int

    model_config = {"from_attributes": True}


class CardBase(BaseModel):
    name: str
    set_name: str
    rarity_id: int


class CardOut(CardBase):
    id: int
    slug: Optional[str] = None  # URL-friendly slug for SEO
    rarity_name: Optional[str] = None
    product_type: Optional[str] = None  # Single, Box, Pack, Bundle, Proof, Lot

    # === PRICES (clear hierarchy) ===
    floor_price: Optional[float] = None  # Avg of 4 lowest sales - THE standard price (cheapest variant)
    floor_by_variant: Optional[dict] = None  # Floor price per variant {variant_name: price}
    vwap: Optional[float] = None  # Volume Weighted Avg Price = SUM(price)/COUNT
    latest_price: Optional[float] = None  # Most recent sale price
    lowest_ask: Optional[float] = None  # Cheapest active listing (cheapest variant)
    lowest_ask_by_variant: Optional[dict] = None  # Lowest ask per variant {variant_name: price}
    max_price: Optional[float] = None  # Highest confirmed sale
    avg_price: Optional[float] = None  # Simple average (from snapshot)
    fair_market_price: Optional[float] = None  # FMP from formula (detail page only)

    # === VOLUME & INVENTORY ===
    volume: Optional[int] = None  # Sales count for selected time period
    inventory: Optional[int] = None  # Active listings count

    # === DELTAS (% changes) ===
    price_delta: Optional[float] = None  # Last sale vs rolling avg (%)
    floor_delta: Optional[float] = None  # Last sale vs floor price (%)

    # === METADATA ===
    last_treatment: Optional[str] = None  # Treatment of last sale (e.g., "Classic Foil")
    last_updated: Optional[datetime] = None  # When market data was last scraped
    image_url: Optional[str] = None  # Card thumbnail URL from blob storage

    # === CARDE.IO DATA ===
    card_type: Optional[str] = None  # Wonder, Item, Spell, Land, Token, Tracker
    orbital: Optional[str] = None  # Heliosynth, Thalwind, Petraia, Solfera, Boundless, Umbrathene
    orbital_color: Optional[str] = None  # Hex color e.g., #a07836
    card_number: Optional[str] = None  # e.g., "143" from Existence_143
    cardeio_image_url: Optional[str] = None  # Official high-res card image

    # === DEPRECATED (keep for backwards compat, remove later) ===
    volume_30d: Optional[int] = None  # @deprecated: use 'volume'
    price_delta_24h: Optional[float] = None  # @deprecated: use 'price_delta'
    last_sale_diff: Optional[float] = None  # @deprecated: use 'floor_delta'
    last_sale_treatment: Optional[str] = None  # @deprecated: use 'last_treatment'

    model_config = {"from_attributes": True}


class CardListItem(BaseModel):
    """Lightweight card for list views - ~50% smaller payload than CardOut"""

    id: int
    name: str
    slug: Optional[str] = None
    set_name: Optional[str] = None
    rarity_name: Optional[str] = None
    product_type: Optional[str] = None
    # Core prices
    floor_price: Optional[float] = None
    latest_price: Optional[float] = None
    lowest_ask: Optional[float] = None
    max_price: Optional[float] = None  # Highest sale (HIGH column)
    # Volume & delta
    volume: Optional[int] = None
    inventory: Optional[int] = None
    price_delta: Optional[float] = None
    # Treatment for display
    last_treatment: Optional[str] = None
    # Image
    image_url: Optional[str] = None  # Card thumbnail URL
    # Carde.io data
    orbital: Optional[str] = None  # Heliosynth, Thalwind, etc.
    orbital_color: Optional[str] = None  # Hex color

    model_config = {"from_attributes": True}


class CardWithMarket(CardOut):
    market_snapshot: Optional[MarketSnapshotOut] = None


# User Schemas
class UserBase(BaseModel):
    email: str


class UserCreate(UserBase):
    password: str


class UserOut(UserBase):
    id: int
    is_active: bool
    is_superuser: bool
    has_api_access: bool = False
    created_at: datetime
    username: Optional[str] = None
    discord_handle: Optional[str] = None
    bio: Optional[str] = None
    onboarding_completed: bool = False
    # Subscription fields
    subscription_tier: str = "free"
    subscription_status: Optional[str] = None
    subscription_current_period_end: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    username: Optional[str] = None
    discord_handle: Optional[str] = None
    bio: Optional[str] = None

    # SECURITY: Reject any unknown fields to prevent privilege escalation
    model_config = {"extra": "forbid"}


# Portfolio Schemas (Legacy - quantity based)
class PortfolioItemBase(BaseModel):
    card_id: int
    quantity: int
    purchase_price: float
    acquired_at: Optional[datetime] = None  # Allow optional for creation, default to now in model


class PortfolioItemCreate(PortfolioItemBase):
    pass


class PortfolioItemUpdate(BaseModel):
    quantity: Optional[int] = None
    purchase_price: Optional[float] = None
    acquired_at: Optional[datetime] = None


class PortfolioItemOut(PortfolioItemBase):
    id: int
    user_id: int
    # Card details for display
    card_name: Optional[str] = None
    card_set: Optional[str] = None
    current_market_price: Optional[float] = None
    current_value: Optional[float] = None
    gain_loss: Optional[float] = None
    gain_loss_percent: Optional[float] = None

    model_config = {"from_attributes": True}


# Portfolio Card Schemas (New - individual card tracking)

# Valid purchase sources - validated on input
VALID_SOURCES = {"eBay", "Blokpax", "TCGPlayer", "LGS", "Trade", "Pack Pull", "Other"}

# Common treatments - validated loosely (other treatments allowed from market data)
COMMON_TREATMENTS = {
    "Classic Paper",
    "Classic Foil",
    "Stonefoil",
    "Full Art Paper",
    "Full Art Foil",
    "Serialized",
    "Paper",
    "Foil",
}


class PortfolioCardBase(BaseModel):
    card_id: int
    treatment: str = "Classic Paper"
    source: str = "Other"
    purchase_price: float
    purchase_date: Optional[date] = None
    grading: Optional[str] = None  # e.g., "PSA 10", "BGS 9.5", null for raw
    notes: Optional[str] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: str) -> str:
        if v not in VALID_SOURCES:
            raise ValueError(f"Invalid source. Must be one of: {', '.join(sorted(VALID_SOURCES))}")
        return v

    @field_validator("purchase_price")
    @classmethod
    def validate_price(cls, v: float) -> float:
        if v < 0:
            raise ValueError("Purchase price cannot be negative")
        return v


class PortfolioCardCreate(PortfolioCardBase):
    """Create a single card in portfolio.

    Use quantity > 1 to create multiple identical cards at once.
    """

    quantity: int = 1  # Number of cards to create (defaults to 1)


class PortfolioCardBatchItem(PortfolioCardBase):
    """Single item in a batch create, with optional quantity."""

    quantity: int = 1  # Number of cards to create (defaults to 1)


class PortfolioCardBatchCreate(BaseModel):
    """Create multiple cards at once (split entry)."""

    cards: List[PortfolioCardBatchItem]


class PortfolioCardUpdate(BaseModel):
    """Update an existing portfolio card."""

    treatment: Optional[str] = None
    source: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[date] = None
    grading: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("source")
    @classmethod
    def validate_source(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in VALID_SOURCES:
            raise ValueError(f"Invalid source. Must be one of: {', '.join(sorted(VALID_SOURCES))}")
        return v

    @field_validator("purchase_price")
    @classmethod
    def validate_price(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and v < 0:
            raise ValueError("Purchase price cannot be negative")
        return v


class PortfolioCardOut(PortfolioCardBase):
    """Portfolio card with computed market data."""

    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime

    # Card details for display
    card_name: Optional[str] = None
    card_set: Optional[str] = None
    card_slug: Optional[str] = None
    rarity_name: Optional[str] = None
    product_type: Optional[str] = None

    # Market data (treatment-specific)
    market_price: Optional[float] = None  # Current market price for this treatment
    profit_loss: Optional[float] = None  # market_price - purchase_price
    profit_loss_percent: Optional[float] = None  # (market_price / purchase_price - 1) * 100

    model_config = {"from_attributes": True}


class PortfolioSummary(BaseModel):
    """Summary of user's portfolio."""

    total_cards: int
    total_cost_basis: float
    total_market_value: float
    total_profit_loss: float
    total_profit_loss_percent: float

    # Breakdown by treatment
    by_treatment: Optional[dict] = None
    # Breakdown by source
    by_source: Optional[dict] = None


# Meta Vote Schemas
class MetaVoteSummary(BaseModel):
    """Vote counts for a card's meta status."""

    yes: int = 0
    no: int = 0
    unsure: int = 0
    total: int = 0


class MetaVoteCreate(BaseModel):
    """Create or update a meta vote."""

    vote: str  # 'yes', 'no', 'unsure'


class MetaVoteResponse(BaseModel):
    """Full meta vote response with summary and user's vote."""

    summary: MetaVoteSummary
    user_vote: Optional[str] = None  # User's current vote, null if not voted
    consensus: Optional[str] = None  # Highest vote category, null if tie/no votes
