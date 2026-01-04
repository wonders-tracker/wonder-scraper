"""
Order Book Confidence Calculation Module

Provides standalone confidence calculation for floor price estimates.
Used by both the OrderBook service and backtest scripts to avoid duplication.
"""

from math import log2

# Default weights for confidence calculation (v2.1)
DEFAULT_LISTING_COUNT_WEIGHT: float = 0.35
DEFAULT_SPREAD_WEIGHT: float = 0.25
DEFAULT_RECENCY_WEIGHT: float = 0.25
DEFAULT_VOLATILITY_WEIGHT: float = 0.15


def calculate_orderbook_confidence(
    total_listings: int,
    spread_pct: float,
    stale_count: int = 0,
    volatility_cv: float = 0.5,
    listing_count_weight: float = DEFAULT_LISTING_COUNT_WEIGHT,
    spread_weight: float = DEFAULT_SPREAD_WEIGHT,
    recency_weight: float = DEFAULT_RECENCY_WEIGHT,
    volatility_weight: float = DEFAULT_VOLATILITY_WEIGHT,
) -> float:
    """
    Calculate confidence score for floor estimate (v2.1 - with volatility).

    Confidence is based on four factors:
    1. Listing count (more listings = higher confidence, with diminishing returns)
    2. Price spread (tighter spread = higher confidence)
    3. Recency (fewer stale listings = higher confidence)
    4. Volatility (stable cards = higher confidence in floor estimate)

    Args:
        total_listings: Number of listings used in the estimate
        spread_pct: Price spread as percentage of lowest price
        stale_count: Number of listings older than the staleness threshold
        volatility_cv: Coefficient of variation (0 = stable, 1+ = volatile)
        listing_count_weight: Weight for listing count factor (default 0.35)
        spread_weight: Weight for spread factor (default 0.25)
        recency_weight: Weight for recency factor (default 0.25)
        volatility_weight: Weight for volatility factor (default 0.15)

    Returns:
        Confidence score between 0.0 and 1.0
    """
    if total_listings == 0:
        return 0.0

    # 1. Listing count score (logarithmic - diminishing returns)
    # 1 listing = 0.3, 3 listings = 0.5, 10 listings = 0.7, 30+ = 0.9
    count_score = min(0.9, 0.3 + 0.2 * log2(max(1, total_listings)))

    # 2. Spread score (lower spread = higher confidence)
    # 0% spread = 1.0, 50% spread = 0.5, 100%+ spread = 0.2
    spread_score = _calculate_spread_score(spread_pct)

    # 3. Recency score (fewer stale = higher confidence)
    stale_ratio = stale_count / total_listings
    recency_score = 1.0 - (stale_ratio * 0.5)  # Max 50% penalty for all stale

    # 4. Volatility score (lower CV = higher confidence)
    volatility_score = _calculate_volatility_score(volatility_cv)

    # Weighted combination
    confidence = (
        listing_count_weight * count_score
        + spread_weight * spread_score
        + recency_weight * recency_score
        + volatility_weight * volatility_score
    )

    return round(min(1.0, max(0.0, confidence)), 3)


def _calculate_spread_score(spread_pct: float) -> float:
    """
    Calculate spread component of confidence score.

    Args:
        spread_pct: Price spread as percentage of lowest price

    Returns:
        Score between 0.0 and 1.0
    """
    if spread_pct <= 0:
        return 1.0
    elif spread_pct <= 20:
        return 1.0 - (spread_pct / 40)  # 0-20% -> 1.0-0.5
    elif spread_pct <= 50:
        return 0.5 - ((spread_pct - 20) / 60)  # 20-50% -> 0.5-0.0
    else:
        return max(0.0, 0.2 - (spread_pct - 50) / 500)  # 50%+ -> small penalty


def _calculate_volatility_score(volatility_cv: float) -> float:
    """
    Calculate volatility component of confidence score.

    Args:
        volatility_cv: Coefficient of variation (0 = stable, 1+ = volatile)

    Returns:
        Score between 0.2 and 1.0
    """
    # CV 0.0 = 1.0 (very stable), CV 0.3 = 0.85, CV 0.5 = 0.5, CV 1.0+ = 0.2
    if volatility_cv <= 0.3:
        return 1.0 - (volatility_cv * 0.5)  # 0-0.3 -> 1.0-0.85
    elif volatility_cv <= 0.5:
        return 0.85 - ((volatility_cv - 0.3) * 1.75)  # 0.3-0.5 -> 0.85-0.5
    else:
        return max(0.2, 0.5 - (volatility_cv - 0.5) * 0.6)  # 0.5+ -> 0.5-0.2


__all__ = [
    "calculate_orderbook_confidence",
    "DEFAULT_LISTING_COUNT_WEIGHT",
    "DEFAULT_SPREAD_WEIGHT",
    "DEFAULT_RECENCY_WEIGHT",
    "DEFAULT_VOLATILITY_WEIGHT",
]
