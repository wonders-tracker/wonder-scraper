from typing import List, Optional
from pydantic import BaseModel
from datetime import datetime

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
    scraped_at: datetime

class MarketPriceOut(MarketPriceBase):
    id: int
    card_id: int

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
    floor_price: Optional[float] = None       # Avg of 4 lowest sales - THE standard price
    vwap: Optional[float] = None              # Volume Weighted Avg Price = SUM(price)/COUNT
    latest_price: Optional[float] = None      # Most recent sale price
    lowest_ask: Optional[float] = None        # Cheapest active listing
    max_price: Optional[float] = None         # Highest confirmed sale
    avg_price: Optional[float] = None         # Simple average (from snapshot)
    fair_market_price: Optional[float] = None # FMP from formula (detail page only)

    # === VOLUME & INVENTORY ===
    volume: Optional[int] = None              # Sales count for selected time period
    inventory: Optional[int] = None           # Active listings count

    # === DELTAS (% changes) ===
    price_delta: Optional[float] = None       # Last sale vs rolling avg (%)
    floor_delta: Optional[float] = None       # Last sale vs floor price (%)

    # === METADATA ===
    last_treatment: Optional[str] = None      # Treatment of last sale (e.g., "Classic Foil")
    last_updated: Optional[datetime] = None   # When market data was last scraped

    # === DEPRECATED (keep for backwards compat, remove later) ===
    volume_30d: Optional[int] = None          # @deprecated: use 'volume'
    price_delta_24h: Optional[float] = None   # @deprecated: use 'price_delta'
    last_sale_diff: Optional[float] = None    # @deprecated: use 'floor_delta'
    last_sale_treatment: Optional[str] = None # @deprecated: use 'last_treatment'

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
    created_at: datetime
    username: Optional[str] = None
    discord_handle: Optional[str] = None
    bio: Optional[str] = None

class UserUpdate(BaseModel):
    username: Optional[str] = None
    discord_handle: Optional[str] = None
    bio: Optional[str] = None

# Portfolio Schemas (Legacy - quantity based)
class PortfolioItemBase(BaseModel):
    card_id: int
    quantity: int
    purchase_price: float
    acquired_at: Optional[datetime] = None # Allow optional for creation, default to now in model

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


# Portfolio Card Schemas (New - individual card tracking)
class PortfolioCardBase(BaseModel):
    card_id: int
    treatment: str = "Classic Paper"
    source: str = "Other"  # eBay, Blokpax, TCGPlayer, LGS, Trade, Pack Pull, Other
    purchase_price: float
    purchase_date: Optional[datetime] = None
    grading: Optional[str] = None  # e.g., "PSA 10", "BGS 9.5", null for raw
    notes: Optional[str] = None


class PortfolioCardCreate(PortfolioCardBase):
    """Create a single card in portfolio."""
    pass


class PortfolioCardBatchCreate(BaseModel):
    """Create multiple cards at once (split entry)."""
    cards: List[PortfolioCardBase]


class PortfolioCardUpdate(BaseModel):
    """Update an existing portfolio card."""
    treatment: Optional[str] = None
    source: Optional[str] = None
    purchase_price: Optional[float] = None
    purchase_date: Optional[datetime] = None
    grading: Optional[str] = None
    notes: Optional[str] = None


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
