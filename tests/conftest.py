"""
Test fixtures for wonder-scraper tests.

Provides database session fixtures and mock data generators.
"""

import pytest
from datetime import datetime, timedelta
from typing import Generator, List
from sqlmodel import Session, SQLModel, create_engine, text
from sqlalchemy.pool import StaticPool

from app.models.card import Card, Rarity
from app.models.market import MarketPrice, MarketSnapshot
from app.models.user import User
from app.core import security


# Use in-memory SQLite for unit tests (fast, isolated)
# For integration tests, we use the real PostgreSQL database
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def test_engine():
    """Create a test database engine with in-memory SQLite."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    yield engine
    SQLModel.metadata.drop_all(engine)


@pytest.fixture(scope="function")
def test_session(test_engine) -> Generator[Session, None, None]:
    """Provide a test database session."""
    with Session(test_engine) as session:
        yield session


@pytest.fixture(scope="function")
def integration_session() -> Generator[Session, None, None]:
    """Provide a session to the real database for integration tests."""
    from app.db import engine
    with Session(engine) as session:
        yield session


@pytest.fixture
def sample_rarities(test_session: Session) -> List[Rarity]:
    """Create sample rarities for testing."""
    rarities = [
        Rarity(id=1, name="Common"),
        Rarity(id=2, name="Uncommon"),
        Rarity(id=3, name="Rare"),
        Rarity(id=4, name="Legendary"),
        Rarity(id=5, name="Mythic"),
    ]
    for r in rarities:
        test_session.add(r)
    test_session.commit()
    return rarities


@pytest.fixture
def sample_cards(test_session: Session, sample_rarities: List[Rarity]) -> List[Card]:
    """Create sample cards for testing."""
    cards = [
        Card(id=1, name="Test Card Common", set_name="Test Set", rarity_id=1, product_type="Single"),
        Card(id=2, name="Test Card Rare", set_name="Test Set", rarity_id=3, product_type="Single"),
        Card(id=3, name="Promo Only Card", set_name="Test Set", rarity_id=1, product_type="Single"),
        Card(id=4, name="Test Box", set_name="Test Set", rarity_id=1, product_type="Box"),
    ]
    for c in cards:
        test_session.add(c)
    test_session.commit()
    return cards


@pytest.fixture
def sample_market_prices(test_session: Session, sample_cards: List[Card]) -> List[MarketPrice]:
    """
    Create sample market prices for testing floor price calculations.

    Card 1 (Common): Has Classic Paper sales - should use base treatment floor
    Card 2 (Rare): Has Classic Paper + Foil sales
    Card 3 (Promo Only): NO Classic Paper/Foil - should fallback to cheapest treatment
    """
    now = datetime.utcnow()
    prices = []

    # Card 1: Classic Paper sales (base treatment)
    for i, price in enumerate([1.00, 1.50, 2.00, 2.50, 3.00]):
        prices.append(MarketPrice(
            card_id=1,
            price=price,
            title=f"Test Card Common - Classic Paper #{i}",
            treatment="Classic Paper",
            listing_type="sold",
            sold_date=now - timedelta(days=i),
            scraped_at=now - timedelta(days=i),
            platform="ebay",
        ))

    # Card 1: Also has some Foil sales (more expensive)
    for i, price in enumerate([5.00, 6.00, 7.00]):
        prices.append(MarketPrice(
            card_id=1,
            price=price,
            title=f"Test Card Common - Classic Foil #{i}",
            treatment="Classic Foil",
            listing_type="sold",
            sold_date=now - timedelta(days=i),
            scraped_at=now - timedelta(days=i),
            platform="ebay",
        ))

    # Card 2: Mixed treatments
    for i, price in enumerate([10.00, 12.00, 15.00, 18.00]):
        prices.append(MarketPrice(
            card_id=2,
            price=price,
            title=f"Test Card Rare - Classic Paper #{i}",
            treatment="Classic Paper",
            listing_type="sold",
            sold_date=now - timedelta(days=i),
            scraped_at=now - timedelta(days=i),
            platform="ebay",
        ))

    # Card 3: ONLY premium treatments (no Classic Paper/Foil)
    # This tests the fallback to cheapest treatment
    for i, price in enumerate([5.00, 6.00, 7.00, 8.00]):  # Formless Foil is cheapest
        prices.append(MarketPrice(
            card_id=3,
            price=price,
            title=f"Promo Only Card - Formless Foil #{i}",
            treatment="Formless Foil",
            listing_type="sold",
            sold_date=now - timedelta(days=i),
            scraped_at=now - timedelta(days=i),
            platform="ebay",
        ))

    for i, price in enumerate([50.00, 60.00, 70.00]):  # OCM Serialized is expensive
        prices.append(MarketPrice(
            card_id=3,
            price=price,
            title=f"Promo Only Card - OCM Serialized #{i}",
            treatment="OCM Serialized",
            listing_type="sold",
            sold_date=now - timedelta(days=i),
            scraped_at=now - timedelta(days=i),
            platform="ebay",
        ))

    for i, price in enumerate([100.00, 150.00]):  # Promo is most expensive
        prices.append(MarketPrice(
            card_id=3,
            price=price,
            title=f"Promo Only Card - Promo #{i}",
            treatment="Promo",
            listing_type="sold",
            sold_date=now - timedelta(days=i),
            scraped_at=now - timedelta(days=i),
            platform="ebay",
        ))

    # Card 3: Active listing (should NOT affect floor calculation)
    prices.append(MarketPrice(
        card_id=3,
        price=0.99,  # Low active listing
        title="Promo Only Card - Classic Paper (Active)",
        treatment="Classic Paper",
        listing_type="active",
        scraped_at=now,
        platform="ebay",
    ))

    for p in prices:
        test_session.add(p)
    test_session.commit()

    return prices


@pytest.fixture
def old_market_prices(test_session: Session, sample_cards: List[Card]) -> List[MarketPrice]:
    """Create market prices older than 30 days for testing time window fallbacks."""
    now = datetime.utcnow()
    prices = []

    # Card 4 (Box): Only has old sales (>30 days ago)
    for i, price in enumerate([50.00, 55.00, 60.00, 65.00]):
        prices.append(MarketPrice(
            card_id=4,
            price=price,
            title=f"Test Box - Sealed #{i}",
            treatment="Sealed",
            listing_type="sold",
            sold_date=now - timedelta(days=45 + i),  # 45-48 days ago
            scraped_at=now - timedelta(days=45 + i),
            platform="ebay",
        ))

    for p in prices:
        test_session.add(p)
    test_session.commit()

    return prices


@pytest.fixture
def null_sold_date_prices(test_session: Session, sample_cards: List[Card]) -> List[MarketPrice]:
    """Create market prices with NULL sold_date to test COALESCE logic."""
    now = datetime.utcnow()
    prices = []

    # Card 1: Sales with NULL sold_date (should use scraped_at)
    for i, price in enumerate([1.25, 1.75]):
        prices.append(MarketPrice(
            card_id=1,
            price=price,
            title=f"Test Card Common - Classic Paper (null date) #{i}",
            treatment="Classic Paper",
            listing_type="sold",
            sold_date=None,  # NULL sold_date
            scraped_at=now - timedelta(days=i + 10),
            platform="ebay",
        ))

    for p in prices:
        test_session.add(p)
    test_session.commit()

    return prices


# ============================================
# User / Auth Fixtures
# ============================================

@pytest.fixture
def sample_user(test_session: Session) -> User:
    """Create a sample user for testing."""
    user = User(
        id=1,
        email="test@example.com",
        hashed_password=security.get_password_hash("testpassword123"),
        is_active=True,
        is_superuser=False,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def sample_user_with_reset_token(test_session: Session) -> User:
    """Create a user with a valid password reset token."""
    import secrets
    user = User(
        id=2,
        email="reset@example.com",
        hashed_password=security.get_password_hash("oldpassword123"),
        is_active=True,
        is_superuser=False,
        password_reset_token=secrets.token_urlsafe(32),
        password_reset_expires=datetime.utcnow() + timedelta(hours=1),
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def sample_user_with_expired_token(test_session: Session) -> User:
    """Create a user with an expired password reset token."""
    import secrets
    user = User(
        id=3,
        email="expired@example.com",
        hashed_password=security.get_password_hash("oldpassword123"),
        is_active=True,
        is_superuser=False,
        password_reset_token=secrets.token_urlsafe(32),
        password_reset_expires=datetime.utcnow() - timedelta(hours=1),  # Expired
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def inactive_user(test_session: Session) -> User:
    """Create an inactive user for testing."""
    user = User(
        id=4,
        email="inactive@example.com",
        hashed_password=security.get_password_hash("testpassword123"),
        is_active=False,
        is_superuser=False,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user
