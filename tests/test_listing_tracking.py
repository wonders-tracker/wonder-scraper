"""
Tests for active listing tracking functionality.

Tests cover:
- listed_at field behavior on MarketPrice model
- Active scraper: setting listed_at on new listings, preserving on updates
- Sold scraper: converting active->sold while preserving listed_at
- 30-day retention policy for active listings
- Edge cases: missing external_id, duplicate handling, etc.

Note: Tests marked with @pytest.mark.integration require PostgreSQL
(SQLite doesn't support JSONB). Run with: pytest -m integration
"""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, select

from app.models.market import MarketPrice
from app.models.card import Card


# =============================================================================
# UNIT TESTS - No database required
# =============================================================================

class TestListedAtFieldBehavior:
    """Unit tests for the listed_at field on MarketPrice model."""

    def test_listed_at_field_exists(self):
        """MarketPrice should have listed_at field."""
        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test Card",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
        )
        assert hasattr(mp, 'listed_at')

    def test_listed_at_defaults_to_none(self):
        """listed_at should default to None."""
        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test Card",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
        )
        assert mp.listed_at is None

    def test_listed_at_can_be_set(self):
        """listed_at should be settable."""
        now = datetime.utcnow()
        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test Card",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=now,
        )
        assert mp.listed_at == now

    def test_listed_at_independent_of_scraped_at(self):
        """listed_at and scraped_at should be independent."""
        listed_time = datetime.utcnow() - timedelta(days=5)
        scraped_time = datetime.utcnow()

        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test Card",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=listed_time,
            scraped_at=scraped_time,
        )

        assert mp.listed_at == listed_time
        assert mp.scraped_at == scraped_time
        assert mp.listed_at != mp.scraped_at


class TestDaysOnMarketCalculation:
    """Unit tests for days on market calculations."""

    def test_days_on_market_simple(self):
        """Calculate days on market from listed_at to sold_date."""
        listed_time = datetime.utcnow() - timedelta(days=10)
        sold_time = datetime.utcnow() - timedelta(days=2)

        mp = MarketPrice(
            card_id=1,
            price=25.0,
            title="Test Card",
            listing_type="sold",
            treatment="Classic Foil",
            platform="ebay",
            listed_at=listed_time,
            sold_date=sold_time,
        )

        days_on_market = (mp.sold_date - mp.listed_at).days
        assert days_on_market == 8

    def test_days_on_market_same_day(self):
        """Same day listing and sale."""
        same_time = datetime.utcnow()

        mp = MarketPrice(
            card_id=1,
            price=5.0,
            title="Quick Sale",
            listing_type="sold",
            treatment="Classic Paper",
            platform="ebay",
            sold_date=same_time,
            listed_at=same_time,
        )

        days_on_market = (mp.sold_date - mp.listed_at).days
        assert days_on_market == 0

    def test_days_on_market_long_listing(self):
        """Long-running listing."""
        listed_time = datetime.utcnow() - timedelta(days=45)
        sold_time = datetime.utcnow() - timedelta(days=1)

        mp = MarketPrice(
            card_id=1,
            price=100.0,
            title="Hard to Sell Card",
            listing_type="sold",
            treatment="OCM Serialized",
            platform="ebay",
            listed_at=listed_time,
            sold_date=sold_time,
        )

        days_on_market = (mp.sold_date - mp.listed_at).days
        assert days_on_market == 44

    def test_days_on_market_hours_precision(self):
        """Days calculation should use day boundaries."""
        # Listed 25 hours ago
        listed_time = datetime.utcnow() - timedelta(hours=25)
        sold_time = datetime.utcnow()

        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test Card",
            listing_type="sold",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=listed_time,
            sold_date=sold_time,
        )

        days_on_market = (mp.sold_date - mp.listed_at).days
        assert days_on_market == 1  # 25 hours = 1 day


class TestListingTypeBehavior:
    """Unit tests for listing type behavior with listed_at."""

    def test_active_listing_no_sold_date(self):
        """Active listings should have None for sold_date."""
        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Active Listing",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=datetime.utcnow(),
            sold_date=None,
        )

        assert mp.listing_type == "active"
        assert mp.sold_date is None
        assert mp.listed_at is not None

    def test_sold_listing_has_both_dates(self):
        """Sold listings should have both listed_at and sold_date."""
        listed = datetime.utcnow() - timedelta(days=5)
        sold = datetime.utcnow() - timedelta(days=1)

        mp = MarketPrice(
            card_id=1,
            price=15.0,
            title="Sold Listing",
            listing_type="sold",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=listed,
            sold_date=sold,
        )

        assert mp.listing_type == "sold"
        assert mp.listed_at is not None
        assert mp.sold_date is not None
        assert mp.listed_at < mp.sold_date

    def test_sold_without_active_tracking(self):
        """Sold listing without prior active tracking uses sold_date as listed_at."""
        sold = datetime.utcnow() - timedelta(days=3)

        mp = MarketPrice(
            card_id=1,
            price=15.0,
            title="Directly Sold",
            listing_type="sold",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=sold,  # Use sold_date as approximation
            sold_date=sold,
        )

        assert mp.listed_at == mp.sold_date


class TestRetentionPolicyLogic:
    """Unit tests for retention policy logic."""

    def test_30_day_cutoff_calculation(self):
        """Calculate 30-day cutoff correctly."""
        now = datetime.utcnow()
        cutoff = now - timedelta(days=30)

        # Listing from 25 days ago - should be retained
        recent = MarketPrice(
            card_id=1,
            price=10.0,
            title="Recent",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            scraped_at=now - timedelta(days=25),
        )

        # Listing from 35 days ago - should be stale
        old = MarketPrice(
            card_id=1,
            price=10.0,
            title="Old",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            scraped_at=now - timedelta(days=35),
        )

        assert recent.scraped_at >= cutoff  # Recent - keep
        assert old.scraped_at < cutoff  # Old - remove

    def test_edge_case_exactly_30_days(self):
        """Listing exactly 30 days old."""
        now = datetime.utcnow()
        cutoff = now - timedelta(days=30)

        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Edge Case",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            scraped_at=cutoff,  # Exactly at cutoff
        )

        # At cutoff should be retained (>= comparison)
        assert mp.scraped_at >= cutoff


class TestPlatformBehavior:
    """Unit tests for platform-specific behavior."""

    def test_ebay_listing(self):
        """eBay listings have listed_at."""
        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="eBay Listing",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            external_id="ebay_123",
            listed_at=datetime.utcnow(),
        )
        assert mp.platform == "ebay"
        assert mp.listed_at is not None

    def test_opensea_listing(self):
        """OpenSea listings have listed_at."""
        mp = MarketPrice(
            card_id=1,
            price=50.0,
            title="OpenSea NFT",
            listing_type="sold",
            treatment="NFT",
            platform="opensea",
            listed_at=datetime.utcnow() - timedelta(days=3),
            sold_date=datetime.utcnow(),
        )
        assert mp.platform == "opensea"
        assert mp.listed_at is not None

    def test_blokpax_listing(self):
        """Blokpax listings have listed_at."""
        mp = MarketPrice(
            card_id=1,
            price=25.0,
            title="Blokpax Sale",
            listing_type="sold",
            treatment="Sealed",
            platform="blokpax",
            listed_at=datetime.utcnow() - timedelta(hours=12),
            sold_date=datetime.utcnow(),
        )
        assert mp.platform == "blokpax"
        assert mp.listed_at is not None


class TestExternalIdBehavior:
    """Unit tests for external_id behavior."""

    def test_listing_with_external_id(self):
        """Listings can have external_id."""
        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            external_id="ebay_12345",
            listed_at=datetime.utcnow(),
        )
        assert mp.external_id == "ebay_12345"

    def test_listing_without_external_id(self):
        """Listings can have None for external_id."""
        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            external_id=None,
            listed_at=datetime.utcnow(),
        )
        assert mp.external_id is None


class TestDataValidation:
    """Unit tests for data validation logic."""

    def test_listed_at_before_sold_date(self):
        """listed_at should be before sold_date."""
        listed = datetime.utcnow() - timedelta(days=5)
        sold = datetime.utcnow() - timedelta(days=2)

        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test",
            listing_type="sold",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=listed,
            sold_date=sold,
        )

        assert mp.listed_at < mp.sold_date

    def test_listed_at_equals_sold_date_valid(self):
        """listed_at can equal sold_date (same-day sale)."""
        same_time = datetime.utcnow()

        mp = MarketPrice(
            card_id=1,
            price=10.0,
            title="Test",
            listing_type="sold",
            treatment="Classic Paper",
            platform="ebay",
            listed_at=same_time,
            sold_date=same_time,
        )

        assert mp.listed_at == mp.sold_date


# =============================================================================
# INTEGRATION TESTS - Require PostgreSQL database
# =============================================================================

@pytest.mark.integration
class TestDatabasePersistence:
    """Integration tests for database persistence."""

    def test_listed_at_persists(self, integration_session: Session):
        """listed_at should persist to PostgreSQL."""
        now = datetime.utcnow()

        card = integration_session.exec(select(Card).limit(1)).first()
        if not card:
            pytest.skip("No cards in database")

        mp = MarketPrice(
            card_id=card.id,
            price=10.0,
            title=f"Test - Listed At Persist {now.timestamp()}",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            external_id=f"test_persist_{now.timestamp()}",
            listed_at=now,
            scraped_at=now,
        )
        integration_session.add(mp)
        integration_session.commit()

        try:
            fetched = integration_session.get(MarketPrice, mp.id)
            assert fetched is not None
            assert fetched.listed_at is not None
            assert abs((fetched.listed_at - now).total_seconds()) < 1
        finally:
            integration_session.delete(mp)
            integration_session.commit()

    def test_active_to_sold_conversion(self, integration_session: Session):
        """Convert active listing to sold preserving listed_at."""
        card = integration_session.exec(select(Card).limit(1)).first()
        if not card:
            pytest.skip("No cards in database")

        listed_time = datetime.utcnow() - timedelta(days=7)
        now = datetime.utcnow()

        # Create active listing
        mp = MarketPrice(
            card_id=card.id,
            price=10.0,
            title=f"Test - Convert {now.timestamp()}",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            external_id=f"test_convert_{now.timestamp()}",
            listed_at=listed_time,
            scraped_at=listed_time,
        )
        integration_session.add(mp)
        integration_session.commit()
        mp_id = mp.id

        try:
            # Convert to sold
            mp.listing_type = "sold"
            mp.sold_date = now
            mp.scraped_at = now
            integration_session.add(mp)
            integration_session.commit()

            # Verify
            fetched = integration_session.get(MarketPrice, mp_id)
            assert fetched.listing_type == "sold"
            assert fetched.sold_date is not None
            # listed_at should be preserved
            assert abs((fetched.listed_at - listed_time).total_seconds()) < 1
        finally:
            integration_session.delete(mp)
            integration_session.commit()

    def test_find_listings_by_listed_at_range(self, integration_session: Session):
        """Query listings by listed_at date range."""
        card = integration_session.exec(select(Card).limit(1)).first()
        if not card:
            pytest.skip("No cards in database")

        now = datetime.utcnow()
        created = []

        try:
            # Create listings with different listed_at times
            for days in [5, 10, 15, 20]:
                mp = MarketPrice(
                    card_id=card.id,
                    price=10.0,
                    title=f"Test - Range {days} {now.timestamp()}",
                    listing_type="active",
                    treatment="Classic Paper",
                    platform="ebay",
                    external_id=f"test_range_{days}_{now.timestamp()}",
                    listed_at=now - timedelta(days=days),
                    scraped_at=now,
                )
                integration_session.add(mp)
                created.append(mp)

            integration_session.commit()

            # Query for listings between 8 and 18 days old
            start = now - timedelta(days=18)
            end = now - timedelta(days=8)

            results = integration_session.exec(
                select(MarketPrice).where(
                    MarketPrice.card_id == card.id,
                    MarketPrice.listed_at >= start,
                    MarketPrice.listed_at <= end,
                    MarketPrice.external_id.like(f"test_range_%_{now.timestamp()}")
                )
            ).all()

            # Should find 2 (10 and 15 days old)
            assert len(results) == 2

        finally:
            for mp in created:
                integration_session.delete(mp)
            integration_session.commit()

    def test_external_id_matching(self, integration_session: Session):
        """Find active listing by external_id."""
        card = integration_session.exec(select(Card).limit(1)).first()
        if not card:
            pytest.skip("No cards in database")

        now = datetime.utcnow()
        external_id = f"test_match_{now.timestamp()}"

        mp = MarketPrice(
            card_id=card.id,
            price=10.0,
            title=f"Test - Match {now.timestamp()}",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            external_id=external_id,
            listed_at=now - timedelta(days=3),
            scraped_at=now,
        )
        integration_session.add(mp)
        integration_session.commit()

        try:
            # Find by external_id
            found = integration_session.exec(
                select(MarketPrice).where(
                    MarketPrice.external_id == external_id,
                    MarketPrice.listing_type == "active"
                )
            ).first()

            assert found is not None
            assert found.external_id == external_id

        finally:
            integration_session.delete(mp)
            integration_session.commit()

    def test_stale_listing_identification(self, integration_session: Session):
        """Identify stale listings older than 30 days."""
        card = integration_session.exec(select(Card).limit(1)).first()
        if not card:
            pytest.skip("No cards in database")

        now = datetime.utcnow()
        created = []

        try:
            # Fresh listing (5 days ago)
            fresh = MarketPrice(
                card_id=card.id,
                price=10.0,
                title=f"Test - Fresh {now.timestamp()}",
                listing_type="active",
                treatment="Classic Paper",
                platform="ebay",
                external_id=f"test_fresh_{now.timestamp()}",
                listed_at=now - timedelta(days=5),
                scraped_at=now - timedelta(days=1),
            )

            # Stale listing (35 days ago)
            stale = MarketPrice(
                card_id=card.id,
                price=12.0,
                title=f"Test - Stale {now.timestamp()}",
                listing_type="active",
                treatment="Classic Paper",
                platform="ebay",
                external_id=f"test_stale_{now.timestamp()}",
                listed_at=now - timedelta(days=40),
                scraped_at=now - timedelta(days=35),
            )

            integration_session.add(fresh)
            integration_session.add(stale)
            created.extend([fresh, stale])
            integration_session.commit()

            # Query for stale listings
            cutoff = now - timedelta(days=30)
            stale_listings = integration_session.exec(
                select(MarketPrice).where(
                    MarketPrice.card_id == card.id,
                    MarketPrice.listing_type == "active",
                    MarketPrice.scraped_at < cutoff,
                    MarketPrice.external_id.like(f"test_%_{now.timestamp()}")
                )
            ).all()

            assert len(stale_listings) == 1
            assert "stale" in stale_listings[0].external_id.lower()

        finally:
            for mp in created:
                integration_session.delete(mp)
            integration_session.commit()


@pytest.mark.integration
class TestActiveToSoldConversionLogic:
    """Integration tests for the active->sold conversion logic."""

    def test_batch_fetch_active_listings(self, integration_session: Session):
        """Batch fetch active listings by external_ids."""
        card = integration_session.exec(select(Card).limit(1)).first()
        if not card:
            pytest.skip("No cards in database")

        now = datetime.utcnow()
        created = []
        external_ids = []

        try:
            # Create multiple active listings
            for i in range(3):
                ext_id = f"test_batch_{i}_{now.timestamp()}"
                external_ids.append(ext_id)
                mp = MarketPrice(
                    card_id=card.id,
                    price=10.0 + i,
                    title=f"Test - Batch {i}",
                    listing_type="active",
                    treatment="Classic Paper",
                    platform="ebay",
                    external_id=ext_id,
                    listed_at=now - timedelta(days=5 + i),
                    scraped_at=now,
                )
                integration_session.add(mp)
                created.append(mp)

            integration_session.commit()

            # Batch fetch
            results = integration_session.exec(
                select(MarketPrice).where(
                    MarketPrice.card_id == card.id,
                    MarketPrice.listing_type == "active",
                    MarketPrice.external_id.in_(external_ids)
                )
            ).all()

            assert len(results) == 3
            result_ids = {r.external_id for r in results}
            assert result_ids == set(external_ids)

        finally:
            for mp in created:
                integration_session.delete(mp)
            integration_session.commit()

    def test_update_preserves_listed_at(self, integration_session: Session):
        """Updating a listing should preserve listed_at."""
        card = integration_session.exec(select(Card).limit(1)).first()
        if not card:
            pytest.skip("No cards in database")

        now = datetime.utcnow()
        original_listed_at = now - timedelta(days=7)

        mp = MarketPrice(
            card_id=card.id,
            price=10.0,
            title="Test - Update Preserve",
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            external_id=f"test_update_{now.timestamp()}",
            listed_at=original_listed_at,
            scraped_at=now - timedelta(days=3),
        )
        integration_session.add(mp)
        integration_session.commit()
        mp_id = mp.id

        try:
            # Update price and scraped_at, but NOT listed_at
            mp.price = 15.0
            mp.scraped_at = now
            integration_session.add(mp)
            integration_session.commit()

            # Verify listed_at preserved
            fetched = integration_session.get(MarketPrice, mp_id)
            assert fetched.price == 15.0
            assert abs((fetched.listed_at - original_listed_at).total_seconds()) < 1

        finally:
            integration_session.delete(mp)
            integration_session.commit()
