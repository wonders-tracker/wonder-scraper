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
    rarity_name: Optional[str] = None # Added rarity_name
    # Flattened fields for easy table access
    latest_price: Optional[float] = None
    volume_30d: Optional[int] = None  # 30-day sales volume (count of sold listings)
    price_delta_24h: Optional[float] = None
    last_sale_diff: Optional[float] = None # Diff between last sale and avg price
    last_sale_treatment: Optional[str] = None # Treatment of the last sold item
    lowest_ask: Optional[float] = None
    inventory: Optional[int] = None
    product_type: Optional[str] = None  # Single, Box, Pack, Proof
    max_price: Optional[float] = None  # Highest confirmed sale
    avg_price: Optional[float] = None  # Average price
    vwap: Optional[float] = None # Volume Weighted Average Price
    last_updated: Optional[datetime] = None # When the market data was scraped
    # Fair Market Price fields
    fair_market_price: Optional[float] = None  # Calculated FMP using formula
    floor_price: Optional[float] = None  # Avg of last 4 lowest sales (30d)

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

# Portfolio Schemas
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
