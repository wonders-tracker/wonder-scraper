"""
Unit and integration tests for the Fair Market Price service.

Tests cover:
- Floor price calculation with base treatments
- Floor price fallback to cheapest treatment
- Floor price time window fallbacks (30d -> 90d)
- COALESCE handling for NULL sold_date
- FMP formula calculations
- Treatment multipliers
- Rarity multipliers
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

from app.services.pricing import (
    FairMarketPriceService,
    DEFAULT_RARITY_MULTIPLIERS,
    DEFAULT_TREATMENT_MULTIPLIERS,
    BASE_TREATMENTS,
)


class TestFloorPriceCalculation:
    """Tests for floor price calculation logic."""

    def test_base_treatments_defined(self):
        """Verify base treatments are Classic Paper and Classic Foil."""
        assert "Classic Paper" in BASE_TREATMENTS
        assert "Classic Foil" in BASE_TREATMENTS
        assert len(BASE_TREATMENTS) == 2

    def test_default_rarity_multipliers(self):
        """Verify default rarity multipliers are sensible."""
        assert DEFAULT_RARITY_MULTIPLIERS["Common"] == 1.0
        assert DEFAULT_RARITY_MULTIPLIERS["Uncommon"] > DEFAULT_RARITY_MULTIPLIERS["Common"]
        assert DEFAULT_RARITY_MULTIPLIERS["Rare"] > DEFAULT_RARITY_MULTIPLIERS["Uncommon"]
        assert DEFAULT_RARITY_MULTIPLIERS["Legendary"] > DEFAULT_RARITY_MULTIPLIERS["Rare"]
        assert DEFAULT_RARITY_MULTIPLIERS["Mythic"] > DEFAULT_RARITY_MULTIPLIERS["Legendary"]

    def test_default_treatment_multipliers(self):
        """Verify default treatment multipliers are sensible."""
        assert DEFAULT_TREATMENT_MULTIPLIERS["Classic Paper"] == 1.0
        assert DEFAULT_TREATMENT_MULTIPLIERS["Classic Foil"] > DEFAULT_TREATMENT_MULTIPLIERS["Classic Paper"]
        assert DEFAULT_TREATMENT_MULTIPLIERS["OCM Serialized"] > DEFAULT_TREATMENT_MULTIPLIERS["Formless Foil"]


class TestFloorPriceIntegration:
    """Integration tests for floor price calculation using real database."""

    @pytest.fixture
    def pricing_service(self, integration_session):
        """Create pricing service with real database session."""
        return FairMarketPriceService(integration_session)

    def test_floor_price_with_base_treatments(self, pricing_service, integration_session):
        """
        Test that floor price uses base treatments (Classic Paper/Foil) when available.
        """
        from sqlmodel import text

        # Find a card that has Classic Paper sales
        result = integration_session.execute(text("""
            SELECT DISTINCT card_id FROM marketprice
            WHERE treatment IN ('Classic Paper', 'Classic Foil')
            AND listing_type = 'sold'
            AND COALESCE(sold_date, scraped_at) >= NOW() - INTERVAL '30 days'
            LIMIT 1
        """)).fetchone()

        if not result:
            pytest.skip("No cards with Classic Paper/Foil sales in last 30 days")

        card_id = result[0]
        floor = pricing_service.calculate_floor_price(card_id)

        assert floor is not None
        assert floor > 0
        assert isinstance(floor, float)

    def test_floor_price_fallback_to_cheapest_treatment(self, pricing_service, integration_session):
        """
        Test that floor price falls back to cheapest treatment when no base treatments exist.
        This tests the PROGO scenario where only Formless Foil/OCM/Promo exist.
        """
        from sqlmodel import text

        # Find a card that has NO Classic Paper/Foil but has other treatments
        result = integration_session.execute(text("""
            SELECT mp.card_id
            FROM marketprice mp
            WHERE mp.listing_type = 'sold'
            AND COALESCE(mp.sold_date, mp.scraped_at) >= NOW() - INTERVAL '30 days'
            GROUP BY mp.card_id
            HAVING COUNT(*) FILTER (WHERE mp.treatment IN ('Classic Paper', 'Classic Foil')) = 0
            AND COUNT(*) > 0
            LIMIT 1
        """)).fetchone()

        if not result:
            pytest.skip("No cards without Classic Paper/Foil sales found")

        card_id = result[0]
        floor = pricing_service.calculate_floor_price(card_id)

        # Should have a floor (from cheapest treatment fallback)
        assert floor is not None
        assert floor > 0

        # Verify it's using the cheapest treatment
        treatments = integration_session.execute(text("""
            SELECT treatment, AVG(price) as avg_price
            FROM (
                SELECT treatment, price,
                       ROW_NUMBER() OVER (PARTITION BY treatment ORDER BY price ASC) as rn
                FROM marketprice
                WHERE card_id = :card_id
                  AND listing_type = 'sold'
                  AND COALESCE(sold_date, scraped_at) >= NOW() - INTERVAL '30 days'
            ) ranked
            WHERE rn <= 4
            GROUP BY treatment
            ORDER BY avg_price ASC
        """), {"card_id": card_id}).fetchall()

        if treatments:
            cheapest_avg = float(treatments[0][1])
            # Floor should be close to the cheapest treatment's average
            assert abs(floor - cheapest_avg) < 0.01

    def test_floor_price_90_day_fallback(self, pricing_service, integration_session):
        """
        Test that floor price falls back to 90 days when no 30-day sales exist.
        """
        from sqlmodel import text

        # Find a card with sales only in the 31-90 day window
        result = integration_session.execute(text("""
            SELECT card_id FROM marketprice
            WHERE listing_type = 'sold'
            AND COALESCE(sold_date, scraped_at) >= NOW() - INTERVAL '90 days'
            AND COALESCE(sold_date, scraped_at) < NOW() - INTERVAL '30 days'
            GROUP BY card_id
            HAVING COUNT(*) >= 4
            LIMIT 1
        """)).fetchone()

        if not result:
            pytest.skip("No cards with only 31-90 day old sales found")

        card_id = result[0]
        floor = pricing_service.calculate_floor_price(card_id)

        # Should still get a floor from 90-day fallback
        assert floor is not None
        assert floor > 0

    def test_floor_price_returns_none_for_no_sales(self, pricing_service):
        """
        Test that floor price returns None for cards with no sales.
        """
        # Use a card ID that doesn't exist
        floor = pricing_service.calculate_floor_price(999999)
        assert floor is None

    def test_floor_price_ignores_active_listings(self, pricing_service, integration_session):
        """
        Test that floor price calculation ignores active listings.
        """
        from sqlmodel import text

        # Find a card with both active and sold listings
        result = integration_session.execute(text("""
            SELECT card_id FROM marketprice
            WHERE listing_type = 'active'
            AND card_id IN (
                SELECT card_id FROM marketprice WHERE listing_type = 'sold'
            )
            LIMIT 1
        """)).fetchone()

        if not result:
            pytest.skip("No cards with both active and sold listings")

        card_id = result[0]

        # Get the lowest active listing price
        active_min = integration_session.execute(text("""
            SELECT MIN(price) FROM marketprice
            WHERE card_id = :card_id AND listing_type = 'active'
        """), {"card_id": card_id}).scalar()

        floor = pricing_service.calculate_floor_price(card_id)

        # Floor should be based on sold prices, not active listings
        # If active min is very low (like $0.99), floor should be different
        if active_min and active_min < 1.0 and floor:
            assert floor != active_min, "Floor should not equal suspicious active listing price"


class TestFMPCalculation:
    """Tests for Fair Market Price formula calculation."""

    @pytest.fixture
    def pricing_service(self, integration_session):
        """Create pricing service with real database session."""
        return FairMarketPriceService(integration_session)

    def test_fmp_returns_breakdown(self, pricing_service, integration_session):
        """Test that FMP calculation returns proper breakdown."""
        from sqlmodel import text

        # Find a Single card with sales
        result = integration_session.execute(text("""
            SELECT c.id, c.set_name, r.name as rarity_name
            FROM card c
            JOIN rarity r ON c.rarity_id = r.id
            WHERE c.product_type = 'Single'
            AND c.id IN (SELECT card_id FROM marketprice WHERE listing_type = 'sold')
            LIMIT 1
        """)).fetchone()

        if not result:
            pytest.skip("No Single cards with sales found")

        card_id, set_name, rarity_name = result

        fmp_result = pricing_service.calculate_fmp(
            card_id=card_id,
            set_name=set_name,
            rarity_name=rarity_name,
            product_type="Single"
        )

        assert "fair_market_price" in fmp_result
        assert "floor_price" in fmp_result
        assert "breakdown" in fmp_result
        assert "calculation_method" in fmp_result

        # For Singles, should have formula method
        assert fmp_result["calculation_method"] == "formula"

        if fmp_result["breakdown"]:
            assert "base_set_price" in fmp_result["breakdown"]
            assert "rarity_multiplier" in fmp_result["breakdown"]
            assert "treatment_multiplier" in fmp_result["breakdown"]
            assert "liquidity_adjustment" in fmp_result["breakdown"]

    def test_fmp_non_single_uses_median(self, pricing_service, integration_session):
        """Test that non-Single products use median price instead of formula."""
        from sqlmodel import text

        # Find a Box/Pack with sales
        result = integration_session.execute(text("""
            SELECT c.id, c.set_name, r.name as rarity_name, c.product_type
            FROM card c
            JOIN rarity r ON c.rarity_id = r.id
            WHERE c.product_type IN ('Box', 'Pack', 'Bundle')
            AND c.id IN (SELECT card_id FROM marketprice WHERE listing_type = 'sold')
            LIMIT 1
        """)).fetchone()

        if not result:
            pytest.skip("No Box/Pack/Bundle products with sales found")

        card_id, set_name, rarity_name, product_type = result

        fmp_result = pricing_service.calculate_fmp(
            card_id=card_id,
            set_name=set_name,
            rarity_name=rarity_name,
            product_type=product_type
        )

        # For non-Singles, should use median method
        assert fmp_result["calculation_method"] == "median"
        assert fmp_result["breakdown"] is None

    def test_liquidity_adjustment_bounds(self, pricing_service):
        """Test that liquidity adjustment is within expected bounds."""
        # Test with various card IDs
        for card_id in [1, 10, 100, 362]:  # PROGO is 362
            adj = pricing_service.get_liquidity_adjustment(card_id)
            assert 0.85 <= adj <= 1.0, f"Liquidity adjustment {adj} out of bounds for card {card_id}"


class TestCoalesceHandling:
    """Tests for COALESCE(sold_date, scraped_at) handling."""

    @pytest.fixture
    def pricing_service(self, integration_session):
        """Create pricing service with real database session."""
        return FairMarketPriceService(integration_session)

    def test_null_sold_date_included_in_floor(self, pricing_service, integration_session):
        """Test that sales with NULL sold_date are included using scraped_at."""
        from sqlmodel import text

        # Check if there are any NULL sold_date records
        null_count = integration_session.execute(text("""
            SELECT COUNT(*) FROM marketprice
            WHERE listing_type = 'sold' AND sold_date IS NULL
        """)).scalar()

        if null_count == 0:
            pytest.skip("No sales with NULL sold_date in database")

        # Find a card with NULL sold_date sales
        result = integration_session.execute(text("""
            SELECT card_id FROM marketprice
            WHERE listing_type = 'sold' AND sold_date IS NULL
            LIMIT 1
        """)).fetchone()

        card_id = result[0]
        floor = pricing_service.calculate_floor_price(card_id, days=365)  # Wide window

        # Should still get a result even with NULL sold_date
        assert floor is not None


class TestSpecificCards:
    """Tests for specific known cards (regression tests)."""

    @pytest.fixture
    def pricing_service(self, integration_session):
        """Create pricing service with real database session."""
        return FairMarketPriceService(integration_session)

    def test_progo_floor_uses_formless_foil(self, pricing_service, integration_session):
        """
        Regression test: PROGO (card 362) should use Formless Foil for floor
        since it has no Classic Paper/Foil sales.
        """
        from sqlmodel import text

        # Check if PROGO exists and has the expected treatment distribution
        progo_check = integration_session.execute(text("""
            SELECT treatment, COUNT(*) as cnt
            FROM marketprice
            WHERE card_id = 362 AND listing_type = 'sold'
            GROUP BY treatment
            ORDER BY cnt DESC
        """)).fetchall()

        if not progo_check:
            pytest.skip("PROGO (card 362) not found or has no sales")

        treatments = {row[0]: row[1] for row in progo_check}

        # Verify PROGO has no Classic Paper/Foil (the bug scenario)
        has_base = "Classic Paper" in treatments or "Classic Foil" in treatments
        has_formless = "Formless Foil" in treatments

        if has_base:
            pytest.skip("PROGO now has Classic Paper/Foil sales, test not applicable")

        if not has_formless:
            pytest.skip("PROGO doesn't have Formless Foil sales")

        # Calculate floor
        floor = pricing_service.calculate_floor_price(362)

        assert floor is not None, "PROGO should have a floor price (from Formless Foil fallback)"

        # Get expected floor from Formless Foil
        formless_floor = integration_session.execute(text("""
            SELECT AVG(price) FROM (
                SELECT price FROM marketprice
                WHERE card_id = 362
                  AND listing_type = 'sold'
                  AND treatment = 'Formless Foil'
                  AND COALESCE(sold_date, scraped_at) >= NOW() - INTERVAL '30 days'
                ORDER BY price ASC
                LIMIT 4
            ) as lowest
        """)).scalar()

        if formless_floor:
            # Floor should be based on Formless Foil (cheapest available treatment)
            assert abs(floor - float(formless_floor)) < 1.0, \
                f"PROGO floor {floor} should be close to Formless Foil avg {formless_floor}"

    def test_progo_floor_not_active_listing(self, pricing_service, integration_session):
        """
        Regression test: PROGO floor should NOT be $0.99 (the active listing price).
        """
        from sqlmodel import text

        # Check if PROGO has a $0.99 active listing
        active_check = integration_session.execute(text("""
            SELECT price FROM marketprice
            WHERE card_id = 362 AND listing_type = 'active'
            ORDER BY price ASC LIMIT 1
        """)).fetchone()

        floor = pricing_service.calculate_floor_price(362)

        if floor and active_check and active_check[0] < 1.0:
            assert floor != active_check[0], \
                f"PROGO floor {floor} should not equal low active listing {active_check[0]}"
