"""
End-to-end tests for billing and subscription flows.

Tests cover:
- Complete checkout flow from upgrade page to subscription active
- API access request and approval workflow
- Subscription cancellation and downgrade
- Webhook event processing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.models.user import User
from app.core import security


class TestE2ECheckoutFlow:
    """End-to-end tests for checkout flow."""

    @pytest.fixture
    def free_user(self, test_session: Session) -> User:
        """Create a free tier user for E2E testing."""
        user = User(
            id=500,
            email="e2e_free@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            subscription_tier="free",
            subscription_status=None,
            has_api_access=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    def test_full_pro_upgrade_flow(self, test_session: Session, free_user: User):
        """Test complete Pro upgrade flow: checkout -> webhook -> upgrade."""
        # Step 1: Verify user starts as free
        assert free_user.subscription_tier == "free"
        assert free_user.is_pro is False
        assert free_user.has_api_access is False

        # Step 2: Simulate checkout creation
        with patch('app.api.billing.create_checkout_session', new_callable=AsyncMock) as mock_checkout:
            mock_checkout.return_value = "https://checkout.polar.sh/test123"

            # This would normally be called via API endpoint
            # Simulating the checkout redirect happening

        # Step 3: Simulate successful webhook callback (subscription.active)
        subscription_data = {
            "id": "sub_e2e_test",
            "customer_id": "cust_e2e_test",
            "status": "active",
            "metadata": {"user_id": str(free_user.id)},
            "current_period_end": (datetime.utcnow() + timedelta(days=30)).isoformat() + "Z"
        }

        # Import and call webhook handler directly
        import asyncio
        from app.api.webhooks import handle_subscription_active

        asyncio.get_event_loop().run_until_complete(
            handle_subscription_active(subscription_data, test_session)
        )

        # Step 4: Verify user is now Pro
        test_session.refresh(free_user)
        assert free_user.subscription_tier == "pro"
        assert free_user.subscription_status == "active"
        assert free_user.is_pro is True
        assert free_user.has_api_access is True
        assert free_user.subscription_id == "sub_e2e_test"
        assert free_user.polar_customer_id == "cust_e2e_test"

    def test_subscription_cancellation_flow(self, test_session: Session, free_user: User):
        """Test subscription cancellation: active -> canceled -> revoked."""
        # Step 1: Start with Pro user
        free_user.subscription_tier = "pro"
        free_user.subscription_status = "active"
        free_user.subscription_id = "sub_cancel_test"
        free_user.polar_customer_id = "cust_cancel_test"
        free_user.has_api_access = True
        test_session.add(free_user)
        test_session.commit()

        assert free_user.is_pro is True

        # Step 2: User cancels (subscription.canceled webhook)
        import asyncio
        from app.api.webhooks import handle_subscription_canceled

        cancel_data = {"id": "sub_cancel_test", "status": "canceled"}
        asyncio.get_event_loop().run_until_complete(
            handle_subscription_canceled(cancel_data, test_session)
        )

        test_session.refresh(free_user)
        assert free_user.subscription_status == "canceled"
        # Should still be "pro" tier until period ends
        assert free_user.subscription_tier == "pro"

        # Step 3: Period ends (subscription.revoked webhook)
        from app.api.webhooks import handle_subscription_revoked

        revoke_data = {"id": "sub_cancel_test"}
        asyncio.get_event_loop().run_until_complete(
            handle_subscription_revoked(revoke_data, test_session)
        )

        test_session.refresh(free_user)
        assert free_user.subscription_tier == "free"
        assert free_user.subscription_status is None
        assert free_user.is_pro is False
        assert free_user.has_api_access is False


class TestE2EAPIAccessFlow:
    """End-to-end tests for API access request flow."""

    @pytest.fixture
    def requesting_user(self, test_session: Session) -> User:
        """Create a user for API access request testing."""
        user = User(
            id=501,
            email="e2e_api_request@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            has_api_access=False,
            api_access_requested=False,
            username="E2EApiUser",
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.fixture
    def admin_user(self, test_session: Session) -> User:
        """Create admin user for approval testing."""
        user = User(
            id=502,
            email="e2e_admin@example.com",
            hashed_password=security.get_password_hash("adminpass"),
            is_active=True,
            is_superuser=True,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_full_api_access_approval_flow(
        self, test_session: Session, requesting_user: User, admin_user: User
    ):
        """Test complete API access flow: request -> admin review -> approval -> email."""
        from app.api.billing import (
            request_api_access,
            list_api_access_requests,
            approve_api_access
        )

        # Step 1: User requests API access
        result = await request_api_access(user=requesting_user, session=test_session)
        assert "submitted" in result["message"]

        test_session.refresh(requesting_user)
        assert requesting_user.api_access_requested is True
        assert requesting_user.api_access_requested_at is not None

        # Step 2: Admin lists pending requests
        pending = await list_api_access_requests(admin=admin_user, session=test_session)
        user_request = next((r for r in pending if r["id"] == requesting_user.id), None)
        assert user_request is not None
        assert user_request["email"] == requesting_user.email

        # Step 3: Admin approves request
        with patch('app.services.email.send_api_access_approved_email', new_callable=AsyncMock) as mock_email:
            result = await approve_api_access(
                user_id=requesting_user.id,
                admin=admin_user,
                session=test_session
            )

            assert "approved" in result["message"]
            mock_email.assert_called_once_with(
                requesting_user.email,
                requesting_user.username
            )

        # Step 4: Verify user is approved
        test_session.refresh(requesting_user)
        assert requesting_user.api_access_approved is True
        assert requesting_user.api_access_approved_at is not None

    @pytest.mark.asyncio
    async def test_api_access_denial_flow(
        self, test_session: Session, requesting_user: User, admin_user: User
    ):
        """Test API access denial flow."""
        from app.api.billing import request_api_access, deny_api_access

        # Step 1: User requests access
        await request_api_access(user=requesting_user, session=test_session)

        test_session.refresh(requesting_user)
        assert requesting_user.api_access_requested is True

        # Step 2: Admin denies request
        result = await deny_api_access(
            user_id=requesting_user.id,
            admin=admin_user,
            session=test_session
        )

        assert "denied" in result["message"]

        # Step 3: Verify request is reset
        test_session.refresh(requesting_user)
        assert requesting_user.api_access_requested is False
        assert requesting_user.api_access_requested_at is None
        assert requesting_user.api_access_approved is False


class TestE2EWebhookProcessing:
    """End-to-end tests for webhook event processing."""

    @pytest.fixture
    def webhook_user(self, test_session: Session) -> User:
        """Create a user for webhook testing."""
        user = User(
            id=503,
            email="e2e_webhook@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    def test_webhook_user_lookup_by_metadata(self, test_session: Session, webhook_user: User):
        """Test webhook finds user by metadata user_id."""
        import asyncio
        from app.api.webhooks import handle_subscription_active

        data = {
            "id": "sub_metadata_lookup",
            "customer_id": "cust_metadata",
            "status": "active",
            "metadata": {"user_id": str(webhook_user.id)},
        }

        asyncio.get_event_loop().run_until_complete(
            handle_subscription_active(data, test_session)
        )

        test_session.refresh(webhook_user)
        assert webhook_user.subscription_tier == "pro"

    def test_webhook_user_lookup_by_subscription_id(self, test_session: Session, webhook_user: User):
        """Test webhook finds user by existing subscription_id."""
        import asyncio
        from app.api.webhooks import handle_subscription_updated

        # Set up user with subscription ID
        webhook_user.subscription_id = "sub_existing"
        webhook_user.subscription_tier = "pro"
        webhook_user.subscription_status = "active"
        test_session.add(webhook_user)
        test_session.commit()

        data = {
            "id": "sub_existing",
            "status": "past_due",
            "metadata": {},
        }

        asyncio.get_event_loop().run_until_complete(
            handle_subscription_updated(data, test_session)
        )

        test_session.refresh(webhook_user)
        assert webhook_user.subscription_status == "past_due"

    def test_webhook_user_lookup_by_customer_id(self, test_session: Session, webhook_user: User):
        """Test webhook finds user by polar_customer_id."""
        import asyncio
        from app.api.webhooks import find_user_from_subscription

        webhook_user.polar_customer_id = "cust_lookup_test"
        test_session.add(webhook_user)
        test_session.commit()

        data = {
            "id": "sub_new",
            "customer_id": "cust_lookup_test",
            "metadata": {},
        }

        user = asyncio.get_event_loop().run_until_complete(
            find_user_from_subscription(data, test_session)
        )

        assert user is not None
        assert user.id == webhook_user.id

    def test_webhook_user_lookup_by_email(self, test_session: Session, webhook_user: User):
        """Test webhook finds user by customer email."""
        import asyncio
        from app.api.webhooks import find_user_from_subscription

        data = {
            "id": "sub_email_lookup",
            "metadata": {},
            "customer": {"email": webhook_user.email}
        }

        user = asyncio.get_event_loop().run_until_complete(
            find_user_from_subscription(data, test_session)
        )

        assert user is not None
        assert user.id == webhook_user.id

    def test_webhook_period_end_is_parsed(self, test_session: Session, webhook_user: User):
        """Test webhook correctly parses period end date."""
        import asyncio
        from app.api.webhooks import handle_subscription_active

        period_end = "2025-03-15T12:00:00Z"

        data = {
            "id": "sub_period_test",
            "customer_id": "cust_period",
            "status": "active",
            "metadata": {"user_id": str(webhook_user.id)},
            "current_period_end": period_end,
        }

        asyncio.get_event_loop().run_until_complete(
            handle_subscription_active(data, test_session)
        )

        test_session.refresh(webhook_user)
        assert webhook_user.subscription_current_period_end is not None
        assert webhook_user.subscription_current_period_end.year == 2025
        assert webhook_user.subscription_current_period_end.month == 3
        assert webhook_user.subscription_current_period_end.day == 15


class TestE2EMeteringIntegration:
    """End-to-end tests for metering integration."""

    @pytest.fixture
    def metered_user(self, test_session: Session) -> User:
        """Create a Pro user with customer ID for metering tests."""
        user = User(
            id=504,
            email="e2e_metered@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            subscription_tier="pro",
            subscription_status="active",
            polar_customer_id="cust_metering_test",
            has_api_access=True,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_metering_sends_correct_event(self, metered_user: User):
        """Test metering sends correctly formatted events to Polar."""
        from app.middleware.metering import APIMeteringMiddleware

        middleware = APIMeteringMiddleware(app=MagicMock())

        with patch('app.services.polar.ingest_usage_event', new_callable=AsyncMock) as mock_ingest:
            await middleware._send_usage_event(
                customer_id=metered_user.polar_customer_id,
                endpoint="/api/v1/cards/123",
                method="GET"
            )

            mock_ingest.assert_called_once()
            call_kwargs = mock_ingest.call_args.kwargs
            assert call_kwargs["customer_id"] == "cust_metering_test"
            assert call_kwargs["event_name"] == "api_request"
            assert call_kwargs["metadata"]["endpoint"] == "/api/v1/cards/123"
            assert call_kwargs["metadata"]["method"] == "GET"
            assert call_kwargs["metadata"]["requests"] == 1


class TestE2ESubscriptionStatusConsistency:
    """End-to-end tests for subscription status consistency."""

    @pytest.fixture
    def status_user(self, test_session: Session) -> User:
        """Create user for status consistency testing."""
        user = User(
            id=505,
            email="e2e_status@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_status_reflects_tier_correctly(self, test_session: Session, status_user: User):
        """Test subscription status endpoint returns correct data."""
        from app.api.billing import get_subscription_status

        # Free user
        result = await get_subscription_status(user=status_user)
        assert result["tier"] == "free"
        assert result["is_pro"] is False

        # Upgrade to Pro
        status_user.subscription_tier = "pro"
        status_user.subscription_status = "active"
        status_user.has_api_access = True
        test_session.add(status_user)
        test_session.commit()
        test_session.refresh(status_user)

        result = await get_subscription_status(user=status_user)
        assert result["tier"] == "pro"
        assert result["is_pro"] is True
        assert result["has_api_access"] is True

        # Cancel subscription
        status_user.subscription_status = "canceled"
        test_session.add(status_user)
        test_session.commit()
        test_session.refresh(status_user)

        result = await get_subscription_status(user=status_user)
        assert result["tier"] == "pro"
        assert result["status"] == "canceled"
        # is_pro should be False when canceled
        assert result["is_pro"] is False
