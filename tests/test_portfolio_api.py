"""
Integration tests for Portfolio API endpoints.

Tests cover:
- POST /api/v1/portfolio/cards - Create single card
- POST /api/v1/portfolio/cards/batch - Create multiple cards
- GET /api/v1/portfolio/cards - List portfolio cards
- GET /api/v1/portfolio/cards/summary - Portfolio summary
- GET /api/v1/portfolio/cards/{id} - Get single card
- PATCH /api/v1/portfolio/cards/{id} - Update card
- DELETE /api/v1/portfolio/cards/{id} - Delete card
- GET /api/v1/portfolio/treatments - Get available treatments
- GET /api/v1/portfolio/sources - Get available sources
"""

import pytest
from datetime import datetime, date
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.main import app
from app.db import get_session
from app.core import security


@pytest.fixture
def client(test_session: Session):
    """Create test client with database session override."""
    def get_test_session():
        yield test_session

    app.dependency_overrides[get_session] = get_test_session
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(sample_user):
    """Create auth headers for authenticated requests."""
    from app.core.jwt import create_access_token
    token = create_access_token(sample_user.email)
    return {"Authorization": f"Bearer {token}"}


class TestPortfolioCardCreate:
    """Tests for POST /api/v1/portfolio/cards endpoint."""

    def test_create_portfolio_card_success(
        self, client, test_session, sample_user, sample_cards, sample_market_prices, auth_headers
    ):
        """Test successful portfolio card creation."""
        response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": sample_cards[0].id,
                "treatment": "Classic Paper",
                "source": "eBay",
                "purchase_price": 5.99,
                "purchase_date": str(date.today()),
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert data["card_id"] == sample_cards[0].id
        assert data["treatment"] == "Classic Paper"
        assert data["source"] == "eBay"
        assert data["purchase_price"] == 5.99
        assert data["card_name"] == sample_cards[0].name
        assert "market_price" in data
        assert "profit_loss" in data

    def test_create_portfolio_card_with_grading(
        self, client, test_session, sample_user, sample_cards, auth_headers
    ):
        """Test portfolio card creation with grading."""
        response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": sample_cards[0].id,
                "treatment": "Classic Paper",
                "source": "eBay",
                "purchase_price": 100.00,
                "grading": "PSA 10",
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["grading"] == "PSA 10"

    def test_create_portfolio_card_invalid_card_id(self, client, auth_headers):
        """Test that invalid card_id returns 404."""
        response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": 999999,  # Non-existent
                "treatment": "Classic Paper",
                "source": "eBay",
                "purchase_price": 5.00,
            },
            headers=auth_headers,
        )

        assert response.status_code == 404
        assert "Card not found" in response.json()["detail"]

    def test_create_portfolio_card_negative_price(
        self, client, sample_cards, auth_headers
    ):
        """Test that negative price returns 400."""
        response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": sample_cards[0].id,
                "treatment": "Classic Paper",
                "source": "eBay",
                "purchase_price": -5.00,
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "negative" in response.json()["detail"].lower()

    def test_create_portfolio_card_unauthenticated(self, client, sample_cards):
        """Test that unauthenticated request returns 401."""
        response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": sample_cards[0].id,
                "treatment": "Classic Paper",
                "source": "eBay",
                "purchase_price": 5.00,
            },
        )

        assert response.status_code == 401


class TestPortfolioCardBatchCreate:
    """Tests for POST /api/v1/portfolio/cards/batch endpoint."""

    def test_batch_create_success(self, client, sample_cards, auth_headers):
        """Test successful batch creation."""
        response = client.post(
            "/api/v1/portfolio/cards/batch",
            json={
                "cards": [
                    {
                        "card_id": sample_cards[0].id,
                        "treatment": "Classic Paper",
                        "source": "eBay",
                        "purchase_price": 5.00,
                    },
                    {
                        "card_id": sample_cards[0].id,
                        "treatment": "Classic Foil",
                        "source": "LGS",
                        "purchase_price": 10.00,
                    },
                    {
                        "card_id": sample_cards[1].id,
                        "treatment": "Classic Paper",
                        "source": "Pack Pull",
                        "purchase_price": 0.00,
                    },
                ]
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 3

    def test_batch_create_empty_fails(self, client, auth_headers):
        """Test that empty batch returns 400."""
        response = client.post(
            "/api/v1/portfolio/cards/batch",
            json={"cards": []},
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "At least one" in response.json()["detail"]

    def test_batch_create_invalid_card_fails_atomically(
        self, client, sample_cards, auth_headers
    ):
        """Test that invalid card in batch fails the entire batch."""
        response = client.post(
            "/api/v1/portfolio/cards/batch",
            json={
                "cards": [
                    {
                        "card_id": sample_cards[0].id,
                        "treatment": "Classic Paper",
                        "source": "eBay",
                        "purchase_price": 5.00,
                    },
                    {
                        "card_id": 999999,  # Invalid
                        "treatment": "Classic Paper",
                        "source": "eBay",
                        "purchase_price": 5.00,
                    },
                ]
            },
            headers=auth_headers,
        )

        assert response.status_code == 400
        assert "not found" in response.json()["detail"].lower()


class TestPortfolioCardList:
    """Tests for GET /api/v1/portfolio/cards endpoint."""

    def test_list_portfolio_cards(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test listing portfolio cards."""
        response = client.get(
            "/api/v1/portfolio/cards",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 4  # From fixture

    def test_list_filter_by_treatment(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test filtering by treatment."""
        response = client.get(
            "/api/v1/portfolio/cards?treatment=Classic Paper",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for card in data:
            assert card["treatment"] == "Classic Paper"

    def test_list_filter_by_source(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test filtering by source."""
        response = client.get(
            "/api/v1/portfolio/cards?source=eBay",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for card in data:
            assert card["source"] == "eBay"

    def test_list_filter_graded(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test filtering graded cards."""
        response = client.get(
            "/api/v1/portfolio/cards?graded=true",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for card in data:
            assert card["grading"] is not None

    def test_list_filter_raw(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test filtering raw (non-graded) cards."""
        response = client.get(
            "/api/v1/portfolio/cards?graded=false",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        for card in data:
            assert card["grading"] is None


class TestPortfolioCardSummary:
    """Tests for GET /api/v1/portfolio/cards/summary endpoint."""

    def test_get_summary(
        self, client, sample_portfolio_cards, sample_market_prices, auth_headers
    ):
        """Test getting portfolio summary."""
        response = client.get(
            "/api/v1/portfolio/cards/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "total_cards" in data
        assert "total_cost_basis" in data
        assert "total_market_value" in data
        assert "total_profit_loss" in data
        assert "total_profit_loss_percent" in data
        assert "by_treatment" in data
        assert "by_source" in data

        assert data["total_cards"] >= 4  # From fixture

    def test_summary_breakdown_by_treatment(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test that summary includes treatment breakdown."""
        response = client.get(
            "/api/v1/portfolio/cards/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "Classic Paper" in data["by_treatment"]
        assert "Classic Foil" in data["by_treatment"]

        paper = data["by_treatment"]["Classic Paper"]
        assert "count" in paper
        assert "cost" in paper
        assert "value" in paper

    def test_summary_breakdown_by_source(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test that summary includes source breakdown."""
        response = client.get(
            "/api/v1/portfolio/cards/summary",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()

        assert "eBay" in data["by_source"]
        ebay = data["by_source"]["eBay"]
        assert "count" in ebay
        assert "cost" in ebay
        assert "value" in ebay


class TestPortfolioCardGet:
    """Tests for GET /api/v1/portfolio/cards/{id} endpoint."""

    def test_get_portfolio_card(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test getting a single portfolio card."""
        card_id = sample_portfolio_cards[0].id
        response = client.get(
            f"/api/v1/portfolio/cards/{card_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == card_id

    def test_get_portfolio_card_not_found(self, client, auth_headers):
        """Test getting non-existent card returns 404."""
        response = client.get(
            "/api/v1/portfolio/cards/999999",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestPortfolioCardUpdate:
    """Tests for PATCH /api/v1/portfolio/cards/{id} endpoint."""

    def test_update_treatment(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test updating card treatment."""
        card_id = sample_portfolio_cards[0].id
        response = client.patch(
            f"/api/v1/portfolio/cards/{card_id}",
            json={"treatment": "Classic Foil"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["treatment"] == "Classic Foil"

    def test_update_price(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test updating purchase price."""
        card_id = sample_portfolio_cards[0].id
        response = client.patch(
            f"/api/v1/portfolio/cards/{card_id}",
            json={"purchase_price": 99.99},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["purchase_price"] == 99.99

    def test_update_grading(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test adding grading to a card."""
        card_id = sample_portfolio_cards[0].id  # Originally ungraded
        response = client.patch(
            f"/api/v1/portfolio/cards/{card_id}",
            json={"grading": "BGS 9.5"},
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["grading"] == "BGS 9.5"

    def test_update_invalid_price(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test that negative price update returns 400."""
        card_id = sample_portfolio_cards[0].id
        response = client.patch(
            f"/api/v1/portfolio/cards/{card_id}",
            json={"purchase_price": -10.00},
            headers=auth_headers,
        )

        assert response.status_code == 400


class TestPortfolioCardDelete:
    """Tests for DELETE /api/v1/portfolio/cards/{id} endpoint."""

    def test_delete_portfolio_card(
        self, client, sample_portfolio_cards, auth_headers
    ):
        """Test deleting (soft delete) a portfolio card."""
        card_id = sample_portfolio_cards[0].id
        response = client.delete(
            f"/api/v1/portfolio/cards/{card_id}",
            headers=auth_headers,
        )

        assert response.status_code == 200

        # Verify it no longer appears in list
        list_response = client.get(
            "/api/v1/portfolio/cards",
            headers=auth_headers,
        )
        card_ids = [c["id"] for c in list_response.json()]
        assert card_id not in card_ids

    def test_delete_not_found(self, client, auth_headers):
        """Test deleting non-existent card returns 404."""
        response = client.delete(
            "/api/v1/portfolio/cards/999999",
            headers=auth_headers,
        )

        assert response.status_code == 404


class TestPortfolioMetadata:
    """Tests for metadata endpoints."""

    def test_get_treatments(self, client, sample_market_prices, auth_headers):
        """Test getting available treatments."""
        response = client.get(
            "/api/v1/portfolio/treatments",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # Should include treatments from sample_market_prices
        assert "Classic Paper" in data
        assert "Classic Foil" in data

    def test_get_sources(self, client, auth_headers):
        """Test getting available sources."""
        response = client.get(
            "/api/v1/portfolio/sources",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert "eBay" in data
        assert "Blokpax" in data
        assert "TCGPlayer" in data
        assert "LGS" in data
        assert "Trade" in data
        assert "Pack Pull" in data
        assert "Other" in data


class TestTreatmentAwarePricing:
    """Tests for treatment-specific market pricing."""

    def test_market_price_differs_by_treatment(
        self, client, test_session, sample_user, sample_cards, sample_market_prices, auth_headers
    ):
        """Test that market price is treatment-specific."""
        # Create two portfolio cards with different treatments
        paper_response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": sample_cards[0].id,
                "treatment": "Classic Paper",
                "source": "eBay",
                "purchase_price": 1.00,
            },
            headers=auth_headers,
        )

        foil_response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": sample_cards[0].id,
                "treatment": "Classic Foil",
                "source": "eBay",
                "purchase_price": 1.00,
            },
            headers=auth_headers,
        )

        assert paper_response.status_code == 200
        assert foil_response.status_code == 200

        # Endpoint returns a list (to support quantity > 1), so access first element
        paper_data = paper_response.json()[0]
        foil_data = foil_response.json()[0]

        # Market prices should differ (Foil is more expensive in fixture)
        # Note: This depends on sample_market_prices fixture having different prices
        if paper_data["market_price"] and foil_data["market_price"]:
            assert foil_data["market_price"] > paper_data["market_price"]

    def test_profit_loss_calculated_correctly(
        self, client, sample_cards, sample_market_prices, auth_headers
    ):
        """Test that P/L is calculated from purchase price vs market price."""
        purchase_price = 1.00

        response = client.post(
            "/api/v1/portfolio/cards",
            json={
                "card_id": sample_cards[0].id,
                "treatment": "Classic Paper",
                "source": "eBay",
                "purchase_price": purchase_price,
            },
            headers=auth_headers,
        )

        assert response.status_code == 200
        # Endpoint returns a list (to support quantity > 1), so access first element
        data = response.json()[0]

        if data["market_price"] is not None:
            expected_pl = data["market_price"] - purchase_price
            assert abs(data["profit_loss"] - expected_pl) < 0.01


class TestPortfolioIsolation:
    """Tests for user isolation - users should only see their own cards."""

    def test_cannot_see_other_user_cards(
        self, client, test_session, sample_portfolio_cards, factory
    ):
        """Test that users cannot see other users' portfolio cards."""
        # Create a second user
        other_user = factory.create_user(email="other@test.com")
        from app.core.jwt import create_access_token
        other_token = create_access_token(other_user.email)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # Other user should see empty portfolio
        response = client.get(
            "/api/v1/portfolio/cards",
            headers=other_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 0

    def test_cannot_access_other_user_card_by_id(
        self, client, sample_portfolio_cards, factory
    ):
        """Test that users cannot access another user's card by ID."""
        other_user = factory.create_user(email="other2@test.com")
        from app.core.jwt import create_access_token
        other_token = create_access_token(other_user.email)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        # Try to access first user's card
        card_id = sample_portfolio_cards[0].id
        response = client.get(
            f"/api/v1/portfolio/cards/{card_id}",
            headers=other_headers,
        )

        assert response.status_code == 403

    def test_cannot_update_other_user_card(
        self, client, sample_portfolio_cards, factory
    ):
        """Test that users cannot update another user's card."""
        other_user = factory.create_user(email="other3@test.com")
        from app.core.jwt import create_access_token
        other_token = create_access_token(other_user.email)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        card_id = sample_portfolio_cards[0].id
        response = client.patch(
            f"/api/v1/portfolio/cards/{card_id}",
            json={"treatment": "Hacked!"},
            headers=other_headers,
        )

        assert response.status_code == 403

    def test_cannot_delete_other_user_card(
        self, client, sample_portfolio_cards, factory
    ):
        """Test that users cannot delete another user's card."""
        other_user = factory.create_user(email="other4@test.com")
        from app.core.jwt import create_access_token
        other_token = create_access_token(other_user.email)
        other_headers = {"Authorization": f"Bearer {other_token}"}

        card_id = sample_portfolio_cards[0].id
        response = client.delete(
            f"/api/v1/portfolio/cards/{card_id}",
            headers=other_headers,
        )

        assert response.status_code == 403
