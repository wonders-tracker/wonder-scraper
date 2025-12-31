"""
Order Book Analysis Service

Analyzes active listings to estimate floor prices using order book depth.
The algorithm buckets prices, finds the deepest bucket (most liquidity),
and returns the midpoint as the floor estimate with a confidence score.

This service is available in both OSS and SaaS modes.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from math import sqrt
from typing import Optional

import numpy as np
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine


# Configuration constants
class OrderBookConfig:
    MIN_BUCKET_WIDTH: float = 5.0  # Minimum bucket size in dollars
    MAX_BUCKET_WIDTH: float = 50.0  # Maximum bucket size in dollars
    OUTLIER_SIGMA_THRESHOLD: float = 2.0  # Standard deviations for outlier detection
    STALE_DAYS: int = 14  # Listings older than this reduce confidence
    MIN_LISTINGS: int = 3  # Minimum listings required for analysis
    DEFAULT_LOOKBACK_DAYS: int = 30  # Default window for active listings


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
    deepest_bucket: BucketInfo
    total_listings: int
    outliers_removed: int
    buckets: list[BucketInfo]
    stale_count: int = 0
    source: str = "order_book"  # "order_book" or "sales_fallback"

    def to_dict(self) -> dict:
        return {
            "floor_estimate": self.floor_estimate,
            "confidence": self.confidence,
            "total_listings": self.total_listings,
            "outliers_removed": self.outliers_removed,
            "stale_count": self.stale_count,
            "source": self.source,
            "deepest_bucket": self.deepest_bucket.to_dict(),
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
        self.session = session
        self.config = OrderBookConfig()

    def estimate_floor(
        self,
        card_id: int,
        treatment: Optional[str] = None,
        days: int = OrderBookConfig.DEFAULT_LOOKBACK_DAYS,
        allow_sales_fallback: bool = True,
    ) -> Optional[OrderBookResult]:
        """
        Estimate floor price from order book depth.

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

        # 2. Filter outliers
        filtered_prices, outliers_removed = self._filter_outliers(prices)

        if len(filtered_prices) < self.config.MIN_LISTINGS:
            return None

        # 3. Create buckets
        buckets = self._create_buckets(filtered_prices)

        if not buckets:
            return None

        # 4. Find deepest bucket
        deepest = self._find_deepest_bucket(buckets)

        # 5. Calculate staleness
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.STALE_DAYS)
        stale_count = 0
        for d in scraped_dates:
            # Handle both timezone-aware and naive datetimes
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d < stale_cutoff:
                stale_count += 1

        # 6. Calculate confidence
        confidence = self._calculate_confidence(deepest, len(filtered_prices), stale_count)

        return OrderBookResult(
            floor_estimate=round(deepest.midpoint, 2),
            confidence=confidence,
            deepest_bucket=deepest,
            total_listings=len(filtered_prices),
            outliers_removed=outliers_removed,
            buckets=buckets,
            stale_count=stale_count,
        )

    def _fetch_active_listings(
        self, card_id: int, treatment: Optional[str], days: int
    ) -> list[dict]:
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

        # Use provided session or create new one
        if self.session:
            result = self.session.execute(
                query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment}
            )
            return [dict(row._mapping) for row in result.fetchall()]
        else:
            with engine.connect() as conn:
                result = conn.execute(
                    query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment}
                )
                return [dict(row._mapping) for row in result.fetchall()]

    def _filter_outliers(
        self, prices: list[float]
    ) -> tuple[list[float], int]:
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

    def _calculate_confidence(
        self, deepest_bucket: BucketInfo, total_listings: int, stale_count: int
    ) -> float:
        """
        Calculate confidence score for floor estimate.

        confidence = depth_ratio × (1 - stale_ratio)

        Where:
        - depth_ratio = deepest_bucket.count / total_listings
        - stale_ratio = stale listings / total_listings
        """
        if total_listings == 0:
            return 0.0

        depth_ratio = deepest_bucket.count / total_listings
        stale_ratio = stale_count / total_listings

        confidence = depth_ratio * (1 - stale_ratio)
        return round(min(1.0, max(0.0, confidence)), 3)

    def _fetch_sold_listings(
        self, card_id: int, treatment: Optional[str], days: int
    ) -> list[dict]:
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

        if self.session:
            result = self.session.execute(
                query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment}
            )
            return [dict(row._mapping) for row in result.fetchall()]
        else:
            with engine.connect() as conn:
                result = conn.execute(
                    query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment}
                )
                return [dict(row._mapping) for row in result.fetchall()]

    def _estimate_from_sales(
        self,
        card_id: int,
        treatment: Optional[str],
        days: int,
    ) -> Optional[OrderBookResult]:
        """
        Fallback: estimate floor from sold listings when active listings are insufficient.

        Uses the same bucketing algorithm but with reduced confidence (0.5x multiplier)
        to reflect that sales data is historical rather than current availability.

        If no data found within the given window, expands to 90 days, then all-time.
        """
        listings = self._fetch_sold_listings(card_id, treatment, days)

        # Expand window if no data found
        if len(listings) == 0 and days < 90:
            listings = self._fetch_sold_listings(card_id, treatment, 90)

        if len(listings) == 0:
            # Last resort: all-time data (365 days)
            listings = self._fetch_sold_listings(card_id, treatment, 365)

        # For sales fallback, we accept even 1 listing
        if len(listings) == 0:
            return None

        prices = [row["price"] for row in listings]
        sold_dates = [row["sold_date"] for row in listings]

        # If only 1-2 listings, return the lowest price directly
        if len(prices) < self.config.MIN_LISTINGS:
            lowest_price = min(prices)
            bucket = BucketInfo(lowest_price, lowest_price, len(prices))
            # Low confidence for sparse data
            confidence = 0.1 * len(prices)  # 0.1 for 1 listing, 0.2 for 2
            return OrderBookResult(
                floor_estimate=round(lowest_price, 2),
                confidence=round(confidence, 3),
                deepest_bucket=bucket,
                total_listings=len(prices),
                outliers_removed=0,
                buckets=[bucket],
                stale_count=0,
                source="sales_fallback",
            )

        # Apply same algorithm as order book
        filtered_prices, outliers_removed = self._filter_outliers(prices)

        if len(filtered_prices) == 0:
            filtered_prices = prices  # Fall back to unfiltered if all removed

        buckets = self._create_buckets(filtered_prices)

        if not buckets:
            # Edge case: create single bucket from lowest price
            lowest = min(filtered_prices)
            buckets = [BucketInfo(lowest, lowest, len(filtered_prices))]

        deepest = self._find_deepest_bucket(buckets)

        # Calculate staleness
        stale_cutoff = datetime.now(timezone.utc) - timedelta(days=self.config.STALE_DAYS)
        stale_count = 0
        for d in sold_dates:
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if d < stale_cutoff:
                stale_count += 1

        # Calculate confidence with 0.5x penalty for sales fallback
        base_confidence = self._calculate_confidence(deepest, len(filtered_prices), stale_count)
        confidence = round(base_confidence * 0.5, 3)

        return OrderBookResult(
            floor_estimate=round(deepest.midpoint, 2),
            confidence=confidence,
            deepest_bucket=deepest,
            total_listings=len(filtered_prices),
            outliers_removed=outliers_removed,
            buckets=buckets,
            stale_count=stale_count,
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
