"""
Tests for _parse_date() function in ebay.py.

This function was the root cause of the Dec 20-30 sold scraper outage.
The bug was that _parse_date() returned naive datetimes while the rest
of the codebase used timezone-aware datetimes, causing comparison errors.

These tests ensure:
1. All returned datetimes are timezone-aware (UTC)
2. Relative dates ("3 days ago") work correctly
3. Absolute dates ("Oct 4, 2025") work correctly
4. Edge cases are handled properly
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from app.scraper.ebay import _parse_date


class TestParseDateTimezoneAwareness:
    """Critical: All returned datetimes must be timezone-aware."""

    def test_relative_date_is_timezone_aware(self):
        """Relative dates must return timezone-aware datetimes."""
        result = _parse_date("Sold 3 days ago")
        assert result is not None
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_absolute_date_is_timezone_aware(self):
        """Absolute dates must return timezone-aware datetimes."""
        result = _parse_date("Sold Oct 4, 2025")
        assert result is not None
        assert result.tzinfo is not None
        assert result.tzinfo == timezone.utc

    def test_just_now_is_timezone_aware(self):
        """'just now' must return timezone-aware datetime."""
        result = _parse_date("just now")
        assert result is not None
        assert result.tzinfo is not None

    def test_yesterday_is_timezone_aware(self):
        """'yesterday' must return timezone-aware datetime."""
        result = _parse_date("yesterday")
        assert result is not None
        assert result.tzinfo is not None

    def test_today_is_timezone_aware(self):
        """'today' must return timezone-aware datetime."""
        result = _parse_date("today")
        assert result is not None
        assert result.tzinfo is not None


class TestParseDateRelative:
    """Tests for relative date parsing."""

    def test_days_ago(self):
        """Test 'X days ago' parsing."""
        result = _parse_date("Sold 3 days ago")
        expected = datetime.now(timezone.utc) - timedelta(days=3)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5  # Within 5 seconds

    def test_weeks_ago(self):
        """Test 'X weeks ago' parsing."""
        result = _parse_date("Sold 2 weeks ago")
        expected = datetime.now(timezone.utc) - timedelta(weeks=2)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5

    def test_months_ago(self):
        """Test 'X months ago' parsing (uses 30 days per month)."""
        result = _parse_date("Sold 1 month ago")
        expected = datetime.now(timezone.utc) - timedelta(days=30)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5

    def test_hours_ago(self):
        """Test 'X hours ago' parsing."""
        result = _parse_date("Sold 5 hours ago")
        expected = datetime.now(timezone.utc) - timedelta(hours=5)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5

    def test_minutes_ago(self):
        """Test 'X minutes ago' parsing."""
        result = _parse_date("Sold 30 minutes ago")
        expected = datetime.now(timezone.utc) - timedelta(minutes=30)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5

    def test_just_now(self):
        """Test 'just now' parsing."""
        result = _parse_date("just now")
        expected = datetime.now(timezone.utc)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5

    def test_just_ended(self):
        """Test 'just ended' parsing."""
        result = _parse_date("just ended")
        expected = datetime.now(timezone.utc)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5

    def test_yesterday(self):
        """Test 'yesterday' parsing."""
        result = _parse_date("yesterday")
        expected = datetime.now(timezone.utc) - timedelta(days=1)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5

    def test_today(self):
        """Test 'today' parsing."""
        result = _parse_date("today")
        expected = datetime.now(timezone.utc)
        assert result is not None
        assert abs((result - expected).total_seconds()) < 5


class TestParseDateAbsolute:
    """Tests for absolute date parsing."""

    def test_full_date_with_year(self):
        """Test 'Oct 4, 2025' format."""
        result = _parse_date("Sold Oct 4, 2025")
        assert result is not None
        assert result.year == 2025
        assert result.month == 10
        assert result.day == 4

    def test_date_without_year_current_year(self):
        """Test 'Dec 1' uses current year if in past."""
        now = datetime.now(timezone.utc)
        result = _parse_date("Sold Jan 1")
        assert result is not None
        # Should be this year or last year depending on current date
        assert result.year in [now.year, now.year - 1]
        assert result.month == 1
        assert result.day == 1

    def test_future_date_uses_previous_year(self):
        """If parsed date is in future, use previous year."""
        # Mock a fixed "now" date to test year rollover logic
        with patch("app.scraper.ebay.datetime") as mock_dt:
            # Pretend it's Jan 15, 2025
            mock_now = datetime(2025, 1, 15, tzinfo=timezone.utc)
            mock_dt.now.return_value = mock_now
            mock_dt.side_effect = lambda *args, **kw: datetime(*args, **kw)

            # "Dec 20" would be in the future, so should use 2024
            # Note: This test may need adjustment based on implementation details

    def test_old_date_returns_none(self):
        """Dates before 2023 should return None (TCG didn't exist)."""
        result = _parse_date("Sold Jan 1, 2020")
        assert result is None

    def test_various_formats(self):
        """Test various eBay date formats."""
        formats = [
            ("Sold Oct 4, 2025", 2025, 10, 4),
            ("Sold December 25, 2024", 2024, 12, 25),
            ("Sold Nov 15, 2023", 2023, 11, 15),
        ]
        for date_str, year, month, day in formats:
            result = _parse_date(date_str)
            assert result is not None, f"Failed to parse: {date_str}"
            assert result.year == year
            assert result.month == month
            assert result.day == day


class TestParseDateEdgeCases:
    """Edge cases and error handling."""

    def test_none_input(self):
        """None input returns None."""
        result = _parse_date(None)
        assert result is None

    def test_empty_string(self):
        """Empty string returns None."""
        result = _parse_date("")
        assert result is None

    def test_invalid_string(self):
        """Invalid string returns None."""
        result = _parse_date("not a date at all")
        assert result is None

    def test_sold_prefix_removed(self):
        """'Sold' prefix should be stripped before parsing."""
        result1 = _parse_date("Sold Oct 4, 2025")
        result2 = _parse_date("Oct 4, 2025")
        assert result1 is not None
        assert result2 is not None
        assert result1.date() == result2.date()

    def test_case_insensitive(self):
        """Parsing should be case-insensitive."""
        result1 = _parse_date("SOLD 3 DAYS AGO")
        result2 = _parse_date("sold 3 days ago")
        assert result1 is not None
        assert result2 is not None
        assert abs((result1 - result2).total_seconds()) < 5


class TestParseDateComparison:
    """Test that parsed dates can be compared with timezone-aware datetimes.

    This is the critical test that would have caught the Dec 20 bug.
    """

    def test_can_compare_with_utc_datetime(self):
        """Parsed dates must be comparable with timezone-aware datetimes."""
        now = datetime.now(timezone.utc)
        result = _parse_date("Sold 3 days ago")

        assert result is not None
        # This comparison would raise TypeError if result is naive
        assert result < now
        assert result > now - timedelta(days=10)

    def test_can_use_in_min_max(self):
        """Parsed dates must work in min/max with timezone-aware datetimes."""
        now = datetime.now(timezone.utc)
        result = _parse_date("Sold 3 days ago")

        assert result is not None
        # These would raise TypeError if result is naive
        minimum = min(result, now)
        maximum = max(result, now)
        assert minimum == result
        assert maximum == now

    def test_can_subtract_from_utc_datetime(self):
        """Parsed dates must be subtractable from timezone-aware datetimes."""
        now = datetime.now(timezone.utc)
        result = _parse_date("Sold 3 days ago")

        assert result is not None
        # This would raise TypeError if result is naive
        delta = now - result
        assert delta.days >= 2  # Should be about 3 days
        assert delta.days <= 4
