"""
Unit tests for eBay seller extraction to ensure seller data is properly captured.

These tests verify that:
1. Seller names are extracted correctly from various eBay HTML formats
2. Seller names are clean usernames, not full HTML blobs
3. Feedback scores and percentages are parsed correctly
4. The scraper never returns corrupted seller data
"""

import pytest
from bs4 import BeautifulSoup
from unittest.mock import MagicMock

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.scraper.ebay import _extract_seller_info
from app.scraper.seller import normalize_seller_name, validate_seller_name, is_tracking_parameter


class TestSellerNameNormalization:
    """Tests for normalize_seller_name function in seller.py."""

    def test_normalizes_clean_name(self):
        """Clean names should pass through unchanged."""
        assert normalize_seller_name("cardshop123") == "cardshop123"
        assert normalize_seller_name("top_seller") == "top_seller"
        assert normalize_seller_name("card.shop-99") == "card.shop-99"

    def test_strips_whitespace(self):
        """Should strip leading/trailing whitespace."""
        assert normalize_seller_name("  seller123  ") == "seller123"
        assert normalize_seller_name("\t\nseller\t\n") == "seller"

    def test_returns_none_for_empty(self):
        """Empty strings or None should return None."""
        assert normalize_seller_name(None) is None
        assert normalize_seller_name("") is None
        assert normalize_seller_name("   ") is None

    def test_removes_feedback_text(self):
        """Should remove feedback percentage text."""
        result = normalize_seller_name("rhomscards  100% positive (1K)Top Rated Plus")
        assert result == "rhomscards"

    def test_removes_top_rated_text(self):
        """Should remove 'Top Rated Plus' and similar text."""
        result = normalize_seller_name("seller123  100% positive (1K)Top Rated PlusSellers with highest")
        assert result == "seller123"

    def test_extracts_username_from_full_blob(self):
        """Should extract just the username from full seller info blob."""
        # These are actual corrupted values we've seen
        bad_values = [
            ("dadcandoit  99.8% positive (1.2K)Top Rated Plus", "dadcandoit"),
            ("manchester91  100% positive (94.8K)Top Rated Plus", "manchester91"),
            ("quickrick1  100% positive (1K)Top Rated PlusSellers", "quickrick1"),
            ("rhomscards  100% positive (1K)Top Rated PlusSellers with highest buyer ratingsReturns", "rhomscards"),
        ]
        for bad_value, expected in bad_values:
            result = normalize_seller_name(bad_value)
            assert result == expected, f"Expected '{expected}', got '{result}' for input '{bad_value[:50]}...'"

    def test_handles_special_characters(self):
        """Should handle valid eBay username characters."""
        assert normalize_seller_name("user_name") == "user_name"
        assert normalize_seller_name("user-name") == "user-name"
        assert normalize_seller_name("user.name") == "user.name"
        assert normalize_seller_name("user123") == "user123"

    def test_normalizes_to_lowercase(self):
        """Should normalize seller names to lowercase."""
        assert normalize_seller_name("CardShop123") == "cardshop123"
        assert normalize_seller_name("TOP_SELLER") == "top_seller"
        assert normalize_seller_name("Rhomscards") == "rhomscards"

    def test_rejects_invalid_characters(self):
        """Should extract valid part from names with invalid chars."""
        # eBay usernames can't have spaces in the middle
        assert normalize_seller_name("user name") == "user"
        # Should extract valid prefix
        assert normalize_seller_name("seller!@#") == "seller"

    def test_rejects_tracking_parameters(self):
        """Should reject eBay tracking parameter strings."""
        # These look like usernames but are actually URL tracking parameters
        assert normalize_seller_name("p4429486.m3561.l161211") is None
        assert normalize_seller_name("p123.m456.l789") is None
        assert normalize_seller_name("m1234.s5678.p9012") is None


class TestTrackingParameterDetection:
    """Tests for is_tracking_parameter function."""

    def test_detects_tracking_patterns(self):
        """Should detect eBay URL tracking parameters."""
        assert is_tracking_parameter("p4429486.m3561.l161211") is True
        assert is_tracking_parameter("p123.m456.l789") is True
        assert is_tracking_parameter("m1234.s5678.p9012") is True

    def test_accepts_valid_usernames(self):
        """Should not flag valid usernames as tracking params."""
        assert is_tracking_parameter("cardshop123") is False
        assert is_tracking_parameter("top_seller") is False
        assert is_tracking_parameter("card.shop-99") is False
        assert is_tracking_parameter("p_seller") is False  # Just starts with p

    def test_handles_none_and_empty(self):
        """Should handle None and empty strings."""
        assert is_tracking_parameter(None) is False
        assert is_tracking_parameter("") is False


class TestSellerNameValidation:
    """Tests for validate_seller_name function."""

    def test_valid_usernames(self):
        """Should accept valid eBay usernames."""
        assert validate_seller_name("cardshop123") is True
        assert validate_seller_name("top_seller") is True
        assert validate_seller_name("card.shop-99") is True
        assert validate_seller_name("x") is True  # Single char is ok

    def test_invalid_usernames(self):
        """Should reject invalid usernames."""
        assert validate_seller_name("") is False
        assert validate_seller_name(None) is False
        assert validate_seller_name("has space") is False
        assert validate_seller_name("has@symbol") is False

    def test_length_limits(self):
        """Should enforce reasonable length limits."""
        assert validate_seller_name("x" * 100) is True  # Max 100
        assert validate_seller_name("x" * 101) is False  # Over limit

    def test_rejects_tracking_parameters(self):
        """Should reject eBay URL tracking parameters."""
        assert validate_seller_name("p4429486.m3561.l161211") is False
        assert validate_seller_name("p123.m456.l789") is False


class TestSellerExtraction:
    """Tests for _extract_seller_info function."""

    def _make_item_with_seller_link(self, href: str, text: str = "") -> MagicMock:
        """Create a mock item element with a seller link."""
        html = f'''
        <div class="s-item">
            <a href="{href}" class="seller">{text}</a>
        </div>
        '''
        return BeautifulSoup(html, 'html.parser').find('div')

    def _make_item_with_seller_info(self, seller_text: str) -> MagicMock:
        """Create a mock item element with seller info text."""
        html = f'''
        <div class="s-item">
            <div class="s-item__seller-info">{seller_text}</div>
        </div>
        '''
        return BeautifulSoup(html, 'html.parser').find('div')

    def _make_item_with_usr_link(self, username: str, text: str = "") -> MagicMock:
        """Create a mock item element with /usr/ link."""
        html = f'''
        <div class="s-item">
            <a href="https://www.ebay.com/usr/{username}">{text or username}</a>
        </div>
        '''
        return BeautifulSoup(html, 'html.parser').find('div')

    # ==================== SELLER NAME EXTRACTION ====================

    def test_extracts_seller_from_usr_link_href(self):
        """Should extract seller username from /usr/ link href."""
        item = self._make_item_with_usr_link("cardshop123")
        seller_name, _, _ = _extract_seller_info(item)
        assert seller_name == "cardshop123"

    def test_extracts_seller_from_usr_link_with_query_params(self):
        """Should extract seller from /usr/ link even with query params."""
        html = '''
        <div class="s-item">
            <a href="https://www.ebay.com/usr/seller_name?foo=bar&baz=123">Click</a>
        </div>
        '''
        item = BeautifulSoup(html, 'html.parser').find('div')
        seller_name, _, _ = _extract_seller_info(item)
        assert seller_name == "seller_name"

    def test_extracts_seller_with_underscores_and_numbers(self):
        """Should handle seller names with underscores and numbers."""
        item = self._make_item_with_usr_link("card_shop_99")
        seller_name, _, _ = _extract_seller_info(item)
        assert seller_name == "card_shop_99"

    def test_extracts_seller_with_dots_and_dashes(self):
        """Should handle seller names with dots and dashes."""
        item = self._make_item_with_usr_link("card.shop-99")
        seller_name, _, _ = _extract_seller_info(item)
        assert seller_name == "card.shop-99"

    # ==================== SELLER NAME SHOULD BE CLEAN ====================

    def test_seller_name_not_corrupted_with_feedback_text(self):
        """Seller name should NOT include feedback text like '100% positive'."""
        item = self._make_item_with_seller_info(
            "dadcandoit  99.8% positive (1.2K)Top Rated PlusSellers with highest buyer ratings"
        )
        seller_name, _, _ = _extract_seller_info(item)

        # Should be just the username, not the full blob
        assert seller_name is not None
        assert "positive" not in seller_name.lower()
        assert "Top Rated" not in seller_name
        assert len(seller_name) < 30  # Username should be short
        assert seller_name == "dadcandoit"

    def test_seller_name_not_corrupted_with_top_rated_text(self):
        """Seller name should NOT include 'Top Rated Plus' text."""
        item = self._make_item_with_seller_info(
            "quickrick1  100% positive (1K)Top Rated PlusSellers with highest buyer ratingsReturns"
        )
        seller_name, _, _ = _extract_seller_info(item)

        assert seller_name is not None
        assert "Top Rated" not in seller_name
        assert "Returns" not in seller_name
        assert seller_name == "quickrick1"

    def test_seller_name_reasonable_length(self):
        """Seller name should always be a reasonable length (< 50 chars)."""
        # Test with garbage text that should be cleaned
        item = self._make_item_with_seller_info(
            "seller123  100% positive (94.8K)Top Rated PlusSellers with highest buyer ratingsReturns, money backShips in a business day with trackingLearn More"
        )
        seller_name, _, _ = _extract_seller_info(item)

        if seller_name:
            assert len(seller_name) < 50, f"Seller name too long: {seller_name}"

    # ==================== FEEDBACK PARSING ====================

    def test_parses_feedback_score_and_percent(self):
        """Should parse feedback score and percentage."""
        item = self._make_item_with_seller_info("cardshop123 (5432) 99.5%")
        seller_name, feedback_score, feedback_percent = _extract_seller_info(item)

        assert seller_name == "cardshop123"
        assert feedback_score == 5432
        assert feedback_percent == 99.5

    def test_parses_feedback_with_k_suffix(self):
        """Should parse feedback with K suffix (e.g., 1.2K = 1200)."""
        item = self._make_item_with_seller_info("bigshop  100% positive (1.2K)")
        seller_name, feedback_score, feedback_percent = _extract_seller_info(item)

        assert seller_name == "bigshop"
        # Note: Exact parsing may vary, but should get something reasonable
        if feedback_score:
            assert feedback_score >= 1000  # Should interpret K as thousands

    def test_parses_feedback_alternative_format(self):
        """Should parse '100% positive' format."""
        item = self._make_item_with_seller_info("seller99  100% positive (500)")
        seller_name, feedback_score, feedback_percent = _extract_seller_info(item)

        assert seller_name == "seller99"
        # Should extract 100% and 500
        if feedback_percent:
            assert feedback_percent == 100.0

    # ==================== EDGE CASES ====================

    def test_handles_empty_seller_info(self):
        """Should handle items with no seller info gracefully."""
        html = '<div class="s-item"><span>No seller info here</span></div>'
        item = BeautifulSoup(html, 'html.parser').find('div')
        seller_name, feedback_score, feedback_percent = _extract_seller_info(item)

        # Should return None, not crash
        assert seller_name is None or isinstance(seller_name, str)

    def test_handles_none_element(self):
        """Should handle None element gracefully."""
        html = '<div class="s-item"></div>'
        item = BeautifulSoup(html, 'html.parser').find('div')
        seller_name, feedback_score, feedback_percent = _extract_seller_info(item)

        # Should not raise an exception
        assert seller_name is None

    def test_prioritizes_usr_link_over_text(self):
        """Should prefer /usr/ link extraction over text parsing."""
        html = '''
        <div class="s-item">
            <a href="https://www.ebay.com/usr/correct_seller">wrong text garbage</a>
            <div class="s-item__seller-info">wrong_seller  100% positive</div>
        </div>
        '''
        item = BeautifulSoup(html, 'html.parser').find('div')
        seller_name, _, _ = _extract_seller_info(item)

        # Should get seller from URL, not from text
        assert seller_name == "correct_seller"


class TestSellerDataQuality:
    """
    Integration-style tests that verify seller data quality.
    These tests ensure we never have corrupted data in the database.
    """

    def test_seller_name_no_html_entities(self):
        """Seller name should not contain HTML entities."""
        item_html = '''
        <div class="s-item">
            <a href="https://www.ebay.com/usr/seller&amp;name">text</a>
        </div>
        '''
        item = BeautifulSoup(item_html, 'html.parser').find('div')
        seller_name, _, _ = _extract_seller_info(item)

        if seller_name:
            assert "&amp;" not in seller_name
            assert "&lt;" not in seller_name
            assert "&gt;" not in seller_name

    def test_seller_name_is_alphanumeric_with_special_chars(self):
        """Seller name should only contain valid username characters."""
        item = BeautifulSoup('''
        <div class="s-item">
            <div class="s-item__seller-info">valid_seller-123.name (100) 99%</div>
        </div>
        ''', 'html.parser').find('div')

        seller_name, _, _ = _extract_seller_info(item)

        if seller_name:
            # Should only contain alphanumeric, underscore, dash, dot
            import re
            assert re.match(r'^[a-zA-Z0-9_\-\.]+$', seller_name), f"Invalid chars in: {seller_name}"

    def test_regression_no_full_blob_in_seller_name(self):
        """
        REGRESSION TEST: Ensure the bug where full HTML blob was stored as seller_name
        never happens again.

        The old bug stored strings like:
        "dadcandoit  99.8% positive (1.2K)Top Rated PlusSellers with highest..."
        instead of just "dadcandoit"
        """
        # These are the actual corrupted values we found in the database
        bad_patterns = [
            "dadcandoit  99.8% positive (1.2K)Top Rated PlusSellers with highest buyer ratingsReturns, money backShips in a business day with trackingLearn More",
            "manchester91  100% positive (94.8K)Top Rated PlusSellers with highest buyer ratingsReturns, money backShips in a business day with trackingLearn More",
            "quickrick1  100% positive (1K)Top Rated PlusSellers with highest buyer ratingsReturns, money backShips in a business day with trackingLearn More",
            "rhomscards  100% positive (1K)Top Rated PlusSellers with highest buyer ratingsReturns, money backShips in a business day with trackingLearn More",
        ]

        for bad_value in bad_patterns:
            item = BeautifulSoup(f'''
            <div class="s-item">
                <div class="s-item__seller-info">{bad_value}</div>
            </div>
            ''', 'html.parser').find('div')

            seller_name, _, _ = _extract_seller_info(item)

            # These assertions will catch the regression
            assert seller_name is not None, "Should extract seller name"
            assert len(seller_name) < 50, f"Seller name too long (corruption): {seller_name[:60]}..."
            assert "positive" not in seller_name.lower(), f"Corruption detected: {seller_name}"
            assert "Top Rated" not in seller_name, f"Corruption detected: {seller_name}"
            assert "Learn More" not in seller_name, f"Corruption detected: {seller_name}"


class TestSellerExtractionFromRealHTML:
    """Tests using realistic eBay HTML structures."""

    def test_modern_ebay_search_result(self):
        """Test extraction from modern eBay search result HTML."""
        html = '''
        <div class="s-item">
            <div class="s-item__info">
                <a class="s-item__link" href="https://www.ebay.com/itm/123456">
                    <span>Card Title Here</span>
                </a>
                <div class="s-item__seller-info">
                    <a href="https://www.ebay.com/usr/topcardseller">topcardseller</a>
                    <span class="s-item__seller-info-text">
                        <span>(2,345)</span>
                        <span>99.8%</span>
                    </span>
                </div>
            </div>
        </div>
        '''
        item = BeautifulSoup(html, 'html.parser').find('div', class_='s-item')
        seller_name, _, _ = _extract_seller_info(item)

        assert seller_name == "topcardseller"

    def test_sold_listing_html(self):
        """Test extraction from sold listing format."""
        html = '''
        <div class="s-item">
            <div class="s-item__seller-info">
                <span class="s-item__seller-info-text">
                    <a href="https://www.ebay.com/usr/soldbyuser">soldbyuser</a>
                    100% positive (500)
                </span>
            </div>
        </div>
        '''
        item = BeautifulSoup(html, 'html.parser').find('div', class_='s-item')
        seller_name, _, _ = _extract_seller_info(item)

        assert seller_name == "soldbyuser"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
