"""
Floor Price Service

Hybrid floor price estimation using a decision tree:
1. Try sales floor first (avg of 4 lowest sales)
2. Fall back to order book floor (OrderBookAnalyzer)
3. Return null if neither available

This service is available in both OSS and SaaS modes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Optional

from sqlalchemy import text
from sqlmodel import Session

from app.db import engine
from app.services.order_book import OrderBookAnalyzer

logger = logging.getLogger(__name__)


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
        # Step 1: Try sales floor (primary source)
        sales_result = self._get_sales_floor(card_id, treatment, days, include_blokpax)

        if sales_result and sales_result["count"] >= self.config.MIN_SALES_HIGH_CONFIDENCE:
            return FloorPriceResult(
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

        # Step 2: Try order book floor (fallback)
        order_book_result = self.order_book_analyzer.estimate_floor(
            card_id=card_id,
            treatment=treatment,
            days=days,
            allow_sales_fallback=False,  # We handle sales ourselves
        )

        if order_book_result and order_book_result.confidence > self.config.ORDER_BOOK_MIN_CONFIDENCE:
            return FloorPriceResult(
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

        # Step 3: Try sales floor with fewer sales
        if sales_result and sales_result["count"] >= self.config.MIN_SALES_LOW_CONFIDENCE:
            confidence_score = sales_result["count"] / self.config.MIN_SALES_HIGH_CONFIDENCE
            confidence = (
                ConfidenceLevel.MEDIUM
                if sales_result["count"] >= self.config.MIN_SALES_MEDIUM_CONFIDENCE
                else ConfidenceLevel.LOW
            )
            return FloorPriceResult(
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

        # Step 4: Try expanded time window (90 days)
        if days < self.config.EXPANDED_LOOKBACK_DAYS:
            return self.get_floor_price(
                card_id, treatment, self.config.EXPANDED_LOOKBACK_DAYS, include_blokpax
            )

        # Step 5: No data available
        return FloorPriceResult(
            price=None,
            source=FloorPriceSource.NONE,
            confidence=ConfidenceLevel.LOW,
            confidence_score=0.0,
            metadata={"reason": "insufficient_data", "days_searched": days},
        )

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
