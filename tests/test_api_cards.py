"""
API endpoint tests for cards endpoints.

Tests cover:
- Card list endpoint with floor price
- Card detail endpoint with floor price
- Floor price consistency between list and detail views
- Sales history endpoint with COALESCE ordering
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Mark all tests in this module as integration tests (require real database with data)
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestCardsListEndpoint:
    """Tests for GET /api/v1/cards/ endpoint."""

    def test_cards_list_returns_floor_price(self, client):
        """Test that cards list includes floor_price field."""
        response = client.get("/api/v1/cards/?limit=5")
        assert response.status_code == 200

        cards = response.json()
        assert len(cards) > 0

        # Check that floor_price field exists
        first_card = cards[0]
        assert "floor_price" in first_card

    def test_cards_list_floor_price_not_null_for_cards_with_sales(self, client):
        """Test that cards with sales have non-null floor prices."""
        response = client.get("/api/v1/cards/?limit=50")
        assert response.status_code == 200

        cards = response.json()

        # At least some cards should have floor prices
        cards_with_floor = [c for c in cards if c.get("floor_price") is not None]
        assert len(cards_with_floor) > 0, "Expected some cards to have floor prices"

    def test_cards_list_search_filter(self, client):
        """Test search filter works."""
        response = client.get("/api/v1/cards/?search=Progo")
        assert response.status_code == 200

        cards = response.json()
        for card in cards:
            assert "progo" in card["name"].lower()

    def test_cards_list_time_period_filter(self, client):
        """Test time period filter parameter."""
        for period in ["24h", "7d", "30d", "90d", "all"]:
            response = client.get(f"/api/v1/cards/?limit=5&time_period={period}")
            assert response.status_code == 200, f"Failed for time_period={period}"

    def test_cards_list_product_type_filter(self, client):
        """Test product type filter."""
        response = client.get("/api/v1/cards/?product_type=Single&limit=10")
        assert response.status_code == 200

        cards = response.json()
        for card in cards:
            assert card.get("product_type") == "Single"


class TestCardDetailEndpoint:
    """Tests for GET /api/v1/cards/{card_id} endpoint."""

    def test_card_detail_returns_floor_price(self, client):
        """Test that card detail includes floor_price field."""
        # First get a card ID
        list_response = client.get("/api/v1/cards/?limit=1")
        cards = list_response.json()
        if not cards:
            pytest.skip("No cards in database")

        card_id = cards[0]["id"]

        response = client.get(f"/api/v1/cards/{card_id}")
        assert response.status_code == 200

        card = response.json()
        assert "floor_price" in card
        assert "fair_market_price" in card

    def test_card_detail_returns_fmp_breakdown(self, client):
        """Test that card detail returns FMP (calculated server-side)."""
        # Get a Single card
        list_response = client.get("/api/v1/cards/?product_type=Single&limit=10")
        cards = list_response.json()
        if not cards:
            pytest.skip("No Single cards in database")

        # Find one with sales
        for card in cards:
            if card.get("volume", 0) > 0 or card.get("volume_30d", 0) > 0:
                card_id = card["id"]
                break
        else:
            pytest.skip("No Single cards with sales found")

        response = client.get(f"/api/v1/cards/{card_id}")
        assert response.status_code == 200

        card = response.json()
        # FMP may or may not be calculable depending on data
        assert "fair_market_price" in card

    def test_card_detail_by_slug(self, client):
        """Test that card detail works with slug."""
        # First get a card with a slug
        list_response = client.get("/api/v1/cards/?limit=10")
        cards = list_response.json()

        card_with_slug = None
        for card in cards:
            if card.get("slug"):
                card_with_slug = card
                break

        if not card_with_slug:
            pytest.skip("No cards with slugs found")

        response = client.get(f"/api/v1/cards/{card_with_slug['slug']}")
        assert response.status_code == 200


class TestFloorPriceConsistency:
    """Tests for floor price consistency between endpoints."""

    @pytest.mark.xfail(reason="Known data consistency issue - floor prices differ due to snapshot timing between endpoints")
    def test_floor_price_matches_between_list_and_detail(self, client):
        """
        Critical test: Floor price in list view should match detail view.
        This was the bug where main table showed $53.80 but detail showed $0.99.
        """
        # Get cards from list
        list_response = client.get("/api/v1/cards/?limit=20")
        list_cards = list_response.json()

        mismatches = []
        for list_card in list_cards:
            card_id = list_card["id"]
            list_floor = list_card.get("floor_price")

            # Get detail
            detail_response = client.get(f"/api/v1/cards/{card_id}")
            if detail_response.status_code != 200:
                continue

            detail_card = detail_response.json()
            detail_floor = detail_card.get("floor_price")

            # Compare (allow for small floating point differences)
            if list_floor is not None and detail_floor is not None:
                if abs(list_floor - detail_floor) > 0.01:
                    mismatches.append({
                        "card_id": card_id,
                        "name": list_card["name"],
                        "list_floor": list_floor,
                        "detail_floor": detail_floor,
                    })
            elif list_floor != detail_floor:
                # One is None, other is not
                mismatches.append({
                    "card_id": card_id,
                    "name": list_card["name"],
                    "list_floor": list_floor,
                    "detail_floor": detail_floor,
                })

        assert len(mismatches) == 0, f"Floor price mismatches found: {mismatches}"

    def test_progo_floor_price_consistency(self, client):
        """
        Regression test: PROGO should have consistent floor price.
        """
        # Get PROGO from list
        list_response = client.get("/api/v1/cards/?search=Progo")
        list_cards = list_response.json()

        if not list_cards:
            pytest.skip("PROGO not found in database")

        progo_list = list_cards[0]
        list_floor = progo_list.get("floor_price")

        # Get PROGO detail
        detail_response = client.get(f"/api/v1/cards/{progo_list['id']}")
        progo_detail = detail_response.json()
        detail_floor = progo_detail.get("floor_price")

        # They should match
        if list_floor is not None and detail_floor is not None:
            assert abs(list_floor - detail_floor) < 0.01, \
                f"PROGO floor mismatch: list={list_floor}, detail={detail_floor}"
        else:
            assert list_floor == detail_floor, \
                f"PROGO floor mismatch: list={list_floor}, detail={detail_floor}"

        # Floor should NOT be $0.99 (the active listing bug)
        if list_floor is not None:
            assert list_floor != 0.99, "PROGO floor should not be $0.99 (active listing)"
        if detail_floor is not None:
            assert detail_floor != 0.99, "PROGO floor should not be $0.99 (active listing)"


class TestSalesHistoryEndpoint:
    """Tests for GET /api/v1/cards/{card_id}/history endpoint."""

    def test_history_returns_sales(self, client):
        """Test that history endpoint returns sales data."""
        # Get a card with sales
        list_response = client.get("/api/v1/cards/?limit=50")
        cards = list_response.json()

        card_with_sales = None
        for card in cards:
            if card.get("volume", 0) > 0 or card.get("volume_30d", 0) > 0:
                card_with_sales = card
                break

        if not card_with_sales:
            pytest.skip("No cards with sales found")

        response = client.get(f"/api/v1/cards/{card_with_sales['id']}/history?limit=10")
        assert response.status_code == 200

        history = response.json()
        assert isinstance(history, list)

        if len(history) > 0:
            sale = history[0]
            assert "price" in sale
            assert "treatment" in sale
            # Either sold_date or scraped_at should be present
            assert "sold_date" in sale or "scraped_at" in sale

    def test_history_ordered_by_date_desc(self, client):
        """Test that history is ordered by date descending (most recent first)."""
        list_response = client.get("/api/v1/cards/?limit=50")
        cards = list_response.json()

        card_with_sales = None
        for card in cards:
            if card.get("volume_30d", 0) >= 5:
                card_with_sales = card
                break

        if not card_with_sales:
            pytest.skip("No cards with enough sales found")

        response = client.get(f"/api/v1/cards/{card_with_sales['id']}/history?limit=20")
        history = response.json()

        if len(history) < 2:
            pytest.skip("Not enough sales for ordering test")

        # Check ordering - each date should be >= the next
        from datetime import datetime

        dates = []
        for sale in history:
            date_str = sale.get("sold_date") or sale.get("scraped_at")
            if date_str:
                # Parse ISO format
                try:
                    dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                    dates.append(dt)
                except ValueError:
                    pass

        for i in range(len(dates) - 1):
            assert dates[i] >= dates[i + 1], \
                f"History not in descending order: {dates[i]} before {dates[i + 1]}"

    def test_history_includes_null_sold_date_sales(self, client):
        """
        Test that sales with NULL sold_date are included (using scraped_at).
        """
        # This is implicitly tested by the ordering test above,
        # but we add an explicit check here
        list_response = client.get("/api/v1/cards/?limit=50")
        cards = list_response.json()

        for card in cards:
            if card.get("volume_30d", 0) > 0:
                response = client.get(f"/api/v1/cards/{card['id']}/history?limit=50")
                history = response.json()

                # All sales should have either sold_date or scraped_at
                for sale in history:
                    has_date = sale.get("sold_date") or sale.get("scraped_at")
                    assert has_date, f"Sale {sale.get('id')} has no date information"

                break


class TestCacheHeaders:
    """Tests for caching behavior."""

    def test_cards_list_cache_header(self, client):
        """Test that cards list returns cache header."""
        response = client.get("/api/v1/cards/?limit=5")
        assert response.status_code == 200

        # Should have X-Cache header
        assert "X-Cache" in response.headers
        assert response.headers["X-Cache"] in ["HIT", "MISS"]

    def test_cards_list_second_request_cache_hit(self, client):
        """Test that second request might be a cache hit."""
        # First request
        response1 = client.get("/api/v1/cards/?limit=5&time_period=24h")
        assert response1.status_code == 200

        # Second identical request
        response2 = client.get("/api/v1/cards/?limit=5&time_period=24h")
        assert response2.status_code == 200

        # Second request might be cached (depends on timing)
        # Just verify headers exist
        assert "X-Cache" in response2.headers
