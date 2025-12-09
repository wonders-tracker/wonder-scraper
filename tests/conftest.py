"""
Test fixtures for wonder-scraper tests.

Provides database session fixtures and mock data generators.
"""

import pytest
from datetime import datetime, timedelta, timezone
from typing import Generator, List
from sqlmodel import Session, SQLModel, create_engine, text
from sqlalchemy.pool import StaticPool

from app.models.card import Card, Rarity
from app.models.market import MarketPrice, MarketSnapshot
from app.models.user import User
from app.core import security


# Check if SaaS module is available
try:
    import saas
    SAAS_AVAILABLE = True
except ImportError:
    SAAS_AVAILABLE = False


def pytest_collection_modifyitems(config, items):
    """
    Auto-skip tests based on environment:
    - SaaS tests when saas/ module is not available
    - Integration tests in CI (empty database)
    """
    import os

    # Skip SaaS tests when module not available
    if not SAAS_AVAILABLE:
        skip_saas = pytest.mark.skip(reason="saas/ module not available (OSS mode)")
        for item in items:
            if "saas" in item.keywords:
                item.add_marker(skip_saas)
            elif "saas/tests" in str(item.fspath) or "saas\\tests" in str(item.fspath):
                item.add_marker(skip_saas)

    # Skip integration tests in CI (they need real data that doesn't exist in CI)
    if os.environ.get("CI") == "true":
        skip_integration = pytest.mark.skip(reason="Integration tests skipped in CI (no data)")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)


# Use in-memory SQLite for unit tests (fast, isolated)
# For integration tests, we use the real PostgreSQL database
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(autouse=True)
def clear_rate_limiters():
    """Clear rate limiters before each test to prevent 429 errors."""
    from app.core.rate_limit import rate_limiter
    from app.core.anti_scraping import AntiScrapingMiddleware

    # Clear the global rate limiter
    rate_limiter.clear()

    # Get the app's middleware stack and find the AntiScrapingMiddleware instance
    from app.main import app

    # Build the middleware stack by accessing it (this creates the stack if not built)
    # The middleware stack is created lazily
    def find_and_clear_middleware(obj):
        """Recursively find and clear AntiScrapingMiddleware in the middleware chain."""
        if isinstance(obj, AntiScrapingMiddleware):
            obj.clear()
        # Check if this object wraps another app
        if hasattr(obj, 'app'):
            find_and_clear_middleware(obj.app)

    # Access middleware_stack to trigger build, then clear
    if hasattr(app, 'middleware_stack') and app.middleware_stack:
        find_and_clear_middleware(app.middleware_stack)

    yield


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
        onboarding_completed=False,
    )
    test_session.add(user)
    test_session.commit()
    test_session.refresh(user)
    return user


@pytest.fixture
def onboarded_user(test_session: Session) -> User:
    """Create a user who has completed onboarding."""
    user = User(
        id=10,
        email="onboarded@example.com",
        hashed_password=security.get_password_hash("testpassword123"),
        is_active=True,
        is_superuser=False,
        onboarding_completed=True,
        username="OnboardedUser",
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
        password_reset_expires=datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1),
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
        password_reset_expires=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1),  # Expired
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


# ============================================
# Test Data Factory
# ============================================

import random
import string
from typing import Optional


class TestDataFactory:
    """
    Factory for generating randomized test data.
    Useful for creating varied test scenarios without hard-coded values.
    """

    # Sample card names for realistic test data
    CARD_NAMES = [
        "Sandura of Heliosynth", "The Prisoner", "Azure Sky Chaser",
        "Progo", "Lightbringer Leonis", "Shadowveil Assassin",
        "Crystal Guardian", "Flame Dancer", "Storm Caller",
        "Earth Warden", "Void Walker", "Divine Protector",
        "Chaos Bringer", "Time Weaver", "Space Drifter",
    ]

    TREATMENTS = [
        "Classic Paper", "Classic Foil", "Formless Foil",
        "OCM Serialized", "Promo", "Prerelease",
    ]

    SOURCES = ["eBay", "Blokpax", "TCGPlayer", "LGS", "Trade", "Pack Pull", "Other"]

    RARITIES = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic"]

    SET_NAMES = ["Wonders of the First", "Existence", "Genesis"]

    PRODUCT_TYPES = ["Single", "Box", "Pack", "Lot", "Proof"]

    def __init__(self, session: Session):
        self.session = session
        self._rarity_cache = {}
        self._card_cache = {}

    def random_string(self, length: int = 8) -> str:
        """Generate a random string."""
        return "".join(random.choices(string.ascii_lowercase, k=length))

    def random_price(self, min_price: float = 0.50, max_price: float = 100.00) -> float:
        """Generate a random price."""
        return round(random.uniform(min_price, max_price), 2)

    def random_date(self, days_back: int = 30) -> datetime:
        """Generate a random date within the past N days."""
        days = random.randint(0, days_back)
        return datetime.utcnow() - timedelta(days=days)

    def get_or_create_rarity(self, name: str) -> Rarity:
        """Get or create a rarity by name."""
        if name in self._rarity_cache:
            return self._rarity_cache[name]

        from sqlmodel import select
        rarity = self.session.exec(
            select(Rarity).where(Rarity.name == name)
        ).first()

        if not rarity:
            rarity = Rarity(name=name)
            self.session.add(rarity)
            self.session.commit()
            self.session.refresh(rarity)

        self._rarity_cache[name] = rarity
        return rarity

    def create_card(
        self,
        name: Optional[str] = None,
        rarity_name: Optional[str] = None,
        product_type: Optional[str] = None,
        set_name: Optional[str] = None,
    ) -> Card:
        """Create a card with optional overrides."""
        name = name or random.choice(self.CARD_NAMES) + f" #{self.random_string(4)}"
        rarity_name = rarity_name or random.choice(self.RARITIES)
        product_type = product_type or random.choice(self.PRODUCT_TYPES)
        set_name = set_name or random.choice(self.SET_NAMES)

        rarity = self.get_or_create_rarity(rarity_name)

        from app.models.card import generate_slug
        card = Card(
            name=name,
            slug=generate_slug(name),
            rarity_id=rarity.id,
            product_type=product_type,
            set_name=set_name,
        )
        self.session.add(card)
        self.session.commit()
        self.session.refresh(card)

        self._card_cache[card.id] = card
        return card

    def create_cards(self, count: int, **kwargs) -> List[Card]:
        """Create multiple cards."""
        return [self.create_card(**kwargs) for _ in range(count)]

    def create_market_price(
        self,
        card: Card,
        price: Optional[float] = None,
        treatment: Optional[str] = None,
        listing_type: str = "sold",
        sold_date: Optional[datetime] = None,
    ) -> MarketPrice:
        """Create a market price record."""
        price = price or self.random_price()
        treatment = treatment or random.choice(self.TREATMENTS)
        sold_date = sold_date or (self.random_date() if listing_type == "sold" else None)

        mp = MarketPrice(
            card_id=card.id,
            price=price,
            treatment=treatment,
            listing_type=listing_type,
            sold_date=sold_date,
            scraped_at=datetime.utcnow(),
            title=f"{card.name} - {treatment}",
            platform="ebay",
        )
        self.session.add(mp)
        self.session.commit()
        self.session.refresh(mp)
        return mp

    def create_market_prices_for_card(
        self,
        card: Card,
        count: int = 5,
        treatment: Optional[str] = None,
        price_range: tuple = (1.0, 50.0),
    ) -> List[MarketPrice]:
        """Create multiple market prices for a card."""
        prices = []
        for i in range(count):
            price = self.random_price(price_range[0], price_range[1])
            mp = self.create_market_price(
                card=card,
                price=price,
                treatment=treatment or random.choice(self.TREATMENTS),
                sold_date=datetime.utcnow() - timedelta(days=i),
            )
            prices.append(mp)
        return prices

    def create_user(
        self,
        email: Optional[str] = None,
        password: str = "testpassword123",
        is_superuser: bool = False,
    ) -> User:
        """Create a user for testing."""
        email = email or f"user_{self.random_string()}@test.com"
        user = User(
            email=email,
            hashed_password=security.get_password_hash(password),
            is_active=True,
            is_superuser=is_superuser,
        )
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user

    def create_portfolio_card(
        self,
        user: User,
        card: Card,
        treatment: Optional[str] = None,
        source: Optional[str] = None,
        purchase_price: Optional[float] = None,
        purchase_date: Optional[datetime] = None,
        grading: Optional[str] = None,
    ):
        """Create a portfolio card entry."""
        from app.models.portfolio import PortfolioCard

        treatment = treatment or random.choice(self.TREATMENTS)
        source = source or random.choice(self.SOURCES)
        purchase_price = purchase_price or self.random_price()
        purchase_date = purchase_date or self.random_date().date()

        pc = PortfolioCard(
            user_id=user.id,
            card_id=card.id,
            treatment=treatment,
            source=source,
            purchase_price=purchase_price,
            purchase_date=purchase_date,
            grading=grading,
        )
        self.session.add(pc)
        self.session.commit()
        self.session.refresh(pc)
        return pc

    def create_portfolio_cards(
        self,
        user: User,
        card: Card,
        count: int,
        **kwargs
    ) -> List:
        """Create multiple portfolio cards for the same base card."""
        from app.models.portfolio import PortfolioCard
        return [self.create_portfolio_card(user, card, **kwargs) for _ in range(count)]


@pytest.fixture
def factory(test_session: Session) -> TestDataFactory:
    """Provide a test data factory."""
    return TestDataFactory(test_session)


@pytest.fixture
def integration_factory(integration_session: Session) -> TestDataFactory:
    """Provide a test data factory for integration tests."""
    return TestDataFactory(integration_session)


# ============================================
# Portfolio Test Fixtures
# ============================================

from app.models.portfolio import PortfolioCard, PortfolioItem


@pytest.fixture
def sample_portfolio_cards(test_session: Session, sample_user: User, sample_cards: List[Card]) -> List[PortfolioCard]:
    """Create sample portfolio cards for testing."""
    cards = []

    # User has 3 copies of Card 1 with different treatments
    cards.append(PortfolioCard(
        user_id=sample_user.id,
        card_id=sample_cards[0].id,
        treatment="Classic Paper",
        source="eBay",
        purchase_price=1.50,
        purchase_date=datetime.utcnow().date() - timedelta(days=10),
    ))
    cards.append(PortfolioCard(
        user_id=sample_user.id,
        card_id=sample_cards[0].id,
        treatment="Classic Foil",
        source="LGS",
        purchase_price=5.00,
        purchase_date=datetime.utcnow().date() - timedelta(days=5),
    ))
    cards.append(PortfolioCard(
        user_id=sample_user.id,
        card_id=sample_cards[0].id,
        treatment="Classic Paper",
        source="Pack Pull",
        purchase_price=0.00,  # Pulled from pack
        purchase_date=datetime.utcnow().date() - timedelta(days=20),
    ))

    # User has 1 graded card
    cards.append(PortfolioCard(
        user_id=sample_user.id,
        card_id=sample_cards[1].id,
        treatment="Classic Paper",
        source="eBay",
        purchase_price=25.00,
        purchase_date=datetime.utcnow().date() - timedelta(days=30),
        grading="PSA 10",
    ))

    for c in cards:
        test_session.add(c)
    test_session.commit()

    for c in cards:
        test_session.refresh(c)

    return cards


@pytest.fixture
def sample_legacy_portfolio(test_session: Session, sample_user: User, sample_cards: List[Card]) -> List[PortfolioItem]:
    """Create legacy portfolio items for migration testing."""
    items = [
        PortfolioItem(
            user_id=sample_user.id,
            card_id=sample_cards[0].id,
            quantity=5,
            purchase_price=2.00,
        ),
        PortfolioItem(
            user_id=sample_user.id,
            card_id=sample_cards[1].id,
            quantity=2,
            purchase_price=15.00,
        ),
    ]

    for item in items:
        test_session.add(item)
    test_session.commit()

    for item in items:
        test_session.refresh(item)

    return items
