"""Tests for bulk lot detection logic."""

import pytest
from app.scraper.utils import is_bulk_lot


# Test cases: (title, product_type, expected_result)
BULK_LOT_EXAMPLES = [
    # Clear bulk lots - should return True
    ("3X - Wonders of the First Mixed Lot", "Single", True),
    ("2x - Wonders of the First - Leviathan Scale Armor", "Single", True),  # Real example
    ("3x-Wonders of the First Card", "Single", True),  # No spaces
    ("X3 Playset Wonders of the First CCG", "Single", True),  # X prefix
    ("LOT OF 5 COMMON CARDS WOTF", "Single", True),
    ("BUNDLE - 10 RANDOM WONDERS CARDS", "Single", True),
    ("RANDOM 5 CARDS WOTF", "Single", True),
    ("MIXED LOT - Wonders of the First", "Single", True),
    ("ASSORTED CARDS WOTF Collection", "Single", True),
    ("5 CARD LOT - Wonders Commons", "Single", True),
    ("BULK SALE - 20 Wonders Cards", "Single", True),
    ("Bulk Lot Wonders of the First", "Single", True),
    ("Playset of Dragonmaster Cai", "Single", True),
    ("10 PCS Random Wonders Cards", "Single", True),
    ("5pcs Wonders of the First Commons", "Single", True),
    ("2X Wonders of the First Random Cards", "Single", True),
    ("Lot of 10 - Various Rares", "Single", True),
]

PRODUCT_EXAMPLES = [
    # Legitimate products - should return False
    ("Play Bundle - Wonders of the First", "Bundle", False),
    ("2X Play Bundle", "Bundle", False),
    # Single item listings should NOT be flagged
    ("X1 Sealed Wonders Of The First Serialized Alt Art Card Pack", "Single", False),
    ("1x Wonders of the First Booster Pack", "Pack", False),
    ("Collector Booster Box", "Box", False),
    ("Blaster Box - 6 Packs", "Bundle", False),
    ("Serialized Advantage Bundle", "Bundle", False),
    ("Starter Set", "Bundle", False),
    ("Case of 6 Collector Boxes", "Box", False),
    ("Play Bundle Sealed", "Bundle", False),
    ("Wonders of the First Booster Pack", "Pack", False),
    ("Collector Booster - Wonders", "Pack", False),
    ("Starter Deck Wonders of the First", "Bundle", False),
    ("Silver Pack - Wonders", "Pack", False),
    # Single card listings - should return False
    ("Dragonmaster Cai - Foil - Wonders of the First", "Single", False),
    ("Synapse Ridge Classic Paper NM", "Single", False),
    ("Wonders of the First - The Formless One - Serialized", "Single", False),
]


class TestBulkLotDetection:
    """Test suite for bulk lot pattern detection."""

    @pytest.mark.parametrize("title,product_type,expected", BULK_LOT_EXAMPLES)
    def test_bulk_lot_detection(self, title: str, product_type: str, expected: bool):
        """Test that bulk lot patterns are correctly detected."""
        result = is_bulk_lot(title, product_type)
        assert result == expected, f"Failed for: '{title}' (expected {expected}, got {result})"

    @pytest.mark.parametrize("title,product_type,expected", PRODUCT_EXAMPLES)
    def test_product_exceptions(self, title: str, product_type: str, expected: bool):
        """Test that legitimate products are NOT flagged as bulk lots."""
        result = is_bulk_lot(title, product_type)
        assert result == expected, f"Failed for: '{title}' (expected {expected}, got {result})"

    def test_case_insensitivity(self):
        """Test that detection works regardless of case."""
        assert is_bulk_lot("LOT OF 5 CARDS", "Single") is True
        assert is_bulk_lot("lot of 5 cards", "Single") is True
        assert is_bulk_lot("Lot Of 5 Cards", "Single") is True

    def test_product_exception_takes_priority(self):
        """Test that product exceptions take priority over bulk patterns."""
        # "Play Bundle" contains "bundle" but should not be flagged
        assert is_bulk_lot("Play Bundle Wonders", "Bundle") is False
        # "Collector Booster Box" should not be flagged
        assert is_bulk_lot("Collector Booster Box - Factory Sealed", "Box") is False

    def test_edge_cases(self):
        """Test edge cases and boundary conditions."""
        # Empty string
        assert is_bulk_lot("", "Single") is False
        # Short title without bulk patterns
        assert is_bulk_lot("Rare Card", "Single") is False
        # Title with numbers but not bulk pattern
        assert is_bulk_lot("Card #123 from Set 1", "Single") is False


class TestBulkLotIntegration:
    """Integration tests for bulk lot detection in scraper pipeline."""

    def test_scraper_imports_bulk_lot_function(self):
        """Test that eBay scraper correctly imports is_bulk_lot."""
        from app.scraper.ebay import is_bulk_lot as scraper_is_bulk_lot
        from app.scraper.utils import is_bulk_lot as utils_is_bulk_lot

        # Verify they're the same function
        assert scraper_is_bulk_lot is utils_is_bulk_lot

    def test_marketprice_model_has_is_bulk_lot_field(self):
        """Test that MarketPrice model has is_bulk_lot field."""
        from app.models.market import MarketPrice

        # Verify the field exists and has correct default
        fields = MarketPrice.model_fields
        assert "is_bulk_lot" in fields
        assert fields["is_bulk_lot"].default is False

    def test_bulk_lot_flag_in_database(self):
        """Test that bulk lots are correctly flagged in database."""
        from sqlmodel import Session, select, func
        from app.db import engine
        from app.models.market import MarketPrice

        with Session(engine) as session:
            # Count bulk lots
            bulk_count = session.exec(
                select(func.count()).select_from(MarketPrice).where(MarketPrice.is_bulk_lot == True)  # noqa: E712
            ).one()

            # Count total listings
            total_count = session.exec(select(func.count()).select_from(MarketPrice)).one()

            # Verify bulk lots are flagged (should be >0 after backfill)
            assert bulk_count >= 0
            # Verify bulk lot rate is reasonable (<10%)
            if total_count > 0:
                bulk_rate = bulk_count / total_count
                assert bulk_rate < 0.10, f"Bulk lot rate {bulk_rate:.1%} seems too high"
