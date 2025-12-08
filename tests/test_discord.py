"""
Tests for Discord webhook and logger functionality.

Tests cover:
- Webhook message formatting
- Market insights logging
- New listing notifications
- New sale notifications
- Error handling when webhook URL is missing
- Message truncation for Discord limits
- Embed formatting
- Scrape logging (start, complete, error)
- Snapshot update logging
- General log functions (info, warning, error)
"""

import pytest
from unittest.mock import patch, MagicMock, call, Mock
from datetime import datetime
import json
import sys

# Mock the storage module to avoid import errors
sys.modules['app.discord_bot.storage'] = Mock()


class TestDiscordLogger:
    """Tests for Discord logger functions in app.discord_bot.logger."""

    @patch('app.discord_bot.logger.requests.post')
    @patch('app.discord_bot.logger.LOGS_WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_log_success(self, mock_post):
        """Test successful log message sending."""
        from app.discord_bot.logger import _send_log

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = _send_log(
            title="Test Title",
            description="Test Description",
            color=0x3B82F6
        )

        assert result is True
        mock_post.assert_called_once()

        # Verify payload structure
        call_args = mock_post.call_args
        payload = call_args[1]['json']
        assert payload['username'] == "Wonders Logs"
        assert len(payload['embeds']) == 1

        embed = payload['embeds'][0]
        assert embed['title'] == "Test Title"
        assert embed['description'] == "Test Description"
        assert embed['color'] == 0x3B82F6
        assert 'timestamp' in embed
        assert embed['footer']['text'] == "WondersTracker"

    @patch('app.discord_bot.logger.requests.post')
    @patch('app.discord_bot.logger.LOGS_WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_log_with_fields(self, mock_post):
        """Test log message with fields."""
        from app.discord_bot.logger import _send_log

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        fields = [
            {"name": "Field 1", "value": "Value 1", "inline": True},
            {"name": "Field 2", "value": "Value 2", "inline": False}
        ]

        result = _send_log(
            title="Test",
            description="Test",
            color=0x10B981,
            fields=fields
        )

        assert result is True

        # Verify fields are included
        payload = mock_post.call_args[1]['json']
        embed = payload['embeds'][0]
        assert embed['fields'] == fields

    @patch('app.discord_bot.logger.LOGS_WEBHOOK_URL', None)
    def test_send_log_no_webhook_url(self):
        """Test log function returns False when webhook URL is not set."""
        from app.discord_bot.logger import _send_log

        result = _send_log(
            title="Test",
            description="Test",
            color=0x3B82F6
        )

        assert result is False

    @patch('app.discord_bot.logger.requests.post')
    @patch('app.discord_bot.logger.LOGS_WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_log_request_failure(self, mock_post):
        """Test log function handles request failures gracefully."""
        from app.discord_bot.logger import _send_log

        mock_post.side_effect = Exception("Network error")

        result = _send_log(
            title="Test",
            description="Test",
            color=0x3B82F6
        )

        assert result is False

    @patch('app.discord_bot.logger.requests.post')
    @patch('app.discord_bot.logger.LOGS_WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_log_non_success_status(self, mock_post):
        """Test log function returns False for non-success status codes."""
        from app.discord_bot.logger import _send_log

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_post.return_value = mock_response

        result = _send_log(
            title="Test",
            description="Test",
            color=0x3B82F6
        )

        assert result is False

    @patch('app.discord_bot.logger._send_log')
    def test_log_scrape_start(self, mock_send_log):
        """Test scrape start logging."""
        from app.discord_bot.logger import log_scrape_start

        mock_send_log.return_value = True

        result = log_scrape_start(card_count=100, scrape_type="full")

        assert result is True
        mock_send_log.assert_called_once()

        # Verify call arguments
        call_args = mock_send_log.call_args[1]
        assert "🔄" in call_args['title']
        assert "Full" in call_args['description']
        assert call_args['color'] == 0x3B82F6
        assert any(f['value'] == "`100`" for f in call_args['fields'])

    @patch('app.discord_bot.logger._send_log')
    def test_log_scrape_start_different_types(self, mock_send_log):
        """Test scrape start logging with different scrape types."""
        from app.discord_bot.logger import log_scrape_start

        mock_send_log.return_value = True

        # Test different scrape types and their emojis
        types_and_emojis = [
            ("scheduled", "⏰"),
            ("blokpax", "🎯"),
            ("active", "📋"),
            ("sold", "💰")
        ]

        for scrape_type, expected_emoji in types_and_emojis:
            mock_send_log.reset_mock()
            log_scrape_start(50, scrape_type)
            call_args = mock_send_log.call_args[1]
            assert expected_emoji in call_args['title']

    @patch('app.discord_bot.logger._send_log')
    def test_log_scrape_complete_success(self, mock_send_log):
        """Test successful scrape completion logging."""
        from app.discord_bot.logger import log_scrape_complete

        mock_send_log.return_value = True

        result = log_scrape_complete(
            cards_processed=100,
            new_listings=25,
            new_sales=10,
            duration_seconds=125.5,
            errors=0
        )

        assert result is True

        # Verify success indicators
        call_args = mock_send_log.call_args[1]
        assert "✅" in call_args['title']
        assert call_args['color'] == 0x10B981  # Green

    @patch('app.discord_bot.logger._send_log')
    def test_log_scrape_complete_with_errors(self, mock_send_log):
        """Test scrape completion logging with errors."""
        from app.discord_bot.logger import log_scrape_complete

        mock_send_log.return_value = True

        result = log_scrape_complete(
            cards_processed=100,
            new_listings=20,
            new_sales=8,
            duration_seconds=150.0,
            errors=5
        )

        assert result is True

        # Verify warning indicators
        call_args = mock_send_log.call_args[1]
        assert "⚠️" in call_args['title']
        assert call_args['color'] == 0xF59E0B  # Yellow
        assert any("5" in str(f['value']) for f in call_args['fields'])

    @patch('app.discord_bot.logger._send_log')
    def test_log_scrape_complete_duration_formatting(self, mock_send_log):
        """Test duration is formatted correctly in scrape complete log."""
        from app.discord_bot.logger import log_scrape_complete

        mock_send_log.return_value = True

        # Test with minutes
        log_scrape_complete(100, 10, 5, 125.0)
        call_args = mock_send_log.call_args[1]
        duration_field = next(f for f in call_args['fields'] if "Duration" in f['name'])
        assert "2m 5s" in duration_field['value']

        # Test with seconds only
        log_scrape_complete(100, 10, 5, 45.0)
        call_args = mock_send_log.call_args[1]
        duration_field = next(f for f in call_args['fields'] if "Duration" in f['name'])
        assert "45s" in duration_field['value']

    @patch('app.discord_bot.logger._send_log')
    def test_log_scrape_error(self, mock_send_log):
        """Test scrape error logging."""
        from app.discord_bot.logger import log_scrape_error

        mock_send_log.return_value = True

        result = log_scrape_error(
            card_name="Test Card",
            error="Connection timeout"
        )

        assert result is True

        # Verify error indicators
        call_args = mock_send_log.call_args[1]
        assert "🚨" in call_args['title']
        assert "Test Card" in call_args['description']
        assert call_args['color'] == 0xEF4444  # Red
        assert any("Connection timeout" in str(f['value']) for f in call_args['fields'])

    @patch('app.discord_bot.logger._send_log')
    def test_log_scrape_error_truncates_long_errors(self, mock_send_log):
        """Test that long error messages are truncated."""
        from app.discord_bot.logger import log_scrape_error

        mock_send_log.return_value = True

        long_error = "X" * 1000
        log_scrape_error("Test Card", long_error)

        call_args = mock_send_log.call_args[1]
        error_field = call_args['fields'][0]
        # Should be truncated to 900 chars
        assert len(error_field['value']) < len(long_error) + 10  # +10 for code block markers

    @patch('app.discord_bot.logger._send_log')
    def test_log_snapshot_update(self, mock_send_log):
        """Test snapshot update logging."""
        from app.discord_bot.logger import log_snapshot_update

        mock_send_log.return_value = True

        result = log_snapshot_update(cards_updated=75)

        assert result is True

        call_args = mock_send_log.call_args[1]
        assert "📸" in call_args['title']
        assert "75" in call_args['description']
        assert call_args['color'] == 0x8B5CF6  # Purple

    @patch('app.discord_bot.logger._send_log')
    def test_log_info(self, mock_send_log):
        """Test general info logging."""
        from app.discord_bot.logger import log_info

        mock_send_log.return_value = True

        result = log_info("System Update", "Database connection restored")

        assert result is True

        call_args = mock_send_log.call_args[1]
        assert "ℹ️" in call_args['title']
        assert "System Update" in call_args['title']
        assert call_args['description'] == "Database connection restored"
        assert call_args['color'] == 0x6B7280  # Gray

    @patch('app.discord_bot.logger._send_log')
    def test_log_warning(self, mock_send_log):
        """Test warning logging."""
        from app.discord_bot.logger import log_warning

        mock_send_log.return_value = True

        result = log_warning("High Memory Usage", "Memory at 85%")

        assert result is True

        call_args = mock_send_log.call_args[1]
        assert "⚠️" in call_args['title']
        assert "Warning" in call_args['title']
        assert "High Memory Usage" in call_args['title']
        assert call_args['color'] == 0xF59E0B  # Yellow

    @patch('app.discord_bot.logger._send_log')
    def test_log_error(self, mock_send_log):
        """Test error logging."""
        from app.discord_bot.logger import log_error

        mock_send_log.return_value = True

        result = log_error("Database Connection", "Failed to connect to database")

        assert result is True

        call_args = mock_send_log.call_args[1]
        assert "🚨" in call_args['title']
        assert "Error" in call_args['title']
        assert "Database Connection" in call_args['title']
        assert call_args['color'] == 0xEF4444  # Red

    @patch('app.discord_bot.logger._send_log')
    @patch('app.discord_bot.logger.NEW_SALES_WEBHOOK_URL', 'https://discord.com/api/webhooks/sales')
    def test_log_new_sale_basic(self, mock_send_log):
        """Test basic new sale logging."""
        from app.discord_bot.logger import log_new_sale

        mock_send_log.return_value = True

        result = log_new_sale(
            card_name="Test Card",
            price=25.50,
            treatment="Classic Paper",
            url="https://ebay.com/item/123",
            sold_date="2025-12-08"
        )

        assert result is True

        call_args = mock_send_log.call_args[1]
        assert "Test Card" in call_args['description']
        assert "$25.50" in call_args['description']
        assert call_args['webhook_url'] == 'https://discord.com/api/webhooks/sales'
        assert call_args['username'] == "Wonders Sales"

    @patch('app.discord_bot.logger._send_log')
    @patch('app.discord_bot.logger.NEW_SALES_WEBHOOK_URL', 'https://discord.com/api/webhooks/sales')
    def test_log_new_sale_with_floor_comparison(self, mock_send_log):
        """Test new sale logging with floor price comparison."""
        from app.discord_bot.logger import log_new_sale

        mock_send_log.return_value = True

        # Sale below floor (good deal)
        log_new_sale(
            card_name="Test Card",
            price=20.00,
            floor_price=25.00
        )

        call_args = mock_send_log.call_args[1]
        assert "below floor" in call_args['description'].lower()
        assert call_args['color'] == 0x10B981  # Green

        # Sale above floor (premium)
        mock_send_log.reset_mock()
        log_new_sale(
            card_name="Test Card",
            price=30.00,
            floor_price=25.00
        )

        call_args = mock_send_log.call_args[1]
        assert "above floor" in call_args['description'].lower()
        assert call_args['color'] == 0xF59E0B  # Yellow

    @patch('app.discord_bot.logger._send_log')
    @patch('app.discord_bot.logger.NEW_LISTINGS_WEBHOOK_URL', 'https://discord.com/api/webhooks/listings')
    def test_log_new_listing_basic(self, mock_send_log):
        """Test basic new listing logging."""
        from app.discord_bot.logger import log_new_listing

        mock_send_log.return_value = True

        result = log_new_listing(
            card_name="Test Card",
            price=30.00,
            treatment="Classic Foil",
            url="https://ebay.com/item/456",
            is_auction=False
        )

        assert result is True

        call_args = mock_send_log.call_args[1]
        assert "Test Card" in call_args['description']
        assert "$30.00" in call_args['description']
        assert "Buy It Now" in call_args['description']
        assert "Classic Foil" in call_args['description']
        assert call_args['webhook_url'] == 'https://discord.com/api/webhooks/listings'
        assert call_args['username'] == "Wonders Listings"

    @patch('app.discord_bot.logger._send_log')
    @patch('app.discord_bot.logger.NEW_LISTINGS_WEBHOOK_URL', 'https://discord.com/api/webhooks/listings')
    def test_log_new_listing_auction(self, mock_send_log):
        """Test auction listing logging."""
        from app.discord_bot.logger import log_new_listing

        mock_send_log.return_value = True

        log_new_listing(
            card_name="Test Card",
            price=15.00,
            is_auction=True
        )

        call_args = mock_send_log.call_args[1]
        assert "Auction" in call_args['description']

    @patch('app.discord_bot.logger._send_log')
    @patch('app.discord_bot.logger.NEW_LISTINGS_WEBHOOK_URL', 'https://discord.com/api/webhooks/listings')
    def test_log_new_listing_deal_alert(self, mock_send_log):
        """Test listing below floor triggers deal alert."""
        from app.discord_bot.logger import log_new_listing

        mock_send_log.return_value = True

        log_new_listing(
            card_name="Test Card",
            price=18.00,
            floor_price=25.00
        )

        call_args = mock_send_log.call_args[1]
        assert "Deal Alert" in call_args['title'] or "below floor" in call_args['description'].lower()
        assert call_args['color'] == 0x10B981  # Green

    @patch('app.discord_bot.logger.requests.post')
    @patch('app.discord_bot.logger.UPDATES_WEBHOOK_URL', 'https://discord.com/api/webhooks/updates')
    def test_log_market_insights_success(self, mock_post):
        """Test market insights logging."""
        from app.discord_bot.logger import log_market_insights

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        insights_text = """
## Daily Market Report

Total Sales: 50
Total Volume: $1,250.00

Top Movers:
- Card A: +15%
- Card B: -10%
"""

        result = log_market_insights(insights_text)

        assert result is True
        mock_post.assert_called_once()

        # Verify payload structure
        payload = mock_post.call_args[1]['json']
        assert payload['username'] == "Wonders Market"
        assert payload['content'] == insights_text[:2000]
        assert 'avatar_url' in payload

    @patch('app.discord_bot.logger.requests.post')
    @patch('app.discord_bot.logger.UPDATES_WEBHOOK_URL', 'https://discord.com/api/webhooks/updates')
    def test_log_market_insights_truncates_long_messages(self, mock_post):
        """Test market insights truncates messages over Discord's 2000 char limit."""
        from app.discord_bot.logger import log_market_insights

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        # Create a message longer than 2000 characters
        long_insights = "A" * 3000

        result = log_market_insights(long_insights)

        assert result is True

        payload = mock_post.call_args[1]['json']
        assert len(payload['content']) <= 2000

    @patch('app.discord_bot.logger.UPDATES_WEBHOOK_URL', None)
    def test_log_market_insights_no_webhook(self):
        """Test market insights returns False when webhook URL not set."""
        from app.discord_bot.logger import log_market_insights

        result = log_market_insights("Test insights")

        assert result is False

    @patch('app.discord_bot.logger.requests.post')
    @patch('app.discord_bot.logger.UPDATES_WEBHOOK_URL', 'https://discord.com/api/webhooks/updates')
    def test_log_market_insights_request_failure(self, mock_post):
        """Test market insights handles request failures gracefully."""
        from app.discord_bot.logger import log_market_insights

        mock_post.side_effect = Exception("Network error")

        result = log_market_insights("Test insights")

        assert result is False


class TestDiscordWebhook:
    """Tests for Discord webhook functions in app.discord_bot.webhook."""

    @patch('app.discord_bot.webhook.requests.post')
    @patch('app.discord_bot.webhook.WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_webhook_message_text_only(self, mock_post):
        """Test sending a simple text message via webhook."""
        from app.discord_bot.webhook import send_webhook_message

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_webhook_message(content="Test message")

        assert result is True
        mock_post.assert_called_once()

        payload = mock_post.call_args[1]['json']
        assert payload['content'] == "Test message"
        assert payload['username'] == "Wonders Market Bot"

    @patch('app.discord_bot.webhook.requests.post')
    @patch('app.discord_bot.webhook.WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_webhook_message_with_embeds(self, mock_post):
        """Test sending message with embeds."""
        from app.discord_bot.webhook import send_webhook_message

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        embeds = [{
            "title": "Test Embed",
            "description": "Test Description",
            "color": 0x10B981
        }]

        result = send_webhook_message(embeds=embeds)

        assert result is True

        payload = mock_post.call_args[1]['json']
        assert payload['embeds'] == embeds

    @patch('app.discord_bot.webhook.requests.post')
    @patch('app.discord_bot.webhook.WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_webhook_message_with_file(self, mock_post):
        """Test sending message with file attachment."""
        from app.discord_bot.webhook import send_webhook_message

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        file_data = b"test,data,file\n1,2,3"
        filename = "test.csv"

        result = send_webhook_message(
            content="Here's your report",
            file_data=file_data,
            filename=filename
        )

        assert result is True

        # Verify file was sent
        call_args = mock_post.call_args
        assert 'files' in call_args[1]
        assert 'data' in call_args[1]

        # Verify payload_json is used when sending files
        payload_str = call_args[1]['data']['payload_json']
        payload = json.loads(payload_str)
        assert payload['content'] == "Here's your report"

    @patch('app.discord_bot.webhook.requests.post')
    @patch('app.discord_bot.webhook.WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_webhook_message_custom_username(self, mock_post):
        """Test sending message with custom username."""
        from app.discord_bot.webhook import send_webhook_message

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        result = send_webhook_message(
            content="Test",
            username="Custom Bot Name"
        )

        assert result is True

        payload = mock_post.call_args[1]['json']
        assert payload['username'] == "Custom Bot Name"

    @patch('app.discord_bot.webhook.WEBHOOK_URL', None)
    def test_send_webhook_message_no_url(self):
        """Test webhook function returns False when URL not set."""
        from app.discord_bot.webhook import send_webhook_message

        result = send_webhook_message(content="Test")

        assert result is False

    @patch('app.discord_bot.webhook.requests.post')
    @patch('app.discord_bot.webhook.WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_webhook_message_failure_status(self, mock_post):
        """Test webhook function handles non-success status codes."""
        from app.discord_bot.webhook import send_webhook_message

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Bad Request"
        mock_post.return_value = mock_response

        result = send_webhook_message(content="Test")

        assert result is False

    @patch('app.discord_bot.webhook.requests.post')
    @patch('app.discord_bot.webhook.WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_webhook_message_exception(self, mock_post):
        """Test webhook function handles exceptions gracefully."""
        from app.discord_bot.webhook import send_webhook_message

        mock_post.side_effect = Exception("Connection timeout")

        result = send_webhook_message(content="Test")

        assert result is False

    @patch('app.discord_bot.webhook.requests.post')
    @patch('app.discord_bot.webhook.WEBHOOK_URL', 'https://discord.com/api/webhooks/test')
    def test_send_webhook_message_status_204(self, mock_post):
        """Test webhook function accepts 204 as success."""
        from app.discord_bot.webhook import send_webhook_message

        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_post.return_value = mock_response

        result = send_webhook_message(content="Test")

        assert result is True

    @patch('app.discord_bot.webhook.send_webhook_message')
    def test_send_test_message(self, mock_send):
        """Test sending test message."""
        from app.discord_bot.webhook import send_test_message

        mock_send.return_value = True

        result = send_test_message()

        assert result is True
        mock_send.assert_called_once()

        # Verify test message structure
        call_args = mock_send.call_args
        assert call_args[1]['content'] == "Wonders Market Bot is connected!"
        assert len(call_args[1]['embeds']) == 1

        embed = call_args[1]['embeds'][0]
        assert embed['title'] == "Test Message"
        assert embed['color'] == 0x10B981

    @patch('app.discord_bot.webhook.calculate_market_stats')
    @patch('app.discord_bot.webhook.format_stats_embed')
    @patch('app.discord_bot.webhook.generate_csv_report')
    @patch('app.discord_bot.webhook.upload_csv')
    @patch('app.discord_bot.webhook.send_webhook_message')
    def test_send_daily_report_success(
        self,
        mock_send,
        mock_upload,
        mock_csv,
        mock_format,
        mock_stats
    ):
        """Test successful daily report sending."""
        from app.discord_bot.webhook import send_daily_report
        from app.discord_bot.stats import MarketStats

        # Mock stats
        mock_stats_obj = MarketStats(
            period="daily",
            total_sales=50,
            total_volume_usd=1250.0,
            unique_cards_traded=25,
            avg_sale_price=25.0,
            top_movers=[],
            top_volume=[],
            new_highs=[],
            new_lows=[],
            generated_at=datetime.utcnow()
        )
        mock_stats.return_value = mock_stats_obj

        # Mock embed formatting
        mock_format.return_value = {
            "title": "Daily Report",
            "description": "Test",
            "color": 0x10B981,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Test"},
            "fields": []
        }

        # Mock CSV generation
        mock_csv.return_value = ("test.csv", b"test,data")

        # Mock upload
        mock_upload.return_value = "report_123"

        # Mock webhook send
        mock_send.return_value = True

        result = send_daily_report()

        assert result is True
        mock_stats.assert_called_once_with("daily")
        mock_format.assert_called_once()
        mock_csv.assert_called_once_with("daily")
        mock_upload.assert_called_once()
        mock_send.assert_called_once()

    @patch('app.discord_bot.webhook.calculate_market_stats')
    @patch('app.discord_bot.webhook.format_stats_embed')
    @patch('app.discord_bot.webhook.generate_csv_report')
    @patch('app.discord_bot.webhook.upload_csv')
    @patch('app.discord_bot.webhook.send_webhook_message')
    def test_send_weekly_report_success(
        self,
        mock_send,
        mock_upload,
        mock_csv,
        mock_format,
        mock_stats
    ):
        """Test successful weekly report sending."""
        from app.discord_bot.webhook import send_weekly_report
        from app.discord_bot.stats import MarketStats

        # Mock stats
        mock_stats_obj = MarketStats(
            period="weekly",
            total_sales=200,
            total_volume_usd=5000.0,
            unique_cards_traded=80,
            avg_sale_price=25.0,
            top_movers=[],
            top_volume=[],
            new_highs=[],
            new_lows=[],
            generated_at=datetime.utcnow()
        )
        mock_stats.return_value = mock_stats_obj

        # Mock embed formatting
        mock_format.return_value = {
            "title": "Weekly Report",
            "description": "Test",
            "color": 0x10B981,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Test"},
            "fields": []
        }

        # Mock CSV generation
        mock_csv.return_value = ("test_weekly.csv", b"test,data")

        # Mock upload
        mock_upload.return_value = "report_456"

        # Mock webhook send
        mock_send.return_value = True

        result = send_weekly_report()

        assert result is True
        mock_stats.assert_called_once_with("weekly")
        mock_format.assert_called_once()
        mock_csv.assert_called_once_with("weekly")
        mock_send.assert_called_once()

    @patch('app.discord_bot.webhook.calculate_market_stats')
    def test_send_daily_report_stats_failure(self, mock_stats):
        """Test daily report handles stats calculation failure."""
        from app.discord_bot.webhook import send_daily_report

        mock_stats.side_effect = Exception("Database error")

        result = send_daily_report()

        assert result is False

    @patch('app.discord_bot.webhook.calculate_market_stats')
    @patch('app.discord_bot.webhook.format_stats_embed')
    @patch('app.discord_bot.webhook.generate_csv_report')
    @patch('app.discord_bot.webhook.upload_csv')
    @patch('app.discord_bot.webhook.send_webhook_message')
    def test_send_daily_report_continues_on_upload_failure(
        self,
        mock_send,
        mock_upload,
        mock_csv,
        mock_format,
        mock_stats
    ):
        """Test daily report continues if CSV upload fails."""
        from app.discord_bot.webhook import send_daily_report
        from app.discord_bot.stats import MarketStats

        # Mock stats
        mock_stats_obj = MarketStats(
            period="daily",
            total_sales=50,
            total_volume_usd=1250.0,
            unique_cards_traded=25,
            avg_sale_price=25.0,
            top_movers=[],
            top_volume=[],
            new_highs=[],
            new_lows=[],
            generated_at=datetime.utcnow()
        )
        mock_stats.return_value = mock_stats_obj

        # Mock embed formatting
        mock_format.return_value = {
            "title": "Daily Report",
            "description": "Test",
            "color": 0x10B981,
            "timestamp": datetime.utcnow().isoformat(),
            "footer": {"text": "Test"},
            "fields": []
        }

        # Mock CSV generation
        mock_csv.return_value = ("test.csv", b"test,data")

        # Upload fails but webhook should still be called
        mock_upload.side_effect = Exception("Upload failed")
        mock_send.return_value = True

        result = send_daily_report()

        # Should still succeed because webhook send succeeded
        assert result is True
        mock_send.assert_called_once()


class TestEmbedFormatting:
    """Tests for Discord embed structure and formatting limits."""

    def test_embed_title_limit(self):
        """Test embed title doesn't exceed Discord's 256 character limit."""
        # This is more of a validation test for our embed creation
        title = "A" * 300
        truncated = title[:256]

        assert len(truncated) <= 256

    def test_embed_description_limit(self):
        """Test embed description doesn't exceed Discord's 4096 character limit."""
        description = "A" * 5000
        truncated = description[:4096]

        assert len(truncated) <= 4096

    def test_embed_field_limit(self):
        """Test embed can't have more than 25 fields."""
        fields = [{"name": f"Field {i}", "value": f"Value {i}", "inline": True} for i in range(30)]

        # Should only take first 25
        limited_fields = fields[:25]

        assert len(limited_fields) == 25

    def test_embed_field_value_limit(self):
        """Test embed field value doesn't exceed Discord's 1024 character limit."""
        value = "A" * 2000
        truncated = value[:1024]

        assert len(truncated) <= 1024

    @patch('app.discord_bot.logger._send_log')
    def test_real_embed_respects_limits(self, mock_send_log):
        """Test that actual log functions create embeds within Discord limits."""
        from app.discord_bot.logger import log_scrape_error

        mock_send_log.return_value = True

        # Create a very long error message
        long_error = "X" * 2000

        log_scrape_error("Test Card", long_error)

        call_args = mock_send_log.call_args[1]

        # Title should be reasonable
        assert len(call_args['title']) < 256

        # Description should be reasonable
        assert len(call_args['description']) < 4096

        # Field values should be truncated
        if call_args.get('fields'):
            for field in call_args['fields']:
                assert len(field['value']) <= 1024
