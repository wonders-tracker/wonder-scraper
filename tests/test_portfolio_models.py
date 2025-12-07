"""
Unit tests for Portfolio models.

Tests cover:
- PortfolioCard model creation and validation
- Field defaults and constraints
- Soft delete functionality
- Model relationships
"""

import pytest
from datetime import datetime, timedelta, date
from sqlmodel import Session, select

from app.models.portfolio import PortfolioCard, PortfolioItem, PurchaseSource
from app.models.card import Card
from app.models.user import User


class TestPortfolioCardModel:
    """Tests for the PortfolioCard model."""

    def test_create_portfolio_card_basic(self, test_session: Session, sample_user: User, sample_cards):
        """Test basic portfolio card creation."""
        card = PortfolioCard(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            treatment="Classic Paper",
            source="eBay",
            purchase_price=5.99,
            purchase_date=date.today(),
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        assert card.id is not None
        assert card.user_id == sample_user.id
        assert card.card_id == sample_cards[0].id
        assert card.treatment == "Classic Paper"
        assert card.source == "eBay"
        assert card.purchase_price == 5.99
        assert card.purchase_date == date.today()
        assert card.grading is None
        assert card.deleted_at is None

    def test_create_portfolio_card_with_grading(self, test_session: Session, sample_user: User, sample_cards):
        """Test portfolio card creation with grading."""
        card = PortfolioCard(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            treatment="Classic Paper",
            source="eBay",
            purchase_price=100.00,
            grading="PSA 10",
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        assert card.grading == "PSA 10"

    def test_create_portfolio_card_with_notes(self, test_session: Session, sample_user: User, sample_cards):
        """Test portfolio card creation with notes."""
        card = PortfolioCard(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            treatment="Classic Paper",
            source="Trade",
            purchase_price=0.00,
            notes="Traded with John at LGS meetup",
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        assert card.notes == "Traded with John at LGS meetup"

    def test_default_treatment(self, test_session: Session, sample_user: User, sample_cards):
        """Test that treatment defaults to 'Classic Paper'."""
        card = PortfolioCard(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            source="eBay",
            purchase_price=5.00,
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        assert card.treatment == "Classic Paper"

    def test_default_source(self, test_session: Session, sample_user: User, sample_cards):
        """Test that source defaults to 'Other'."""
        card = PortfolioCard(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            treatment="Classic Foil",
            purchase_price=10.00,
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        assert card.source == "Other"

    def test_timestamps_auto_set(self, test_session: Session, sample_user: User, sample_cards):
        """Test that created_at and updated_at are auto-set."""
        before = datetime.utcnow()

        card = PortfolioCard(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            purchase_price=5.00,
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        after = datetime.utcnow()

        assert card.created_at is not None
        assert card.updated_at is not None
        assert before <= card.created_at <= after
        assert before <= card.updated_at <= after

    def test_soft_delete(self, test_session: Session, sample_user: User, sample_cards):
        """Test soft delete functionality."""
        card = PortfolioCard(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            purchase_price=5.00,
        )
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        assert card.deleted_at is None

        # Soft delete
        card.deleted_at = datetime.utcnow()
        test_session.add(card)
        test_session.commit()
        test_session.refresh(card)

        assert card.deleted_at is not None

        # Verify it's still in DB (soft deleted, not hard deleted)
        found = test_session.get(PortfolioCard, card.id)
        assert found is not None
        assert found.deleted_at is not None

    def test_multiple_cards_same_base_card(self, test_session: Session, sample_user: User, sample_cards):
        """Test that user can have multiple portfolio cards for the same base card."""
        cards = []
        for i in range(5):
            card = PortfolioCard(
                user_id=sample_user.id,
                card_id=sample_cards[0].id,
                treatment="Classic Paper",
                source="eBay",
                purchase_price=5.00 + i,
            )
            test_session.add(card)
            cards.append(card)

        test_session.commit()

        # Verify all were created
        result = test_session.exec(
            select(PortfolioCard)
            .where(PortfolioCard.user_id == sample_user.id)
            .where(PortfolioCard.card_id == sample_cards[0].id)
        ).all()

        assert len(result) == 5

    def test_query_by_treatment(self, test_session: Session, sample_portfolio_cards):
        """Test filtering portfolio cards by treatment."""
        paper_cards = test_session.exec(
            select(PortfolioCard)
            .where(PortfolioCard.treatment == "Classic Paper")
            .where(PortfolioCard.deleted_at.is_(None))
        ).all()

        foil_cards = test_session.exec(
            select(PortfolioCard)
            .where(PortfolioCard.treatment == "Classic Foil")
            .where(PortfolioCard.deleted_at.is_(None))
        ).all()

        assert len(paper_cards) >= 2  # At least 2 paper cards from fixture
        assert len(foil_cards) >= 1  # At least 1 foil card from fixture

    def test_query_by_source(self, test_session: Session, sample_portfolio_cards):
        """Test filtering portfolio cards by source."""
        ebay_cards = test_session.exec(
            select(PortfolioCard)
            .where(PortfolioCard.source == "eBay")
            .where(PortfolioCard.deleted_at.is_(None))
        ).all()

        assert len(ebay_cards) >= 2  # At least 2 eBay cards from fixture

    def test_query_graded_cards(self, test_session: Session, sample_portfolio_cards):
        """Test filtering for graded cards."""
        graded = test_session.exec(
            select(PortfolioCard)
            .where(PortfolioCard.grading.isnot(None))
            .where(PortfolioCard.deleted_at.is_(None))
        ).all()

        raw = test_session.exec(
            select(PortfolioCard)
            .where(PortfolioCard.grading.is_(None))
            .where(PortfolioCard.deleted_at.is_(None))
        ).all()

        assert len(graded) >= 1  # At least 1 graded from fixture
        assert len(raw) >= 3  # At least 3 raw from fixture


class TestPurchaseSourceEnum:
    """Tests for the PurchaseSource enum."""

    def test_all_sources_defined(self):
        """Test that all expected sources are defined."""
        expected = ["eBay", "Blokpax", "TCGPlayer", "LGS", "Trade", "Pack Pull", "Other"]
        for source in expected:
            assert source in [s.value for s in PurchaseSource]

    def test_source_values(self):
        """Test source enum values."""
        assert PurchaseSource.EBAY.value == "eBay"
        assert PurchaseSource.BLOKPAX.value == "Blokpax"
        assert PurchaseSource.TCGPLAYER.value == "TCGPlayer"
        assert PurchaseSource.LGS.value == "LGS"
        assert PurchaseSource.TRADE.value == "Trade"
        assert PurchaseSource.PACK_PULL.value == "Pack Pull"
        assert PurchaseSource.OTHER.value == "Other"


class TestLegacyPortfolioItem:
    """Tests for the legacy PortfolioItem model."""

    def test_legacy_item_still_works(self, test_session: Session, sample_user: User, sample_cards):
        """Test that legacy PortfolioItem model still works."""
        item = PortfolioItem(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            quantity=10,
            purchase_price=2.50,
        )
        test_session.add(item)
        test_session.commit()
        test_session.refresh(item)

        assert item.id is not None
        assert item.quantity == 10
        assert item.purchase_price == 2.50


class TestFactoryGeneration:
    """Tests for the TestDataFactory."""

    def test_factory_creates_random_cards(self, factory):
        """Test that factory can create random cards."""
        cards = factory.create_cards(5)
        assert len(cards) == 5

        # All should have unique IDs
        ids = [c.id for c in cards]
        assert len(set(ids)) == 5

    def test_factory_creates_market_prices(self, factory):
        """Test that factory can create market prices."""
        card = factory.create_card()
        prices = factory.create_market_prices_for_card(card, count=10)

        assert len(prices) == 10
        for p in prices:
            assert p.card_id == card.id
            assert p.price > 0

    def test_factory_creates_portfolio_cards(self, factory):
        """Test that factory can create portfolio cards."""
        user = factory.create_user()
        card = factory.create_card()

        pc = factory.create_portfolio_card(user, card)

        assert pc.user_id == user.id
        assert pc.card_id == card.id
        assert pc.treatment in factory.TREATMENTS
        assert pc.source in factory.SOURCES

    def test_factory_creates_multiple_portfolio_cards(self, factory):
        """Test that factory can create multiple portfolio cards."""
        user = factory.create_user()
        card = factory.create_card()

        pcs = factory.create_portfolio_cards(user, card, count=10)

        assert len(pcs) == 10
        for pc in pcs:
            assert pc.user_id == user.id
            assert pc.card_id == card.id
