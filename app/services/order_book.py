"""
Order Book Analysis Service

Analyzes active listings to estimate floor prices using order book depth.
The algorithm buckets prices, finds the deepest bucket (most liquidity),
and returns the midpoint as the floor estimate with a confidence score.

This service is available in both OSS and SaaS modes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Optional

import numpy as np
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine
from app.services.confidence import calculate_orderbook_confidence

logger = logging.getLogger(__name__)


# Configuration constants
class OrderBookConfig:
    """Configuration constants for order book floor price estimation."""

    MIN_BUCKET_WIDTH: float = 5.0  # Minimum bucket size in dollars
    MAX_BUCKET_WIDTH: float = 50.0  # Maximum bucket size in dollars
    OUTLIER_SIGMA_THRESHOLD: float = 2.0  # Standard deviations for outlier detection
    STALE_DAYS: int = 14  # Listings older than this reduce confidence
    MIN_LISTINGS: int = 1  # Minimum listings required (lowered from 3)
    DEFAULT_LOOKBACK_DAYS: int = 30  # Default window for active listings
    SPARSE_DATA_CONFIDENCE_MULTIPLIER: float = 0.1  # Confidence per listing for sparse data
    SALES_FALLBACK_CONFIDENCE_PENALTY: float = 0.5  # Confidence multiplier for sales fallback
    # Confidence calculation weights (v2.1 - with volatility)
    LISTING_COUNT_WEIGHT: float = 0.35  # Weight for number of listings
    SPREAD_WEIGHT: float = 0.25  # Weight for price spread tightness
    RECENCY_WEIGHT: float = 0.25  # Weight for listing recency
    VOLATILITY_WEIGHT: float = 0.15  # Weight for historical price stability


@dataclass
class BucketInfo:
    """Represents a price bucket in the order book."""

    min_price: float
    max_price: float
    count: int

    @property
    def midpoint(self) -> float:
        return (self.min_price + self.max_price) / 2

    def to_dict(self) -> dict:
        return {
            "min_price": self.min_price,
            "max_price": self.max_price,
            "count": self.count,
            "midpoint": self.midpoint,
        }


@dataclass
class OrderBookResult:
    """Result of order book floor estimation."""

    floor_estimate: float
    confidence: float
    lowest_ask: float  # The actual lowest active listing price
    total_listings: int
    outliers_removed: int
    buckets: list[BucketInfo]
    deepest_bucket: Optional[BucketInfo] = None
    stale_count: int = 0
    spread_pct: float = 0.0  # Price spread as percentage of lowest
    source: str = "order_book"  # "order_book" or "sales_fallback"
    volatility_cv: float = 0.5  # Coefficient of variation (0 = stable, 1+ = volatile)

    def to_dict(self) -> dict:
        return {
            "floor_estimate": self.floor_estimate,
            "lowest_ask": self.lowest_ask,
            "confidence": self.confidence,
            "total_listings": self.total_listings,
            "outliers_removed": self.outliers_removed,
            "stale_count": self.stale_count,
            "spread_pct": self.spread_pct,
            "volatility_cv": self.volatility_cv,
            "source": self.source,
            "deepest_bucket": self.deepest_bucket.to_dict() if self.deepest_bucket else None,
            "buckets": [b.to_dict() for b in self.buckets],
        }


class OrderBookAnalyzer:
    """
    Analyzes order book depth to estimate floor prices from active listings.

    Algorithm:
    1. Fetch active listings for a card/variant (excluding bulk lots)
    2. Filter outliers using local price gap analysis (>2σ from mean gap)
    3. Create adaptive price buckets (width = range/√n, constrained)
    4. Find deepest bucket (most liquidity)
    5. Return midpoint as floor estimate with confidence score

    Example:
        analyzer = OrderBookAnalyzer(session)
        result = analyzer.estimate_floor(card_id=123, treatment="Classic Foil")
        if result:
            print(f"Floor: ${result.floor_estimate:.2f} (confidence: {result.confidence:.2f})")
    """

    def __init__(self, session: Optional[Session] = None):
        """
        Initialize the OrderBookAnalyzer.

        Args:
            session: Optional SQLModel session. If not provided, creates new connections per query.
        """
        self.session = session
        self.config = OrderBookConfig()
        self._market_patterns = None

    @property
    def market_patterns(self):
        """Lazy-load MarketPatternsService to avoid circular imports."""
        if self._market_patterns is None:
            from app.services.market_patterns import MarketPatternsService

            self._market_patterns = MarketPatternsService(self.session)
        return self._market_patterns

    def estimate_floor(
        self,
        card_id: int,
        treatment: Optional[str] = None,
        days: int = OrderBookConfig.DEFAULT_LOOKBACK_DAYS,
        allow_sales_fallback: bool = True,
    ) -> Optional[OrderBookResult]:
        """
        Estimate floor price from order book depth.

        Algorithm (v2 - fixed):
        1. Fetch active listings for a card/variant
        2. Use LOWEST ASK as floor estimate (not bucket midpoint)
        3. Calculate confidence based on: listing count, price spread, recency

        Args:
            card_id: Database ID of the card
            treatment: Optional treatment filter (e.g., "Classic Foil")
            days: Lookback window for active listings (default 30)
            allow_sales_fallback: If True, fall back to sales data when insufficient active listings

        Returns:
            OrderBookResult with floor estimate and confidence, or None if insufficient data
        """
        # 1. Fetch active listings
        listings = self._fetch_active_listings(card_id, treatment, days)

        if len(listings) < self.config.MIN_LISTINGS:
            # Try sales fallback if allowed
            if allow_sales_fallback:
                return self._estimate_from_sales(card_id, treatment, days)
            return None

        prices = [row["price"] for row in listings]
        scraped_dates = [row["scraped_at"] for row in listings]

        # 2. Calculate key metrics BEFORE filtering (we want true lowest ask)
        lowest_ask = min(prices)

        # 3. Filter outliers for bucket analysis
        filtered_prices, outliers_removed = self._filter_outliers(prices)

        if len(filtered_prices) == 0:
            filtered_prices = prices  # Fall back to unfiltered

        # 4. Create buckets (for analysis, not floor estimation)
        buckets = self._create_buckets(filtered_prices)
        deepest = self._find_deepest_bucket(buckets) if buckets else None

        # 5. Calculate price spread
        if len(filtered_prices) > 1:
            spread_pct = ((max(filtered_prices) - min(filtered_prices)) / min(filtered_prices)) * 100
        else:
            spread_pct = 0.0

        # 6. Calculate staleness
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.STALE_DAYS)
        stale_count = 0
        for d in scraped_dates:
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d < stale_cutoff:
                stale_count += 1

        # 7. Get card volatility for confidence adjustment
        volatility = self.market_patterns.get_card_volatility(card_id, treatment)
        volatility_cv = volatility.coefficient_of_variation

        # 8. Calculate NEW confidence score (with volatility)
        confidence = self._calculate_confidence_v2(
            total_listings=len(filtered_prices),
            spread_pct=spread_pct,
            stale_count=stale_count,
            volatility_cv=volatility_cv,
        )

        # Floor estimate = lowest ask (the actual floor!)
        return OrderBookResult(
            floor_estimate=round(lowest_ask, 2),
            lowest_ask=round(lowest_ask, 2),
            confidence=confidence,
            deepest_bucket=deepest,
            total_listings=len(filtered_prices),
            outliers_removed=outliers_removed,
            buckets=buckets,
            stale_count=stale_count,
            spread_pct=round(spread_pct, 1),
            volatility_cv=round(volatility_cv, 3),
        )

    def _fetch_active_listings(self, card_id: int, treatment: Optional[str], days: int) -> list[dict]:
        """Fetch active listings from database, excluding bulk lots."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = text("""
            SELECT price, scraped_at, treatment, title
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'active'
              AND scraped_at >= :cutoff
              AND is_bulk_lot = FALSE
              AND (:treatment IS NULL OR treatment = :treatment)
            ORDER BY price ASC
        """)

        try:
            # Use provided session or create new one
            if self.session:
                result = self.session.execute(query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment})
                return [dict(row._mapping) for row in result.fetchall()]
            else:
                with engine.connect() as conn:
                    result = conn.execute(query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment})
                    return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"[OrderBook] Failed to fetch active listings for card {card_id}: {e}")
            return []

    def _filter_outliers(self, prices: list[float]) -> tuple[list[float], int]:
        """
        Filter outliers based on local price gaps.
        Removes prices where gap to nearest neighbor is >2σ from mean gap.

        Returns: (filtered_prices, num_removed)
        """
        if len(prices) < 3:
            return prices, 0

        sorted_prices = sorted(prices)

        # Calculate gaps between consecutive prices
        gaps = [sorted_prices[i + 1] - sorted_prices[i] for i in range(len(sorted_prices) - 1)]

        if not gaps:
            return prices, 0

        mean_gap = float(np.mean(gaps))
        std_gap = float(np.std(gaps))
        threshold = mean_gap + self.config.OUTLIER_SIGMA_THRESHOLD * std_gap

        # Keep prices that have at least one close neighbor
        filtered = []
        for i, price in enumerate(sorted_prices):
            gap_before = sorted_prices[i] - sorted_prices[i - 1] if i > 0 else 0
            gap_after = sorted_prices[i + 1] - sorted_prices[i] if i < len(sorted_prices) - 1 else 0

            if gap_before <= threshold or gap_after <= threshold:
                filtered.append(price)

        return filtered, len(prices) - len(filtered)

    def _create_buckets(self, prices: list[float]) -> list[BucketInfo]:
        """
        Create price buckets with adaptive width.
        Width = (max - min) / sqrt(n), constrained to [min_width, max_width]
        """
        if not prices:
            return []

        min_price = min(prices)
        max_price = max(prices)
        price_range = max_price - min_price

        # Handle edge case: all prices are the same
        if price_range == 0:
            return [BucketInfo(min_price, max_price, len(prices))]

        # Adaptive bucket width
        bucket_width = max(
            self.config.MIN_BUCKET_WIDTH,
            min(self.config.MAX_BUCKET_WIDTH, price_range / sqrt(len(prices))),
        )

        # Create buckets
        buckets = []
        bucket_start = min_price

        while bucket_start < max_price:
            bucket_end = bucket_start + bucket_width

            # Include max_price in last bucket
            if bucket_end >= max_price:
                count = sum(1 for p in prices if bucket_start <= p <= max_price)
                bucket_end = max_price
            else:
                count = sum(1 for p in prices if bucket_start <= p < bucket_end)

            if count > 0:
                buckets.append(BucketInfo(bucket_start, bucket_end, count))

            bucket_start = bucket_end

        return buckets

    def _find_deepest_bucket(self, buckets: list[BucketInfo]) -> BucketInfo:
        """
        Find bucket with most listings (deepest liquidity).
        Tie-breaker: choose lower price bucket.
        """
        return max(buckets, key=lambda b: (b.count, -b.min_price))

    def _calculate_confidence(self, deepest_bucket: BucketInfo, total_listings: int, stale_count: int) -> float:
        """
        DEPRECATED: Old confidence calculation (kept for backwards compatibility).
        Use _calculate_confidence_v2 instead.
        """
        if total_listings == 0:
            return 0.0

        depth_ratio = deepest_bucket.count / total_listings
        stale_ratio = stale_count / total_listings

        confidence = depth_ratio * (1 - stale_ratio)
        return round(min(1.0, max(0.0, confidence)), 3)

    def _calculate_confidence_v2(
        self,
        total_listings: int,
        spread_pct: float,
        stale_count: int,
        volatility_cv: float = 0.5,
    ) -> float:
        """
        Calculate confidence score for floor estimate (v2.1 - with volatility).

        Delegates to the shared calculate_orderbook_confidence function.

        Returns: 0.0 to 1.0
        """
        return calculate_orderbook_confidence(
            total_listings=total_listings,
            spread_pct=spread_pct,
            stale_count=stale_count,
            volatility_cv=volatility_cv,
            listing_count_weight=self.config.LISTING_COUNT_WEIGHT,
            spread_weight=self.config.SPREAD_WEIGHT,
            recency_weight=self.config.RECENCY_WEIGHT,
            volatility_weight=self.config.VOLATILITY_WEIGHT,
        )

    def _fetch_sold_listings(self, card_id: int, treatment: Optional[str], days: int) -> list[dict]:
        """Fetch sold listings from database, excluding bulk lots."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = text("""
            SELECT price, COALESCE(sold_date, scraped_at) as sold_date, treatment, title
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
              AND is_bulk_lot = FALSE
              AND (:treatment IS NULL OR treatment = :treatment)
            ORDER BY price ASC
        """)

        try:
            if self.session:
                result = self.session.execute(query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment})
                return [dict(row._mapping) for row in result.fetchall()]
            else:
                with engine.connect() as conn:
                    result = conn.execute(query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment})
                    return [dict(row._mapping) for row in result.fetchall()]
        except Exception as e:
            logger.error(f"[OrderBook] Failed to fetch sold listings for card {card_id}: {e}")
            return []

    def _estimate_from_sales(
        self,
        card_id: int,
        treatment: Optional[str],
        days: int,
    ) -> Optional[OrderBookResult]:
        """
        Fallback: estimate floor from sold listings when active listings are insufficient.

        Uses lowest sale price (floor) with confidence penalty to reflect that
        sales data is historical rather than current availability.

        If no data found within the given window, expands to 90 days, then all-time.
        """
        listings = self._fetch_sold_listings(card_id, treatment, days)

        # Expand window if no data found
        if len(listings) == 0 and days < 90:
            listings = self._fetch_sold_listings(card_id, treatment, 90)

        if len(listings) == 0:
            # Last resort: all-time data (365 days)
            listings = self._fetch_sold_listings(card_id, treatment, 365)

        if len(listings) == 0:
            return None

        prices = [row["price"] for row in listings]
        sold_dates = [row["sold_date"] for row in listings]

        # Use avg of 4 lowest sales as floor (matches floor_price service)
        sorted_prices = sorted(prices)
        floor_sample = sorted_prices[:4]
        floor_estimate = sum(floor_sample) / len(floor_sample)
        lowest_sale = min(prices)

        # Filter outliers for bucket analysis
        filtered_prices, outliers_removed = self._filter_outliers(prices)
        if len(filtered_prices) == 0:
            filtered_prices = prices

        # Create buckets for analysis
        buckets = self._create_buckets(filtered_prices)
        deepest = self._find_deepest_bucket(buckets) if buckets else None

        # Calculate spread
        if len(filtered_prices) > 1:
            spread_pct = ((max(filtered_prices) - min(filtered_prices)) / min(filtered_prices)) * 100
        else:
            spread_pct = 0.0

        # Calculate staleness
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.STALE_DAYS)
        stale_count = 0
        for d in sold_dates:
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d < stale_cutoff:
                stale_count += 1

        # Get card volatility for confidence adjustment
        volatility = self.market_patterns.get_card_volatility(card_id, treatment)
        volatility_cv = volatility.coefficient_of_variation

        # Calculate confidence with sales fallback penalty
        base_confidence = self._calculate_confidence_v2(
            total_listings=len(filtered_prices),
            spread_pct=spread_pct,
            stale_count=stale_count,
            volatility_cv=volatility_cv,
        )
        confidence = round(base_confidence * self.config.SALES_FALLBACK_CONFIDENCE_PENALTY, 3)

        return OrderBookResult(
            floor_estimate=round(floor_estimate, 2),
            lowest_ask=round(lowest_sale, 2),  # Lowest sale, not ask
            confidence=confidence,
            deepest_bucket=deepest,
            total_listings=len(filtered_prices),
            outliers_removed=outliers_removed,
            buckets=buckets,
            stale_count=stale_count,
            spread_pct=round(spread_pct, 1),
            volatility_cv=round(volatility_cv, 3),
            source="sales_fallback",
        )


def get_order_book_analyzer(session: Optional[Session] = None) -> OrderBookAnalyzer:
    """Factory function to create OrderBookAnalyzer."""
    return OrderBookAnalyzer(session)


__all__ = [
    "OrderBookAnalyzer",
    "OrderBookResult",
    "BucketInfo",
    "OrderBookConfig",
    "get_order_book_analyzer",
]
