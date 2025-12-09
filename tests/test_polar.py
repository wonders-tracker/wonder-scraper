"""
Tests for Polar.sh billing integration.

Tests cover:
- Polar client configuration
- Checkout session creation
- Customer portal URL generation
- Usage event ingestion
- Webhook signature verification
- Subscription lifecycle event handlers
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from sqlmodel import Session

from app.models.user import User
from app.core import security


class TestPolarClient:
    """Tests for Polar client configuration."""

    @patch('app.services.polar.settings')
    def test_get_polar_client_production(self, mock_settings):
        """Test Polar client uses production by default."""
        mock_settings.POLAR_ACCESS_TOKEN = "test_token"
        mock_settings.POLAR_ENVIRONMENT = "production"

        from app.services.polar import get_polar_client
        with patch('app.services.polar.Polar') as mock_polar:
            get_polar_client()
            mock_polar.assert_called_once_with(
                access_token="test_token",
                server=None  # None = production
            )

    @patch('app.services.polar.settings')
    def test_get_polar_client_sandbox(self, mock_settings):
        """Test Polar client uses sandbox when configured."""
        mock_settings.POLAR_ACCESS_TOKEN = "test_token"
        mock_settings.POLAR_ENVIRONMENT = "sandbox"

        from app.services.polar import get_polar_client
        with patch('app.services.polar.Polar') as mock_polar:
            get_polar_client()
            mock_polar.assert_called_once_with(
                access_token="test_token",
                server="sandbox"
            )


class TestCheckoutSession:
    """Tests for checkout session creation."""

    @pytest.mark.asyncio
    async def test_create_checkout_session_success(self):
        """Test successful checkout session creation."""
        mock_checkout = MagicMock()
        mock_checkout.url = "https://checkout.polar.sh/abc123"

        mock_polar = MagicMock()
        mock_polar.checkouts.custom.create.return_value = mock_checkout

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            from app.services.polar import create_checkout_session

            url = await create_checkout_session(
                product_id="prod_123",
                customer_email="test@example.com",
                success_url="https://example.com/success",
                metadata={"user_id": "1"}
            )

            assert url == "https://checkout.polar.sh/abc123"
            mock_polar.checkouts.custom.create.assert_called_once_with(
                product_id="prod_123",
                customer_email="test@example.com",
                success_url="https://example.com/success",
                metadata={"user_id": "1"}
            )

    @pytest.mark.asyncio
    async def test_create_checkout_session_no_metadata(self):
        """Test checkout session creation without metadata uses empty dict."""
        mock_checkout = MagicMock()
        mock_checkout.url = "https://checkout.polar.sh/xyz789"

        mock_polar = MagicMock()
        mock_polar.checkouts.custom.create.return_value = mock_checkout

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            from app.services.polar import create_checkout_session

            url = await create_checkout_session(
                product_id="prod_123",
                customer_email="test@example.com",
                success_url="https://example.com/success"
            )

            # Verify empty dict is used when metadata is None
            mock_polar.checkouts.custom.create.assert_called_once_with(
                product_id="prod_123",
                customer_email="test@example.com",
                success_url="https://example.com/success",
                metadata={}
            )


class TestCustomerPortal:
    """Tests for customer portal URL generation."""

    @pytest.mark.asyncio
    async def test_get_customer_portal_url_success(self):
        """Test successful customer portal URL generation."""
        mock_session = MagicMock()
        mock_session.customer_portal_url = "https://portal.polar.sh/cust_123"

        mock_polar = MagicMock()
        mock_polar.customer_sessions.create.return_value = mock_session

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            from app.services.polar import get_customer_portal_url

            url = await get_customer_portal_url("cust_123")

            assert url == "https://portal.polar.sh/cust_123"
            mock_polar.customer_sessions.create.assert_called_once_with(
                customer_id="cust_123"
            )


class TestUsageEventIngestion:
    """Tests for usage event ingestion."""

    @pytest.mark.asyncio
    async def test_ingest_usage_event_success(self):
        """Test successful usage event ingestion."""
        mock_polar = MagicMock()

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            with patch('app.services.polar.settings') as mock_settings:
                mock_settings.POLAR_ACCESS_TOKEN = "test_token"

                from app.services.polar import ingest_usage_event

                await ingest_usage_event(
                    customer_id="cust_123",
                    event_name="api_request",
                    metadata={"endpoint": "/api/v1/cards/1", "method": "GET"}
                )

                mock_polar.events.ingest.assert_called_once_with(
                    events=[{
                        "name": "api_request",
                        "external_customer_id": "cust_123",
                        "metadata": {"endpoint": "/api/v1/cards/1", "method": "GET"}
                    }]
                )

    @pytest.mark.asyncio
    async def test_ingest_usage_event_no_customer_id_skips(self):
        """Test usage event ingestion is skipped when customer_id is empty."""
        mock_polar = MagicMock()

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            with patch('app.services.polar.settings') as mock_settings:
                mock_settings.POLAR_ACCESS_TOKEN = "test_token"

                from app.services.polar import ingest_usage_event

                await ingest_usage_event(
                    customer_id="",  # Empty
                    event_name="api_request"
                )

                # Should not call ingest
                mock_polar.events.ingest.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_usage_event_no_token_skips(self):
        """Test usage event ingestion is skipped when access token is missing."""
        mock_polar = MagicMock()

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            with patch('app.services.polar.settings') as mock_settings:
                mock_settings.POLAR_ACCESS_TOKEN = ""

                from app.services.polar import ingest_usage_event

                await ingest_usage_event(
                    customer_id="cust_123",
                    event_name="api_request"
                )

                # Should not call ingest
                mock_polar.events.ingest.assert_not_called()

    @pytest.mark.asyncio
    async def test_ingest_usage_event_handles_exception(self):
        """Test usage event ingestion handles exceptions gracefully."""
        mock_polar = MagicMock()
        mock_polar.events.ingest.side_effect = Exception("Network error")

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            with patch('app.services.polar.settings') as mock_settings:
                mock_settings.POLAR_ACCESS_TOKEN = "test_token"

                from app.services.polar import ingest_usage_event

                # Should not raise exception
                await ingest_usage_event(
                    customer_id="cust_123",
                    event_name="api_request"
                )

    @pytest.mark.asyncio
    async def test_ingest_usage_event_no_metadata_uses_empty_dict(self):
        """Test usage event ingestion uses empty dict when metadata is None."""
        mock_polar = MagicMock()

        with patch('app.services.polar.get_polar_client', return_value=mock_polar):
            with patch('app.services.polar.settings') as mock_settings:
                mock_settings.POLAR_ACCESS_TOKEN = "test_token"

                from app.services.polar import ingest_usage_event

                await ingest_usage_event(
                    customer_id="cust_123",
                    event_name="api_request"
                )

                mock_polar.events.ingest.assert_called_once_with(
                    events=[{
                        "name": "api_request",
                        "external_customer_id": "cust_123",
                        "metadata": {}
                    }]
                )


class TestWebhookSignatureVerification:
    """Tests for Polar webhook signature verification."""

    def test_verify_polar_signature_valid(self):
        """Test verification of valid webhook signature."""
        import hmac
        import hashlib

        from app.api.webhooks import verify_polar_signature

        secret = "whsec_test123"
        payload = b'{"type": "subscription.active"}'
        timestamp = "1234567890"

        # Compute expected signature
        signed_payload = f"{timestamp}.{payload.decode('utf-8')}"
        expected_sig = hmac.new(
            secret.encode("utf-8"),
            signed_payload.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        signature = f"v1,{timestamp},{expected_sig}"

        assert verify_polar_signature(payload, signature, secret) is True

    def test_verify_polar_signature_invalid(self):
        """Test verification fails with invalid signature."""
        from app.api.webhooks import verify_polar_signature

        secret = "whsec_test123"
        payload = b'{"type": "subscription.active"}'
        signature = "v1,1234567890,invalid_signature"

        assert verify_polar_signature(payload, signature, secret) is False

    def test_verify_polar_signature_empty_signature(self):
        """Test verification fails with empty signature."""
        from app.api.webhooks import verify_polar_signature

        assert verify_polar_signature(b'{}', "", "secret") is False

    def test_verify_polar_signature_empty_secret(self):
        """Test verification fails with empty secret."""
        from app.api.webhooks import verify_polar_signature

        assert verify_polar_signature(b'{}', "v1,123,abc", "") is False

    def test_verify_polar_signature_malformed(self):
        """Test verification fails with malformed signature."""
        from app.api.webhooks import verify_polar_signature

        assert verify_polar_signature(b'{}', "invalid", "secret") is False
        assert verify_polar_signature(b'{}', "v1,123", "secret") is False  # Missing sig part


class TestWebhookHandlers:
    """Tests for webhook event handlers."""

    @pytest.fixture
    def pro_user(self, test_session: Session) -> User:
        """Create a user for subscription testing."""
        user = User(
            id=100,
            email="pro@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            subscription_tier="free",
            subscription_status=None,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_handle_subscription_active(self, test_session: Session, pro_user: User):
        """Test subscription.active event upgrades user to Pro."""
        from app.api.webhooks import handle_subscription_active

        data = {
            "id": "sub_123",
            "customer_id": "cust_abc",
            "status": "active",
            "metadata": {"user_id": str(pro_user.id)},
            "current_period_end": "2025-02-01T00:00:00Z"
        }

        await handle_subscription_active(data, test_session)

        test_session.refresh(pro_user)
        assert pro_user.subscription_tier == "pro"
        assert pro_user.subscription_status == "active"
        assert pro_user.subscription_id == "sub_123"
        assert pro_user.polar_customer_id == "cust_abc"
        assert pro_user.has_api_access is True

    @pytest.mark.asyncio
    async def test_handle_subscription_canceled(self, test_session: Session, pro_user: User):
        """Test subscription.canceled event marks user as canceled."""
        from app.api.webhooks import handle_subscription_canceled

        # First make user Pro
        pro_user.subscription_tier = "pro"
        pro_user.subscription_status = "active"
        pro_user.subscription_id = "sub_123"
        test_session.add(pro_user)
        test_session.commit()

        data = {"id": "sub_123", "status": "canceled"}

        await handle_subscription_canceled(data, test_session)

        test_session.refresh(pro_user)
        assert pro_user.subscription_status == "canceled"
        # Tier should still be pro until period end
        assert pro_user.subscription_tier == "pro"

    @pytest.mark.asyncio
    async def test_handle_subscription_revoked(self, test_session: Session, pro_user: User):
        """Test subscription.revoked event downgrades user to free."""
        from app.api.webhooks import handle_subscription_revoked

        # First make user Pro
        pro_user.subscription_tier = "pro"
        pro_user.subscription_status = "active"
        pro_user.subscription_id = "sub_123"
        pro_user.has_api_access = True
        test_session.add(pro_user)
        test_session.commit()

        data = {"id": "sub_123"}

        await handle_subscription_revoked(data, test_session)

        test_session.refresh(pro_user)
        assert pro_user.subscription_tier == "free"
        assert pro_user.subscription_status is None
        assert pro_user.has_api_access is False

    @pytest.mark.asyncio
    async def test_find_user_from_subscription_by_metadata(self, test_session: Session, pro_user: User):
        """Test finding user by metadata user_id."""
        from app.api.webhooks import find_user_from_subscription

        data = {"metadata": {"user_id": str(pro_user.id)}}

        user = await find_user_from_subscription(data, test_session)
        assert user is not None
        assert user.id == pro_user.id

    @pytest.mark.asyncio
    async def test_find_user_from_subscription_by_subscription_id(self, test_session: Session, pro_user: User):
        """Test finding user by subscription_id."""
        from app.api.webhooks import find_user_from_subscription

        pro_user.subscription_id = "sub_xyz"
        test_session.add(pro_user)
        test_session.commit()

        data = {"id": "sub_xyz", "metadata": {}}

        user = await find_user_from_subscription(data, test_session)
        assert user is not None
        assert user.id == pro_user.id

    @pytest.mark.asyncio
    async def test_find_user_from_subscription_by_customer_id(self, test_session: Session, pro_user: User):
        """Test finding user by polar_customer_id."""
        from app.api.webhooks import find_user_from_subscription

        pro_user.polar_customer_id = "cust_xyz"
        test_session.add(pro_user)
        test_session.commit()

        data = {"customer_id": "cust_xyz", "metadata": {}}

        user = await find_user_from_subscription(data, test_session)
        assert user is not None
        assert user.id == pro_user.id

    @pytest.mark.asyncio
    async def test_find_user_from_subscription_by_email(self, test_session: Session, pro_user: User):
        """Test finding user by customer email."""
        from app.api.webhooks import find_user_from_subscription

        data = {"customer": {"email": pro_user.email}, "metadata": {}}

        user = await find_user_from_subscription(data, test_session)
        assert user is not None
        assert user.id == pro_user.id

    @pytest.mark.asyncio
    async def test_find_user_from_subscription_not_found(self, test_session: Session):
        """Test finding user returns None when not found."""
        from app.api.webhooks import find_user_from_subscription

        data = {
            "id": "sub_nonexistent",
            "customer_id": "cust_nonexistent",
            "customer": {"email": "nobody@example.com"},
            "metadata": {"user_id": "99999"}
        }

        user = await find_user_from_subscription(data, test_session)
        assert user is None
