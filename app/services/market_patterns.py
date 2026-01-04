"""
Market Patterns Service

Provides learned market patterns for pricing algorithms:
- Treatment multipliers (vs Classic Paper baseline)
- Rarity multipliers
- Card volatility scores
- Deal detection thresholds

Multipliers are derived from historical analysis (see scripts/discover_market_patterns.py).
"""

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import text
from sqlmodel import Session

from app.db import engine

logger = logging.getLogger(__name__)

# Module-level cache for volatility results
# Key: (card_id, treatment, days) -> (CardVolatility, timestamp)
_volatility_cache: dict[tuple, tuple[Any, datetime]] = {}
_cache_lock = threading.Lock()
_CACHE_TTL = timedelta(minutes=5)
_CACHE_MAX_SIZE = 1000


def _get_cached_volatility(key: tuple) -> Optional[Any]:
    """Get cached volatility result if still valid."""
    with _cache_lock:
        if key in _volatility_cache:
            result, timestamp = _volatility_cache[key]
            if datetime.now(timezone.utc) - timestamp < _CACHE_TTL:
                return result
            # Expired - remove from cache
            del _volatility_cache[key]
    return None


def _set_cached_volatility(key: tuple, result: Any) -> None:
    """Cache a volatility result with TTL and max-size eviction."""
    with _cache_lock:
        _volatility_cache[key] = (result, datetime.now(timezone.utc))
        # Evict expired entries when cache grows too large
        if len(_volatility_cache) > _CACHE_MAX_SIZE:
            now = datetime.now(timezone.utc)
            expired = [k for k, (_, ts) in _volatility_cache.items() if now - ts >= _CACHE_TTL]
            for k in expired:
                del _volatility_cache[k]


def clear_volatility_cache() -> None:
    """Clear the volatility cache. Useful for testing."""
    with _cache_lock:
        _volatility_cache.clear()


# Treatment multipliers derived from market analysis
# Relative to Classic Paper = 1.0
TREATMENT_MULTIPLIERS: dict[str, float] = {
    "Classic Paper": 1.0,
    "Classic Foil": 1.55,
    "Classic Foil Alt Art": 1.9,  # Estimated from limited data
    "Formless Foil": 6.72,
    "Graded/Preslab": 16.46,
    "Promo": 26.69,
    "Serialized": 42.71,
    "Stonefoil": 115.0,  # $1500 / $13 median Classic Paper
    "Error/Errata": 4.0,  # Limited data, conservative estimate
}

# Rarity multipliers (within same treatment)
# Relative to Common = 1.0
RARITY_MULTIPLIERS: dict[str, float] = {
    "Common": 1.0,
    "Uncommon": 1.31,
    "Rare": 1.95,
    "Epic": 3.73,
    "Mythic": 14.91,
    "Secret Mythic": 20.0,  # Estimated
}

# Default volatility (CV) when no data available
DEFAULT_VOLATILITY = 0.5

# Volatility thresholds for deal detection
VOLATILITY_THRESHOLDS = {
    "stable": 0.3,  # CV < 0.3: stable pricing
    "moderate": 0.5,  # CV 0.3-0.5: moderate volatility
    "volatile": 1.0,  # CV > 0.5: high volatility
}


@dataclass
class CardVolatility:
    """Volatility metrics for a card/treatment combination."""

    card_id: int
    treatment: Optional[str]
    coefficient_of_variation: float  # CV = std / mean
    price_range_pct: float  # (max - min) / min
    sales_count: int

    @property
    def is_stable(self) -> bool:
        return self.coefficient_of_variation < VOLATILITY_THRESHOLDS["stable"]

    @property
    def is_volatile(self) -> bool:
        return self.coefficient_of_variation > VOLATILITY_THRESHOLDS["moderate"]

    @property
    def deal_threshold(self) -> float:
        """
        Dynamic deal threshold based on volatility.

        Stable cards: 15% below floor = deal
        Moderate: 25% below floor = deal
        Volatile: 40% below floor = deal
        """
        if self.is_stable:
            return 0.15
        elif self.is_volatile:
            return 0.40
        else:
            return 0.25


class MarketPatternsService:
    """
    Service for market pattern lookups and calculations.

    Provides:
    - Treatment/rarity multiplier lookups
    - Card volatility calculation
    - Deal detection thresholds
    - Floor estimation fallbacks
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session

    def get_treatment_multiplier(
        self,
        treatment: str,
        base_treatment: str = "Classic Paper",
    ) -> float:
        """
        Get price multiplier for a treatment relative to base.

        Example:
            multiplier = service.get_treatment_multiplier("Formless Foil")
            # Returns 6.72 (Formless Foil is ~6.72x Classic Paper)
        """
        target = TREATMENT_MULTIPLIERS.get(treatment, 1.0)
        base = TREATMENT_MULTIPLIERS.get(base_treatment, 1.0)
        return round(target / base, 2)

    def get_rarity_multiplier(
        self,
        rarity: str,
        base_rarity: str = "Common",
    ) -> float:
        """
        Get price multiplier for a rarity relative to base.

        Example:
            multiplier = service.get_rarity_multiplier("Mythic")
            # Returns 14.91 (Mythic is ~14.91x Common)
        """
        target = RARITY_MULTIPLIERS.get(rarity, 1.0)
        base = RARITY_MULTIPLIERS.get(base_rarity, 1.0)
        return round(target / base, 2)

    def estimate_from_treatment_multiplier(
        self,
        known_price: float,
        known_treatment: str,
        target_treatment: str,
    ) -> Optional[float]:
        """
        Estimate price for a treatment based on another treatment's known price.

        Example:
            # Classic Paper is $10, estimate Formless Foil
            estimated = service.estimate_from_treatment_multiplier(10.0, "Classic Paper", "Formless Foil")
            # Returns 67.20 ($10 * 6.72)
        """
        if known_treatment not in TREATMENT_MULTIPLIERS:
            return None
        if target_treatment not in TREATMENT_MULTIPLIERS:
            return None

        multiplier = self.get_treatment_multiplier(target_treatment, known_treatment)
        return round(known_price * multiplier, 2)

    def get_card_volatility(
        self,
        card_id: int,
        treatment: Optional[str] = None,
        days: int = 90,
    ) -> CardVolatility:
        """
        Calculate volatility metrics for a card/treatment.

        Uses coefficient of variation (CV = std/mean) as primary metric.

        Args:
            card_id: Database ID of the card
            treatment: Optional treatment filter
            days: Lookback window for sales data

        Returns:
            CardVolatility with CV, range %, and deal threshold
        """
        cache_key = (card_id, treatment, days)
        cached = _get_cached_volatility(cache_key)
        if cached is not None:
            return cached

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        treatment_clause = "AND treatment = :treatment" if treatment else ""
        query = text(f"""
            SELECT
                AVG(price) as mean_price,
                STDDEV(price) as std_price,
                MIN(price) as min_price,
                MAX(price) as max_price,
                COUNT(*) as sales_count
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
              AND is_bulk_lot = FALSE
              {treatment_clause}
        """)

        params: dict = {"card_id": card_id, "cutoff": cutoff}
        if treatment:
            params["treatment"] = treatment

        try:
            if self.session:
                result = self.session.execute(query, params)
            else:
                with engine.connect() as conn:
                    result = conn.execute(query, params)

            row = result.fetchone()

            if row and row[0] and row[4] >= 3:  # Need at least 3 sales for CV
                mean_price = float(row[0])
                std_price = float(row[1]) if row[1] else 0.0
                min_price = float(row[2])
                max_price = float(row[3])
                sales_count = int(row[4])

                cv = std_price / mean_price if mean_price > 0 else DEFAULT_VOLATILITY
                range_pct = ((max_price - min_price) / min_price * 100) if min_price > 0 else 0

                volatility = CardVolatility(
                    card_id=card_id,
                    treatment=treatment,
                    coefficient_of_variation=round(cv, 3),
                    price_range_pct=round(range_pct, 1),
                    sales_count=sales_count,
                )
            else:
                # Not enough data - return default
                volatility = CardVolatility(
                    card_id=card_id,
                    treatment=treatment,
                    coefficient_of_variation=DEFAULT_VOLATILITY,
                    price_range_pct=0.0,
                    sales_count=int(row[4]) if row and row[4] else 0,
                )

            _set_cached_volatility(cache_key, volatility)
            return volatility

        except Exception as e:
            logger.error(f"[MarketPatterns] Failed to calculate volatility for card {card_id}: {e}")
            return CardVolatility(
                card_id=card_id,
                treatment=treatment,
                coefficient_of_variation=DEFAULT_VOLATILITY,
                price_range_pct=0.0,
                sales_count=0,
            )

    def is_deal(
        self,
        card_id: int,
        treatment: Optional[str],
        price: float,
        floor_price: float,
    ) -> tuple[bool, float]:
        """
        Check if a price is a deal based on card-specific volatility.

        Returns:
            (is_deal: bool, discount_pct: float)
        """
        if floor_price <= 0 or price <= 0:
            return False, 0.0

        discount_pct = (floor_price - price) / floor_price
        volatility = self.get_card_volatility(card_id, treatment)
        threshold = volatility.deal_threshold

        return discount_pct >= threshold, round(discount_pct * 100, 1)

    def get_available_treatments_for_card(
        self,
        card_id: int,
        days: int = 90,
    ) -> dict[str, dict]:
        """
        Get all treatments with sales data for a card.

        Returns:
            dict[treatment, {"floor": float, "count": int}]
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = text("""
            WITH ranked AS (
                SELECT
                    treatment,
                    price,
                    ROW_NUMBER() OVER (PARTITION BY treatment ORDER BY price ASC) as rn,
                    COUNT(*) OVER (PARTITION BY treatment) as treatment_count
                FROM marketprice
                WHERE card_id = :card_id
                  AND listing_type = 'sold'
                  AND COALESCE(sold_date, scraped_at) >= :cutoff
                  AND is_bulk_lot = FALSE
                  AND treatment IS NOT NULL
            )
            SELECT
                treatment,
                ROUND(AVG(price)::numeric, 2) as floor_price,
                MAX(treatment_count) as sales_count
            FROM ranked
            WHERE rn <= 4
            GROUP BY treatment
        """)

        try:
            if self.session:
                result = self.session.execute(query, {"card_id": card_id, "cutoff": cutoff})
            else:
                with engine.connect() as conn:
                    result = conn.execute(query, {"card_id": card_id, "cutoff": cutoff})

            return {row[0]: {"floor": float(row[1]), "count": int(row[2])} for row in result.fetchall()}
        except Exception as e:
            logger.error(f"[MarketPatterns] Failed to get treatments for card {card_id}: {e}")
            return {}


@dataclass
class DealResult:
    """Result of deal detection analysis."""

    is_deal: bool
    card_id: int
    treatment: Optional[str]
    price: float
    floor_price: float
    discount_pct: float  # e.g., 25.0 for 25% below floor
    threshold_pct: float  # e.g., 15.0 for cards with 15% deal threshold
    volatility_cv: float
    deal_quality: str  # "hot", "good", "marginal", "not_a_deal"

    def to_dict(self) -> dict:
        return {
            "is_deal": self.is_deal,
            "card_id": self.card_id,
            "treatment": self.treatment,
            "price": self.price,
            "floor_price": self.floor_price,
            "discount_pct": self.discount_pct,
            "threshold_pct": self.threshold_pct,
            "volatility_cv": self.volatility_cv,
            "deal_quality": self.deal_quality,
        }


class DealDetector:
    """
    Smart deal detection with card-specific thresholds.

    Uses historical volatility to set appropriate deal thresholds:
    - Stable cards (CV < 0.3): 15% below floor = deal
    - Moderate volatility (CV 0.3-0.5): 25% below floor = deal
    - Volatile cards (CV > 0.5): 40% below floor = deal

    This prevents false positives for volatile cards where large price
    swings are normal, while catching real deals on stable cards.
    """

    def __init__(self, session: Optional[Session] = None):
        self.session = session
        self._market_patterns = MarketPatternsService(session)
        self._floor_service = None

    @property
    def floor_service(self):
        """Lazy-load FloorPriceService to avoid circular imports."""
        if self._floor_service is None:
            from app.services.floor_price import FloorPriceService

            self._floor_service = FloorPriceService(self.session)
        return self._floor_service

    def check_deal(
        self,
        card_id: int,
        price: float,
        treatment: Optional[str] = None,
        floor_price: Optional[float] = None,
    ) -> DealResult:
        """
        Check if a price qualifies as a deal.

        Args:
            card_id: Database ID of the card
            price: The listing/sale price to check
            treatment: Optional treatment filter
            floor_price: Optional pre-calculated floor (will be fetched if not provided)

        Returns:
            DealResult with deal status and metrics
        """
        # Get floor price if not provided
        if floor_price is None:
            floor_result = self.floor_service.get_floor_price(card_id, treatment)
            floor_price = floor_result.price if floor_result.price else 0.0

        if floor_price <= 0 or price <= 0:
            return DealResult(
                is_deal=False,
                card_id=card_id,
                treatment=treatment,
                price=price,
                floor_price=floor_price or 0.0,
                discount_pct=0.0,
                threshold_pct=0.0,
                volatility_cv=0.5,
                deal_quality="not_a_deal",
            )

        # Get volatility for threshold calculation
        volatility = self._market_patterns.get_card_volatility(card_id, treatment)
        threshold = volatility.deal_threshold
        threshold_pct = threshold * 100

        # Calculate discount
        discount = (floor_price - price) / floor_price
        discount_pct = round(discount * 100, 1)

        # Determine deal quality
        is_deal = discount >= threshold
        if discount >= threshold * 2:  # Double the threshold = hot deal
            deal_quality = "hot"
        elif discount >= threshold * 1.5:
            deal_quality = "good"
        elif is_deal:
            deal_quality = "marginal"
        else:
            deal_quality = "not_a_deal"

        return DealResult(
            is_deal=is_deal,
            card_id=card_id,
            treatment=treatment,
            price=price,
            floor_price=floor_price,
            discount_pct=discount_pct,
            threshold_pct=round(threshold_pct, 1),
            volatility_cv=volatility.coefficient_of_variation,
            deal_quality=deal_quality,
        )

    def find_deals_in_listings(
        self,
        listings: list[dict],
        min_quality: str = "marginal",
    ) -> list[DealResult]:
        """
        Scan a list of listings for deals.

        Args:
            listings: List of dicts with card_id, price, treatment (optional)
            min_quality: Minimum deal quality ("marginal", "good", "hot")

        Returns:
            List of DealResult for qualifying deals, sorted by discount
        """
        quality_order = {"not_a_deal": 0, "marginal": 1, "good": 2, "hot": 3}
        min_quality_level = quality_order.get(min_quality, 1)

        deals = []
        for listing in listings:
            result = self.check_deal(
                card_id=listing["card_id"],
                price=listing["price"],
                treatment=listing.get("treatment"),
                floor_price=listing.get("floor_price"),
            )

            if quality_order.get(result.deal_quality, 0) >= min_quality_level:
                deals.append(result)

        # Sort by discount (best deals first)
        deals.sort(key=lambda d: d.discount_pct, reverse=True)
        return deals


def get_market_patterns_service(session: Optional[Session] = None) -> MarketPatternsService:
    """Factory function to create MarketPatternsService."""
    return MarketPatternsService(session)


def get_deal_detector(session: Optional[Session] = None) -> DealDetector:
    """Factory function to create DealDetector."""
    return DealDetector(session)


__all__ = [
    "MarketPatternsService",
    "CardVolatility",
    "DealDetector",
    "DealResult",
    "TREATMENT_MULTIPLIERS",
    "RARITY_MULTIPLIERS",
    "get_market_patterns_service",
    "get_deal_detector",
    "clear_volatility_cache",
]
