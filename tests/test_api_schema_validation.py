"""
API Schema Validation Tests.

Tests that API endpoints return properly validated Pydantic schemas,
not raw SQLModel objects. This prevents ValidationError exceptions
at runtime when FastAPI tries to serialize responses.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Mark all tests in this module as integration tests (client uses real database)
pytestmark = pytest.mark.integration


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


class TestCardsEndpointSchemas:
    """Tests for card endpoint schema validation."""

    def test_card_market_returns_valid_schema(self, client):
        """Test that /cards/{id}/market returns MarketSnapshotOut schema."""
        # Get a card ID first
        list_response = client.get("/api/v1/cards/?limit=1")
        if list_response.status_code != 200 or not list_response.json():
            pytest.skip("No cards available")

        card_id = list_response.json()[0]["id"]

        response = client.get(f"/api/v1/cards/{card_id}/market")
        # 404 is valid if no market data exists
        if response.status_code == 404:
            pytest.skip("No market data for this card")

        assert response.status_code == 200

        data = response.json()
        # Verify schema fields exist
        assert "id" in data
        assert "card_id" in data
        assert "timestamp" in data

    def test_card_history_returns_valid_schema(self, client):
        """Test that /cards/{id}/history returns List[MarketPriceOut] schema."""
        # Get a card with sales
        list_response = client.get("/api/v1/cards/?limit=50")
        cards = list_response.json()

        card_with_sales = None
        for card in cards:
            if card.get("volume", 0) > 0:
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
            # Verify MarketPriceOut schema fields
            assert "id" in sale
            assert "card_id" in sale
            assert "price" in sale
            assert "title" in sale
            assert "listing_type" in sale

    def test_card_history_paginated_returns_valid_schema(self, client):
        """Test that /cards/{id}/history?paginated=true returns proper schema."""
        list_response = client.get("/api/v1/cards/?limit=50")
        cards = list_response.json()

        card_with_sales = None
        for card in cards:
            if card.get("volume", 0) > 0:
                card_with_sales = card
                break

        if not card_with_sales:
            pytest.skip("No cards with sales found")

        response = client.get(f"/api/v1/cards/{card_with_sales['id']}/history?limit=10&paginated=true")
        assert response.status_code == 200

        data = response.json()
        # Verify paginated response structure
        assert "items" in data
        assert "total" in data
        assert "offset" in data
        assert "limit" in data
        assert "hasMore" in data

        # Verify items are MarketPriceOut schemas
        if len(data["items"]) > 0:
            item = data["items"][0]
            assert "id" in item
            assert "card_id" in item
            assert "price" in item

    def test_card_active_returns_valid_schema(self, client):
        """Test that /cards/{id}/active returns List[MarketPriceOut] schema."""
        # Get a card
        list_response = client.get("/api/v1/cards/?limit=50")
        cards = list_response.json()

        if not cards:
            pytest.skip("No cards available")

        # Try a few cards to find one with active listings
        for card in cards[:10]:
            response = client.get(f"/api/v1/cards/{card['id']}/active?limit=5")
            assert response.status_code == 200

            active = response.json()
            assert isinstance(active, list)

            if len(active) > 0:
                listing = active[0]
                # Verify MarketPriceOut schema fields
                assert "id" in listing
                assert "card_id" in listing
                assert "price" in listing
                assert "title" in listing
                assert "listing_type" in listing
                return

        # If no active listings found, that's okay
        pytest.skip("No active listings found")

    def test_card_snapshots_returns_valid_schema(self, client):
        """Test that /cards/{id}/snapshots returns List[MarketSnapshotOut] schema."""
        list_response = client.get("/api/v1/cards/?limit=1")
        if list_response.status_code != 200 or not list_response.json():
            pytest.skip("No cards available")

        card_id = list_response.json()[0]["id"]

        response = client.get(f"/api/v1/cards/{card_id}/snapshots?days=30&limit=10")
        assert response.status_code == 200

        snapshots = response.json()
        assert isinstance(snapshots, list)

        if len(snapshots) > 0:
            snapshot = snapshots[0]
            # Verify MarketSnapshotOut schema fields
            assert "id" in snapshot
            assert "card_id" in snapshot
            assert "timestamp" in snapshot


class TestBlokpaxEndpointSchemas:
    """Tests for Blokpax endpoint schema validation."""

    def test_storefronts_list_returns_valid_schema(self, client):
        """Test that /blokpax/storefronts returns List[BlokpaxStorefrontOut] schema."""
        response = client.get("/api/v1/blokpax/storefronts")
        assert response.status_code == 200

        storefronts = response.json()
        assert isinstance(storefronts, list)

        if len(storefronts) > 0:
            sf = storefronts[0]
            # Verify BlokpaxStorefrontOut schema fields
            assert "id" in sf
            assert "slug" in sf
            assert "name" in sf
            assert "updated_at" in sf

    def test_storefront_detail_returns_valid_schema(self, client):
        """Test that /blokpax/storefronts/{slug} returns BlokpaxStorefrontOut schema."""
        # First get a storefront slug
        list_response = client.get("/api/v1/blokpax/storefronts")
        storefronts = list_response.json()

        if not storefronts:
            pytest.skip("No storefronts available")

        slug = storefronts[0]["slug"]

        response = client.get(f"/api/v1/blokpax/storefronts/{slug}")
        assert response.status_code == 200

        sf = response.json()
        assert "id" in sf
        assert "slug" in sf
        assert "name" in sf
        assert "updated_at" in sf

    def test_storefront_snapshots_returns_valid_schema(self, client):
        """Test that /blokpax/storefronts/{slug}/snapshots returns proper schema."""
        list_response = client.get("/api/v1/blokpax/storefronts")
        storefronts = list_response.json()

        if not storefronts:
            pytest.skip("No storefronts available")

        slug = storefronts[0]["slug"]

        response = client.get(f"/api/v1/blokpax/storefronts/{slug}/snapshots?days=7&limit=10")
        assert response.status_code == 200

        snapshots = response.json()
        assert isinstance(snapshots, list)

        if len(snapshots) > 0:
            snapshot = snapshots[0]
            # Verify BlokpaxSnapshotOut schema fields
            assert "id" in snapshot
            assert "storefront_slug" in snapshot
            assert "timestamp" in snapshot

    def test_storefront_sales_returns_valid_schema(self, client):
        """Test that /blokpax/storefronts/{slug}/sales returns proper schema."""
        list_response = client.get("/api/v1/blokpax/storefronts")
        storefronts = list_response.json()

        if not storefronts:
            pytest.skip("No storefronts available")

        slug = storefronts[0]["slug"]

        response = client.get(f"/api/v1/blokpax/storefronts/{slug}/sales?days=30&limit=10")
        assert response.status_code == 200

        sales = response.json()
        assert isinstance(sales, list)

        if len(sales) > 0:
            sale = sales[0]
            # Verify BlokpaxSaleOut schema fields
            assert "id" in sale
            assert "listing_id" in sale
            assert "asset_name" in sale
            assert "filled_at" in sale

    def test_all_sales_returns_valid_schema(self, client):
        """Test that /blokpax/sales returns List[BlokpaxSaleOut] schema."""
        response = client.get("/api/v1/blokpax/sales?days=7&limit=10")
        assert response.status_code == 200

        sales = response.json()
        assert isinstance(sales, list)

        if len(sales) > 0:
            sale = sales[0]
            assert "id" in sale
            assert "listing_id" in sale
            assert "filled_at" in sale

    def test_assets_returns_valid_schema(self, client):
        """Test that /blokpax/assets returns List[BlokpaxAssetOut] schema."""
        response = client.get("/api/v1/blokpax/assets?limit=10")
        assert response.status_code == 200

        assets = response.json()
        assert isinstance(assets, list)

        if len(assets) > 0:
            asset = assets[0]
            # Verify BlokpaxAssetOut schema fields
            assert "id" in asset
            assert "external_id" in asset
            assert "storefront_slug" in asset
            assert "name" in asset

    def test_offers_returns_valid_schema(self, client):
        """Test that /blokpax/offers returns List[BlokpaxOfferOut] schema."""
        response = client.get("/api/v1/blokpax/offers?limit=10")
        assert response.status_code == 200

        offers = response.json()
        assert isinstance(offers, list)

        if len(offers) > 0:
            offer = offers[0]
            # Verify BlokpaxOfferOut schema fields
            assert "id" in offer
            assert "external_id" in offer
            assert "asset_id" in offer
            assert "price_bpx" in offer


class TestUserEndpointSchemas:
    """Tests for user endpoint schema validation (requires auth)."""

    def test_user_me_unauthorized(self, client):
        """Test that /users/me returns 401 without auth."""
        response = client.get("/api/v1/users/me")
        assert response.status_code == 401


class TestSchemaValidationDoesNotRaise:
    """
    Tests that endpoints don't raise Pydantic ValidationError.

    These tests verify that the response can be parsed back into
    the expected schema without errors.
    """

    def test_market_snapshot_schema_validation(self, client):
        """Test MarketSnapshotOut schema validation."""
        from app.schemas import MarketSnapshotOut

        list_response = client.get("/api/v1/cards/?limit=1")
        if not list_response.json():
            pytest.skip("No cards available")

        card_id = list_response.json()[0]["id"]
        response = client.get(f"/api/v1/cards/{card_id}/market")

        if response.status_code == 404:
            pytest.skip("No market data")

        # This should not raise ValidationError
        data = response.json()
        validated = MarketSnapshotOut.model_validate(data)
        assert validated.id == data["id"]

    def test_market_price_schema_validation(self, client):
        """Test MarketPriceOut schema validation."""
        from app.schemas import MarketPriceOut

        list_response = client.get("/api/v1/cards/?limit=50")
        cards = list_response.json()

        for card in cards:
            if card.get("volume", 0) > 0:
                response = client.get(f"/api/v1/cards/{card['id']}/history?limit=1")
                if response.status_code == 200 and response.json():
                    data = response.json()[0]
                    # This should not raise ValidationError
                    validated = MarketPriceOut.model_validate(data)
                    assert validated.id == data["id"]
                    return

        pytest.skip("No sales data available")

    def test_blokpax_storefront_schema_validation(self, client):
        """Test BlokpaxStorefrontOut schema validation."""
        from app.api.blokpax import BlokpaxStorefrontOut

        response = client.get("/api/v1/blokpax/storefronts")
        if not response.json():
            pytest.skip("No storefronts available")

        data = response.json()[0]
        # This should not raise ValidationError
        validated = BlokpaxStorefrontOut.model_validate(data)
        assert validated.id == data["id"]

    def test_blokpax_snapshot_schema_validation(self, client):
        """Test BlokpaxSnapshotOut schema validation."""
        from app.api.blokpax import BlokpaxSnapshotOut

        # Get storefront slug
        sf_response = client.get("/api/v1/blokpax/storefronts")
        if not sf_response.json():
            pytest.skip("No storefronts available")

        slug = sf_response.json()[0]["slug"]
        response = client.get(f"/api/v1/blokpax/storefronts/{slug}/snapshots?limit=1")

        if not response.json():
            pytest.skip("No snapshots available")

        data = response.json()[0]
        # This should not raise ValidationError
        validated = BlokpaxSnapshotOut.model_validate(data)
        assert validated.id == data["id"]
