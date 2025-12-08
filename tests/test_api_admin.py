"""
Tests for admin API endpoints.

Tests cover:
- POST /admin/backfill - backfill job triggering
- GET /admin/backfill/status - job status checking
- POST /admin/scrape/trigger - manual scrape triggering
- GET /admin/stats - database statistics
- GET /admin/scheduler/status - scheduler status
- Authentication/authorization (superuser-only access)
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock, AsyncMock
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.models.user import User
from app.models.card import Card
from app.models.market import MarketPrice, MarketSnapshot
from app.models.portfolio import PortfolioCard
from app.core import security
from app.api import deps


@pytest.fixture(scope="function")
def client(test_engine):
    """Create test client with test database."""
    from app.db import get_session

    # Override the get_session dependency
    def override_get_session():
        with Session(test_engine) as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    client = TestClient(app)
    yield client

    # Clean up
    app.dependency_overrides.clear()


@pytest.fixture
def superuser(test_session: Session) -> User:
    """Create a superuser for testing admin endpoints."""
    user = User(
        id=10,
        email="admin@example.com",
        hashed_password=security.get_password_hash("adminpassword123"),
        is_active=True,
        is_superuser=True,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def regular_user(test_session: Session) -> User:
    """Create a regular non-superuser for testing authorization."""
    user = User(
        id=11,
        email="regular@example.com",
        hashed_password=security.get_password_hash("userpassword123"),
        is_active=True,
        is_superuser=False,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def superuser_token(superuser: User) -> str:
    """Generate JWT token for superuser."""
    from app.core.jwt import create_access_token
    from datetime import timedelta

    access_token_expires = timedelta(minutes=30)
    return create_access_token(
        subject=superuser.email, expires_delta=access_token_expires
    )


@pytest.fixture
def regular_user_token(regular_user: User) -> str:
    """Generate JWT token for regular user."""
    from app.core.jwt import create_access_token
    from datetime import timedelta

    access_token_expires = timedelta(minutes=30)
    return create_access_token(
        subject=regular_user.email, expires_delta=access_token_expires
    )


@pytest.fixture
def auth_headers(superuser_token: str) -> dict:
    """Create authentication headers with superuser token."""
    return {"Authorization": f"Bearer {superuser_token}"}


@pytest.fixture
def regular_auth_headers(regular_user_token: str) -> dict:
    """Create authentication headers with regular user token."""
    return {"Authorization": f"Bearer {regular_user_token}"}


class TestBackfillEndpoint:
    """Tests for POST /admin/backfill endpoint."""

    @patch('app.api.admin.run_backfill_job')
    def test_trigger_backfill_success(self, mock_backfill, client, auth_headers):
        """Test successful backfill job trigger."""
        response = client.post(
            "/api/v1/admin/backfill",
            json={"limit": 50, "force_all": False, "is_backfill": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert "job_id" in data
        assert data["job_id"].startswith("backfill_")
        assert "started_at" in data
        assert "limit=50" in data["message"]
        assert "force_all=False" in data["message"]

    @patch('app.api.admin.run_backfill_job')
    def test_trigger_backfill_with_force_all(self, mock_backfill, client, auth_headers):
        """Test backfill with force_all=True."""
        response = client.post(
            "/api/v1/admin/backfill",
            json={"limit": 100, "force_all": True, "is_backfill": True},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert "force_all=True" in data["message"]

    @patch('app.api.admin.run_backfill_job')
    def test_trigger_backfill_default_values(self, mock_backfill, client, auth_headers):
        """Test backfill with default values."""
        response = client.post(
            "/api/v1/admin/backfill",
            json={},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "started"
        assert "limit=100" in data["message"]  # Default limit
        assert "force_all=False" in data["message"]  # Default force_all

    @patch('app.api.admin._running_jobs', {"backfill_20231201_120000": {"status": "running", "processed": 5, "total": 10}})
    def test_trigger_backfill_when_job_running(self, client, auth_headers):
        """Test that triggering backfill fails when another job is running."""
        response = client.post(
            "/api/v1/admin/backfill",
            json={"limit": 50, "force_all": False, "is_backfill": True},
            headers=auth_headers,
        )

        assert response.status_code == 409
        data = response.json()
        assert "already running" in data["detail"].lower()
        assert "backfill_20231201_120000" in data["detail"]

    def test_trigger_backfill_unauthorized(self, client):
        """Test backfill endpoint without authentication."""
        response = client.post(
            "/api/v1/admin/backfill",
            json={"limit": 50, "force_all": False, "is_backfill": True},
        )

        assert response.status_code == 401

    def test_trigger_backfill_forbidden_regular_user(self, client, regular_auth_headers):
        """Test backfill endpoint with non-superuser."""
        response = client.post(
            "/api/v1/admin/backfill",
            json={"limit": 50, "force_all": False, "is_backfill": True},
            headers=regular_auth_headers,
        )

        assert response.status_code == 403
        data = response.json()
        assert "not enough permissions" in data["detail"].lower()


class TestBackfillStatusEndpoint:
    """Tests for GET /admin/backfill/status endpoint."""

    @patch('app.api.admin._running_jobs', {
        "backfill_20231201_120000": {
            "status": "running",
            "started": datetime(2023, 12, 1, 12, 0, 0),
            "processed": 25,
            "total": 100,
            "errors": 2,
            "new_listings": 50,
        }
    })
    def test_get_all_jobs_status(self, client, auth_headers):
        """Test getting status of all jobs."""
        response = client.get(
            "/api/v1/admin/backfill/status",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "backfill_20231201_120000" in data
        job = data["backfill_20231201_120000"]
        assert job["status"] == "running"
        assert job["processed"] == 25
        assert job["total"] == 100
        assert job["errors"] == 2

    @patch('app.api.admin._running_jobs', {
        "backfill_20231201_120000": {
            "status": "completed",
            "processed": 100,
            "total": 100,
        }
    })
    def test_get_specific_job_status(self, client, auth_headers):
        """Test getting status of specific job."""
        response = client.get(
            "/api/v1/admin/backfill/status?job_id=backfill_20231201_120000",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "completed"
        assert data["processed"] == 100
        assert data["total"] == 100

    def test_get_nonexistent_job_status(self, client, auth_headers):
        """Test getting status of job that doesn't exist."""
        response = client.get(
            "/api/v1/admin/backfill/status?job_id=nonexistent_job",
            headers=auth_headers,
        )

        assert response.status_code == 404
        data = response.json()
        assert "not found" in data["detail"].lower()

    @patch('app.api.admin._running_jobs', {})
    def test_get_status_when_no_jobs(self, client, auth_headers):
        """Test getting status when no jobs exist."""
        response = client.get(
            "/api/v1/admin/backfill/status",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data == {}

    def test_get_status_unauthorized(self, client):
        """Test status endpoint without authentication."""
        response = client.get("/api/v1/admin/backfill/status")

        assert response.status_code == 401

    def test_get_status_forbidden_regular_user(self, client, regular_auth_headers):
        """Test status endpoint with non-superuser."""
        response = client.get(
            "/api/v1/admin/backfill/status",
            headers=regular_auth_headers,
        )

        assert response.status_code == 403


class TestScrapeTriggertEndpoint:
    """Tests for POST /admin/scrape/trigger endpoint."""

    @patch('app.core.scheduler.job_update_market_data')
    def test_trigger_scrape_success(self, mock_scrape, client, auth_headers):
        """Test successful manual scrape trigger."""
        response = client.post(
            "/api/v1/admin/scrape/trigger",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["status"] == "triggered"
        assert "scrape" in data["message"].lower()

    def test_trigger_scrape_unauthorized(self, client):
        """Test scrape trigger without authentication."""
        response = client.post("/api/v1/admin/scrape/trigger")

        assert response.status_code == 401

    def test_trigger_scrape_forbidden_regular_user(self, client, regular_auth_headers):
        """Test scrape trigger with non-superuser."""
        response = client.post(
            "/api/v1/admin/scrape/trigger",
            headers=regular_auth_headers,
        )

        assert response.status_code == 403


class TestAdminStatsEndpoint:
    """Tests for GET /admin/stats endpoint."""

    def test_get_stats_success(
        self,
        client,
        auth_headers,
        test_session: Session,
        sample_cards,
        sample_market_prices,
    ):
        """Test successful retrieval of admin stats."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        # Check top-level structure
        assert "users" in data
        assert "cards" in data
        assert "listings" in data
        assert "portfolio" in data
        assert "snapshots" in data
        assert "database" in data
        assert "top_cards" in data
        assert "daily_volume" in data
        assert "scraper_jobs" in data
        assert "analytics" in data

    def test_get_stats_users_section(
        self,
        client,
        auth_headers,
        test_session: Session,
        superuser: User,
    ):
        """Test user stats section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        users = data["users"]
        assert "total" in users
        assert "active_24h" in users
        assert "list" in users
        assert isinstance(users["list"], list)

        # Should include our superuser
        assert users["total"] >= 1

        # Check user list structure
        if len(users["list"]) > 0:
            user = users["list"][0]
            assert "id" in user
            assert "email" in user
            assert "is_superuser" in user
            assert "is_active" in user
            assert "created_at" in user

    def test_get_stats_cards_section(
        self,
        client,
        auth_headers,
        test_session: Session,
        sample_cards,
    ):
        """Test cards stats section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        cards = data["cards"]
        assert "total" in cards
        assert cards["total"] >= len(sample_cards)

    def test_get_stats_listings_section(
        self,
        client,
        auth_headers,
        test_session: Session,
        sample_market_prices,
    ):
        """Test listings stats section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        listings = data["listings"]
        assert "total" in listings
        assert "sold" in listings
        assert "active" in listings
        assert "last_24h" in listings
        assert "last_7d" in listings

        # Should have some listings from fixtures
        assert listings["total"] >= len(sample_market_prices)

    def test_get_stats_portfolio_section(
        self,
        client,
        auth_headers,
        test_session: Session,
    ):
        """Test portfolio stats section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        portfolio = data["portfolio"]
        assert "total_cards" in portfolio
        assert isinstance(portfolio["total_cards"], int)

    def test_get_stats_snapshots_section(
        self,
        client,
        auth_headers,
        test_session: Session,
    ):
        """Test snapshots stats section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        snapshots = data["snapshots"]
        assert "total" in snapshots
        assert "latest" in snapshots

    def test_get_stats_database_section(
        self,
        client,
        auth_headers,
        test_session: Session,
    ):
        """Test database stats section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        database = data["database"]
        assert "size" in database

    def test_get_stats_top_cards(
        self,
        client,
        auth_headers,
        test_session: Session,
        sample_cards,
        sample_market_prices,
    ):
        """Test top cards section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        top_cards = data["top_cards"]
        assert isinstance(top_cards, list)

        if len(top_cards) > 0:
            card = top_cards[0]
            assert "name" in card
            assert "listings" in card

    def test_get_stats_daily_volume(
        self,
        client,
        auth_headers,
        test_session: Session,
    ):
        """Test daily volume section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        daily_volume = data["daily_volume"]
        assert isinstance(daily_volume, list)

        if len(daily_volume) > 0:
            day = daily_volume[0]
            assert "date" in day
            assert "count" in day

    def test_get_stats_scraper_jobs(
        self,
        client,
        auth_headers,
        test_session: Session,
    ):
        """Test scraper jobs section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        scraper_jobs = data["scraper_jobs"]
        assert isinstance(scraper_jobs, dict)

    def test_get_stats_analytics_section(
        self,
        client,
        auth_headers,
        test_session: Session,
    ):
        """Test analytics section."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        analytics = data["analytics"]
        assert "total_pageviews" in analytics
        assert "pageviews_24h" in analytics
        assert "pageviews_7d" in analytics
        assert "unique_visitors_24h" in analytics
        assert "unique_visitors_7d" in analytics
        assert "top_pages" in analytics
        assert "device_breakdown" in analytics
        assert "daily_pageviews" in analytics
        assert "top_referrers" in analytics

    def test_get_stats_unauthorized(self, client):
        """Test stats endpoint without authentication."""
        response = client.get("/api/v1/admin/stats")

        assert response.status_code == 401

    def test_get_stats_forbidden_regular_user(self, client, regular_auth_headers):
        """Test stats endpoint with non-superuser."""
        response = client.get(
            "/api/v1/admin/stats",
            headers=regular_auth_headers,
        )

        assert response.status_code == 403


class TestSchedulerStatusEndpoint:
    """Tests for GET /admin/scheduler/status endpoint."""

    @patch('app.core.scheduler.scheduler')
    def test_get_scheduler_status_running(self, mock_scheduler, client, auth_headers):
        """Test scheduler status when running."""
        # Mock scheduler
        mock_scheduler.running = True

        # Mock job
        mock_job = MagicMock()
        mock_job.id = "job_update_market_data"
        mock_job.name = "Update Market Data"
        mock_job.next_run_time = datetime(2023, 12, 1, 14, 0, 0)
        mock_job.trigger = "cron[hour='2,14']"

        mock_scheduler.get_jobs.return_value = [mock_job]

        response = client.get(
            "/api/v1/admin/scheduler/status",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["running"] is True
        assert "jobs" in data
        assert len(data["jobs"]) == 1

        job = data["jobs"][0]
        assert job["id"] == "job_update_market_data"
        assert job["name"] == "Update Market Data"
        assert "next_run" in job
        assert "trigger" in job

    @patch('app.core.scheduler.scheduler')
    def test_get_scheduler_status_not_running(self, mock_scheduler, client, auth_headers):
        """Test scheduler status when not running."""
        mock_scheduler.running = False
        mock_scheduler.get_jobs.return_value = []

        response = client.get(
            "/api/v1/admin/scheduler/status",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["running"] is False
        assert data["jobs"] == []

    @patch('app.core.scheduler.scheduler')
    def test_get_scheduler_status_multiple_jobs(self, mock_scheduler, client, auth_headers):
        """Test scheduler status with multiple jobs."""
        mock_scheduler.running = True

        # Mock multiple jobs
        job1 = MagicMock()
        job1.id = "job_1"
        job1.name = "Job 1"
        job1.next_run_time = datetime(2023, 12, 1, 14, 0, 0)
        job1.trigger = "interval[0:15:00]"

        job2 = MagicMock()
        job2.id = "job_2"
        job2.name = "Job 2"
        job2.next_run_time = None  # Not scheduled
        job2.trigger = "cron[hour='2']"

        mock_scheduler.get_jobs.return_value = [job1, job2]

        response = client.get(
            "/api/v1/admin/scheduler/status",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert len(data["jobs"]) == 2
        assert data["jobs"][0]["id"] == "job_1"
        assert data["jobs"][1]["id"] == "job_2"
        assert data["jobs"][1]["next_run"] is None

    def test_get_scheduler_status_unauthorized(self, client):
        """Test scheduler status without authentication."""
        response = client.get("/api/v1/admin/scheduler/status")

        assert response.status_code == 401

    def test_get_scheduler_status_forbidden_regular_user(self, client, regular_auth_headers):
        """Test scheduler status with non-superuser."""
        response = client.get(
            "/api/v1/admin/scheduler/status",
            headers=regular_auth_headers,
        )

        assert response.status_code == 403


class TestBackfillJobExecution:
    """Tests for backfill job background execution."""

    @pytest.mark.asyncio
    @patch('app.scraper.browser.BrowserManager')
    @patch('scripts.scrape_card.scrape_card')
    @patch('app.discord_bot.logger.log_scrape_start')
    @patch('app.discord_bot.logger.log_scrape_complete')
    async def test_backfill_job_processes_cards(
        self,
        mock_log_complete,
        mock_log_start,
        mock_scrape,
        mock_browser,
        test_session: Session,
        sample_cards,
    ):
        """Test that backfill job processes cards correctly."""
        from app.api.admin import run_backfill_job, _running_jobs

        # Mock browser manager methods
        mock_browser.get_browser = AsyncMock()
        mock_browser.close = AsyncMock()
        mock_scrape.return_value = AsyncMock()

        job_id = "test_job_123"

        # Run the backfill job
        await run_backfill_job(
            job_id=job_id,
            limit=2,
            force_all=True,
            is_backfill=True,
        )

        # Verify job was tracked
        assert job_id in _running_jobs
        job_status = _running_jobs[job_id]

        assert job_status["status"] in ["completed", "failed"]
        assert job_status["processed"] >= 0

    @pytest.mark.asyncio
    @patch('app.scraper.browser.BrowserManager')
    async def test_backfill_job_respects_limit(
        self,
        mock_browser,
        test_session: Session,
        sample_cards,
    ):
        """Test that backfill job respects the limit parameter."""
        from app.api.admin import run_backfill_job, _running_jobs

        # Mock browser manager methods
        mock_browser.get_browser = AsyncMock()
        mock_browser.close = AsyncMock()

        job_id = "test_job_limit"
        limit = 2

        with patch('scripts.scrape_card.scrape_card', new_callable=AsyncMock) as mock_scrape:
            with patch('app.discord_bot.logger.log_scrape_start'):
                with patch('app.discord_bot.logger.log_scrape_complete'):
                    await run_backfill_job(
                        job_id=job_id,
                        limit=limit,
                        force_all=True,
                        is_backfill=True,
                    )

                    # Should not scrape more than limit
                    job_status = _running_jobs[job_id]
                    assert job_status["processed"] <= limit

    @pytest.mark.asyncio
    @patch('app.scraper.browser.BrowserManager')
    @patch('scripts.scrape_card.scrape_card', side_effect=Exception("Scrape error"))
    @patch('app.discord_bot.logger.log_scrape_start')
    @patch('app.discord_bot.logger.log_scrape_complete')
    async def test_backfill_job_handles_errors(
        self,
        mock_log_complete,
        mock_log_start,
        mock_scrape,
        mock_browser,
        test_session: Session,
        sample_cards,
    ):
        """Test that backfill job handles scraping errors gracefully."""
        from app.api.admin import run_backfill_job, _running_jobs

        # Mock browser manager methods
        mock_browser.get_browser = AsyncMock()
        mock_browser.close = AsyncMock()

        job_id = "test_job_errors"

        await run_backfill_job(
            job_id=job_id,
            limit=2,
            force_all=True,
            is_backfill=True,
        )

        # Job should still complete despite errors
        job_status = _running_jobs[job_id]
        assert job_status["status"] in ["completed", "failed"]

        # Should track errors
        if "errors" in job_status:
            assert job_status["errors"] >= 0

    @pytest.mark.asyncio
    @patch('app.scraper.browser.BrowserManager')
    @patch('scripts.scrape_card.scrape_card')
    @patch('app.discord_bot.logger.log_scrape_start')
    @patch('app.discord_bot.logger.log_scrape_complete')
    async def test_backfill_job_no_cards_needed(
        self,
        mock_log_complete,
        mock_log_start,
        mock_scrape,
        mock_browser,
        test_session: Session,
    ):
        """Test backfill job when no cards need updating."""
        from app.api.admin import run_backfill_job, _running_jobs

        # Mock browser manager methods
        mock_browser.get_browser = AsyncMock()
        mock_browser.close = AsyncMock()

        # Clear all cards
        job_id = "test_job_no_cards"

        await run_backfill_job(
            job_id=job_id,
            limit=100,
            force_all=False,
            is_backfill=True,
        )

        # Job should complete with message
        job_status = _running_jobs[job_id]
        assert job_status["status"] == "completed"


class TestAuthorizationConsistency:
    """Tests to ensure all admin endpoints require superuser access."""

    def test_all_endpoints_require_auth(self, client):
        """Test that all admin endpoints reject unauthenticated requests."""
        endpoints = [
            ("POST", "/api/v1/admin/backfill", {"limit": 10}),
            ("GET", "/api/v1/admin/backfill/status", None),
            ("POST", "/api/v1/admin/scrape/trigger", None),
            ("GET", "/api/v1/admin/stats", None),
            ("GET", "/api/v1/admin/scheduler/status", None),
        ]

        for method, endpoint, json_data in endpoints:
            if method == "POST":
                if json_data:
                    response = client.post(endpoint, json=json_data)
                else:
                    response = client.post(endpoint)
            else:
                response = client.get(endpoint)

            assert response.status_code == 401, f"Endpoint {method} {endpoint} should require auth"

    def test_all_endpoints_require_superuser(self, client, regular_auth_headers):
        """Test that all admin endpoints reject non-superuser requests."""
        endpoints = [
            ("POST", "/api/v1/admin/backfill", {"limit": 10}),
            ("GET", "/api/v1/admin/backfill/status", None),
            ("POST", "/api/v1/admin/scrape/trigger", None),
            ("GET", "/api/v1/admin/stats", None),
            ("GET", "/api/v1/admin/scheduler/status", None),
        ]

        for method, endpoint, json_data in endpoints:
            if method == "POST":
                if json_data:
                    response = client.post(endpoint, json=json_data, headers=regular_auth_headers)
                else:
                    response = client.post(endpoint, headers=regular_auth_headers)
            else:
                response = client.get(endpoint, headers=regular_auth_headers)

            assert response.status_code == 403, f"Endpoint {method} {endpoint} should require superuser"
            assert "not enough permissions" in response.json()["detail"].lower()
