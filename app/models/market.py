from typing import Optional
from sqlmodel import Field, SQLModel
from datetime import datetime

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
    highest_bid: Optional[float] = None # eBay auctions only
    inventory: Optional[int] = None # Count of active listings

    # Last Sale Data
    last_sale_price: Optional[float] = None
    last_sale_date: Optional[datetime] = None

    platform: str = Field(default="ebay") # 'ebay', 'opensea'
    
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class MarketPrice(SQLModel, table=True):
    """Individual raw price data points (optional, for detailed history)"""
    id: Optional[int] = Field(default=None, primary_key=True)
    card_id: int = Field(foreign_key="card.id", index=True)
    price: float
    title: str
    sold_date: Optional[datetime] = None
    listing_type: str = Field(default="sold") # 'sold' or 'active'
    treatment: str = Field(default="Classic Paper") # New field: Classic Paper, Foil, Serialized, etc.
    bid_count: int = Field(default=0) # New field: Number of bids (for auctions)
    external_id: Optional[str] = Field(default=None, index=True) # Unique ID from source (e.g., eBay item ID)
    url: Optional[str] = Field(default=None) # Link to the listing
    image_url: Optional[str] = Field(default=None) # Link to listing image
    description: Optional[str] = Field(default=None) # Short description or specifics
    platform: str = Field(default="ebay") # 'ebay', 'opensea', 'tcgplayer', etc.

    # Seller Info
    seller_name: Optional[str] = Field(default=None, index=True) # Seller username
    seller_feedback_score: Optional[int] = Field(default=None) # Feedback count (e.g., 1234)
    seller_feedback_percent: Optional[float] = Field(default=None) # Positive feedback % (e.g., 99.5)

    # Listing Details
    condition: Optional[str] = Field(default=None) # "New", "Like New", "Used", etc.
    shipping_cost: Optional[float] = Field(default=None) # Shipping price (0 = free)

    scraped_at: datetime = Field(default_factory=datetime.utcnow)
