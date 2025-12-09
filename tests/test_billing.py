"""
Tests for billing API endpoints.

Tests cover:
- Checkout creation (Pro and API products)
- Customer portal access
- Subscription status queries
- API access request flow
- Admin approval/denial workflow
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from sqlmodel import Session

from app.models.user import User
from app.core import security


class TestBillingCheckout:
    """Tests for checkout endpoint."""

    @pytest.fixture
    def mock_request(self):
        """Create a mock request object."""
        request = MagicMock()
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        request.headers = {}
        return request

    @pytest.fixture
    def free_user(self, test_session: Session) -> User:
        """Create a free tier user."""
        user = User(
            id=200,
            email="free@example.com",
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

    @pytest.fixture
    def pro_user(self, test_session: Session) -> User:
        """Create a Pro tier user."""
        user = User(
            id=201,
            email="existing_pro@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            subscription_tier="pro",
            subscription_status="active",
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_checkout_creates_pro_session(self, test_session: Session, free_user: User, mock_request):
        """Test checkout creates session for Pro product."""
        with patch('app.api.billing.create_checkout_session', new_callable=AsyncMock) as mock_checkout:
            with patch('app.api.billing.settings') as mock_settings:
                with patch('app.api.billing.rate_limiter') as mock_limiter:
                    mock_limiter.is_rate_limited.return_value = (False, 0)
                    mock_settings.POLAR_PRO_PRODUCT_ID = "prod_pro_123"
                    mock_settings.POLAR_SUCCESS_URL = "https://example.com/success"
                    mock_settings.FRONTEND_URL = "https://example.com"
                    mock_checkout.return_value = "https://checkout.polar.sh/abc123"

                    from app.api.billing import create_checkout

                    result = await create_checkout(
                        request=mock_request,
                        product="pro",
                        user=free_user,
                        session=test_session
                    )

                    assert result["checkout_url"] == "https://checkout.polar.sh/abc123"
                    mock_checkout.assert_called_once()
                    call_args = mock_checkout.call_args
                    assert call_args.kwargs["product_id"] == "prod_pro_123"
                    assert call_args.kwargs["customer_email"] == free_user.email

    @pytest.mark.asyncio
    async def test_checkout_creates_api_session(self, test_session: Session, free_user: User, mock_request):
        """Test checkout creates session for API product."""
        with patch('app.api.billing.create_checkout_session', new_callable=AsyncMock) as mock_checkout:
            with patch('app.api.billing.settings') as mock_settings:
                with patch('app.api.billing.rate_limiter') as mock_limiter:
                    mock_limiter.is_rate_limited.return_value = (False, 0)
                    mock_settings.POLAR_API_PRODUCT_ID = "prod_api_456"
                    mock_settings.POLAR_SUCCESS_URL = "https://example.com/success"
                    mock_settings.FRONTEND_URL = "https://example.com"
                    mock_checkout.return_value = "https://checkout.polar.sh/xyz789"

                    from app.api.billing import create_checkout

                    result = await create_checkout(
                        request=mock_request,
                        product="api",
                        user=free_user,
                        session=test_session
                    )

                    assert result["checkout_url"] == "https://checkout.polar.sh/xyz789"
                    call_args = mock_checkout.call_args
                    assert call_args.kwargs["product_id"] == "prod_api_456"

    @pytest.mark.asyncio
    async def test_checkout_already_pro_fails(self, test_session: Session, pro_user: User, mock_request):
        """Test checkout fails for users who already have Pro."""
        from app.api.billing import create_checkout
        from fastapi import HTTPException

        with patch('app.api.billing.rate_limiter') as mock_limiter:
            mock_limiter.is_rate_limited.return_value = (False, 0)

            with pytest.raises(HTTPException) as exc_info:
                await create_checkout(request=mock_request, product="pro", user=pro_user, session=test_session)

            assert exc_info.value.status_code == 400
            assert "already have an active subscription" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_checkout_missing_product_id_fails(self, test_session: Session, free_user: User, mock_request):
        """Test checkout fails when product ID is not configured."""
        with patch('app.api.billing.settings') as mock_settings:
            with patch('app.api.billing.rate_limiter') as mock_limiter:
                mock_limiter.is_rate_limited.return_value = (False, 0)
                mock_settings.POLAR_PRO_PRODUCT_ID = ""  # Empty

                from app.api.billing import create_checkout
                from fastapi import HTTPException

                with pytest.raises(HTTPException) as exc_info:
                    await create_checkout(request=mock_request, product="pro", user=free_user, session=test_session)

            assert exc_info.value.status_code == 500
            assert "not configured" in exc_info.value.detail


class TestBillingPortal:
    """Tests for billing portal endpoint."""

    @pytest.fixture
    def subscribed_user(self, test_session: Session) -> User:
        """Create a user with a subscription and customer ID."""
        user = User(
            id=202,
            email="subscribed@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            subscription_tier="pro",
            subscription_status="active",
            polar_customer_id="cust_abc123",
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_get_billing_portal_success(self, subscribed_user: User):
        """Test successful portal URL retrieval."""
        with patch('app.api.billing.get_customer_portal_url', new_callable=AsyncMock) as mock_portal:
            mock_portal.return_value = "https://portal.polar.sh/session123"

            from app.api.billing import get_billing_portal

            result = await get_billing_portal(user=subscribed_user)

            assert result["portal_url"] == "https://portal.polar.sh/session123"
            mock_portal.assert_called_once_with("cust_abc123")

    @pytest.mark.asyncio
    async def test_get_billing_portal_no_customer_id_fails(self, test_session: Session):
        """Test portal fails for user without customer ID."""
        user = User(
            id=203,
            email="nocustomer@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            polar_customer_id=None,
        )
        test_session.add(user)
        test_session.commit()

        from app.api.billing import get_billing_portal
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await get_billing_portal(user=user)

        assert exc_info.value.status_code == 400
        assert "No subscription found" in exc_info.value.detail


class TestSubscriptionStatus:
    """Tests for subscription status endpoint."""

    @pytest.mark.asyncio
    async def test_get_subscription_status_free_user(self, test_session: Session):
        """Test status for free tier user."""
        user = User(
            id=204,
            email="status_free@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            subscription_tier="free",
            subscription_status=None,
        )
        test_session.add(user)
        test_session.commit()

        from app.api.billing import get_subscription_status

        result = await get_subscription_status(user=user)

        assert result["tier"] == "free"
        assert result["status"] is None
        assert result["is_pro"] is False
        assert result["has_api_access"] is False

    @pytest.mark.asyncio
    async def test_get_subscription_status_pro_user(self, test_session: Session):
        """Test status for Pro tier user."""
        period_end = datetime.utcnow() + timedelta(days=30)
        user = User(
            id=205,
            email="status_pro@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            subscription_tier="pro",
            subscription_status="active",
            has_api_access=True,
            subscription_current_period_end=period_end,
        )
        test_session.add(user)
        test_session.commit()

        from app.api.billing import get_subscription_status

        result = await get_subscription_status(user=user)

        assert result["tier"] == "pro"
        assert result["status"] == "active"
        assert result["is_pro"] is True
        assert result["has_api_access"] is True
        assert result["current_period_end"] == period_end.isoformat()


class TestAPIAccessRequest:
    """Tests for API access request flow."""

    @pytest.fixture
    def regular_user(self, test_session: Session) -> User:
        """Create a regular user without API access."""
        user = User(
            id=206,
            email="regular@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            has_api_access=False,
            api_access_requested=False,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.fixture
    def requesting_user(self, test_session: Session) -> User:
        """Create a user who has already requested API access."""
        user = User(
            id=207,
            email="requesting@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            has_api_access=False,
            api_access_requested=True,
            api_access_requested_at=datetime.utcnow(),
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.fixture
    def admin_user(self, test_session: Session) -> User:
        """Create an admin user."""
        user = User(
            id=208,
            email="admin@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=True,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_request_api_access_success(self, test_session: Session, regular_user: User):
        """Test successful API access request."""
        from app.api.billing import request_api_access

        result = await request_api_access(user=regular_user, session=test_session)

        test_session.refresh(regular_user)
        assert regular_user.api_access_requested is True
        assert regular_user.api_access_requested_at is not None
        assert "submitted" in result["message"]

    @pytest.mark.asyncio
    async def test_request_api_access_already_has_access_fails(self, test_session: Session, regular_user: User):
        """Test request fails if user already has API access."""
        regular_user.has_api_access = True
        test_session.add(regular_user)
        test_session.commit()

        from app.api.billing import request_api_access
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await request_api_access(user=regular_user, session=test_session)

        assert exc_info.value.status_code == 400
        assert "already have API access" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_request_api_access_already_requested_fails(self, test_session: Session, requesting_user: User):
        """Test request fails if already submitted."""
        from app.api.billing import request_api_access
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await request_api_access(user=requesting_user, session=test_session)

        assert exc_info.value.status_code == 400
        assert "already requested" in exc_info.value.detail


class TestAdminAPIAccessApproval:
    """Tests for admin API access approval workflow."""

    @pytest.fixture
    def pending_request_user(self, test_session: Session) -> User:
        """Create a user with pending API access request."""
        user = User(
            id=209,
            email="pending@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=False,
            has_api_access=False,
            api_access_requested=True,
            api_access_requested_at=datetime.utcnow(),
            api_access_approved=False,
            username="PendingUser",
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.fixture
    def admin_user(self, test_session: Session) -> User:
        """Create an admin user."""
        user = User(
            id=210,
            email="admin2@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            is_superuser=True,
        )
        test_session.add(user)
        test_session.commit()
        test_session.refresh(user)
        return user

    @pytest.mark.asyncio
    async def test_list_api_access_requests(
        self, test_session: Session, pending_request_user: User, admin_user: User
    ):
        """Test listing pending API access requests."""
        from app.api.billing import list_api_access_requests

        result = await list_api_access_requests(admin=admin_user, session=test_session)

        assert len(result) >= 1
        request = next((r for r in result if r["id"] == pending_request_user.id), None)
        assert request is not None
        assert request["email"] == pending_request_user.email
        assert request["username"] == "PendingUser"

    @pytest.mark.asyncio
    async def test_approve_api_access(
        self, test_session: Session, pending_request_user: User, admin_user: User
    ):
        """Test approving API access request."""
        with patch('app.services.email.send_api_access_approved_email', new_callable=AsyncMock):
            from app.api.billing import approve_api_access

            result = await approve_api_access(
                user_id=pending_request_user.id,
                admin=admin_user,
                session=test_session
            )

            test_session.refresh(pending_request_user)
            assert pending_request_user.api_access_approved is True
            assert pending_request_user.api_access_approved_at is not None
            assert "approved" in result["message"]

    @pytest.mark.asyncio
    async def test_approve_nonexistent_user_fails(self, test_session: Session, admin_user: User):
        """Test approving non-existent user fails."""
        from app.api.billing import approve_api_access
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await approve_api_access(user_id=99999, admin=admin_user, session=test_session)

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_user_not_requested_fails(self, test_session: Session, admin_user: User):
        """Test approving user who hasn't requested fails."""
        user = User(
            id=211,
            email="notrequested@example.com",
            hashed_password=security.get_password_hash("password123"),
            is_active=True,
            api_access_requested=False,
        )
        test_session.add(user)
        test_session.commit()

        from app.api.billing import approve_api_access
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await approve_api_access(user_id=user.id, admin=admin_user, session=test_session)

        assert exc_info.value.status_code == 400
        assert "has not requested" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_deny_api_access(
        self, test_session: Session, pending_request_user: User, admin_user: User
    ):
        """Test denying API access request."""
        from app.api.billing import deny_api_access

        result = await deny_api_access(
            user_id=pending_request_user.id,
            admin=admin_user,
            session=test_session
        )

        test_session.refresh(pending_request_user)
        assert pending_request_user.api_access_requested is False
        assert pending_request_user.api_access_requested_at is None
        assert "denied" in result["message"]

    @pytest.mark.asyncio
    async def test_deny_nonexistent_user_fails(self, test_session: Session, admin_user: User):
        """Test denying non-existent user fails."""
        from app.api.billing import deny_api_access
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            await deny_api_access(user_id=99999, admin=admin_user, session=test_session)

        assert exc_info.value.status_code == 404


class TestUserModelSubscriptionProperties:
    """Tests for User model subscription properties."""

    def test_is_pro_active_subscription(self, test_session: Session):
        """Test is_pro returns True for active Pro subscription."""
        user = User(
            email="proptest@example.com",
            hashed_password="hash",
            subscription_tier="pro",
            subscription_status="active",
        )
        assert user.is_pro is True

    def test_is_pro_free_tier(self, test_session: Session):
        """Test is_pro returns False for free tier."""
        user = User(
            email="freetest@example.com",
            hashed_password="hash",
            subscription_tier="free",
            subscription_status=None,
        )
        assert user.is_pro is False

    def test_is_pro_canceled_subscription(self, test_session: Session):
        """Test is_pro returns False for canceled subscription."""
        user = User(
            email="canceledtest@example.com",
            hashed_password="hash",
            subscription_tier="pro",
            subscription_status="canceled",
        )
        assert user.is_pro is False

    def test_is_pro_past_due_subscription(self, test_session: Session):
        """Test is_pro returns False for past_due subscription."""
        user = User(
            email="pastduetest@example.com",
            hashed_password="hash",
            subscription_tier="pro",
            subscription_status="past_due",
        )
        assert user.is_pro is False
