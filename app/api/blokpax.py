"""
Blokpax API endpoints for frontend integration.
Provides access to WOTF storefront data, floor prices, and sales history.
"""

import threading
from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, select, desc
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel

from app.core.typing import col
from app.db import get_session
from app.models.blokpax import (
    BlokpaxStorefront,
    BlokpaxSnapshot,
    BlokpaxSale,
    BlokpaxAssetDB,
    BlokpaxOffer,
)

router = APIRouter()

# Module-level cache for summary endpoint (expensive aggregation)
_summary_cache: dict[str, tuple[Any, datetime]] = {}
_summary_cache_lock = threading.Lock()
_SUMMARY_CACHE_TTL = timedelta(minutes=5)


# Pydantic schemas for API responses
class BlokpaxStorefrontOut(BaseModel):
    id: int
    slug: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    network_id: int
    floor_price_bpx: Optional[float] = None
    floor_price_usd: Optional[float] = None
    total_tokens: int
    listed_count: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class BlokpaxSnapshotOut(BaseModel):
    id: int
    storefront_slug: str
    floor_price_bpx: Optional[float] = None
    floor_price_usd: Optional[float] = None
    bpx_price_usd: float
    listed_count: int
    total_tokens: int
    timestamp: datetime

    model_config = {"from_attributes": True}


class BlokpaxSaleOut(BaseModel):
    id: int
    listing_id: str
    asset_id: str
    asset_name: str
    price_bpx: float
    price_usd: float
    quantity: int
    seller_address: str
    buyer_address: str
    treatment: Optional[str] = None
    filled_at: datetime
    card_id: Optional[int] = None

    model_config = {"from_attributes": True}


class BlokpaxAssetOut(BaseModel):
    id: int
    external_id: str
    storefront_slug: str
    name: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    network_id: int
    owner_count: int
    token_count: int
    floor_price_bpx: Optional[float] = None
    floor_price_usd: Optional[float] = None
    card_id: Optional[int] = None

    model_config = {"from_attributes": True}


class BlokpaxOfferOut(BaseModel):
    id: int
    external_id: str
    asset_id: str
    price_bpx: float
    price_usd: float
    quantity: int
    buyer_address: str
    status: str
    created_at: Optional[datetime] = None
    scraped_at: datetime

    model_config = {"from_attributes": True}


@router.get("/storefronts", response_model=List[BlokpaxStorefrontOut])
def list_storefronts(
    session: Session = Depends(get_session),
) -> Any:
    """
    List all WOTF storefronts with current floor prices.
    """
    storefronts = session.exec(select(BlokpaxStorefront).order_by(col(BlokpaxStorefront.name))).all()
    return [BlokpaxStorefrontOut.model_validate(s) for s in storefronts]


@router.get("/storefronts/{slug}", response_model=BlokpaxStorefrontOut)
def get_storefront(
    slug: str,
    session: Session = Depends(get_session),
) -> Any:
    """
    Get detailed data for a specific storefront.
    """
    storefront = session.exec(select(BlokpaxStorefront).where(BlokpaxStorefront.slug == slug)).first()

    if not storefront:
        raise HTTPException(status_code=404, detail="Storefront not found")

    return BlokpaxStorefrontOut.model_validate(storefront)


@router.get("/storefronts/{slug}/snapshots", response_model=List[BlokpaxSnapshotOut])
def get_storefront_snapshots(
    slug: str,
    session: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> Any:
    """
    Get price history snapshots for a storefront (for charts).
    """
    # Verify storefront exists
    storefront = session.exec(select(BlokpaxStorefront).where(BlokpaxStorefront.slug == slug)).first()

    if not storefront:
        raise HTTPException(status_code=404, detail="Storefront not found")

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    snapshots = session.exec(
        select(BlokpaxSnapshot)
        .where(BlokpaxSnapshot.storefront_slug == slug)
        .where(col(BlokpaxSnapshot.timestamp) >= cutoff)
        .order_by(desc(BlokpaxSnapshot.timestamp), desc(BlokpaxSnapshot.id))
        .limit(limit)
    ).all()

    return [BlokpaxSnapshotOut.model_validate(s) for s in snapshots]


@router.get("/storefronts/{slug}/sales", response_model=List[BlokpaxSaleOut])
def get_storefront_sales(
    slug: str,
    session: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=365, description="Number of days of history"),
    limit: int = Query(default=50, ge=1, le=500),
) -> Any:
    """
    Get recent sales for a specific storefront.
    """
    # For reward-room, we filter WOTF assets in the scraper
    # For dedicated storefronts, all sales are WOTF

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    # Get sales that match assets in this storefront
    # Since BlokpaxSale doesn't have storefront_slug, we need to join through assets
    # Or we can infer from asset naming patterns

    # For now, get all WOTF sales and let frontend filter by storefront if needed
    # This is a simplification - ideally we'd add storefront_slug to BlokpaxSale
    sales = session.exec(
        select(BlokpaxSale).where(BlokpaxSale.filled_at >= cutoff).order_by(desc(BlokpaxSale.filled_at)).limit(limit)
    ).all()

    return [BlokpaxSaleOut.model_validate(s) for s in sales]


@router.get("/sales", response_model=List[BlokpaxSaleOut])
def list_all_sales(
    session: Session = Depends(get_session),
    days: int = Query(default=7, ge=1, le=90, description="Number of days of history"),
    limit: int = Query(default=100, ge=1, le=500),
) -> Any:
    """
    Get recent sales across all WOTF storefronts.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    sales = session.exec(
        select(BlokpaxSale).where(BlokpaxSale.filled_at >= cutoff).order_by(desc(BlokpaxSale.filled_at)).limit(limit)
    ).all()

    return [BlokpaxSaleOut.model_validate(s) for s in sales]


@router.get("/assets", response_model=List[BlokpaxAssetOut])
def list_assets(
    session: Session = Depends(get_session),
    storefront_slug: Optional[str] = Query(default=None, description="Filter by storefront"),
    limit: int = Query(default=50, ge=1, le=500),
) -> Any:
    """
    List indexed Blokpax assets, optionally filtered by storefront.
    """
    query = select(BlokpaxAssetDB)

    if storefront_slug:
        query = query.where(BlokpaxAssetDB.storefront_slug == storefront_slug)

    query = query.order_by(col(BlokpaxAssetDB.floor_price_usd).asc()).limit(limit)

    assets = session.exec(query).all()
    return [BlokpaxAssetOut.model_validate(a) for a in assets]


@router.get("/summary")
def get_blokpax_summary(
    session: Session = Depends(get_session),
) -> Any:
    """
    Get a summary of all WOTF Blokpax data for dashboard display.
    Cached for 5 minutes to avoid repeated expensive aggregations.
    """
    cache_key = "blokpax_summary"

    # Check cache first
    with _summary_cache_lock:
        if cache_key in _summary_cache:
            cached_result, cached_at = _summary_cache[cache_key]
            if datetime.now(timezone.utc) - cached_at < _SUMMARY_CACHE_TTL:
                return cached_result

    storefronts = session.exec(select(BlokpaxStorefront)).all()

    # Calculate totals
    total_listed = sum(sf.listed_count or 0 for sf in storefronts)
    total_tokens = sum(sf.total_tokens or 0 for sf in storefronts)

    # Get lowest floor across all storefronts
    floors = [sf.floor_price_usd for sf in storefronts if sf.floor_price_usd]
    lowest_floor = min(floors) if floors else None

    # Get recent sales count (last 24h) and volume (last 7d) in single efficient query
    from sqlalchemy import text

    cutoff_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    cutoff_7d = datetime.now(timezone.utc) - timedelta(days=7)

    # Single aggregate query instead of loading all records into memory
    sales_stats = session.execute(
        text("""
            SELECT
                COUNT(*) FILTER (WHERE filled_at >= :cutoff_24h) as sales_24h,
                COALESCE(SUM(price_usd * quantity) FILTER (WHERE filled_at >= :cutoff_7d), 0) as volume_7d
            FROM blokpaxsale
            WHERE filled_at >= :cutoff_7d
        """),
        {"cutoff_24h": cutoff_24h, "cutoff_7d": cutoff_7d}
    ).first()

    recent_sales = int(sales_stats[0]) if sales_stats else 0
    volume_7d_usd = float(sales_stats[1]) if sales_stats else 0.0

    result = {
        "storefronts": [
            {
                "slug": sf.slug,
                "name": sf.name,
                "floor_price_usd": sf.floor_price_usd,
                "floor_price_bpx": sf.floor_price_bpx,
                "listed_count": sf.listed_count,
                "total_tokens": sf.total_tokens,
            }
            for sf in storefronts
        ],
        "totals": {
            "total_listed": total_listed,
            "total_tokens": total_tokens,
            "lowest_floor_usd": lowest_floor,
            "recent_sales_24h": recent_sales,
            "volume_7d_usd": volume_7d_usd,
        },
    }

    # Cache the result
    with _summary_cache_lock:
        _summary_cache[cache_key] = (result, datetime.now(timezone.utc))

    return result


@router.get("/offers", response_model=List[BlokpaxOfferOut])
def list_offers(
    session: Session = Depends(get_session),
    status: Optional[str] = Query(default="open", description="Filter by status: open, filled, cancelled"),
    limit: int = Query(default=50, ge=1, le=500),
) -> Any:
    """
    List all offers/bids across WOTF storefronts.
    """
    query = select(BlokpaxOffer)

    if status:
        query = query.where(BlokpaxOffer.status == status)

    query = query.order_by(desc(BlokpaxOffer.price_usd)).limit(limit)

    offers = session.exec(query).all()
    return [BlokpaxOfferOut.model_validate(o) for o in offers]


@router.get("/offers/asset/{asset_id}", response_model=List[BlokpaxOfferOut])
def get_asset_offers(
    asset_id: str,
    session: Session = Depends(get_session),
    status: Optional[str] = Query(default=None, description="Filter by status"),
) -> Any:
    """
    Get all offers for a specific asset.
    """
    query = select(BlokpaxOffer).where(BlokpaxOffer.asset_id == asset_id)

    if status:
        query = query.where(BlokpaxOffer.status == status)

    query = query.order_by(desc(BlokpaxOffer.price_usd))

    offers = session.exec(query).all()
    return [BlokpaxOfferOut.model_validate(o) for o in offers]
