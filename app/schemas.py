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
    treatment: Optional[str] = "Classic Paper" # Added treatment field
    bid_count: Optional[int] = 0 # Added bid_count field
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
    rarity_name: Optional[str] = None # Added rarity_name
    # Flattened fields for easy table access
    latest_price: Optional[float] = None 
    volume_24h: Optional[int] = None
    price_delta_24h: Optional[float] = None
    lowest_ask: Optional[float] = None
    inventory: Optional[int] = None
    product_type: Optional[str] = None  # Single, Box, Pack, Proof
    max_price: Optional[float] = None  # Highest confirmed sale

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
    # Optionally include card details for display
    card: Optional[CardOut] = None # This would require a join in the API
