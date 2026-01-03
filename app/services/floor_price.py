"""
Floor Price Service

Hybrid floor price estimation using a decision tree:
1. Try sales floor first (avg of 4 lowest sales)
2. Fall back to order book floor (OrderBookAnalyzer)
3. Return null if neither available

This service is available in both OSS and SaaS modes.
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Literal, Optional, overload

from sqlalchemy import text
from sqlmodel import Session

from app.db import engine
from app.services.order_book import OrderBookAnalyzer

logger = logging.getLogger(__name__)

# Module-level cache for floor price results
# Key: (card_id, treatment, days) -> (FloorPriceResult, timestamp)
_floor_cache: dict[tuple, tuple[Any, datetime]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = timedelta(minutes=5)


def _get_cached_floor(key: tuple) -> Optional[Any]:
    """Get cached floor price result if still valid."""
    with _cache_lock:
        if key in _floor_cache:
            result, timestamp = _floor_cache[key]
            if datetime.now(timezone.utc) - timestamp < _CACHE_TTL:
                return result
            # Expired - remove from cache
            del _floor_cache[key]
    return None


def _set_cached_floor(key: tuple, result: Any) -> None:
    """Cache a floor price result."""
    with _cache_lock:
        _floor_cache[key] = (result, datetime.now(timezone.utc))
        # Simple cache eviction: remove old entries if cache grows too large
        if len(_floor_cache) > 1000:
            now = datetime.now(timezone.utc)
            expired = [k for k, (_, ts) in _floor_cache.items() if now - ts >= _CACHE_TTL]
            for k in expired:
                del _floor_cache[k]


def clear_floor_cache() -> None:
    """Clear the floor price cache. Useful for testing."""
    with _cache_lock:
        _floor_cache.clear()


class FloorPriceSource(str, Enum):
    """Source of the floor price estimate."""

    SALES = "sales"  # Avg of lowest sales
    ORDER_BOOK = "order_book"  # Order book bucket analysis
    NONE = "none"  # No data available


class ConfidenceLevel(str, Enum):
    """Confidence level for floor price estimate."""

    HIGH = "high"  # >=4 sales OR order book confidence >0.7
    MEDIUM = "medium"  # 2-3 sales OR order book confidence 0.4-0.7
    LOW = "low"  # <2 sales OR order book confidence <0.4


@dataclass
class FloorPriceResult:
    """Result of hybrid floor price calculation."""

    price: Optional[float]
    source: FloorPriceSource
    confidence: ConfidenceLevel
    confidence_score: float  # Raw 0.0-1.0 score
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "price": self.price,
            "source": self.source.value,
            "confidence": self.confidence.value,
            "confidence_score": self.confidence_score,
            "metadata": self.metadata,
        }


class FloorPriceConfig:
    """Configuration for floor price estimation."""

    MIN_SALES_HIGH_CONFIDENCE: int = 4  # Minimum sales for HIGH confidence
    MIN_SALES_MEDIUM_CONFIDENCE: int = 3  # Minimum sales for MEDIUM confidence
    MIN_SALES_LOW_CONFIDENCE: int = 2  # Minimum sales for LOW confidence
    ORDER_BOOK_MIN_CONFIDENCE: float = 0.3  # Minimum OB confidence to use
    DEFAULT_LOOKBACK_DAYS: int = 30
    EXPANDED_LOOKBACK_DAYS: int = 90


class FloorPriceService:
    """
    Hybrid floor price service with decision tree.

    Decision tree:
    1. sales_count >= 4? -> SALES, HIGH confidence
    2. order_book confidence > 0.3? -> ORDER_BOOK, mapped confidence
    3. sales_count >= 2? -> SALES, LOW/MEDIUM confidence
    4. Expand to 90 days and retry
    5. Return NONE if still no data

    Example:
        service = FloorPriceService(session)
        result = service.get_floor_price(card_id=123, treatment="Classic Foil")
        if result.price:
            print(f"Floor: ${result.price:.2f} ({result.source.value})")
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self.config = FloorPriceConfig()
        self._order_book_analyzer: Optional[OrderBookAnalyzer] = None

    @property
    def order_book_analyzer(self) -> OrderBookAnalyzer:
        """Lazy-load OrderBookAnalyzer."""
        if self._order_book_analyzer is None:
            self._order_book_analyzer = OrderBookAnalyzer(self.session)
        return self._order_book_analyzer

    def get_floor_price(
        self,
        card_id: int,
        treatment: Optional[str] = None,
        days: int = FloorPriceConfig.DEFAULT_LOOKBACK_DAYS,
        include_blokpax: bool = True,
    ) -> FloorPriceResult:
        """
        Get hybrid floor price with fallback logic.

        Args:
            card_id: Database ID of the card
            treatment: Optional treatment filter (e.g., "Classic Foil")
            days: Lookback window for sales data
            include_blokpax: Include Blokpax sales in calculation

        Returns:
            FloorPriceResult with price, source, and confidence
        """
        # Check cache first
        cache_key = (card_id, treatment, days, include_blokpax)
        cached = _get_cached_floor(cache_key)
        if cached is not None:
            logger.debug(f"Floor price cache HIT for card_id={card_id}, treatment={treatment}")
            return cached

        # Step 1: Try sales floor (primary source)
        sales_result = self._get_sales_floor(card_id, treatment, days, include_blokpax)

        if sales_result and sales_result["count"] >= self.config.MIN_SALES_HIGH_CONFIDENCE:
            result = FloorPriceResult(
                price=sales_result["price"],
                source=FloorPriceSource.SALES,
                confidence=ConfidenceLevel.HIGH,
                confidence_score=1.0,
                metadata={
                    "sales_count": sales_result["count"],
                    "treatment": treatment,
                    "days": days,
                    "platforms": sales_result.get("platforms", []),
                },
            )
            _set_cached_floor(cache_key, result)
            return result

        # Step 2: Try order book floor (fallback)
        order_book_result = self.order_book_analyzer.estimate_floor(
            card_id=card_id,
            treatment=treatment,
            days=days,
            allow_sales_fallback=False,  # We handle sales ourselves
        )

        if order_book_result and order_book_result.confidence > self.config.ORDER_BOOK_MIN_CONFIDENCE:
            result = FloorPriceResult(
                price=order_book_result.floor_estimate,
                source=FloorPriceSource.ORDER_BOOK,
                confidence=self._map_confidence(order_book_result.confidence),
                confidence_score=order_book_result.confidence,
                metadata={
                    "bucket_depth": order_book_result.deepest_bucket.count,
                    "total_listings": order_book_result.total_listings,
                    "outliers_removed": order_book_result.outliers_removed,
                    "treatment": treatment,
                },
            )
            _set_cached_floor(cache_key, result)
            return result

        # Step 3: Try sales floor with fewer sales
        if sales_result and sales_result["count"] >= self.config.MIN_SALES_LOW_CONFIDENCE:
            confidence_score = sales_result["count"] / self.config.MIN_SALES_HIGH_CONFIDENCE
            confidence = (
                ConfidenceLevel.MEDIUM
                if sales_result["count"] >= self.config.MIN_SALES_MEDIUM_CONFIDENCE
                else ConfidenceLevel.LOW
            )
            result = FloorPriceResult(
                price=sales_result["price"],
                source=FloorPriceSource.SALES,
                confidence=confidence,
                confidence_score=confidence_score,
                metadata={
                    "sales_count": sales_result["count"],
                    "treatment": treatment,
                    "days": days,
                    "platforms": sales_result.get("platforms", []),
                },
            )
            _set_cached_floor(cache_key, result)
            return result

        # Step 4: Try expanded time window (90 days)
        # Note: Recursive call will cache its own result
        if days < self.config.EXPANDED_LOOKBACK_DAYS:
            return self.get_floor_price(
                card_id, treatment, self.config.EXPANDED_LOOKBACK_DAYS, include_blokpax
            )

        # Step 5: No data available
        result = FloorPriceResult(
            price=None,
            source=FloorPriceSource.NONE,
            confidence=ConfidenceLevel.LOW,
            confidence_score=0.0,
            metadata={"reason": "insufficient_data", "days_searched": days},
        )
        _set_cached_floor(cache_key, result)
        return result

    def _get_sales_floor(
        self,
        card_id: int,
        treatment: Optional[str],
        days: int,
        include_blokpax: bool = True,
    ) -> Optional[dict[str, Any]]:
        """
        Calculate sales floor as avg of up to 4 lowest sales.

        Combines eBay/OpenSea (marketprice) and Blokpax (blokpaxsale) data.

        Returns: {"price": float, "count": int, "platforms": list} or None
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        all_prices: list[tuple[float, str]] = []  # (price, platform)

        # Query marketprice (eBay, OpenSea)
        treatment_clause = "AND treatment = :treatment" if treatment else ""
        query = text(f"""
            SELECT price, platform
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
              AND is_bulk_lot = FALSE
              {treatment_clause}
            ORDER BY price ASC
            LIMIT :num_sales
        """)

        params: dict[str, Any] = {
            "card_id": card_id,
            "cutoff": cutoff,
            "num_sales": self.config.MIN_SALES_HIGH_CONFIDENCE,
        }
        if treatment:
            params["treatment"] = treatment

        try:
            if self.session:
                result = self.session.execute(query, params)
            else:
                with engine.connect() as conn:
                    result = conn.execute(query, params)

            for row in result.fetchall():
                all_prices.append((float(row[0]), row[1]))
        except Exception as e:
            logger.error(f"[FloorPrice] Failed to query marketprice for card {card_id}: {e}")

        # Query blokpaxsale if enabled
        if include_blokpax:
            bpx_query = text("""
                SELECT price_usd
                FROM blokpaxsale
                WHERE card_id = :card_id
                  AND filled_at >= :cutoff
                ORDER BY price_usd ASC
                LIMIT :num_sales
            """)

            try:
                if self.session:
                    result = self.session.execute(
                        bpx_query,
                        {"card_id": card_id, "cutoff": cutoff, "num_sales": self.config.MIN_SALES_HIGH_CONFIDENCE},
                    )
                else:
                    with engine.connect() as conn:
                        result = conn.execute(
                            bpx_query,
                            {"card_id": card_id, "cutoff": cutoff, "num_sales": self.config.MIN_SALES_HIGH_CONFIDENCE},
                        )

                for row in result.fetchall():
                    all_prices.append((float(row[0]), "blokpax"))
            except Exception as e:
                logger.error(f"[FloorPrice] Failed to query blokpaxsale for card {card_id}: {e}")

        if not all_prices:
            return None

        # Sort all prices and take lowest N
        all_prices.sort(key=lambda x: x[0])
        lowest = all_prices[: self.config.MIN_SALES_HIGH_CONFIDENCE]

        avg_price = sum(p[0] for p in lowest) / len(lowest)
        platforms = list(set(p[1] for p in lowest))

        return {
            "price": round(avg_price, 2),
            "count": len(lowest),
            "platforms": platforms,
        }

    def _map_confidence(self, score: float) -> ConfidenceLevel:
        """Map raw confidence score to ConfidenceLevel enum."""
        if score > 0.7:
            return ConfidenceLevel.HIGH
        elif score > 0.4:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.LOW

    @overload
    def get_floor_prices_batch(
        self,
        card_ids: list[int],
        days: int = ...,
        include_blokpax: bool = ...,
        by_variant: Literal[False] = ...,
    ) -> dict[int, FloorPriceResult]: ...

    @overload
    def get_floor_prices_batch(
        self,
        card_ids: list[int],
        days: int = ...,
        include_blokpax: bool = ...,
        by_variant: Literal[True] = ...,
    ) -> dict[tuple[int, str], FloorPriceResult]: ...

    def get_floor_prices_batch(
        self,
        card_ids: list[int],
        days: int = FloorPriceConfig.DEFAULT_LOOKBACK_DAYS,
        include_blokpax: bool = True,
        by_variant: bool = False,
    ) -> dict[int, FloorPriceResult] | dict[tuple[int, str], FloorPriceResult]:
        """
        Batch floor price calculation for multiple cards.

        For performance, uses bulk SQL queries instead of per-card lookups.
        Does NOT fall back to order book (sales-only for batch efficiency).

        Args:
            card_ids: List of card database IDs
            days: Lookback window for sales data
            include_blokpax: Include Blokpax sales in calculation
            by_variant: If True, group by (card_id, variant) instead of card_id

        Returns:
            If by_variant=False: dict[card_id, FloorPriceResult]
            If by_variant=True: dict[(card_id, variant), FloorPriceResult]
        """
        if not card_ids:
            return {}

        # Get batch sales floors
        sales_data = self._get_sales_floors_batch(
            card_ids, days, include_blokpax, by_variant
        )

        results: dict[Any, FloorPriceResult] = {}

        for key, data in sales_data.items():
            count = data["count"]
            if count >= self.config.MIN_SALES_HIGH_CONFIDENCE:
                confidence = ConfidenceLevel.HIGH
                confidence_score = 1.0
            elif count >= self.config.MIN_SALES_MEDIUM_CONFIDENCE:
                confidence = ConfidenceLevel.MEDIUM
                confidence_score = count / self.config.MIN_SALES_HIGH_CONFIDENCE
            elif count >= self.config.MIN_SALES_LOW_CONFIDENCE:
                confidence = ConfidenceLevel.LOW
                confidence_score = count / self.config.MIN_SALES_HIGH_CONFIDENCE
            else:
                # Not enough sales - skip (will not be in results)
                continue

            results[key] = FloorPriceResult(
                price=data["price"],
                source=FloorPriceSource.SALES,
                confidence=confidence,
                confidence_score=confidence_score,
                metadata={
                    "sales_count": count,
                    "days": days,
                    "platforms": data.get("platforms", []),
                    "variant": data.get("variant") if by_variant else None,
                },
            )

        return results

    def _get_sales_floors_batch(
        self,
        card_ids: list[int],
        days: int,
        include_blokpax: bool = True,
        by_variant: bool = False,
    ) -> dict[Any, dict[str, Any]]:
        """
        Batch calculate sales floors for multiple cards.

        Uses window functions to get lowest N sales per card efficiently.

        Returns:
            If by_variant=False: dict[card_id, {"price": float, "count": int, "platforms": list}]
            If by_variant=True: dict[(card_id, variant), {"price": float, "count": int, ...}]
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        results: dict[Any, dict[str, Any]] = {}

        # Build variant column expression
        variant_col = "COALESCE(NULLIF(product_subtype, ''), treatment)" if by_variant else "NULL"
        group_cols = "card_id, variant" if by_variant else "card_id"

        # Query marketprice (eBay, OpenSea) with window function
        query = text(f"""
            WITH ranked_sales AS (
                SELECT
                    card_id,
                    {variant_col} as variant,
                    price,
                    platform,
                    ROW_NUMBER() OVER (
                        PARTITION BY card_id{', ' + variant_col if by_variant else ''}
                        ORDER BY price ASC
                    ) as rn
                FROM marketprice
                WHERE card_id = ANY(:card_ids)
                  AND listing_type = 'sold'
                  AND COALESCE(sold_date, scraped_at) >= :cutoff
                  AND is_bulk_lot = FALSE
            )
            SELECT
                {group_cols},
                ROUND(AVG(price)::numeric, 2) as avg_price,
                COUNT(*) as sale_count,
                ARRAY_AGG(DISTINCT platform) as platforms
            FROM ranked_sales
            WHERE rn <= :num_sales
            GROUP BY {group_cols}
        """)

        try:
            if self.session:
                result = self.session.execute(
                    query,
                    {"card_ids": card_ids, "cutoff": cutoff, "num_sales": self.config.MIN_SALES_HIGH_CONFIDENCE},
                )
            else:
                with engine.connect() as conn:
                    result = conn.execute(
                        query,
                        {"card_ids": card_ids, "cutoff": cutoff, "num_sales": self.config.MIN_SALES_HIGH_CONFIDENCE},
                    )

            for row in result.fetchall():
                if by_variant:
                    key = (row[0], row[1])  # (card_id, variant)
                    results[key] = {
                        "price": float(row[2]),
                        "count": int(row[3]),
                        "platforms": list(row[4]) if row[4] else [],
                        "variant": row[1],
                    }
                else:
                    key = row[0]  # card_id
                    results[key] = {
                        "price": float(row[1]),
                        "count": int(row[2]),
                        "platforms": list(row[3]) if row[3] else [],
                    }
        except Exception as e:
            logger.error(f"[FloorPrice] Batch marketprice query failed: {e}")

        # Query blokpaxsale if enabled (no variant support - Blokpax doesn't track treatment)
        if include_blokpax:
            bpx_query = text("""
                WITH ranked_bpx AS (
                    SELECT
                        card_id,
                        price_usd as price,
                        ROW_NUMBER() OVER (PARTITION BY card_id ORDER BY price_usd ASC) as rn
                    FROM blokpaxsale
                    WHERE card_id = ANY(:card_ids)
                      AND filled_at >= :cutoff
                )
                SELECT
                    card_id,
                    ROUND(AVG(price)::numeric, 2) as avg_price,
                    COUNT(*) as sale_count
                FROM ranked_bpx
                WHERE rn <= :num_sales
                GROUP BY card_id
            """)

            try:
                if self.session:
                    bpx_result = self.session.execute(
                        bpx_query,
                        {"card_ids": card_ids, "cutoff": cutoff, "num_sales": self.config.MIN_SALES_HIGH_CONFIDENCE},
                    )
                else:
                    with engine.connect() as conn:
                        bpx_result = conn.execute(
                            bpx_query,
                            {"card_ids": card_ids, "cutoff": cutoff, "num_sales": self.config.MIN_SALES_HIGH_CONFIDENCE},
                        )

                for row in bpx_result.fetchall():
                    card_id = row[0]
                    bpx_price = float(row[1])
                    bpx_count = int(row[2])

                    if by_variant:
                        # For by_variant mode, add Blokpax to "Base" variant
                        key = (card_id, "Base")
                        if key in results:
                            # Merge with existing - recalculate avg
                            existing = results[key]
                            total_count = existing["count"] + bpx_count
                            merged_price = (existing["price"] * existing["count"] + bpx_price * bpx_count) / total_count
                            results[key] = {
                                "price": round(merged_price, 2),
                                "count": min(total_count, self.config.MIN_SALES_HIGH_CONFIDENCE),
                                "platforms": existing["platforms"] + ["blokpax"],
                                "variant": "Base",
                            }
                        else:
                            results[key] = {
                                "price": bpx_price,
                                "count": bpx_count,
                                "platforms": ["blokpax"],
                                "variant": "Base",
                            }
                    else:
                        # For card-level, merge with marketprice results
                        if card_id in results:
                            existing = results[card_id]
                            total_count = existing["count"] + bpx_count
                            merged_price = (existing["price"] * existing["count"] + bpx_price * bpx_count) / total_count
                            results[card_id] = {
                                "price": round(merged_price, 2),
                                "count": min(total_count, self.config.MIN_SALES_HIGH_CONFIDENCE),
                                "platforms": existing["platforms"] + ["blokpax"],
                            }
                        else:
                            results[card_id] = {
                                "price": bpx_price,
                                "count": bpx_count,
                                "platforms": ["blokpax"],
                            }
            except Exception as e:
                logger.error(f"[FloorPrice] Batch blokpaxsale query failed: {e}")

        return results


def get_floor_price_service(session: Optional[Session] = None) -> FloorPriceService:
    """Factory function to create FloorPriceService."""
    return FloorPriceService(session)


__all__ = [
    "FloorPriceService",
    "FloorPriceResult",
    "FloorPriceSource",
    "ConfidenceLevel",
    "FloorPriceConfig",
    "get_floor_price_service",
]
