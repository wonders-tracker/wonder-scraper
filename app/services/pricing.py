"""
Fair Market Price (FMP) Service Stub

This module provides the FMP pricing interface. The actual implementation
lives in the private saas/ module. In OSS mode, FMP features are unavailable.

Usage:
    from app.services.pricing import FMP_AVAILABLE, get_pricing_service

    if FMP_AVAILABLE:
        service = get_pricing_service(session)
        fmp = service.calculate_fmp(...)
"""

from typing import Optional, Dict, Any, List, TYPE_CHECKING, Protocol, runtime_checkable

if TYPE_CHECKING:
    from sqlmodel import Session

from app.services.order_book import get_order_book_analyzer


# Protocol defining the pricing service interface
# Both the SaaS implementation and OSS stub must satisfy this interface
@runtime_checkable
class PricingServiceProtocol(Protocol):
    """Protocol defining the FairMarketPriceService interface."""

    def calculate_fmp(
        self,
        card_id: int,
        set_name: str,
        rarity_name: str,
        treatment: str = "Classic Paper",
        days: int = 30,
        product_type: str = "Single",
    ) -> Dict[str, Any]: ...

    def calculate_fmp_simple(
        self, card_id: int, set_name: str, rarity_name: str, days: int = 30
    ) -> tuple[Optional[float], Optional[float]]: ...

    def get_fmp_by_treatment(
        self, card_id: int, set_name: str, rarity_name: str, days: int = 30, product_type: str = "Single"
    ) -> List[Dict[str, Any]]: ...

    def calculate_floor_price(self, card_id: int, num_sales: int = 4, days: int = 30) -> Optional[float]: ...

    def get_median_price(self, card_id: int, days: int = 30) -> Optional[float]: ...


# Try to import from saas module
try:
    from saas.services.pricing import (
        FairMarketPriceService as _SaaSFairMarketPriceService,
        get_pricing_service as _saas_get_pricing_service,
        BASE_TREATMENTS,
        DEFAULT_RARITY_MULTIPLIERS,
        DEFAULT_TREATMENT_MULTIPLIERS,
    )

    FMP_AVAILABLE = True

    # Re-export the SaaS class as FairMarketPriceService for backwards compatibility
    FairMarketPriceService = _SaaSFairMarketPriceService

    def get_pricing_service(session: "Session") -> PricingServiceProtocol:
        """Factory function to create pricing service (SaaS mode)."""
        return _saas_get_pricing_service(session)

except ImportError:
    FMP_AVAILABLE = False

    # Stub constants for OSS mode
    BASE_TREATMENTS = ["Classic Paper", "Classic Foil"]
    DEFAULT_RARITY_MULTIPLIERS = {
        "Common": 1.0,
        "Uncommon": 1.5,
        "Rare": 3.0,
        "Legendary": 8.0,
        "Mythic": 20.0,
        "Sealed": 1.0,
    }
    DEFAULT_TREATMENT_MULTIPLIERS = {
        "Classic Paper": 1.0,
        "Classic Foil": 1.3,
        "Stonefoil": 2.0,
        "Formless Foil": 3.5,
        "Prerelease": 2.0,
        "Promo": 2.0,
        "OCM Serialized": 10.0,
        "Sealed": 1.0,
        "Factory Sealed": 1.0,
    }

    class FairMarketPriceService:
        """Stub service when FMP is unavailable (OSS mode)."""

        def __init__(self, session: "Session"):
            self.session = session

        def calculate_fmp(
            self,
            card_id: int,
            set_name: str,
            rarity_name: str,
            treatment: str = "Classic Paper",
            days: int = 30,
            product_type: str = "Single",
        ) -> Dict[str, Any]:
            """
            FMP formula unavailable in OSS mode, but provides order-book floor.

            Returns the order book floor estimate with confidence score.
            """
            analyzer = get_order_book_analyzer(self.session)
            result = analyzer.estimate_floor(card_id=card_id, treatment=treatment, days=days)

            if result:
                return {
                    "fair_market_price": None,  # FMP algorithm requires SaaS
                    "floor_price": result.floor_estimate,
                    "floor_confidence": result.confidence,
                    "floor_source": result.source,
                    "breakdown": None,
                    "product_type": product_type,
                    "calculation_method": "order_book",
                    "data_quality": {
                        "has_base_price": False,
                        "has_floor_price": True,
                        "using_defaults": False,
                        "fmp_available": False,
                        "total_listings": result.total_listings,
                        "stale_count": result.stale_count,
                    },
                }

            return {
                "fair_market_price": None,
                "floor_price": None,
                "breakdown": None,
                "product_type": product_type,
                "calculation_method": "unavailable",
                "data_quality": {
                    "has_base_price": False,
                    "has_floor_price": False,
                    "using_defaults": False,
                    "fmp_available": False,
                },
                "error": "Insufficient market data for floor estimation",
            }

        def calculate_fmp_simple(
            self, card_id: int, set_name: str, rarity_name: str, days: int = 30
        ) -> tuple[Optional[float], Optional[float]]:
            """FMP unavailable in OSS mode."""
            return None, None

        def get_fmp_by_treatment(
            self, card_id: int, set_name: str, rarity_name: str, days: int = 30, product_type: str = "Single"
        ) -> List[Dict[str, Any]]:
            """FMP unavailable in OSS mode."""
            return []

        def calculate_floor_price(self, card_id: int, num_sales: int = 4, days: int = 30) -> Optional[float]:
            """
            Calculate floor price using order book analysis (OSS mode).

            Uses the OrderBookAnalyzer to find the floor based on active listing
            liquidity depth. Falls back to sales data if insufficient active listings.
            """
            analyzer = get_order_book_analyzer(self.session)
            result = analyzer.estimate_floor(card_id=card_id, days=days)
            if result:
                return result.floor_estimate
            return None

        def get_median_price(self, card_id: int, days: int = 30) -> Optional[float]:
            """Median price unavailable in OSS mode."""
            return None

    def get_pricing_service(session: "Session") -> PricingServiceProtocol:
        """Factory function to create pricing service stub."""
        return FairMarketPriceService(session)


__all__ = [
    "FMP_AVAILABLE",
    "FairMarketPriceService",
    "PricingServiceProtocol",
    "get_pricing_service",
    "BASE_TREATMENTS",
    "DEFAULT_RARITY_MULTIPLIERS",
    "DEFAULT_TREATMENT_MULTIPLIERS",
]
