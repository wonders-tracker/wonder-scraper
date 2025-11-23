"""
Price calculation service for market metrics.

Provides centralized calculation logic for:
- VWAP (Volume Weighted Average Price)
- EMA (Exponential Moving Average)
- Floor prices (by rarity, treatment)
- Price deltas
- Bid/Ask spreads
- Price-to-sale ratios
"""

from typing import Optional, List, Dict, Tuple
from datetime import datetime, timedelta
from sqlmodel import Session, select, func
from sqlalchemy import text
import statistics

from app.models.market import MarketPrice, MarketSnapshot
from app.models.card import Card, Rarity


class PriceCalculator:
    """Centralized price calculation service."""

    # Time period definitions
    TIME_PERIODS = {
        "1d": timedelta(days=1),
        "3d": timedelta(days=3),
        "7d": timedelta(days=7),
        "14d": timedelta(days=14),
        "30d": timedelta(days=30),
        "90d": timedelta(days=90),
        "all": None
    }

    def __init__(self, session: Session):
        self.session = session

    def _get_cutoff_time(self, period: str) -> Optional[datetime]:
        """Get cutoff datetime for a time period."""
        if period == "all" or period not in self.TIME_PERIODS:
            return None
        return datetime.utcnow() - self.TIME_PERIODS[period]

    # =========================================================================
    # VWAP Calculation
    # =========================================================================

    def calculate_vwap(
        self,
        card_id: int,
        period: str = "30d"
    ) -> Optional[float]:
        """
        Calculate Volume Weighted Average Price.

        Currently uses simple average since quantity per sale isn't tracked.
        Formula: AVG(price) for sold items in period

        Future: SUM(price * quantity) / SUM(quantity) when quantity is tracked
        """
        cutoff = self._get_cutoff_time(period)

        query = text("""
            SELECT AVG(price) as vwap
            FROM marketprice
            WHERE card_id = :card_id
            AND listing_type = 'sold'
            AND price > 0
            {}
        """.format("AND sold_date >= :cutoff" if cutoff else ""))

        params = {"card_id": card_id}
        if cutoff:
            params["cutoff"] = cutoff

        result = self.session.exec(query, params=params).first()
        return float(result[0]) if result and result[0] is not None else None

    # =========================================================================
    # EMA Calculation
    # =========================================================================

    def calculate_ema(
        self,
        card_id: int,
        period: str = "30d",
        window: int = 14
    ) -> Optional[float]:
        """
        Calculate Exponential Moving Average.

        Formula: EMA = Price(t) × k + EMA(y) × (1 - k)
        where k = 2 / (window + 1)

        Args:
            card_id: Card ID
            period: Time period to calculate over
            window: EMA window (7, 14, 30 typical)

        Returns:
            EMA value or None if insufficient data
        """
        cutoff = self._get_cutoff_time(period)

        # Get sold prices in chronological order
        query = select(MarketPrice.price, MarketPrice.sold_date).where(
            MarketPrice.card_id == card_id,
            MarketPrice.listing_type == "sold",
            MarketPrice.price > 0
        )

        if cutoff:
            query = query.where(MarketPrice.sold_date >= cutoff)

        query = query.order_by(MarketPrice.sold_date)

        results = self.session.exec(query).all()

        if not results or len(results) < window:
            return None

        prices = [float(r[0]) for r in results]

        # Calculate smoothing factor
        k = 2.0 / (window + 1)

        # Initialize EMA with SMA of first window prices
        ema = statistics.mean(prices[:window])

        # Calculate EMA for remaining prices
        for price in prices[window:]:
            ema = (price * k) + (ema * (1 - k))

        return round(ema, 2)

    # =========================================================================
    # Price Delta Calculation (FIXED)
    # =========================================================================

    def calculate_price_delta(
        self,
        card_id: int,
        period: str = "1d"
    ) -> Optional[float]:
        """
        Calculate price delta (percentage change) over period.

        Fixed implementation that uses actual sold prices at period boundaries,
        not snapshot aggregates.

        Method:
        1. Get last sold price before period start
        2. Get most recent sold price in period
        3. Calculate percentage change

        Returns:
            Percentage change (e.g., 5.25 for 5.25% increase)
        """
        cutoff = self._get_cutoff_time(period)

        if not cutoff:
            # For "all" period, use earliest vs latest
            query_old = text("""
                SELECT price FROM marketprice
                WHERE card_id = :card_id AND listing_type = 'sold'
                ORDER BY sold_date ASC NULLS LAST
                LIMIT 1
            """)
            query_new = text("""
                SELECT price FROM marketprice
                WHERE card_id = :card_id AND listing_type = 'sold'
                ORDER BY sold_date DESC NULLS LAST
                LIMIT 1
            """)
        else:
            # Price at start of period (before cutoff)
            query_old = text("""
                SELECT price FROM marketprice
                WHERE card_id = :card_id
                AND listing_type = 'sold'
                AND sold_date < :cutoff
                ORDER BY sold_date DESC NULLS LAST
                LIMIT 1
            """)

            # Price at end of period (most recent in period)
            query_new = text("""
                SELECT price FROM marketprice
                WHERE card_id = :card_id
                AND listing_type = 'sold'
                AND sold_date >= :cutoff
                ORDER BY sold_date DESC NULLS LAST
                LIMIT 1
            """)

        params = {"card_id": card_id}
        if cutoff:
            params["cutoff"] = cutoff

        old_result = self.session.exec(query_old, params=params).first()
        new_result = self.session.exec(query_new, params=params).first()

        if not old_result or not new_result:
            return None

        old_price = float(old_result[0])
        new_price = float(new_result[0])

        if old_price <= 0:
            return None

        delta = ((new_price - old_price) / old_price) * 100
        return round(delta, 2)

    # =========================================================================
    # Floor Price Calculation
    # =========================================================================

    def calculate_floor_by_rarity(
        self,
        rarity_id: Optional[int] = None,
        period: str = "30d",
        product_type: str = "Single"
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate floor prices by rarity.

        Returns:
            {
                "rarity_name": {
                    "floor": min_price,
                    "count": sale_count,
                    "avg": average_price
                }
            }
        """
        cutoff = self._get_cutoff_time(period)

        query = text("""
            SELECT r.name as rarity_name,
                   MIN(mp.price) as floor,
                   COUNT(*) as count,
                   AVG(mp.price) as avg
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN rarity r ON c.rarity_id = r.id
            WHERE mp.listing_type = 'sold'
            AND mp.price > 0
            AND c.product_type = :product_type
            {}
            {}
            GROUP BY r.name
            ORDER BY floor ASC
        """.format(
            "AND r.id = :rarity_id" if rarity_id else "",
            "AND mp.sold_date >= :cutoff" if cutoff else ""
        ))

        params = {"product_type": product_type}
        if rarity_id:
            params["rarity_id"] = rarity_id
        if cutoff:
            params["cutoff"] = cutoff

        results = self.session.exec(query, params=params).all()

        return {
            row[0]: {
                "floor": float(row[1]),
                "count": int(row[2]),
                "avg": float(row[3])
            }
            for row in results
        }

    def calculate_floor_by_treatment(
        self,
        treatment: Optional[str] = None,
        period: str = "30d",
        product_type: str = "Single"
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate floor prices by treatment.

        Returns:
            {
                "treatment_name": {
                    "floor": min_price,
                    "count": sale_count,
                    "avg": average_price
                }
            }
        """
        cutoff = self._get_cutoff_time(period)

        query = text("""
            SELECT mp.treatment,
                   MIN(mp.price) as floor,
                   COUNT(*) as count,
                   AVG(mp.price) as avg
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            WHERE mp.listing_type = 'sold'
            AND mp.price > 0
            AND c.product_type = :product_type
            {}
            {}
            GROUP BY mp.treatment
            ORDER BY floor ASC
        """.format(
            "AND mp.treatment = :treatment" if treatment else "",
            "AND mp.sold_date >= :cutoff" if cutoff else ""
        ))

        params = {"product_type": product_type}
        if treatment:
            params["treatment"] = treatment
        if cutoff:
            params["cutoff"] = cutoff

        results = self.session.exec(query, params=params).all()

        return {
            row[0]: {
                "floor": float(row[1]),
                "count": int(row[2]),
                "avg": float(row[3])
            }
            for row in results
        }

    def calculate_floor_by_combination(
        self,
        period: str = "30d",
        product_type: str = "Single",
        min_sales: int = 3
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate floor prices by rarity + treatment combination.

        Only returns combinations with at least min_sales transactions.
        """
        cutoff = self._get_cutoff_time(period)

        query = text("""
            SELECT r.name || '_' || mp.treatment as combination,
                   MIN(mp.price) as floor,
                   COUNT(*) as count,
                   AVG(mp.price) as avg
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN rarity r ON c.rarity_id = r.id
            WHERE mp.listing_type = 'sold'
            AND mp.price > 0
            AND c.product_type = :product_type
            {}
            GROUP BY r.name, mp.treatment
            HAVING COUNT(*) >= :min_sales
            ORDER BY floor DESC
        """.format("AND mp.sold_date >= :cutoff" if cutoff else ""))

        params = {"product_type": product_type, "min_sales": min_sales}
        if cutoff:
            params["cutoff"] = cutoff

        results = self.session.exec(query, params=params).all()

        return {
            row[0]: {
                "floor": float(row[1]),
                "count": int(row[2]),
                "avg": float(row[3])
            }
            for row in results
        }

    # =========================================================================
    # Bid/Ask Spread Calculation
    # =========================================================================

    def calculate_bid_ask_spread(
        self,
        card_id: int
    ) -> Optional[Dict[str, float]]:
        """
        Calculate bid/ask spread for a card.

        Returns:
            {
                "lowest_ask": float,
                "highest_bid": float,
                "spread_amount": float,
                "spread_percent": float
            }
        """
        # Get latest snapshot for bid/ask data
        snapshot = self.session.exec(
            select(MarketSnapshot)
            .where(MarketSnapshot.card_id == card_id)
            .order_by(MarketSnapshot.timestamp.desc())
        ).first()

        if not snapshot or not snapshot.lowest_ask:
            return None

        # For bid, we need to check active listings with bids
        # Since we don't have separate bid tracking, use highest_bid from snapshot
        bid = snapshot.highest_bid or 0
        ask = snapshot.lowest_ask

        if ask <= 0:
            return None

        spread_amount = ask - bid
        spread_percent = (spread_amount / ask) * 100 if ask > 0 else 0

        return {
            "lowest_ask": float(ask),
            "highest_bid": float(bid) if bid else 0,
            "spread_amount": float(spread_amount),
            "spread_percent": round(spread_percent, 2)
        }

    # =========================================================================
    # Price-to-Sale Ratio
    # =========================================================================

    def calculate_price_to_sale(
        self,
        card_id: int,
        period: str = "30d"
    ) -> Optional[float]:
        """
        Calculate price-to-sale ratio.

        Formula: current_lowest_ask / vwap

        Interpretation:
        - < 1.0: Good deal (below average)
        - = 1.0: Fair price
        - > 1.0: Premium price
        """
        vwap = self.calculate_vwap(card_id, period)

        if not vwap or vwap <= 0:
            return None

        # Get current lowest ask
        snapshot = self.session.exec(
            select(MarketSnapshot)
            .where(MarketSnapshot.card_id == card_id)
            .order_by(MarketSnapshot.timestamp.desc())
        ).first()

        if not snapshot or not snapshot.lowest_ask or snapshot.lowest_ask <= 0:
            return None

        ratio = snapshot.lowest_ask / vwap
        return round(ratio, 2)

    # =========================================================================
    # Time Series Data
    # =========================================================================

    def get_time_series(
        self,
        card_id: Optional[int] = None,
        interval: str = "1d",  # 1d, 1w, 1m
        period: str = "30d",
        product_type: Optional[str] = None
    ) -> List[Dict]:
        """
        Get aggregated price data over time.

        Args:
            card_id: Specific card (None for all cards of product_type)
            interval: Data point interval (1d, 1w, 1m)
            period: Total time range
            product_type: Filter by product type if card_id is None

        Returns:
            List of time series data points with VWAP, volume, floor
        """
        cutoff = self._get_cutoff_time(period)

        # Determine PostgreSQL date_trunc interval
        trunc_interval = {
            "1d": "day",
            "1w": "week",
            "1m": "month"
        }.get(interval, "day")

        if card_id:
            # Single card time series
            query = text("""
                SELECT
                    DATE_TRUNC(:interval, sold_date) as date,
                    AVG(price) as vwap,
                    MIN(price) as floor,
                    MAX(price) as ceiling,
                    COUNT(*) as volume
                FROM marketprice
                WHERE card_id = :card_id
                AND listing_type = 'sold'
                AND price > 0
                {}
                GROUP BY DATE_TRUNC(:interval, sold_date)
                ORDER BY date ASC
            """.format("AND sold_date >= :cutoff" if cutoff else ""))

            params = {"card_id": card_id, "interval": trunc_interval}
            if cutoff:
                params["cutoff"] = cutoff
        else:
            # Aggregate time series for product type
            query = text("""
                SELECT
                    DATE_TRUNC(:interval, mp.sold_date) as date,
                    AVG(mp.price) as vwap,
                    MIN(mp.price) as floor,
                    MAX(mp.price) as ceiling,
                    COUNT(*) as volume
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.price > 0
                {}
                {}
                GROUP BY DATE_TRUNC(:interval, mp.sold_date)
                ORDER BY date ASC
            """.format(
                "AND c.product_type = :product_type" if product_type else "",
                "AND mp.sold_date >= :cutoff" if cutoff else ""
            ))

            params = {"interval": trunc_interval}
            if product_type:
                params["product_type"] = product_type
            if cutoff:
                params["cutoff"] = cutoff

        results = self.session.exec(query, params=params).all()

        return [
            {
                "date": row[0].isoformat() if row[0] else None,
                "vwap": float(row[1]) if row[1] else 0,
                "floor": float(row[2]) if row[2] else 0,
                "ceiling": float(row[3]) if row[3] else 0,
                "volume": int(row[4]) if row[4] else 0
            }
            for row in results
        ]

    # =========================================================================
    # Comprehensive Market Data
    # =========================================================================

    def get_comprehensive_metrics(
        self,
        card_id: int,
        period: str = "30d"
    ) -> Dict:
        """
        Get all calculated metrics for a card in one call.

        Useful for API endpoints that need complete data.
        """
        vwap = self.calculate_vwap(card_id, period)

        return {
            "vwap": vwap,
            "ema_7d": self.calculate_ema(card_id, period, window=7),
            "ema_14d": self.calculate_ema(card_id, period, window=14),
            "ema_30d": self.calculate_ema(card_id, period, window=30),
            "price_delta_1d": self.calculate_price_delta(card_id, "1d"),
            "price_delta_7d": self.calculate_price_delta(card_id, "7d"),
            "price_delta_30d": self.calculate_price_delta(card_id, "30d"),
            "bid_ask_spread": self.calculate_bid_ask_spread(card_id),
            "price_to_sale": self.calculate_price_to_sale(card_id, period)
        }
