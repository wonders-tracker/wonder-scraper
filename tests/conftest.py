"""
Pytest configuration and fixtures for testing.

Provides database setup, test data, and common fixtures.
"""

import pytest
from datetime import datetime, timedelta
from sqlmodel import Session, SQLModel, create_engine, select
from sqlmodel.pool import StaticPool
from fastapi.testclient import TestClient

from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice
from app.db import get_session
from app.main import app


@pytest.fixture(name="engine")
def engine_fixture():
    """Create in-memory SQLite database for testing."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    """Create database session for testing."""
    with Session(engine) as session:
        yield session


@pytest.fixture(name="client")
def client_fixture(engine):
    """Create FastAPI test client with test database."""
    def get_session_override():
        with Session(engine) as session:
            yield session

    app.dependency_overrides[get_session] = get_session_override
    client = TestClient(app)
    yield client
    app.dependency_overrides.clear()


@pytest.fixture(name="test_rarity")
def test_rarity_fixture(session: Session):
    """Create test rarity."""
    rarity = Rarity(name="Legendary")
    session.add(rarity)
    session.commit()
    session.refresh(rarity)
    return rarity


@pytest.fixture(name="test_card")
def test_card_fixture(session: Session, test_rarity: Rarity):
    """Create test card."""
    card = Card(
        name="Test Card",
        set_name="Wonders of the First",
        rarity_id=test_rarity.id,
        product_type="Single"
    )
    session.add(card)
    session.commit()
    session.refresh(card)
    return card


@pytest.fixture(name="test_prices")
def test_prices_fixture(session: Session, test_card: Card):
    """Create test price data spanning 30 days."""
    now = datetime.utcnow()
    prices = []

    # Create 30 days of price data
    for i in range(30):
        date = now - timedelta(days=29 - i)
        # Price trends upward from $10 to $30
        base_price = 10 + (i * 0.67)

        # Add some variation
        for j in range(3):  # 3 sales per day
            price = MarketPrice(
                card_id=test_card.id,
                price=base_price + (j * 0.5),
                quantity=1,  # Default quantity for test data
                title=f"Test Listing {i}-{j}",
                sold_date=date + timedelta(hours=j * 8),
                listing_type="sold",
                treatment="Classic Paper",
                platform="ebay",
                scraped_at=now
            )
            session.add(price)
            prices.append(price)

    session.commit()
    return prices


@pytest.fixture(name="test_snapshot")
def test_snapshot_fixture(session: Session, test_card: Card):
    """Create test market snapshot."""
    snapshot = MarketSnapshot(
        card_id=test_card.id,
        min_price=10.0,
        max_price=50.0,
        avg_price=25.0,
        volume=100,
        lowest_ask=28.0,
        highest_bid=24.0,
        inventory=15,
        platform="ebay",
        timestamp=datetime.utcnow()
    )
    session.add(snapshot)
    session.commit()
    session.refresh(snapshot)
    return snapshot


@pytest.fixture(name="multiple_cards")
def multiple_cards_fixture(session: Session, test_rarity: Rarity):
    """Create multiple test cards with different rarities and treatments."""
    # Create additional rarities
    common = Rarity(name="Common")
    rare = Rarity(name="Rare")
    session.add(common)
    session.add(rare)
    session.commit()
    session.refresh(common)
    session.refresh(rare)

    cards = []
    now = datetime.utcnow()

    # Card 1: Common, Classic Paper, $1-5
    card1 = Card(name="Common Card", set_name="Wonders of the First",
                 rarity_id=common.id, product_type="Single")
    session.add(card1)
    session.commit()
    session.refresh(card1)

    for i in range(10):
        price = MarketPrice(
            card_id=card1.id,
            price=1.0 + (i * 0.4),
            quantity=1,
            title=f"Common Listing {i}",
            sold_date=now - timedelta(days=9 - i),
            listing_type="sold",
            treatment="Classic Paper",
            platform="ebay",
            scraped_at=now
        )
        session.add(price)

    cards.append(card1)

    # Card 2: Rare, Classic Foil, $10-20
    card2 = Card(name="Rare Foil", set_name="Wonders of the First",
                 rarity_id=rare.id, product_type="Single")
    session.add(card2)
    session.commit()
    session.refresh(card2)

    for i in range(10):
        price = MarketPrice(
            card_id=card2.id,
            price=10.0 + (i * 1.0),
            quantity=1,
            title=f"Rare Foil Listing {i}",
            sold_date=now - timedelta(days=9 - i),
            listing_type="sold",
            treatment="Classic Foil",
            platform="ebay",
            scraped_at=now
        )
        session.add(price)

    cards.append(card2)

    # Card 3: Legendary, OCM Serialized, $100-200
    card3 = Card(name="Legendary Serial", set_name="Wonders of the First",
                 rarity_id=test_rarity.id, product_type="Single")
    session.add(card3)
    session.commit()
    session.refresh(card3)

    for i in range(10):
        price = MarketPrice(
            card_id=card3.id,
            price=100.0 + (i * 10.0),
            title=f"Serial Listing {i}",
            sold_date=now - timedelta(days=9 - i),
            listing_type="sold",
            treatment="OCM Serialized",
            platform="ebay",
            scraped_at=now
        )
        session.add(price)

    cards.append(card3)

    session.commit()
    return cards


@pytest.fixture(name="active_listings")
def active_listings_fixture(session: Session, test_card: Card):
    """Create active listings for bid/ask testing."""
    now = datetime.utcnow()

    # Create active buy-it-now listings
    for i in range(5):
        listing = MarketPrice(
            card_id=test_card.id,
            price=25.0 + i,
            title=f"Active Listing {i}",
            sold_date=None,
            listing_type="active",
            treatment="Classic Paper",
            platform="ebay",
            scraped_at=now
        )
        session.add(listing)

    session.commit()


@pytest.fixture(name="box_product")
def box_product_fixture(session: Session, test_rarity: Rarity):
    """Create test box product."""
    box = Card(
        name="Play Booster Box",
        set_name="Wonders of the First",
        rarity_id=test_rarity.id,
        product_type="Box"
    )
    session.add(box)
    session.commit()
    session.refresh(box)

    # Add some sales
    now = datetime.utcnow()
    for i in range(5):
        price = MarketPrice(
            card_id=box.id,
            price=100.0 + (i * 5.0),
            title=f"Box Listing {i}",
            sold_date=now - timedelta(days=4 - i),
            listing_type="sold",
            treatment="Sealed",
            platform="ebay",
            scraped_at=now
        )
        session.add(price)

    session.commit()
    return box
