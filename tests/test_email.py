"""
Tests for the email service.

Tests cover:
- Welcome email sending
- Password reset email sending
- Email service error handling
- Template content validation
"""

from unittest.mock import patch


class TestEmailService:
    """Tests for the email service functions."""

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_send_welcome_email_success(self, mock_resend, mock_settings):
        """Test successful welcome email sending."""
        from app.services.email import send_welcome_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "test@example.com"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.return_value = {"id": "test_email_id"}

        result = send_welcome_email("user@example.com", "TestUser")

        assert result is True
        mock_resend.Emails.send.assert_called_once()

        # Verify email content
        call_args = mock_resend.Emails.send.call_args[0][0]
        assert call_args["to"] == ["user@example.com"]
        assert "Welcome" in call_args["subject"]
        assert "TestUser" in call_args["html"]

    @patch("app.services.email.settings")
    def test_send_welcome_email_no_api_key(self, mock_settings):
        """Test welcome email skipped when no API key configured."""
        from app.services.email import send_welcome_email

        mock_settings.RESEND_API_KEY = ""

        result = send_welcome_email("user@example.com")

        assert result is False

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_send_welcome_email_with_default_name(self, mock_resend, mock_settings):
        """Test welcome email uses email prefix when no name provided."""
        from app.services.email import send_welcome_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "test@example.com"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.return_value = {"id": "test_email_id"}

        result = send_welcome_email("johndoe@example.com")

        assert result is True
        call_args = mock_resend.Emails.send.call_args[0][0]
        assert "johndoe" in call_args["html"]

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_send_welcome_email_exception_handling(self, mock_resend, mock_settings):
        """Test welcome email handles exceptions gracefully."""
        from app.services.email import send_welcome_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "test@example.com"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.side_effect = Exception("API Error")

        result = send_welcome_email("user@example.com")

        assert result is False

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_send_password_reset_email_success(self, mock_resend, mock_settings):
        """Test successful password reset email sending."""
        from app.services.email import send_password_reset_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "test@example.com"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.return_value = {"id": "test_email_id"}

        result = send_password_reset_email("user@example.com", "test_token_123")

        assert result is True
        mock_resend.Emails.send.assert_called_once()

        # Verify email content
        call_args = mock_resend.Emails.send.call_args[0][0]
        assert call_args["to"] == ["user@example.com"]
        assert "Reset" in call_args["subject"]
        assert "test_token_123" in call_args["html"]
        assert "https://example.com/reset-password?token=test_token_123" in call_args["html"]

    @patch("app.services.email.settings")
    def test_send_password_reset_email_no_api_key(self, mock_settings):
        """Test password reset email skipped when no API key configured."""
        from app.services.email import send_password_reset_email

        mock_settings.RESEND_API_KEY = ""

        result = send_password_reset_email("user@example.com", "test_token")

        assert result is False

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_send_password_reset_email_exception_handling(self, mock_resend, mock_settings):
        """Test password reset email handles exceptions gracefully."""
        from app.services.email import send_password_reset_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "test@example.com"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.side_effect = Exception("API Error")

        result = send_password_reset_email("user@example.com", "test_token")

        assert result is False


class TestEmailTemplates:
    """Tests for email template content."""

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_welcome_email_contains_required_elements(self, mock_resend, mock_settings):
        """Test welcome email contains all required elements."""
        from app.services.email import send_welcome_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "test@example.com"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.return_value = {"id": "test_email_id"}

        send_welcome_email("user@example.com", "TestUser")

        call_args = mock_resend.Emails.send.call_args[0][0]
        html_content = call_args["html"]

        # Check required elements
        assert "WondersTracker" in html_content or "WONDERSTRACKER" in html_content
        assert "TestUser" in html_content
        assert "https://example.com" in html_content  # Dashboard link
        assert "portfolio" in html_content.lower()  # Feature mention
        assert "market" in html_content.lower() or "price" in html_content.lower()

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_password_reset_email_contains_required_elements(self, mock_resend, mock_settings):
        """Test password reset email contains all required elements."""
        from app.services.email import send_password_reset_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "test@example.com"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.return_value = {"id": "test_email_id"}

        send_password_reset_email("user@example.com", "secure_token_xyz")

        call_args = mock_resend.Emails.send.call_args[0][0]
        html_content = call_args["html"]

        # Check required elements
        assert "Reset" in html_content or "reset" in html_content
        assert "secure_token_xyz" in html_content
        assert "1 hour" in html_content or "expire" in html_content.lower()
        assert "didn't request" in html_content.lower() or "ignore" in html_content.lower()

    @patch("app.services.email.settings")
    @patch("app.services.email.resend")
    def test_email_from_address_is_correct(self, mock_resend, mock_settings):
        """Test emails use correct from address."""
        from app.services.email import send_welcome_email

        mock_settings.RESEND_API_KEY = "test_api_key"
        mock_settings.FROM_EMAIL = "WondersTracker <noreply@wonderstrader.com>"
        mock_settings.FRONTEND_URL = "https://example.com"
        mock_resend.Emails.send.return_value = {"id": "test_email_id"}

        send_welcome_email("user@example.com")

        call_args = mock_resend.Emails.send.call_args[0][0]
        assert call_args["from"] == "WondersTracker <noreply@wonderstrader.com>"
