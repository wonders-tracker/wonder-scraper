"""
Fair Market Price (FMP) Calculation Service

FMP = BaseSetPrice × RarityMultiplier × TreatmentMultiplier × ConditionMultiplier × LiquidityAdjustment

Floor Price = Average of last 4 lowest sales (30-day window)
"""

from typing import Optional, Dict, Any, List
from sqlmodel import Session, text
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

# Treatment categories for base price calculation
BASE_TREATMENTS = ['Classic Paper', 'Classic Foil']

# Default multipliers when no data available
DEFAULT_RARITY_MULTIPLIERS = {
    'Common': 1.0,
    'Uncommon': 1.5,
    'Rare': 3.0,
    'Legendary': 8.0,
    'Mythic': 20.0,
    'Sealed': 1.0,  # For sealed products
}

DEFAULT_TREATMENT_MULTIPLIERS = {
    'Classic Paper': 1.0,
    'Classic Foil': 1.3,
    'Stonefoil': 2.0,
    'Formless Foil': 3.5,
    'Prerelease': 2.0,
    'Promo': 2.0,
    'OCM Serialized': 10.0,
    'Sealed': 1.0,
    'Factory Sealed': 1.0,
}


class FairMarketPriceService:
    """Service for calculating Fair Market Price and Floor Price."""

    def __init__(self, session: Session):
        self.session = session
        # In-memory caches for batch operations (cleared per request)
        self._base_price_cache: Dict[str, Optional[float]] = {}
        self._rarity_mult_cache: Dict[str, float] = {}

    def get_base_set_price(self, set_name: str, days: int = 30) -> Optional[float]:
        """
        Calculate base set price as median of Classic Paper Common sales.
        This is the reference point for FMP calculations.
        """
        cache_key = f"{set_name}:{days}"
        if cache_key in self._base_price_cache:
            return self._base_price_cache[cache_key]

        cutoff = datetime.utcnow() - timedelta(days=days)

        query = text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN rarity r ON c.rarity_id = r.id
            WHERE c.set_name = :set_name
              AND r.name = 'Common'
              AND mp.treatment IN ('Classic Paper', 'Classic Foil')
              AND mp.listing_type = 'sold'
              AND COALESCE(mp.sold_date, mp.scraped_at) >= :cutoff
        """)

        result = self.session.execute(query, {"set_name": set_name, "cutoff": cutoff}).fetchone()

        if result and result[0]:
            price = float(result[0])
            self._base_price_cache[cache_key] = price
            return price

        # Fallback: try 90 days
        if days == 30:
            result = self.get_base_set_price(set_name, days=90)
            self._base_price_cache[cache_key] = result
            return result

        self._base_price_cache[cache_key] = None
        return None

    def get_rarity_multiplier(self, set_name: str, rarity_name: str, days: int = 30) -> float:
        """
        Calculate rarity multiplier dynamically from sales data.
        Multiplier = median_price(rarity) / median_price(Common)
        """
        if rarity_name == 'Common':
            return 1.0

        cache_key = f"{set_name}:{rarity_name}:{days}"
        if cache_key in self._rarity_mult_cache:
            return self._rarity_mult_cache[cache_key]

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get median for Common (base)
        common_query = text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN rarity r ON c.rarity_id = r.id
            WHERE c.set_name = :set_name
              AND r.name = 'Common'
              AND mp.treatment IN ('Classic Paper', 'Classic Foil')
              AND mp.listing_type = 'sold'
              AND COALESCE(mp.sold_date, mp.scraped_at) >= :cutoff
            HAVING COUNT(*) >= 3
        """)

        common_result = self.session.execute(common_query, {"set_name": set_name, "cutoff": cutoff}).fetchone()
        common_median = float(common_result[0]) if common_result and common_result[0] else None

        if not common_median:
            return DEFAULT_RARITY_MULTIPLIERS.get(rarity_name, 1.0)

        # Get median for target rarity
        rarity_query = text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN rarity r ON c.rarity_id = r.id
            WHERE c.set_name = :set_name
              AND r.name = :rarity_name
              AND mp.treatment IN ('Classic Paper', 'Classic Foil')
              AND mp.listing_type = 'sold'
              AND COALESCE(mp.sold_date, mp.scraped_at) >= :cutoff
            HAVING COUNT(*) >= 2
        """)

        rarity_result = self.session.execute(
            rarity_query,
            {"set_name": set_name, "rarity_name": rarity_name, "cutoff": cutoff}
        ).fetchone()

        if rarity_result and rarity_result[0]:
            mult = float(rarity_result[0]) / common_median
            self._rarity_mult_cache[cache_key] = mult
            return mult

        default_mult = DEFAULT_RARITY_MULTIPLIERS.get(rarity_name, 1.0)
        self._rarity_mult_cache[cache_key] = default_mult
        return default_mult

    def get_treatment_multiplier(self, card_id: int, treatment: str, days: int = 30) -> float:
        """
        Calculate treatment multiplier from card-specific sales data.
        Multiplier = median_price(treatment) / median_price(Classic Paper)
        """
        if treatment in ('Classic Paper', None):
            return 1.0

        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get median for Classic Paper (base)
        base_query = text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price
            FROM marketprice
            WHERE card_id = :card_id
              AND treatment = 'Classic Paper'
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
            HAVING COUNT(*) >= 2
        """)

        base_result = self.session.execute(base_query, {"card_id": card_id, "cutoff": cutoff}).fetchone()
        base_median = float(base_result[0]) if base_result and base_result[0] else None

        if not base_median:
            return DEFAULT_TREATMENT_MULTIPLIERS.get(treatment, 1.0)

        # Get median for target treatment
        treatment_query = text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price
            FROM marketprice
            WHERE card_id = :card_id
              AND treatment = :treatment
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
            HAVING COUNT(*) >= 1
        """)

        treatment_result = self.session.execute(
            treatment_query,
            {"card_id": card_id, "treatment": treatment, "cutoff": cutoff}
        ).fetchone()

        if treatment_result and treatment_result[0]:
            return float(treatment_result[0]) / base_median

        return DEFAULT_TREATMENT_MULTIPLIERS.get(treatment, 1.0)

    def get_liquidity_adjustment(self, card_id: int, days: int = 30) -> float:
        """
        Calculate liquidity adjustment based on volume/inventory ratio.
        Higher liquidity = less discount (closer to 1.0)
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Get volume (sold count) and inventory (active count)
        query = text("""
            SELECT
                COUNT(*) FILTER (WHERE listing_type = 'sold' AND COALESCE(sold_date, scraped_at) >= :cutoff) as volume,
                COUNT(*) FILTER (WHERE listing_type = 'active') as inventory
            FROM marketprice
            WHERE card_id = :card_id
        """)

        result = self.session.execute(query, {"card_id": card_id, "cutoff": cutoff}).fetchone()

        if not result:
            return 0.90

        volume = result[0] or 0
        inventory = result[1] or 0

        # Calculate liquidity ratio
        liquidity = volume / (inventory + 1)  # +1 to avoid division by zero

        if liquidity > 1.0:
            return 1.0   # High demand
        elif liquidity > 0.5:
            return 0.95  # Normal
        elif liquidity > 0.2:
            return 0.90  # Low demand
        else:
            return 0.85  # Very low demand

    def calculate_floor_price(self, card_id: int, num_sales: int = 4, days: int = 30) -> Optional[float]:
        """
        Calculate floor price as average of up to N lowest sales.
        Prefers base treatments (Classic Paper/Classic Foil), but falls back to
        the CHEAPEST available treatment if no base treatment sales exist.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Use COALESCE(sold_date, scraped_at) as fallback when sold_date is NULL
        # First try base treatments only (Classic Paper, Classic Foil)
        base_query = text("""
            SELECT AVG(price) as floor_price
            FROM (
                SELECT price
                FROM marketprice
                WHERE card_id = :card_id
                  AND listing_type = 'sold'
                  AND treatment IN ('Classic Paper', 'Classic Foil')
                  AND COALESCE(sold_date, scraped_at) >= :cutoff
                ORDER BY price ASC
                LIMIT GREATEST(1, LEAST(:num_sales, (
                    SELECT COUNT(*) FROM marketprice
                    WHERE card_id = :card_id AND listing_type = 'sold'
                      AND treatment IN ('Classic Paper', 'Classic Foil')
                      AND COALESCE(sold_date, scraped_at) >= :cutoff
                )))
            ) as lowest_sales
        """)

        result = self.session.execute(
            base_query,
            {"card_id": card_id, "cutoff": cutoff, "num_sales": num_sales}
        ).fetchone()

        if result and result[0]:
            return round(float(result[0]), 2)

        # Fallback: find cheapest treatment and use that treatment's lowest sales
        # This avoids mixing expensive promos with cheaper treatments
        cheapest_treatment_query = text("""
            SELECT treatment, AVG(price) as floor_price
            FROM (
                SELECT treatment, price,
                       ROW_NUMBER() OVER (PARTITION BY treatment ORDER BY price ASC) as rn
                FROM marketprice
                WHERE card_id = :card_id
                  AND listing_type = 'sold'
                  AND COALESCE(sold_date, scraped_at) >= :cutoff
            ) ranked
            WHERE rn <= :num_sales
            GROUP BY treatment
            ORDER BY floor_price ASC
            LIMIT 1
        """)

        cheapest_result = self.session.execute(
            cheapest_treatment_query,
            {"card_id": card_id, "cutoff": cutoff, "num_sales": num_sales}
        ).fetchone()

        if cheapest_result and cheapest_result[1]:
            return round(float(cheapest_result[1]), 2)

        # Fallback: try 90 days if no recent sales
        if days == 30:
            return self.calculate_floor_price(card_id, num_sales, days=90)

        return None

    def get_median_price(self, card_id: int, days: int = 30) -> Optional[float]:
        """
        Get simple median price for a card (used for non-Single products).
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        query = text("""
            SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
        """)

        result = self.session.execute(query, {"card_id": card_id, "cutoff": cutoff}).fetchone()

        if result and result[0]:
            return round(float(result[0]), 2)

        # Fallback to 90 days
        if days == 30:
            return self.get_median_price(card_id, days=90)

        return None

    def calculate_fmp(
        self,
        card_id: int,
        set_name: str,
        rarity_name: str,
        treatment: str = 'Classic Paper',
        days: int = 30,
        product_type: str = 'Single'
    ) -> Dict[str, Any]:
        """
        Calculate Fair Market Price.

        For Singles: FMP = BaseSetPrice × RarityMultiplier × TreatmentMultiplier × LiquidityAdjustment
        For Boxes/Packs/Bundles/Proofs/Lots: FMP = Median price (formula doesn't apply)

        Returns dict with FMP value and breakdown.
        """
        floor_price = self.calculate_floor_price(card_id, num_sales=4, days=days)

        # For non-Single products, just use median price - formula doesn't apply
        if product_type and product_type not in ['Single', None, '']:
            median_price = self.get_median_price(card_id, days)
            return {
                'fair_market_price': median_price,
                'floor_price': floor_price,
                'breakdown': None,  # No formula breakdown for non-Singles
                'product_type': product_type,
                'calculation_method': 'median',  # Indicates simple median was used
                'data_quality': {
                    'has_base_price': False,
                    'has_floor_price': floor_price is not None,
                    'using_defaults': False,
                }
            }

        # For Singles: use the full FMP formula
        base_price = self.get_base_set_price(set_name, days)
        rarity_mult = self.get_rarity_multiplier(set_name, rarity_name, days)
        treatment_mult = self.get_treatment_multiplier(card_id, treatment, days)
        condition_mult = 1.0  # Default to Near Mint (future: parse from listings)
        liquidity_adj = self.get_liquidity_adjustment(card_id, days)

        # Calculate FMP
        fmp = None
        if base_price:
            fmp = base_price * rarity_mult * treatment_mult * condition_mult * liquidity_adj
            fmp = round(fmp, 2)

        return {
            'fair_market_price': fmp,
            'floor_price': floor_price,
            'breakdown': {
                'base_set_price': round(base_price, 2) if base_price else None,
                'rarity_multiplier': round(rarity_mult, 2),
                'treatment_multiplier': round(treatment_mult, 2),
                'condition_multiplier': condition_mult,
                'liquidity_adjustment': round(liquidity_adj, 2),
            },
            'product_type': product_type,
            'calculation_method': 'formula',
            'data_quality': {
                'has_base_price': base_price is not None,
                'has_floor_price': floor_price is not None,
                'using_defaults': base_price is None,
            }
        }

    def calculate_fmp_simple(
        self,
        card_id: int,
        set_name: str,
        rarity_name: str,
        days: int = 30
    ) -> tuple[Optional[float], Optional[float]]:
        """
        Simplified FMP calculation returning just (fmp, floor_price).
        Uses Classic Paper treatment as default for base FMP.
        """
        result = self.calculate_fmp(card_id, set_name, rarity_name, 'Classic Paper', days)
        return result['fair_market_price'], result['floor_price']


    def get_fmp_by_treatment(self, card_id: int, set_name: str, rarity_name: str, days: int = 30, product_type: str = 'Single') -> List[Dict[str, Any]]:
        """
        Calculate FMP for all treatments/variants available for this card.
        Returns list of treatment FMPs sorted by price.

        For Singles: treatments like Classic Paper, Foil, Serialized, etc.
        For Boxes/Packs: treatments like Sealed, Unsealed, Factory Sealed, etc.
        """
        cutoff = datetime.utcnow() - timedelta(days=days)

        # Query with time window filter - get treatments with recent sales
        # Use COALESCE(sold_date, scraped_at) as fallback when sold_date is NULL
        query = text("""
            SELECT
                treatment,
                COUNT(*) as sales_count,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price) as median_price,
                MIN(price) as min_price,
                MAX(price) as max_price,
                AVG(price) as avg_price
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'sold'
              AND COALESCE(sold_date, scraped_at) >= :cutoff
            GROUP BY treatment
            ORDER BY median_price ASC NULLS LAST
        """)

        results = self.session.execute(query, {"card_id": card_id, "cutoff": cutoff}).fetchall()

        if not results:
            # Fallback to 90 days if no recent sales
            if days == 30:
                return self.get_fmp_by_treatment(card_id, set_name, rarity_name, days=90, product_type=product_type)
            return []

        # Default treatment label for NULL values based on product type
        default_treatment = 'Sealed' if product_type in ['Box', 'Pack', 'Bundle'] else 'Classic Paper'

        treatment_fmps = []
        for row in results:
            treatment = row[0] or default_treatment
            sales_count = row[1]
            median_price = float(row[2]) if row[2] else None
            min_price = float(row[3]) if row[3] else None
            max_price = float(row[4]) if row[4] else None
            avg_price = float(row[5]) if row[5] else None

            # Calculate FMP for this treatment
            treatment_mult = self.get_treatment_multiplier(card_id, treatment, days)
            liquidity_adj = self.get_liquidity_adjustment(card_id, days)

            # Use median price as the FMP for this treatment
            fmp = median_price

            treatment_fmps.append({
                'treatment': treatment,
                'fmp': round(fmp, 2) if fmp else None,
                'median_price': round(median_price, 2) if median_price else None,
                'min_price': round(min_price, 2) if min_price else None,
                'max_price': round(max_price, 2) if max_price else None,
                'avg_price': round(avg_price, 2) if avg_price else None,
                'sales_count': sales_count,
                'treatment_multiplier': round(treatment_mult, 2),
                'liquidity_adjustment': round(liquidity_adj, 2),
            })

        return treatment_fmps


def get_pricing_service(session: Session) -> FairMarketPriceService:
    """Factory function to create pricing service."""
    return FairMarketPriceService(session)
