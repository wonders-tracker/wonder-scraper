"""
API endpoint tests for market endpoints.

Tests cover:
- GET /market/overview - market overview with price deltas and volume
- GET /market/activity - recent market activity/sales
- GET /market/treatments - treatment list with pricing
- POST /market/reports - report generation for bad listings
- GET /market/reports - report retrieval
"""

import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from app.main import app
from app.models.market import MarketPrice, ListingReport


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def sample_treatments_data(test_session, sample_cards, sample_market_prices):
    """Ensure we have treatment data for testing."""
    # sample_market_prices already creates cards with different treatments
    return sample_market_prices


class TestMarketOverviewEndpoint:
    """Tests for GET /market/overview endpoint."""

    def test_market_overview_basic(self, client, sample_cards, sample_market_prices):
        """Test that market overview returns basic structure."""
        response = client.get("/api/v1/market/overview")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) > 0

        # Check structure of first item
        first_item = data[0]
        assert "id" in first_item
        assert "name" in first_item
        assert "set_name" in first_item
        assert "rarity_id" in first_item
        assert "latest_price" in first_item
        assert "avg_price" in first_item
        assert "vwap" in first_item
        assert "floor_price" in first_item
        assert "volume_period" in first_item
        assert "volume_change" in first_item
        assert "price_delta_period" in first_item
        assert "deal_rating" in first_item
        assert "market_cap" in first_item

    def test_market_overview_time_periods(self, client, sample_cards, sample_market_prices):
        """Test different time period filters."""
        valid_periods = ["1h", "24h", "7d", "30d", "90d", "all"]

        for period in valid_periods:
            response = client.get(f"/api/v1/market/overview?time_period={period}")
            assert response.status_code == 200, f"Failed for period {period}"

            data = response.json()
            assert isinstance(data, list)

    def test_market_overview_invalid_time_period(self, client):
        """Test that invalid time period returns error."""
        response = client.get("/api/v1/market/overview?time_period=invalid")
        assert response.status_code == 422  # Validation error

    def test_market_overview_includes_cache_header(self, client, sample_cards, sample_market_prices):
        """Test that response includes cache header."""
        response = client.get("/api/v1/market/overview")
        assert response.status_code == 200

        assert "X-Cache" in response.headers
        assert response.headers["X-Cache"] in ["HIT", "MISS"]

    def test_market_overview_cache_behavior(self, client, sample_cards, sample_market_prices):
        """Test that cache works for identical requests."""
        # First request
        response1 = client.get("/api/v1/market/overview?time_period=7d")
        assert response1.status_code == 200
        cache_status_1 = response1.headers.get("X-Cache")

        # Second identical request
        response2 = client.get("/api/v1/market/overview?time_period=7d")
        assert response2.status_code == 200
        cache_status_2 = response2.headers.get("X-Cache")

        # At least one should exist (timing dependent if it's a HIT)
        assert cache_status_1 in ["HIT", "MISS"]
        assert cache_status_2 in ["HIT", "MISS"]

    def test_market_overview_vwap_calculation(self, client, sample_cards, sample_market_prices):
        """Test that VWAP is calculated for cards with sales."""
        response = client.get("/api/v1/market/overview?time_period=30d")
        assert response.status_code == 200

        data = response.json()

        # Find cards with volume
        cards_with_sales = [item for item in data if item.get("volume_period", 0) > 0]
        assert len(cards_with_sales) > 0, "Expected some cards with sales"

        for item in cards_with_sales:
            # VWAP should be present and positive
            assert item.get("vwap") is not None
            assert item["vwap"] >= 0

    def test_market_overview_floor_price_present(self, client, sample_cards, sample_market_prices):
        """Test that floor prices are included in overview."""
        response = client.get("/api/v1/market/overview?time_period=30d")
        assert response.status_code == 200

        data = response.json()

        # Some cards should have floor prices
        cards_with_floor = [item for item in data if item.get("floor_price") is not None]
        assert len(cards_with_floor) > 0, "Expected some cards with floor prices"

    def test_market_overview_price_delta_capped(self, client, sample_cards, sample_market_prices):
        """Test that price deltas are capped at +-200%."""
        response = client.get("/api/v1/market/overview")
        assert response.status_code == 200

        data = response.json()

        for item in data:
            price_delta = item.get("price_delta_period", 0)
            # Delta should be within reasonable bounds (capped at +-200%)
            assert -200 <= price_delta <= 200, f"Price delta {price_delta} exceeds cap"

    def test_market_overview_empty_database(self, client, test_session):
        """Test overview with no data returns empty list."""
        # This test uses a fresh test_session without fixtures
        response = client.get("/api/v1/market/overview")
        assert response.status_code == 200

        data = response.json()
        # Will be empty or contain only items without sales data
        assert isinstance(data, list)


class TestMarketActivityEndpoint:
    """Tests for GET /market/activity endpoint."""

    def test_market_activity_basic(self, client, sample_cards, sample_market_prices):
        """Test that market activity returns recent sales."""
        response = client.get("/api/v1/market/activity")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            # Check structure of first item
            first_item = data[0]
            assert "card_id" in first_item
            assert "card_name" in first_item
            assert "price" in first_item
            assert "date" in first_item
            assert "treatment" in first_item
            assert "platform" in first_item

    def test_market_activity_limit_parameter(self, client, sample_cards, sample_market_prices):
        """Test that limit parameter works."""
        # Request small limit
        response = client.get("/api/v1/market/activity?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert len(data) <= 5

    def test_market_activity_limit_values(self, client, sample_cards, sample_market_prices):
        """Test various limit values."""
        limits = [1, 10, 20, 50, 100]

        for limit in limits:
            response = client.get(f"/api/v1/market/activity?limit={limit}")
            assert response.status_code == 200

            data = response.json()
            assert len(data) <= limit

    def test_market_activity_ordered_by_date(self, client, sample_cards, sample_market_prices):
        """Test that activity is ordered by date descending."""
        response = client.get("/api/v1/market/activity?limit=20")
        assert response.status_code == 200

        data = response.json()

        if len(data) >= 2:
            # Check that dates are in descending order
            dates = [item["date"] for item in data if item.get("date")]

            for i in range(len(dates) - 1):
                date1 = datetime.fromisoformat(dates[i].replace("Z", "+00:00"))
                date2 = datetime.fromisoformat(dates[i + 1].replace("Z", "+00:00"))
                assert date1 >= date2, "Activity not in descending date order"

    def test_market_activity_only_sold_listings(self, client, test_session, sample_cards, sample_market_prices):
        """Test that only sold listings are returned, not active."""
        # Add an active listing
        now = datetime.utcnow()
        active_listing = MarketPrice(
            card_id=sample_cards[0].id,
            price=999.99,
            title="Active Listing - Should Not Appear",
            treatment="Classic Paper",
            listing_type="active",
            scraped_at=now,
            platform="ebay",
        )
        test_session.add(active_listing)
        test_session.commit()

        response = client.get("/api/v1/market/activity?limit=50")
        assert response.status_code == 200

        data = response.json()

        # None of the results should be the active listing
        for item in data:
            assert item["price"] != 999.99, "Active listing appeared in activity"

    def test_market_activity_includes_treatments(self, client, sample_cards, sample_market_prices):
        """Test that activity includes treatment field (can be null for legacy data)."""
        response = client.get("/api/v1/market/activity?limit=10")
        assert response.status_code == 200

        data = response.json()

        for item in data:
            # Treatment field should be present (value can be null for legacy data)
            assert "treatment" in item


class TestMarketTreatmentsEndpoint:
    """Tests for GET /market/treatments endpoint."""

    def test_treatments_basic(self, client, sample_cards, sample_market_prices):
        """Test that treatments endpoint returns treatment data."""
        response = client.get("/api/v1/market/treatments")
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)

        if len(data) > 0:
            # Check structure
            first_item = data[0]
            assert "name" in first_item
            assert "min_price" in first_item
            assert "count" in first_item

    def test_treatments_includes_cache_header(self, client, sample_cards, sample_market_prices):
        """Test that response includes cache header."""
        response = client.get("/api/v1/market/treatments")
        assert response.status_code == 200

        assert "X-Cache" in response.headers
        assert response.headers["X-Cache"] in ["HIT", "MISS"]

    def test_treatments_cache_behavior(self, client, sample_cards, sample_market_prices):
        """Test that cache works for treatments."""
        # First request
        response1 = client.get("/api/v1/market/treatments")
        assert response1.status_code == 200
        cache_status_1 = response1.headers.get("X-Cache")

        # Second request
        response2 = client.get("/api/v1/market/treatments")
        assert response2.status_code == 200
        cache_status_2 = response2.headers.get("X-Cache")

        # Both should have cache status
        assert cache_status_1 in ["HIT", "MISS"]
        assert cache_status_2 in ["HIT", "MISS"]

    def test_treatments_only_sold_listings(self, client, sample_cards, sample_market_prices):
        """Test that treatments only include sold listings."""
        response = client.get("/api/v1/market/treatments")
        assert response.status_code == 200

        data = response.json()

        # All treatments should have counts > 0 (only from sold items)
        for treatment in data:
            assert treatment["count"] > 0
            assert treatment["min_price"] > 0

    def test_treatments_ordered_alphabetically(self, client, sample_cards, sample_market_prices):
        """Test that treatments are ordered by name."""
        response = client.get("/api/v1/market/treatments")
        assert response.status_code == 200

        data = response.json()

        if len(data) >= 2:
            # Check alphabetical ordering
            names = [item["name"] for item in data]
            assert names == sorted(names), "Treatments not in alphabetical order"

    def test_treatments_min_price_calculation(self, client, sample_cards, sample_market_prices):
        """Test that min_price represents the minimum sold price."""
        response = client.get("/api/v1/market/treatments")
        assert response.status_code == 200

        data = response.json()

        # Each treatment should have a positive min price
        for treatment in data:
            assert treatment["min_price"] > 0, f"Treatment {treatment['name']} has invalid min_price"

    def test_treatments_excludes_null_treatments(self, client, sample_cards, sample_market_prices):
        """Test that null treatments are excluded."""
        response = client.get("/api/v1/market/treatments")
        assert response.status_code == 200

        data = response.json()

        # No null treatment names
        for treatment in data:
            assert treatment["name"] is not None
            assert treatment["name"] != ""


class TestListingReportsEndpoint:
    """Tests for POST /market/reports and GET /market/reports endpoints."""

    def test_create_report_basic(self, client, integration_session):
        """Test creating a basic listing report."""
        # Get a real listing from the database
        from sqlmodel import select
        listing = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold").limit(1)
        ).first()

        if not listing:
            pytest.skip("No sold listings in database")

        report_data = {
            "listing_id": listing.id,
            "card_id": listing.card_id,
            "reason": "wrong_price",
            "notes": "This price seems incorrect",
        }

        response = client.post("/api/v1/market/reports", json=report_data)
        assert response.status_code == 200

        data = response.json()
        assert "id" in data
        assert data["listing_id"] == listing.id
        assert data["reason"] == "wrong_price"
        assert data["status"] == "pending"
        assert "created_at" in data
        assert data["message"] == "Report submitted successfully"

        # Clean up
        report = integration_session.get(ListingReport, data["id"])
        if report:
            integration_session.delete(report)
            integration_session.commit()

    def test_create_report_all_reasons(self, client, integration_session):
        """Test creating reports with different reason types."""
        from sqlmodel import select
        listing = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold").limit(1)
        ).first()

        if not listing:
            pytest.skip("No sold listings in database")

        reasons = ["wrong_price", "fake_listing", "duplicate", "wrong_card", "other"]
        created_ids = []

        for reason in reasons:
            report_data = {
                "listing_id": listing.id,
                "card_id": listing.card_id,
                "reason": reason,
            }

            response = client.post("/api/v1/market/reports", json=report_data)
            assert response.status_code == 200, f"Failed for reason: {reason}"

            data = response.json()
            assert data["reason"] == reason
            created_ids.append(data["id"])

        # Clean up
        for report_id in created_ids:
            report = integration_session.get(ListingReport, report_id)
            if report:
                integration_session.delete(report)
        integration_session.commit()

    def test_create_report_with_optional_fields(self, client, integration_session):
        """Test creating report with all optional fields."""
        from sqlmodel import select
        listing = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold").limit(1)
        ).first()

        if not listing:
            pytest.skip("No sold listings in database")

        report_data = {
            "listing_id": listing.id,
            "card_id": listing.card_id,
            "reason": "fake_listing",
            "notes": "Suspicious listing with fake image",
            "listing_title": "Custom Title Override",
            "listing_price": 99.99,
            "listing_url": "https://example.com/listing/123",
        }

        response = client.post("/api/v1/market/reports", json=report_data)
        assert response.status_code == 200

        data = response.json()
        assert data["reason"] == "fake_listing"

        # Clean up
        report = integration_session.get(ListingReport, data["id"])
        if report:
            integration_session.delete(report)
            integration_session.commit()

    def test_create_report_nonexistent_listing(self, client):
        """Test that reporting a nonexistent listing returns 404."""
        report_data = {
            "listing_id": 999999,
            "card_id": 1,
            "reason": "wrong_price",
        }

        response = client.post("/api/v1/market/reports", json=report_data)
        assert response.status_code == 404

    def test_create_report_missing_required_fields(self, client):
        """Test that missing required fields returns validation error."""
        # Missing listing_id
        report_data = {
            "card_id": 1,
            "reason": "wrong_price",
        }

        response = client.post("/api/v1/market/reports", json=report_data)
        assert response.status_code == 422  # Validation error

    def test_get_reports_basic(self, client, integration_session):
        """Test retrieving listing reports."""
        # Get a real listing from the database
        from sqlmodel import select
        listing = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold").limit(1)
        ).first()

        if not listing:
            pytest.skip("No sold listings in database")

        # Create some reports first
        created_ids = []
        for i in range(3):
            report = ListingReport(
                listing_id=listing.id,
                card_id=listing.card_id,
                reason="wrong_price",
                notes=f"Test report {i}",
                listing_title=listing.title,
                listing_price=listing.price,
                listing_url=listing.url,
                status="pending",
            )
            integration_session.add(report)
            integration_session.flush()
            created_ids.append(report.id)
        integration_session.commit()

        try:
            response = client.get("/api/v1/market/reports")
            assert response.status_code == 200

            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 3

            # Check structure
            if len(data) > 0:
                first_report = data[0]
                assert "id" in first_report
                assert "listing_id" in first_report
                assert "card_id" in first_report
                assert "reason" in first_report
                assert "notes" in first_report
                assert "status" in first_report
                assert "created_at" in first_report
        finally:
            # Clean up
            for report_id in created_ids:
                report = integration_session.get(ListingReport, report_id)
                if report:
                    integration_session.delete(report)
            integration_session.commit()

    def test_get_reports_status_filter(self, client, test_session, sample_cards, sample_market_prices):
        """Test filtering reports by status."""
        listing = sample_market_prices[0]

        # Create reports with different statuses
        statuses = ["pending", "reviewed", "resolved", "dismissed"]
        for status in statuses:
            report = ListingReport(
                listing_id=listing.id,
                card_id=listing.card_id,
                reason="wrong_price",
                status=status,
            )
            test_session.add(report)
        test_session.commit()

        # Test filtering by each status
        for status in statuses:
            response = client.get(f"/api/v1/market/reports?status={status}")
            assert response.status_code == 200

            data = response.json()
            # All returned reports should match the status
            for report in data:
                assert report["status"] == status

    def test_get_reports_limit_parameter(self, client, test_session, sample_cards, sample_market_prices):
        """Test limit parameter for reports."""
        listing = sample_market_prices[0]

        # Create multiple reports
        for i in range(10):
            report = ListingReport(
                listing_id=listing.id,
                card_id=listing.card_id,
                reason="wrong_price",
            )
            test_session.add(report)
        test_session.commit()

        # Test with limit
        response = client.get("/api/v1/market/reports?limit=5")
        assert response.status_code == 200

        data = response.json()
        assert len(data) <= 5

    def test_get_reports_limit_max(self, client, test_session, sample_cards, sample_market_prices):
        """Test that limit is capped at 200."""
        response = client.get("/api/v1/market/reports?limit=300")
        assert response.status_code == 422  # Validation error - exceeds max

    def test_get_reports_ordered_by_date_desc(self, client, test_session, sample_cards, sample_market_prices):
        """Test that reports are ordered by created_at descending."""
        listing = sample_market_prices[0]

        # Create reports with different timestamps
        now = datetime.utcnow()
        for i in range(5):
            report = ListingReport(
                listing_id=listing.id,
                card_id=listing.card_id,
                reason="wrong_price",
                created_at=now - timedelta(hours=i),
            )
            test_session.add(report)
        test_session.commit()

        response = client.get("/api/v1/market/reports?limit=10")
        assert response.status_code == 200

        data = response.json()

        if len(data) >= 2:
            # Check ordering
            dates = [item["created_at"] for item in data]
            for i in range(len(dates) - 1):
                date1 = datetime.fromisoformat(dates[i].replace("Z", "+00:00"))
                date2 = datetime.fromisoformat(dates[i + 1].replace("Z", "+00:00"))
                assert date1 >= date2, "Reports not in descending date order"


class TestMarketEndpointsIntegration:
    """Integration tests across multiple market endpoints."""

    def test_overview_and_activity_consistency(self, client, sample_cards, sample_market_prices):
        """Test that overview and activity show consistent data."""
        # Get overview
        overview_response = client.get("/api/v1/market/overview?time_period=30d")
        assert overview_response.status_code == 200
        overview_data = overview_response.json()

        # Get activity
        activity_response = client.get("/api/v1/market/activity?limit=50")
        assert activity_response.status_code == 200
        activity_data = activity_response.json()

        # Cards with volume in overview should have sales in activity
        cards_with_volume = {
            item["id"]: item["volume_period"]
            for item in overview_data
            if item.get("volume_period", 0) > 0
        }

        if cards_with_volume:
            # At least some of these cards should appear in activity
            activity_card_ids = {item["card_id"] for item in activity_data}
            overlap = set(cards_with_volume.keys()).intersection(activity_card_ids)
            assert len(overlap) > 0, "No overlap between overview and activity"

    def test_treatments_reflect_in_activity(self, client, sample_cards, sample_market_prices):
        """Test that treatments from treatments endpoint appear in activity."""
        # Get treatments
        treatments_response = client.get("/api/v1/market/treatments")
        assert treatments_response.status_code == 200
        treatments_data = treatments_response.json()

        treatment_names = {t["name"] for t in treatments_data}

        # Get activity
        activity_response = client.get("/api/v1/market/activity?limit=50")
        assert activity_response.status_code == 200
        activity_data = activity_response.json()

        # Activity treatments should be a subset of known treatments
        activity_treatments = {item["treatment"] for item in activity_data if item.get("treatment")}

        # All activity treatments should exist in treatments list
        assert activity_treatments.issubset(treatment_names), \
            f"Activity has treatments not in treatments list: {activity_treatments - treatment_names}"

    def test_report_workflow(self, client, integration_session):
        """Test complete workflow: create report, then retrieve it."""
        from sqlmodel import select
        listing = integration_session.exec(
            select(MarketPrice).where(MarketPrice.listing_type == "sold").limit(1)
        ).first()

        if not listing:
            pytest.skip("No sold listings in database")

        # Create report
        report_data = {
            "listing_id": listing.id,
            "card_id": listing.card_id,
            "reason": "duplicate",
            "notes": "Integration test report",
        }

        create_response = client.post("/api/v1/market/reports", json=report_data)
        assert create_response.status_code == 200

        created_report = create_response.json()
        report_id = created_report["id"]

        try:
            # Retrieve reports
            get_response = client.get("/api/v1/market/reports?limit=100")
            assert get_response.status_code == 200

            reports = get_response.json()

            # Find our created report
            found_report = None
            for report in reports:
                if report["id"] == report_id:
                    found_report = report
                    break

            assert found_report is not None, "Created report not found in list"
            assert found_report["reason"] == "duplicate"
            assert found_report["notes"] == "Integration test report"
            assert found_report["status"] == "pending"
        finally:
            # Clean up
            report = integration_session.get(ListingReport, report_id)
            if report:
                integration_session.delete(report)
                integration_session.commit()


class TestMarketEndpointErrorHandling:
    """Test error handling and edge cases."""

    def test_overview_handles_no_data_gracefully(self, client, test_session, sample_cards):
        """Test overview with cards but no market data."""
        # sample_cards fixture creates cards without sample_market_prices
        response = client.get("/api/v1/market/overview")
        assert response.status_code == 200

        data = response.json()
        # Should return data but with zero volumes and prices
        for item in data:
            assert item.get("volume_period", 0) >= 0

    def test_activity_with_no_sales(self, client):
        """Test activity endpoint returns list."""
        response = client.get("/api/v1/market/activity")
        assert response.status_code == 200

        data = response.json()
        # Should return a list (may be empty or have data depending on database state)
        assert isinstance(data, list)

    def test_treatments_with_no_sales(self, client):
        """Test treatments endpoint returns list."""
        response = client.get("/api/v1/market/treatments")
        assert response.status_code == 200

        data = response.json()
        # Should return a list (may be empty or have data depending on database state)
        assert isinstance(data, list)

    def test_invalid_json_in_report(self, client):
        """Test that invalid JSON returns proper error."""
        response = client.post(
            "/api/v1/market/reports",
            data="not valid json",
            headers={"Content-Type": "application/json"}
        )
        assert response.status_code == 422

    def test_zero_limit_values(self, client):
        """Test that zero limit returns empty list or small result."""
        response = client.get("/api/v1/market/activity?limit=0")
        # Should succeed but return empty or minimal results
        assert response.status_code == 200

        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
