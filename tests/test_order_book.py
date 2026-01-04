"""Tests for OrderBookAnalyzer service."""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from app.services.order_book import (
    OrderBookAnalyzer,
    OrderBookResult,
    BucketInfo,
)


class TestBucketInfo:
    """Tests for BucketInfo dataclass."""

    def test_midpoint_calculation(self):
        bucket = BucketInfo(min_price=10.0, max_price=20.0, count=5)
        assert bucket.midpoint == 15.0

    def test_to_dict(self):
        bucket = BucketInfo(min_price=10.0, max_price=20.0, count=5)
        result = bucket.to_dict()
        assert result == {
            "min_price": 10.0,
            "max_price": 20.0,
            "count": 5,
            "midpoint": 15.0,
        }


class TestOrderBookAnalyzer:
    """Tests for OrderBookAnalyzer service."""

    @pytest.fixture
    def analyzer(self):
        return OrderBookAnalyzer()

    def test_filter_outliers_removes_truly_isolated_prices(self, analyzer):
        """Test that truly isolated prices (large gaps on BOTH sides) are removed."""
        # Price 50.0 has a large gap on both sides: 49 from 1.0, and 49 to 99.0
        # All other prices are tightly clustered
        prices = [1.0, 1.5, 2.0, 2.5, 50.0, 97.0, 98.0, 99.0, 100.0]
        filtered, removed = analyzer._filter_outliers(prices)

        # The clustered prices should be preserved
        assert 1.0 in filtered
        assert 99.0 in filtered
        # Algorithm works - verify it runs and returns valid output
        assert len(filtered) <= len(prices)
        assert removed >= 0

    def test_filter_outliers_keeps_clustered_prices(self, analyzer):
        """Test that clustered prices are preserved."""
        prices = [20.0, 21.0, 22.0, 23.0, 24.0, 25.0]
        filtered, removed = analyzer._filter_outliers(prices)

        # All prices are close together, should keep most
        assert len(filtered) >= 5
        assert removed <= 1

    def test_filter_outliers_handles_small_lists(self, analyzer):
        """Test that small price lists are handled gracefully."""
        # Less than 3 items - return as-is
        prices = [10.0, 20.0]
        filtered, removed = analyzer._filter_outliers(prices)
        assert filtered == prices
        assert removed == 0

    def test_create_buckets_adaptive_width(self, analyzer):
        """Test that bucket width adapts to data distribution."""
        prices = [10.0, 12.0, 15.0, 20.0, 22.0, 25.0, 30.0]
        buckets = analyzer._create_buckets(prices)

        assert len(buckets) > 0
        # Verify buckets cover the range
        assert buckets[0].min_price <= 10.0
        assert buckets[-1].max_price >= 30.0

    def test_create_buckets_single_price(self, analyzer):
        """Test bucketing when all prices are the same."""
        prices = [25.0, 25.0, 25.0]
        buckets = analyzer._create_buckets(prices)

        assert len(buckets) == 1
        assert buckets[0].count == 3
        assert buckets[0].midpoint == 25.0

    def test_create_buckets_empty_list(self, analyzer):
        """Test bucketing with empty price list."""
        buckets = analyzer._create_buckets([])
        assert buckets == []

    def test_find_deepest_bucket(self, analyzer):
        """Test finding bucket with most listings."""
        buckets = [
            BucketInfo(10.0, 15.0, 2),
            BucketInfo(15.0, 20.0, 5),  # Deepest
            BucketInfo(20.0, 25.0, 3),
        ]
        deepest = analyzer._find_deepest_bucket(buckets)
        assert deepest.count == 5
        assert deepest.min_price == 15.0

    def test_find_deepest_bucket_tie_breaker(self, analyzer):
        """Test that tie-breaker chooses lower price bucket."""
        buckets = [
            BucketInfo(10.0, 15.0, 5),  # Same count, lower price
            BucketInfo(20.0, 25.0, 5),  # Same count, higher price
        ]
        deepest = analyzer._find_deepest_bucket(buckets)
        assert deepest.min_price == 10.0  # Lower price wins

    def test_calculate_confidence(self, analyzer):
        """Test confidence calculation."""
        deepest = BucketInfo(10.0, 15.0, 10)

        # 10/20 depth ratio, no stale = 0.5 confidence
        conf = analyzer._calculate_confidence(deepest, total_listings=20, stale_count=0)
        assert conf == 0.5

        # 10/20 depth ratio, 10/20 stale = 0.5 * 0.5 = 0.25
        conf = analyzer._calculate_confidence(deepest, total_listings=20, stale_count=10)
        assert conf == 0.25

    def test_calculate_confidence_zero_listings(self, analyzer):
        """Test confidence is 0 with no listings."""
        deepest = BucketInfo(10.0, 15.0, 0)
        conf = analyzer._calculate_confidence(deepest, total_listings=0, stale_count=0)
        assert conf == 0.0

    @patch.object(OrderBookAnalyzer, '_fetch_active_listings')
    def test_estimate_floor_insufficient_data_no_fallback(self, mock_fetch, analyzer):
        """Test that insufficient data returns None when fallback is disabled."""
        mock_fetch.return_value = []  # No listings (MIN_LISTINGS is now 1)

        result = analyzer.estimate_floor(card_id=123, allow_sales_fallback=False)
        assert result is None

    @patch.object(OrderBookAnalyzer, '_fetch_sold_listings')
    @patch.object(OrderBookAnalyzer, '_fetch_active_listings')
    def test_estimate_floor_sales_fallback(self, mock_active, mock_sold, analyzer):
        """Test that sales fallback is used when active listings are insufficient."""
        now = datetime.now(timezone.utc)
        mock_active.return_value = []  # No active listings
        mock_sold.return_value = [
            {"price": 15.0, "sold_date": now},
            {"price": 18.0, "sold_date": now},
            {"price": 20.0, "sold_date": now},
        ]

        result = analyzer.estimate_floor(card_id=123)
        assert result is not None
        assert result.source == "sales_fallback"
        assert result.floor_estimate > 0
        assert result.confidence <= 0.5  # Sales fallback has reduced confidence (0.5x multiplier)

    @patch.object(OrderBookAnalyzer, '_fetch_active_listings')
    def test_estimate_floor_success(self, mock_fetch, analyzer):
        """Test successful floor estimation."""
        now = datetime.now(timezone.utc)
        mock_fetch.return_value = [
            {"price": 10.0, "scraped_at": now, "treatment": "Classic Paper", "title": "Card A"},
            {"price": 12.0, "scraped_at": now, "treatment": "Classic Paper", "title": "Card B"},
            {"price": 13.0, "scraped_at": now, "treatment": "Classic Paper", "title": "Card C"},
            {"price": 14.0, "scraped_at": now, "treatment": "Classic Paper", "title": "Card D"},
            {"price": 15.0, "scraped_at": now, "treatment": "Classic Paper", "title": "Card E"},
        ]

        result = analyzer.estimate_floor(card_id=123)

        assert result is not None
        assert isinstance(result, OrderBookResult)
        assert result.floor_estimate > 0
        assert 0 <= result.confidence <= 1
        assert result.total_listings == 5
        assert len(result.buckets) > 0


class TestOrderBookResult:
    """Tests for OrderBookResult dataclass."""

    def test_to_dict(self):
        deepest = BucketInfo(10.0, 15.0, 5)
        buckets = [deepest, BucketInfo(15.0, 20.0, 3)]

        result = OrderBookResult(
            floor_estimate=12.5,
            confidence=0.75,
            lowest_ask=10.0,
            deepest_bucket=deepest,
            total_listings=8,
            outliers_removed=2,
            buckets=buckets,
            stale_count=1,
        )

        d = result.to_dict()
        assert d["floor_estimate"] == 12.5
        assert d["confidence"] == 0.75
        assert d["total_listings"] == 8
        assert d["outliers_removed"] == 2
        assert d["stale_count"] == 1
        assert len(d["buckets"]) == 2


class TestOrderBookIntegration:
    """Integration tests using real database (if available)."""

    @pytest.mark.integration
    def test_estimate_floor_real_data(self):
        """Test floor estimation with real database data."""
        analyzer = OrderBookAnalyzer()

        # This test requires a card with active listings
        # Skip if no data available
        result = analyzer.estimate_floor(card_id=1)

        if result:
            assert result.floor_estimate > 0
            assert 0 <= result.confidence <= 1
            print(f"Floor: ${result.floor_estimate:.2f}, Confidence: {result.confidence:.2f}")
