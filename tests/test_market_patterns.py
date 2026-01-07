"""
Tests for MarketPatternsService and DealDetector.

Tests cover:
- CardVolatility.deal_threshold for all volatility tiers (stable, moderate, volatile)
- Treatment/rarity multiplier lookups
- estimate_from_treatment_multiplier edge cases
- DealDetector.check_deal with various price/floor/volatility combinations
- Deal quality classification (hot, good, marginal, not_a_deal)
- find_deals_in_listings batch processing
"""

import pytest
from unittest.mock import MagicMock, patch

from app.services.market_patterns import (
    MarketPatternsService,
    CardVolatility,
    DealDetector,
    DealResult,
    TREATMENT_MULTIPLIERS,
    RARITY_MULTIPLIERS,
    VOLATILITY_THRESHOLDS,
    DEFAULT_VOLATILITY,
    get_market_patterns_service,
    get_deal_detector,
    clear_volatility_cache,
)


# ============================================
# CardVolatility Tests
# ============================================


class TestCardVolatility:
    """Tests for CardVolatility dataclass."""

    def test_deal_threshold_stable_card(self):
        """Stable cards (CV < 0.3) should have 15% deal threshold."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Classic Paper",
            coefficient_of_variation=0.15,  # Below 0.3 = stable
            price_range_pct=20.0,
            sales_count=10,
        )

        assert volatility.is_stable is True
        assert volatility.is_volatile is False
        assert volatility.deal_threshold == 0.15

    def test_deal_threshold_moderate_volatility(self):
        """Moderate volatility cards (CV 0.3-0.5) should have 25% deal threshold."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Classic Foil",
            coefficient_of_variation=0.40,  # Between 0.3 and 0.5 = moderate
            price_range_pct=50.0,
            sales_count=8,
        )

        assert volatility.is_stable is False
        assert volatility.is_volatile is False
        assert volatility.deal_threshold == 0.25

    def test_deal_threshold_volatile_card(self):
        """Volatile cards (CV > 0.5) should have 40% deal threshold."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Formless Foil",
            coefficient_of_variation=0.75,  # Above 0.5 = volatile
            price_range_pct=150.0,
            sales_count=5,
        )

        assert volatility.is_stable is False
        assert volatility.is_volatile is True
        assert volatility.deal_threshold == 0.40

    def test_deal_threshold_boundary_stable_to_moderate(self):
        """CV exactly at 0.3 should be moderate (not stable)."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Classic Paper",
            coefficient_of_variation=0.30,  # Exactly at threshold
            price_range_pct=30.0,
            sales_count=10,
        )

        assert volatility.is_stable is False  # 0.3 is NOT < 0.3
        assert volatility.is_volatile is False
        assert volatility.deal_threshold == 0.25

    def test_deal_threshold_boundary_moderate_to_volatile(self):
        """CV exactly at 0.5 should be moderate (not volatile)."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Classic Foil",
            coefficient_of_variation=0.50,  # Exactly at threshold
            price_range_pct=60.0,
            sales_count=8,
        )

        assert volatility.is_stable is False
        assert volatility.is_volatile is False  # 0.5 is NOT > 0.5
        assert volatility.deal_threshold == 0.25

    def test_deal_threshold_above_volatile_threshold(self):
        """CV just above 0.5 should be volatile."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Serialized",
            coefficient_of_variation=0.51,  # Just above 0.5
            price_range_pct=100.0,
            sales_count=4,
        )

        assert volatility.is_volatile is True
        assert volatility.deal_threshold == 0.40

    def test_deal_threshold_zero_cv(self):
        """Zero CV (all same price) should be stable."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Classic Paper",
            coefficient_of_variation=0.0,
            price_range_pct=0.0,
            sales_count=5,
        )

        assert volatility.is_stable is True
        assert volatility.deal_threshold == 0.15

    def test_deal_threshold_extreme_volatility(self):
        """Extremely volatile cards should still have 40% threshold."""
        volatility = CardVolatility(
            card_id=1,
            treatment="Stonefoil",
            coefficient_of_variation=2.5,  # Very high CV
            price_range_pct=500.0,
            sales_count=3,
        )

        assert volatility.is_volatile is True
        assert volatility.deal_threshold == 0.40

    def test_none_treatment(self):
        """CardVolatility should accept None as treatment."""
        volatility = CardVolatility(
            card_id=1,
            treatment=None,
            coefficient_of_variation=0.35,
            price_range_pct=40.0,
            sales_count=10,
        )

        assert volatility.treatment is None
        assert volatility.deal_threshold == 0.25


# ============================================
# MarketPatternsService - Multiplier Tests
# ============================================


class TestTreatmentMultipliers:
    """Tests for treatment multiplier lookups."""

    @pytest.fixture
    def service(self):
        """Create MarketPatternsService instance."""
        return MarketPatternsService()

    def test_classic_paper_baseline(self, service):
        """Classic Paper relative to itself should be 1.0."""
        multiplier = service.get_treatment_multiplier("Classic Paper", "Classic Paper")
        assert multiplier == 1.0

    def test_classic_foil_vs_classic_paper(self, service):
        """Classic Foil should be ~1.55x Classic Paper."""
        multiplier = service.get_treatment_multiplier("Classic Foil", "Classic Paper")
        assert multiplier == 1.55

    def test_formless_foil_vs_classic_paper(self, service):
        """Formless Foil should be ~6.72x Classic Paper."""
        multiplier = service.get_treatment_multiplier("Formless Foil", "Classic Paper")
        assert multiplier == 6.72

    def test_stonefoil_vs_classic_paper(self, service):
        """Stonefoil should be 115x Classic Paper."""
        multiplier = service.get_treatment_multiplier("Stonefoil", "Classic Paper")
        assert multiplier == 115.0

    def test_serialized_vs_classic_foil(self, service):
        """Serialized relative to Classic Foil."""
        # Serialized = 42.71, Classic Foil = 1.55
        # 42.71 / 1.55 = 27.55...
        multiplier = service.get_treatment_multiplier("Serialized", "Classic Foil")
        assert multiplier == pytest.approx(27.55, rel=0.01)

    def test_unknown_treatment_defaults_to_1(self, service):
        """Unknown treatments should default to multiplier 1.0."""
        multiplier = service.get_treatment_multiplier("Unknown Treatment", "Classic Paper")
        assert multiplier == 1.0

    def test_unknown_base_treatment_defaults_to_1(self, service):
        """Unknown base treatment should default to 1.0."""
        multiplier = service.get_treatment_multiplier("Classic Foil", "Unknown Base")
        assert multiplier == 1.55

    def test_both_unknown_treatments(self, service):
        """Both unknown treatments should result in 1.0."""
        multiplier = service.get_treatment_multiplier("Unknown1", "Unknown2")
        assert multiplier == 1.0

    def test_default_base_is_classic_paper(self, service):
        """Default base treatment should be Classic Paper."""
        # Without specifying base, should use Classic Paper
        multiplier = service.get_treatment_multiplier("Formless Foil")
        assert multiplier == 6.72

    def test_all_known_treatments_have_multipliers(self, service):
        """All treatments in TREATMENT_MULTIPLIERS should return valid values."""
        for treatment in TREATMENT_MULTIPLIERS:
            multiplier = service.get_treatment_multiplier(treatment)
            assert multiplier > 0
            assert isinstance(multiplier, float)


class TestRarityMultipliers:
    """Tests for rarity multiplier lookups."""

    @pytest.fixture
    def service(self):
        """Create MarketPatternsService instance."""
        return MarketPatternsService()

    def test_common_baseline(self, service):
        """Common relative to itself should be 1.0."""
        multiplier = service.get_rarity_multiplier("Common", "Common")
        assert multiplier == 1.0

    def test_mythic_vs_common(self, service):
        """Mythic should be ~14.91x Common."""
        multiplier = service.get_rarity_multiplier("Mythic", "Common")
        assert multiplier == 14.91

    def test_rare_vs_uncommon(self, service):
        """Rare relative to Uncommon."""
        # Rare = 1.95, Uncommon = 1.31
        # 1.95 / 1.31 = 1.49...
        multiplier = service.get_rarity_multiplier("Rare", "Uncommon")
        assert multiplier == pytest.approx(1.49, rel=0.01)

    def test_epic_vs_common(self, service):
        """Epic should be 3.73x Common."""
        multiplier = service.get_rarity_multiplier("Epic", "Common")
        assert multiplier == 3.73

    def test_secret_mythic_vs_mythic(self, service):
        """Secret Mythic relative to Mythic."""
        # Secret Mythic = 20.0, Mythic = 14.91
        # 20.0 / 14.91 = 1.34...
        multiplier = service.get_rarity_multiplier("Secret Mythic", "Mythic")
        assert multiplier == pytest.approx(1.34, rel=0.01)

    def test_unknown_rarity_defaults_to_1(self, service):
        """Unknown rarity should default to 1.0."""
        multiplier = service.get_rarity_multiplier("Unknown Rarity")
        assert multiplier == 1.0

    def test_default_base_is_common(self, service):
        """Default base rarity should be Common."""
        multiplier = service.get_rarity_multiplier("Epic")
        assert multiplier == 3.73

    def test_all_known_rarities_have_multipliers(self, service):
        """All rarities in RARITY_MULTIPLIERS should return valid values."""
        for rarity in RARITY_MULTIPLIERS:
            multiplier = service.get_rarity_multiplier(rarity)
            assert multiplier > 0
            assert isinstance(multiplier, float)


# ============================================
# MarketPatternsService - Estimate Tests
# ============================================


class TestEstimateFromTreatmentMultiplier:
    """Tests for price estimation from treatment multipliers."""

    @pytest.fixture
    def service(self):
        """Create MarketPatternsService instance."""
        return MarketPatternsService()

    def test_estimate_formless_from_classic_paper(self, service):
        """Estimate Formless Foil from Classic Paper price."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=10.00,
            known_treatment="Classic Paper",
            target_treatment="Formless Foil",
        )
        assert estimated == 67.20  # 10.00 * 6.72

    def test_estimate_classic_paper_from_formless(self, service):
        """Estimate Classic Paper from Formless Foil price (reverse)."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=67.20,
            known_treatment="Formless Foil",
            target_treatment="Classic Paper",
        )
        # 67.20 * (1.0 / 6.72) = 10.00
        assert estimated == pytest.approx(10.00, rel=0.01)

    def test_estimate_stonefoil_from_classic_paper(self, service):
        """Estimate Stonefoil from Classic Paper price."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=13.00,
            known_treatment="Classic Paper",
            target_treatment="Stonefoil",
        )
        assert estimated == 1495.00  # 13.00 * 115.0

    def test_estimate_same_treatment(self, service):
        """Estimating same treatment should return same price."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=25.00,
            known_treatment="Classic Foil",
            target_treatment="Classic Foil",
        )
        assert estimated == 25.00

    def test_estimate_unknown_known_treatment_returns_none(self, service):
        """Unknown known_treatment should return None."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=10.00,
            known_treatment="Unknown Treatment",
            target_treatment="Classic Foil",
        )
        assert estimated is None

    def test_estimate_unknown_target_treatment_returns_none(self, service):
        """Unknown target_treatment should return None."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=10.00,
            known_treatment="Classic Paper",
            target_treatment="Unknown Treatment",
        )
        assert estimated is None

    def test_estimate_both_unknown_returns_none(self, service):
        """Both unknown treatments should return None."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=10.00,
            known_treatment="Unknown1",
            target_treatment="Unknown2",
        )
        assert estimated is None

    def test_estimate_zero_price(self, service):
        """Zero known price should return 0."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=0.00,
            known_treatment="Classic Paper",
            target_treatment="Formless Foil",
        )
        assert estimated == 0.00

    def test_estimate_rounds_to_two_decimals(self, service):
        """Estimated prices should be rounded to 2 decimal places."""
        estimated = service.estimate_from_treatment_multiplier(
            known_price=7.33,
            known_treatment="Classic Paper",
            target_treatment="Formless Foil",
        )
        # 7.33 * 6.72 = 49.2576 -> 49.26
        assert estimated == 49.26


# ============================================
# MarketPatternsService - Volatility Tests
# ============================================


class TestGetCardVolatility:
    """Tests for card volatility calculation."""

    @pytest.fixture
    def service(self):
        """Create MarketPatternsService instance."""
        return MarketPatternsService()

    def test_returns_default_volatility_on_db_error(self, service):
        """Should return default volatility when database query fails."""
        with patch.object(service, "session", None):
            with patch("app.services.market_patterns.engine") as mock_engine:
                mock_engine.connect.side_effect = Exception("DB Error")

                volatility = service.get_card_volatility(card_id=1)

                assert volatility.coefficient_of_variation == DEFAULT_VOLATILITY
                assert volatility.sales_count == 0

    def test_caches_volatility_results(self, service):
        """Should cache volatility results for repeated calls."""
        # Clear the global cache first
        clear_volatility_cache()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (25.0, 5.0, 20.0, 35.0, 10)

        with patch("app.services.market_patterns.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            # First call
            vol1 = service.get_card_volatility(card_id=1, treatment="Classic Paper")

            # Second call - should use cache
            vol2 = service.get_card_volatility(card_id=1, treatment="Classic Paper")

            # Should only execute once
            assert mock_conn.execute.call_count == 1
            # Cache returns a copy, so check equality instead of identity
            assert vol1.card_id == vol2.card_id
            assert vol1.treatment == vol2.treatment
            assert vol1.coefficient_of_variation == vol2.coefficient_of_variation

        # Clean up
        clear_volatility_cache()

    def test_different_treatments_cached_separately(self):
        """Different treatments should have separate cache entries."""
        # Clear the global volatility cache first
        clear_volatility_cache()
        fresh_service = MarketPatternsService()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (25.0, 5.0, 20.0, 35.0, 10)

        with patch("app.services.market_patterns.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            fresh_service.get_card_volatility(card_id=1, treatment="Classic Paper")
            fresh_service.get_card_volatility(card_id=1, treatment="Classic Foil")

            # Should execute twice for different treatments
            assert mock_conn.execute.call_count == 2

        # Clean up
        clear_volatility_cache()

    def test_returns_default_with_insufficient_sales(self, service):
        """Should return default volatility when fewer than 3 sales."""
        mock_result = MagicMock()
        mock_result.fetchone.return_value = (25.0, 5.0, 20.0, 30.0, 2)  # Only 2 sales

        with patch("app.services.market_patterns.engine") as mock_engine:
            mock_conn = MagicMock()
            mock_conn.execute.return_value = mock_result
            mock_engine.connect.return_value.__enter__.return_value = mock_conn

            volatility = service.get_card_volatility(card_id=1)

            assert volatility.coefficient_of_variation == DEFAULT_VOLATILITY
            assert volatility.sales_count == 2


# ============================================
# MarketPatternsService - is_deal Tests
# ============================================


class TestIsDeal:
    """Tests for the is_deal method."""

    @pytest.fixture
    def service(self):
        """Create MarketPatternsService instance."""
        return MarketPatternsService()

    def test_is_deal_with_zero_floor(self, service):
        """Zero floor price should return not a deal."""
        is_deal, discount = service.is_deal(
            card_id=1,
            treatment="Classic Paper",
            price=10.00,
            floor_price=0.00,
        )
        assert is_deal is False
        assert discount == 0.0

    def test_is_deal_with_zero_price(self, service):
        """Zero price should return not a deal."""
        is_deal, discount = service.is_deal(
            card_id=1,
            treatment="Classic Paper",
            price=0.00,
            floor_price=25.00,
        )
        assert is_deal is False
        assert discount == 0.0

    def test_is_deal_with_negative_floor(self, service):
        """Negative floor price should return not a deal."""
        is_deal, discount = service.is_deal(
            card_id=1,
            treatment="Classic Paper",
            price=10.00,
            floor_price=-5.00,
        )
        assert is_deal is False
        assert discount == 0.0

    def test_is_deal_calculates_discount_pct(self, service):
        """Should correctly calculate discount percentage."""
        # Mock volatility to get a known threshold
        mock_volatility = CardVolatility(
            card_id=1,
            treatment="Classic Paper",
            coefficient_of_variation=0.20,  # Stable = 15% threshold
            price_range_pct=20.0,
            sales_count=10,
        )

        with patch.object(service, "get_card_volatility", return_value=mock_volatility):
            # Price 17.00 vs floor 20.00 = 15% discount
            is_deal, discount = service.is_deal(
                card_id=1,
                treatment="Classic Paper",
                price=17.00,
                floor_price=20.00,
            )

            assert is_deal is True  # 15% >= 15% threshold
            assert discount == 15.0


# ============================================
# DealDetector Tests
# ============================================


class TestDealDetectorCheckDeal:
    """Tests for DealDetector.check_deal method."""

    @pytest.fixture
    def detector(self):
        """Create DealDetector instance."""
        return DealDetector()

    def test_check_deal_zero_floor_returns_not_a_deal(self, detector):
        """Zero floor should return not_a_deal."""
        result = detector.check_deal(
            card_id=1,
            price=10.00,
            treatment="Classic Paper",
            floor_price=0.00,
        )

        assert result.is_deal is False
        assert result.deal_quality == "not_a_deal"
        assert result.discount_pct == 0.0

    def test_check_deal_zero_price_returns_not_a_deal(self, detector):
        """Zero price should return not_a_deal."""
        result = detector.check_deal(
            card_id=1,
            price=0.00,
            treatment="Classic Paper",
            floor_price=25.00,
        )

        assert result.is_deal is False
        assert result.deal_quality == "not_a_deal"

    def test_check_deal_fetches_floor_when_not_provided(self, detector):
        """Should fetch floor price when not provided."""
        mock_floor_result = MagicMock()
        mock_floor_result.price = 100.00

        mock_volatility = CardVolatility(
            card_id=1,
            treatment="Classic Paper",
            coefficient_of_variation=0.20,
            price_range_pct=20.0,
            sales_count=10,
        )

        with patch.object(detector.floor_service, "get_floor_price", return_value=mock_floor_result):
            with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
                result = detector.check_deal(
                    card_id=1,
                    price=80.00,
                    treatment="Classic Paper",
                    floor_price=None,  # Should trigger fetch
                )

        # 20% discount should exceed 15% threshold for stable card
        assert result.floor_price == 100.00
        assert result.is_deal is True

    def test_check_deal_uses_provided_floor(self, detector):
        """Should use provided floor price without fetching."""
        mock_volatility = CardVolatility(
            card_id=1,
            treatment="Classic Paper",
            coefficient_of_variation=0.20,
            price_range_pct=20.0,
            sales_count=10,
        )

        # Patch the _floor_service directly since floor_service is a property
        mock_floor_service = MagicMock()
        detector._floor_service = mock_floor_service

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=85.00,
                treatment="Classic Paper",
                floor_price=100.00,  # Provided floor
            )

            # Should NOT call get_floor_price when floor is provided
            mock_floor_service.get_floor_price.assert_not_called()

        assert result.floor_price == 100.00


class TestDealQualityClassification:
    """Tests for deal quality classification (hot, good, marginal, not_a_deal)."""

    @pytest.fixture
    def detector(self):
        """Create DealDetector instance."""
        return DealDetector()

    def _create_mock_volatility(self, cv: float):
        """Helper to create mock volatility with specific CV."""
        return CardVolatility(
            card_id=1,
            treatment="Classic Paper",
            coefficient_of_variation=cv,
            price_range_pct=50.0,
            sales_count=10,
        )

    def test_hot_deal_stable_card(self, detector):
        """Hot deal for stable card: discount >= 2x threshold (30%+ for 15% threshold)."""
        mock_volatility = self._create_mock_volatility(0.15)  # Stable, 15% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=65.00,  # 35% below floor
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is True
        assert result.deal_quality == "hot"
        assert result.discount_pct == 35.0

    def test_good_deal_stable_card(self, detector):
        """Good deal for stable card: discount >= 1.5x threshold (22.5%+ for 15% threshold)."""
        mock_volatility = self._create_mock_volatility(0.15)  # Stable, 15% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=76.00,  # 24% below floor
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is True
        assert result.deal_quality == "good"

    def test_marginal_deal_stable_card(self, detector):
        """Marginal deal for stable card: discount >= threshold (15%+)."""
        mock_volatility = self._create_mock_volatility(0.15)  # Stable, 15% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=85.00,  # 15% below floor
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is True
        assert result.deal_quality == "marginal"

    def test_not_a_deal_stable_card(self, detector):
        """Not a deal for stable card: discount < threshold."""
        mock_volatility = self._create_mock_volatility(0.15)  # Stable, 15% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=90.00,  # 10% below floor - not enough
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is False
        assert result.deal_quality == "not_a_deal"
        assert result.discount_pct == 10.0

    def test_hot_deal_volatile_card(self, detector):
        """Hot deal for volatile card: discount >= 80% (2x 40% threshold)."""
        mock_volatility = self._create_mock_volatility(0.75)  # Volatile, 40% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=15.00,  # 85% below floor
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is True
        assert result.deal_quality == "hot"

    def test_marginal_deal_volatile_card(self, detector):
        """Marginal deal for volatile card: discount 40-59%."""
        mock_volatility = self._create_mock_volatility(0.75)  # Volatile, 40% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=58.00,  # 42% below floor
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is True
        assert result.deal_quality == "marginal"

    def test_not_a_deal_volatile_card_35_percent_discount(self, detector):
        """35% discount on volatile card is NOT a deal (threshold is 40%)."""
        mock_volatility = self._create_mock_volatility(0.75)  # Volatile, 40% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=65.00,  # 35% below floor
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is False
        assert result.deal_quality == "not_a_deal"

    def test_price_above_floor_is_not_deal(self, detector):
        """Price above floor should not be a deal."""
        mock_volatility = self._create_mock_volatility(0.15)

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=110.00,  # Above floor
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.is_deal is False
        assert result.deal_quality == "not_a_deal"
        assert result.discount_pct == -10.0  # Negative discount

    def test_deal_result_includes_threshold_pct(self, detector):
        """DealResult should include threshold percentage."""
        mock_volatility = self._create_mock_volatility(0.40)  # Moderate, 25% threshold

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=70.00,
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.threshold_pct == 25.0

    def test_deal_result_includes_volatility_cv(self, detector):
        """DealResult should include volatility CV."""
        mock_volatility = self._create_mock_volatility(0.42)

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            result = detector.check_deal(
                card_id=1,
                price=70.00,
                treatment="Classic Paper",
                floor_price=100.00,
            )

        assert result.volatility_cv == 0.42


class TestDealResultToDict:
    """Tests for DealResult.to_dict serialization."""

    def test_to_dict_all_fields(self):
        """to_dict should include all fields."""
        result = DealResult(
            is_deal=True,
            card_id=123,
            treatment="Classic Foil",
            price=75.00,
            floor_price=100.00,
            discount_pct=25.0,
            threshold_pct=15.0,
            volatility_cv=0.2,
            deal_quality="good",
        )

        d = result.to_dict()

        assert d["is_deal"] is True
        assert d["card_id"] == 123
        assert d["treatment"] == "Classic Foil"
        assert d["price"] == 75.00
        assert d["floor_price"] == 100.00
        assert d["discount_pct"] == 25.0
        assert d["threshold_pct"] == 15.0
        assert d["volatility_cv"] == 0.2
        assert d["deal_quality"] == "good"

    def test_to_dict_none_treatment(self):
        """to_dict should handle None treatment."""
        result = DealResult(
            is_deal=False,
            card_id=456,
            treatment=None,
            price=50.00,
            floor_price=45.00,
            discount_pct=-11.1,
            threshold_pct=25.0,
            volatility_cv=0.4,
            deal_quality="not_a_deal",
        )

        d = result.to_dict()
        assert d["treatment"] is None


# ============================================
# DealDetector.find_deals_in_listings Tests
# ============================================


class TestFindDealsInListings:
    """Tests for batch deal detection in listings."""

    @pytest.fixture
    def detector(self):
        """Create DealDetector instance."""
        return DealDetector()

    def _create_mock_volatility(self, cv: float):
        """Helper to create stable mock volatility."""
        return CardVolatility(
            card_id=1,
            treatment=None,
            coefficient_of_variation=cv,
            price_range_pct=20.0,
            sales_count=10,
        )

    def test_finds_deals_in_batch(self, detector):
        """Should find deals in a batch of listings."""
        mock_volatility = self._create_mock_volatility(0.15)  # 15% threshold

        listings = [
            {"card_id": 1, "price": 85.00, "floor_price": 100.00},  # 15% - marginal
            {"card_id": 2, "price": 70.00, "floor_price": 100.00},  # 30% - good/hot
            {"card_id": 3, "price": 95.00, "floor_price": 100.00},  # 5% - not a deal
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            deals = detector.find_deals_in_listings(listings, min_quality="marginal")

        # Should find 2 deals (85.00 and 70.00)
        assert len(deals) == 2

    def test_filters_by_min_quality_marginal(self, detector):
        """min_quality='marginal' should include marginal and above."""
        mock_volatility = self._create_mock_volatility(0.15)  # 15% threshold

        listings = [
            {"card_id": 1, "price": 85.00, "floor_price": 100.00},  # 15% - marginal
            {"card_id": 2, "price": 75.00, "floor_price": 100.00},  # 25% - good
            {"card_id": 3, "price": 65.00, "floor_price": 100.00},  # 35% - hot
            {"card_id": 4, "price": 90.00, "floor_price": 100.00},  # 10% - not_a_deal
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            deals = detector.find_deals_in_listings(listings, min_quality="marginal")

        assert len(deals) == 3  # marginal, good, hot

    def test_filters_by_min_quality_good(self, detector):
        """min_quality='good' should include good and hot only."""
        mock_volatility = self._create_mock_volatility(0.15)  # 15% threshold

        listings = [
            {"card_id": 1, "price": 85.00, "floor_price": 100.00},  # marginal
            {"card_id": 2, "price": 75.00, "floor_price": 100.00},  # good
            {"card_id": 3, "price": 65.00, "floor_price": 100.00},  # hot
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            deals = detector.find_deals_in_listings(listings, min_quality="good")

        assert len(deals) == 2  # good, hot only

    def test_filters_by_min_quality_hot(self, detector):
        """min_quality='hot' should include hot deals only."""
        mock_volatility = self._create_mock_volatility(0.15)  # 15% threshold

        listings = [
            {"card_id": 1, "price": 85.00, "floor_price": 100.00},  # marginal
            {"card_id": 2, "price": 75.00, "floor_price": 100.00},  # good
            {"card_id": 3, "price": 65.00, "floor_price": 100.00},  # hot
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            deals = detector.find_deals_in_listings(listings, min_quality="hot")

        assert len(deals) == 1  # hot only

    def test_sorts_by_discount_descending(self, detector):
        """Results should be sorted by discount (best deals first)."""
        mock_volatility = self._create_mock_volatility(0.15)

        listings = [
            {"card_id": 1, "price": 85.00, "floor_price": 100.00},  # 15% discount
            {"card_id": 2, "price": 65.00, "floor_price": 100.00},  # 35% discount
            {"card_id": 3, "price": 75.00, "floor_price": 100.00},  # 25% discount
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            deals = detector.find_deals_in_listings(listings, min_quality="marginal")

        # Best discount first
        assert deals[0].discount_pct == 35.0
        assert deals[1].discount_pct == 25.0
        assert deals[2].discount_pct == 15.0

    def test_handles_empty_listings(self, detector):
        """Should return empty list for empty input."""
        deals = detector.find_deals_in_listings([], min_quality="marginal")
        assert deals == []

    def test_handles_listings_without_floor_price(self, detector):
        """Should fetch floor price when not provided in listing."""
        mock_volatility = self._create_mock_volatility(0.15)
        mock_floor_result = MagicMock()
        mock_floor_result.price = 100.00

        listings = [
            {"card_id": 1, "price": 85.00},  # No floor_price
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            with patch.object(detector.floor_service, "get_floor_price", return_value=mock_floor_result):
                deals = detector.find_deals_in_listings(listings, min_quality="marginal")

        assert len(deals) == 1

    def test_handles_listings_with_treatment(self, detector):
        """Should pass treatment to check_deal."""
        mock_volatility = self._create_mock_volatility(0.15)

        listings = [
            {"card_id": 1, "price": 85.00, "floor_price": 100.00, "treatment": "Classic Foil"},
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            deals = detector.find_deals_in_listings(listings, min_quality="marginal")

        assert len(deals) == 1
        assert deals[0].treatment == "Classic Foil"

    def test_default_min_quality_is_marginal(self, detector):
        """Default min_quality should be marginal."""
        mock_volatility = self._create_mock_volatility(0.15)

        listings = [
            {"card_id": 1, "price": 85.00, "floor_price": 100.00},  # marginal
            {"card_id": 2, "price": 90.00, "floor_price": 100.00},  # not_a_deal
        ]

        with patch.object(detector._market_patterns, "get_card_volatility", return_value=mock_volatility):
            deals = detector.find_deals_in_listings(listings)  # No min_quality

        assert len(deals) == 1  # Only marginal included


# ============================================
# Factory Function Tests
# ============================================


class TestFactoryFunctions:
    """Tests for factory functions."""

    def test_get_market_patterns_service_without_session(self):
        """Should create MarketPatternsService without session."""
        service = get_market_patterns_service()
        assert isinstance(service, MarketPatternsService)
        assert service.session is None

    def test_get_market_patterns_service_with_session(self):
        """Should create MarketPatternsService with session."""
        mock_session = MagicMock()
        service = get_market_patterns_service(mock_session)
        assert service.session is mock_session

    def test_get_deal_detector_without_session(self):
        """Should create DealDetector without session."""
        detector = get_deal_detector()
        assert isinstance(detector, DealDetector)
        assert detector.session is None

    def test_get_deal_detector_with_session(self):
        """Should create DealDetector with session."""
        mock_session = MagicMock()
        detector = get_deal_detector(mock_session)
        assert detector.session is mock_session


# ============================================
# Constants Verification Tests
# ============================================


class TestConstants:
    """Tests to verify constant values match expected values."""

    def test_volatility_thresholds(self):
        """Verify volatility threshold values."""
        assert VOLATILITY_THRESHOLDS["stable"] == 0.3
        assert VOLATILITY_THRESHOLDS["moderate"] == 0.5
        assert VOLATILITY_THRESHOLDS["volatile"] == 1.0

    def test_default_volatility(self):
        """Verify default volatility value."""
        assert DEFAULT_VOLATILITY == 0.5

    def test_treatment_multipliers_include_expected_treatments(self):
        """Verify key treatments exist in multipliers."""
        expected = [
            "Classic Paper",
            "Classic Foil",
            "Formless Foil",
            "Stonefoil",
            "Serialized",
            "Promo",
            "Graded/Preslab",
        ]
        for treatment in expected:
            assert treatment in TREATMENT_MULTIPLIERS

    def test_rarity_multipliers_include_expected_rarities(self):
        """Verify key rarities exist in multipliers."""
        expected = [
            "Common",
            "Uncommon",
            "Rare",
            "Epic",
            "Mythic",
            "Secret Mythic",
        ]
        for rarity in expected:
            assert rarity in RARITY_MULTIPLIERS

    def test_multipliers_are_ascending_for_rarities(self):
        """Rarity multipliers should increase with rarity."""
        assert RARITY_MULTIPLIERS["Common"] < RARITY_MULTIPLIERS["Uncommon"]
        assert RARITY_MULTIPLIERS["Uncommon"] < RARITY_MULTIPLIERS["Rare"]
        assert RARITY_MULTIPLIERS["Rare"] < RARITY_MULTIPLIERS["Epic"]
        assert RARITY_MULTIPLIERS["Epic"] < RARITY_MULTIPLIERS["Mythic"]
        assert RARITY_MULTIPLIERS["Mythic"] < RARITY_MULTIPLIERS["Secret Mythic"]
