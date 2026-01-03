"""
Tests for FloorPriceService.

Tests cover:
- Sales floor calculation with sufficient data
- Order book fallback when sales insufficient
- Confidence scoring
- Time window expansion
- Multi-platform sales aggregation
- Edge cases (no data, single sale, etc.)
"""

import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from app.services.floor_price import (
    FloorPriceService,
    FloorPriceResult,
    FloorPriceSource,
    ConfidenceLevel,
    FloorPriceConfig,
    get_floor_price_service,
    clear_floor_cache,
)
from app.services.order_book import OrderBookAnalyzer, OrderBookResult, BucketInfo


@pytest.fixture(autouse=True)
def clear_cache():
    """Clear the floor price cache before each test."""
    clear_floor_cache()
    yield
    clear_floor_cache()


class TestFloorPriceService:
    """Tests for FloorPriceService class."""

    @pytest.fixture
    def service(self):
        """Create a FloorPriceService instance."""
        return FloorPriceService()

    @pytest.fixture
    def mock_sales_result(self):
        """Mock sales result with 4+ sales."""
        return {
            "price": 25.00,
            "count": 6,
            "platforms": ["ebay", "opensea"],
        }

    @pytest.fixture
    def mock_order_book_result(self):
        """Mock OrderBookResult with high confidence."""
        return OrderBookResult(
            floor_estimate=28.50,
            confidence=0.85,
            deepest_bucket=BucketInfo(min_price=25.0, max_price=30.0, count=8),
            total_listings=12,
            outliers_removed=2,
            buckets=[BucketInfo(min_price=25.0, max_price=30.0, count=8)],
            stale_count=1,
            source="order_book",
        )


class TestSalesFloorHighConfidence(TestFloorPriceService):
    """Tests for sales floor with high confidence (>=4 sales)."""

    def test_returns_sales_floor_with_4_plus_sales(self, service, mock_sales_result):
        """Should return SALES source with HIGH confidence when >=4 sales."""
        with patch.object(service, "_get_sales_floor", return_value=mock_sales_result):
            result = service.get_floor_price(card_id=123)

        assert result.price == 25.00
        assert result.source == FloorPriceSource.SALES
        assert result.confidence == ConfidenceLevel.HIGH
        assert result.confidence_score == 1.0
        assert result.metadata["sales_count"] == 6

    def test_does_not_check_order_book_when_sales_sufficient(self, service, mock_sales_result):
        """Should not query order book when sales are sufficient."""
        with patch.object(service, "_get_sales_floor", return_value=mock_sales_result):
            with patch.object(OrderBookAnalyzer, "estimate_floor") as mock_estimate:
                result = service.get_floor_price(card_id=123)
                mock_estimate.assert_not_called()

        assert result.source == FloorPriceSource.SALES


class TestOrderBookFallback(TestFloorPriceService):
    """Tests for order book fallback when sales insufficient."""

    def test_falls_back_to_order_book_when_no_sales(self, service, mock_order_book_result):
        """Should use order book when no sales data available."""
        with patch.object(service, "_get_sales_floor", return_value=None):
            with patch.object(
                service.order_book_analyzer,
                "estimate_floor",
                return_value=mock_order_book_result,
            ):
                result = service.get_floor_price(card_id=123)

        assert result.price == 28.50
        assert result.source == FloorPriceSource.ORDER_BOOK
        assert result.confidence == ConfidenceLevel.HIGH
        assert result.confidence_score == 0.85

    def test_falls_back_to_order_book_when_few_sales(self, service, mock_order_book_result):
        """Should use order book when only 1 sale (below threshold)."""
        sparse_sales = {"price": 20.00, "count": 1, "platforms": ["ebay"]}

        with patch.object(service, "_get_sales_floor", return_value=sparse_sales):
            with patch.object(
                service.order_book_analyzer,
                "estimate_floor",
                return_value=mock_order_book_result,
            ):
                result = service.get_floor_price(card_id=123)

        assert result.source == FloorPriceSource.ORDER_BOOK
        assert result.price == 28.50

    def test_order_book_confidence_mapping_high(self, service):
        """Should map OB confidence >0.7 to HIGH."""
        ob_result = OrderBookResult(
            floor_estimate=30.0,
            confidence=0.75,
            deepest_bucket=BucketInfo(25.0, 35.0, 10),
            total_listings=15,
            outliers_removed=0,
            buckets=[],
        )

        with patch.object(service, "_get_sales_floor", return_value=None):
            with patch.object(
                service.order_book_analyzer, "estimate_floor", return_value=ob_result
            ):
                result = service.get_floor_price(card_id=123)

        assert result.confidence == ConfidenceLevel.HIGH

    def test_order_book_confidence_mapping_medium(self, service):
        """Should map OB confidence 0.4-0.7 to MEDIUM."""
        ob_result = OrderBookResult(
            floor_estimate=30.0,
            confidence=0.55,
            deepest_bucket=BucketInfo(25.0, 35.0, 5),
            total_listings=10,
            outliers_removed=0,
            buckets=[],
        )

        with patch.object(service, "_get_sales_floor", return_value=None):
            with patch.object(
                service.order_book_analyzer, "estimate_floor", return_value=ob_result
            ):
                result = service.get_floor_price(card_id=123)

        assert result.confidence == ConfidenceLevel.MEDIUM

    def test_order_book_confidence_mapping_low(self, service):
        """Should map OB confidence <0.4 to LOW."""
        ob_result = OrderBookResult(
            floor_estimate=30.0,
            confidence=0.35,
            deepest_bucket=BucketInfo(25.0, 35.0, 3),
            total_listings=8,
            outliers_removed=0,
            buckets=[],
        )

        with patch.object(service, "_get_sales_floor", return_value=None):
            with patch.object(
                service.order_book_analyzer, "estimate_floor", return_value=ob_result
            ):
                result = service.get_floor_price(card_id=123)

        assert result.confidence == ConfidenceLevel.LOW


class TestLowConfidenceSales(TestFloorPriceService):
    """Tests for sales floor with low confidence (2-3 sales)."""

    def test_uses_sales_with_2_sales_low_confidence(self, service):
        """Should use SALES with LOW confidence when 2 sales and OB fails."""
        sparse_sales = {"price": 22.00, "count": 2, "platforms": ["ebay"]}
        low_ob_result = OrderBookResult(
            floor_estimate=25.0,
            confidence=0.2,  # Below threshold
            deepest_bucket=BucketInfo(20.0, 30.0, 2),
            total_listings=3,
            outliers_removed=0,
            buckets=[],
        )

        with patch.object(service, "_get_sales_floor", return_value=sparse_sales):
            with patch.object(
                service.order_book_analyzer, "estimate_floor", return_value=low_ob_result
            ):
                result = service.get_floor_price(card_id=123)

        assert result.price == 22.00
        assert result.source == FloorPriceSource.SALES
        assert result.confidence == ConfidenceLevel.LOW
        assert result.confidence_score == 0.5  # 2/4

    def test_uses_sales_with_3_sales_medium_confidence(self, service):
        """Should use SALES with MEDIUM confidence when 3 sales and OB fails."""
        sparse_sales = {"price": 23.00, "count": 3, "platforms": ["opensea"]}

        with patch.object(service, "_get_sales_floor", return_value=sparse_sales):
            with patch.object(
                service.order_book_analyzer, "estimate_floor", return_value=None
            ):
                result = service.get_floor_price(card_id=123)

        assert result.price == 23.00
        assert result.source == FloorPriceSource.SALES
        assert result.confidence == ConfidenceLevel.MEDIUM
        assert result.confidence_score == 0.75  # 3/4


class TestTimeWindowExpansion(TestFloorPriceService):
    """Tests for time window expansion (30d -> 90d)."""

    def test_expands_to_90_days_when_no_data(self, service):
        """Should expand to 90 days when no data in 30 days."""
        call_count = 0

        def mock_get_sales(card_id, treatment, days, include_blokpax):
            nonlocal call_count
            call_count += 1
            if days == 30:
                return None  # No data in 30 days
            elif days == 90:
                return {"price": 30.00, "count": 5, "platforms": ["ebay"]}
            return None

        with patch.object(service, "_get_sales_floor", side_effect=mock_get_sales):
            with patch.object(
                service.order_book_analyzer, "estimate_floor", return_value=None
            ):
                result = service.get_floor_price(card_id=123)

        assert result.price == 30.00
        assert result.source == FloorPriceSource.SALES
        assert call_count == 2  # Called twice (30d, then 90d)

    def test_returns_none_when_no_data_in_90_days(self, service):
        """Should return NONE source when no data even in 90 days."""
        with patch.object(service, "_get_sales_floor", return_value=None):
            with patch.object(
                service.order_book_analyzer, "estimate_floor", return_value=None
            ):
                result = service.get_floor_price(card_id=123)

        assert result.price is None
        assert result.source == FloorPriceSource.NONE
        assert result.confidence == ConfidenceLevel.LOW
        assert result.metadata["reason"] == "insufficient_data"


class TestMultiPlatformAggregation(TestFloorPriceService):
    """Tests for multi-platform sales aggregation."""

    def test_combines_ebay_opensea_blokpax(self, service):
        """Should combine sales from all platforms."""
        combined_sales = {
            "price": 24.50,
            "count": 4,
            "platforms": ["ebay", "opensea", "blokpax"],
        }

        with patch.object(service, "_get_sales_floor", return_value=combined_sales):
            result = service.get_floor_price(card_id=123)

        assert result.price == 24.50
        assert "ebay" in result.metadata["platforms"]
        assert "opensea" in result.metadata["platforms"]
        assert "blokpax" in result.metadata["platforms"]

    def test_exclude_blokpax_when_disabled(self, service):
        """Should exclude Blokpax when include_blokpax=False."""
        # This tests the parameter is passed through
        with patch.object(service, "_get_sales_floor") as mock_sales:
            mock_sales.return_value = {"price": 25.0, "count": 4, "platforms": ["ebay"]}
            service.get_floor_price(card_id=123, include_blokpax=False)

            # Check include_blokpax was passed as False
            mock_sales.assert_called_once()
            call_args = mock_sales.call_args
            assert call_args[0][3] is False  # include_blokpax argument


class TestTreatmentFilter(TestFloorPriceService):
    """Tests for treatment filtering."""

    def test_passes_treatment_to_queries(self, service):
        """Should pass treatment filter to sales query."""
        with patch.object(service, "_get_sales_floor") as mock_sales:
            mock_sales.return_value = {"price": 50.0, "count": 4, "platforms": ["ebay"]}
            result = service.get_floor_price(card_id=123, treatment="Classic Foil")

            # Check treatment was passed
            call_args = mock_sales.call_args
            assert call_args[0][1] == "Classic Foil"

        assert result.metadata["treatment"] == "Classic Foil"


class TestFloorPriceResult:
    """Tests for FloorPriceResult dataclass."""

    def test_to_dict(self):
        """Should serialize to dict correctly."""
        result = FloorPriceResult(
            price=25.00,
            source=FloorPriceSource.SALES,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=1.0,
            metadata={"sales_count": 5},
        )

        d = result.to_dict()

        assert d["price"] == 25.00
        assert d["source"] == "sales"
        assert d["confidence"] == "high"
        assert d["confidence_score"] == 1.0
        assert d["metadata"]["sales_count"] == 5

    def test_to_dict_with_none_price(self):
        """Should handle None price in serialization."""
        result = FloorPriceResult(
            price=None,
            source=FloorPriceSource.NONE,
            confidence=ConfidenceLevel.LOW,
            confidence_score=0.0,
            metadata={"reason": "no_data"},
        )

        d = result.to_dict()

        assert d["price"] is None
        assert d["source"] == "none"


class TestFactoryFunction:
    """Tests for get_floor_price_service factory."""

    def test_creates_service_without_session(self):
        """Should create service without session."""
        service = get_floor_price_service()
        assert isinstance(service, FloorPriceService)
        assert service.session is None

    def test_creates_service_with_session(self):
        """Should create service with session."""
        mock_session = MagicMock()
        service = get_floor_price_service(mock_session)
        assert service.session is mock_session


class TestFloorPriceConfig:
    """Tests for FloorPriceConfig defaults."""

    def test_default_values(self):
        """Should have sensible default values."""
        config = FloorPriceConfig()

        assert config.MIN_SALES_HIGH_CONFIDENCE == 4
        assert config.MIN_SALES_MEDIUM_CONFIDENCE == 3
        assert config.MIN_SALES_LOW_CONFIDENCE == 2
        assert config.ORDER_BOOK_MIN_CONFIDENCE == 0.3
        assert config.DEFAULT_LOOKBACK_DAYS == 30
        assert config.EXPANDED_LOOKBACK_DAYS == 90


class TestBatchFloorPrice(TestFloorPriceService):
    """Tests for batch floor price calculation."""

    def test_batch_returns_empty_dict_for_empty_list(self, service):
        """Should return empty dict when card_ids is empty."""
        result = service.get_floor_prices_batch([])
        assert result == {}

    def test_batch_returns_results_keyed_by_card_id(self, service):
        """Should return dict keyed by card_id when by_variant=False."""
        mock_sales_data = {
            1: {"price": 25.00, "count": 4, "platforms": ["ebay"]},
            2: {"price": 30.00, "count": 4, "platforms": ["opensea"]},
        }

        with patch.object(service, "_get_sales_floors_batch", return_value=mock_sales_data):
            result = service.get_floor_prices_batch([1, 2])

        assert 1 in result
        assert 2 in result
        assert result[1].price == 25.00
        assert result[2].price == 30.00

    def test_batch_returns_results_keyed_by_card_variant_tuple(self, service):
        """Should return dict keyed by (card_id, variant) when by_variant=True."""
        mock_sales_data = {
            (1, "Classic Paper"): {"price": 20.00, "count": 4, "platforms": ["ebay"], "variant": "Classic Paper"},
            (1, "Classic Foil"): {"price": 50.00, "count": 4, "platforms": ["ebay"], "variant": "Classic Foil"},
        }

        with patch.object(service, "_get_sales_floors_batch", return_value=mock_sales_data):
            result = service.get_floor_prices_batch([1], by_variant=True)

        assert (1, "Classic Paper") in result
        assert (1, "Classic Foil") in result
        assert result[(1, "Classic Paper")].price == 20.00
        assert result[(1, "Classic Foil")].price == 50.00

    def test_batch_excludes_cards_with_insufficient_sales(self, service):
        """Should not include cards with less than MIN_SALES_LOW_CONFIDENCE sales."""
        mock_sales_data = {
            1: {"price": 25.00, "count": 4, "platforms": ["ebay"]},
            2: {"price": 30.00, "count": 1, "platforms": ["opensea"]},  # Only 1 sale
        }

        with patch.object(service, "_get_sales_floors_batch", return_value=mock_sales_data):
            result = service.get_floor_prices_batch([1, 2])

        assert 1 in result
        assert 2 not in result  # Excluded due to insufficient sales

    def test_batch_maps_confidence_correctly(self, service):
        """Should map confidence levels based on sales count."""
        mock_sales_data = {
            1: {"price": 25.00, "count": 4, "platforms": ["ebay"]},  # HIGH
            2: {"price": 30.00, "count": 3, "platforms": ["opensea"]},  # MEDIUM
            3: {"price": 35.00, "count": 2, "platforms": ["blokpax"]},  # LOW
        }

        with patch.object(service, "_get_sales_floors_batch", return_value=mock_sales_data):
            result = service.get_floor_prices_batch([1, 2, 3])

        assert result[1].confidence == ConfidenceLevel.HIGH
        assert result[1].confidence_score == 1.0
        assert result[2].confidence == ConfidenceLevel.MEDIUM
        assert result[2].confidence_score == 0.75
        assert result[3].confidence == ConfidenceLevel.LOW
        assert result[3].confidence_score == 0.5

    def test_batch_includes_metadata(self, service):
        """Should include metadata in results."""
        mock_sales_data = {
            1: {"price": 25.00, "count": 4, "platforms": ["ebay", "blokpax"]},
        }

        with patch.object(service, "_get_sales_floors_batch", return_value=mock_sales_data):
            result = service.get_floor_prices_batch([1], days=30)

        assert result[1].metadata["sales_count"] == 4
        assert result[1].metadata["days"] == 30
        assert "ebay" in result[1].metadata["platforms"]

    def test_batch_all_results_are_sales_source(self, service):
        """Batch method always uses SALES source (no order book fallback)."""
        mock_sales_data = {
            1: {"price": 25.00, "count": 2, "platforms": ["ebay"]},
        }

        with patch.object(service, "_get_sales_floors_batch", return_value=mock_sales_data):
            result = service.get_floor_prices_batch([1])

        assert result[1].source == FloorPriceSource.SALES


class TestIntegration:
    """Integration tests with real database (if available)."""

    @pytest.mark.integration
    def test_real_card_floor_price(self, test_engine):
        """Should calculate floor price for a real card."""
        service = FloorPriceService()
        # Use a card ID that exists in test data
        result = service.get_floor_price(card_id=1)

        # Just verify it returns a valid result structure
        assert isinstance(result, FloorPriceResult)
        assert result.source in FloorPriceSource
        assert result.confidence in ConfidenceLevel
        assert 0.0 <= result.confidence_score <= 1.0
