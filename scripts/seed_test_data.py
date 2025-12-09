#!/usr/bin/env python3
"""
Seed test data for CI environment.

This script populates the database with minimal test data so integration tests
can run in CI. Uses the same patterns as conftest.py fixtures.

Usage:
    python scripts/seed_test_data.py
"""

import os
import sys
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, SQLModel
from app.db import engine
from app.models.card import Card, Rarity
from app.models.market import MarketPrice, MarketSnapshot
from app.models.user import User
from app.core import security

# Import all models to ensure they're registered with SQLModel.metadata
from app.models import (  # noqa: F401
    PortfolioItem, PortfolioCard, PurchaseSource,
    PageView, CardMetaVote, CardMetaVoteReaction,
)
from app.models.api_key import APIKey  # noqa: F401
from app.models.watchlist import Watchlist, EmailPreferences  # noqa: F401
from app.models.webhook_event import WebhookEvent  # noqa: F401
from app.models.blokpax import BlokpaxListing  # noqa: F401


def create_tables():
    """Create all tables if they don't exist."""
    print("  - Creating tables...")
    SQLModel.metadata.create_all(engine)
    print("    Tables created successfully")


def seed_rarities(session: Session) -> dict:
    """Seed rarity records."""
    rarities = {}
    rarity_names = ["Common", "Uncommon", "Rare", "Legendary", "Mythic", "SEALED"]

    for name in rarity_names:
        existing = session.exec(select(Rarity).where(Rarity.name == name)).first()
        if existing:
            rarities[name] = existing
        else:
            rarity = Rarity(name=name)
            session.add(rarity)
            session.commit()
            session.refresh(rarity)
            rarities[name] = rarity

    return rarities


def seed_cards(session: Session, rarities: dict) -> list:
    """Seed card records for testing."""
    cards_data = [
        # Singles with various rarities
        {"name": "Test Card Common", "slug": "test-card-common", "rarity": "Common", "product_type": "Single", "set_name": "Wonders of the First"},
        {"name": "Test Card Rare", "slug": "test-card-rare", "rarity": "Rare", "product_type": "Single", "set_name": "Wonders of the First"},
        {"name": "Progo", "slug": "progo", "rarity": "Rare", "product_type": "Single", "set_name": "Wonders of the First"},
        {"name": "Sandura of Heliosynth", "slug": "sandura-of-heliosynth", "rarity": "Mythic", "product_type": "Single", "set_name": "Wonders of the First"},
        {"name": "The Prisoner", "slug": "the-prisoner", "rarity": "Legendary", "product_type": "Single", "set_name": "Wonders of the First"},
        {"name": "Azure Sky Chaser", "slug": "azure-sky-chaser", "rarity": "Uncommon", "product_type": "Single", "set_name": "Wonders of the First"},
        # Boxes and sealed products
        {"name": "Collector Booster Box", "slug": "collector-booster-box", "rarity": "SEALED", "product_type": "Box", "set_name": "Wonders of the First"},
        {"name": "Play Bundle", "slug": "play-bundle", "rarity": "SEALED", "product_type": "Bundle", "set_name": "Wonders of the First"},
        {"name": "Booster Pack", "slug": "booster-pack", "rarity": "SEALED", "product_type": "Pack", "set_name": "Wonders of the First"},
    ]

    cards = []
    for data in cards_data:
        existing = session.exec(select(Card).where(Card.slug == data["slug"])).first()
        if existing:
            cards.append(existing)
        else:
            card = Card(
                name=data["name"],
                slug=data["slug"],
                rarity_id=rarities[data["rarity"]].id,
                product_type=data["product_type"],
                set_name=data["set_name"],
            )
            session.add(card)
            session.commit()
            session.refresh(card)
            cards.append(card)

    return cards


def seed_market_prices(session: Session, cards: list) -> list:
    """Seed market price records for floor price and FMP calculations."""
    now = datetime.utcnow()
    prices = []

    # Map cards by slug for easy access
    card_map = {c.slug: c for c in cards}

    # Test Card Common: Classic Paper and Foil sales (tests base treatment floor)
    test_common = card_map.get("test-card-common")
    if test_common:
        for i, price in enumerate([1.00, 1.50, 2.00, 2.50, 3.00]):
            prices.append(MarketPrice(
                card_id=test_common.id,
                price=price,
                title=f"Test Card Common - Classic Paper #{i}",
                treatment="Classic Paper",
                listing_type="sold",
                sold_date=now - timedelta(days=i),
                scraped_at=now - timedelta(days=i),
                platform="ebay",
            ))
        for i, price in enumerate([5.00, 6.00, 7.00]):
            prices.append(MarketPrice(
                card_id=test_common.id,
                price=price,
                title=f"Test Card Common - Classic Foil #{i}",
                treatment="Classic Foil",
                listing_type="sold",
                sold_date=now - timedelta(days=i),
                scraped_at=now - timedelta(days=i),
                platform="ebay",
            ))

    # Progo: NO Classic Paper/Foil - tests fallback to cheapest treatment
    progo = card_map.get("progo")
    if progo:
        for i, price in enumerate([5.00, 6.00, 7.00, 8.00]):
            prices.append(MarketPrice(
                card_id=progo.id,
                price=price,
                title=f"Progo - Formless Foil #{i}",
                treatment="Formless Foil",
                listing_type="sold",
                sold_date=now - timedelta(days=i),
                scraped_at=now - timedelta(days=i),
                platform="ebay",
            ))
        for i, price in enumerate([50.00, 60.00, 70.00]):
            prices.append(MarketPrice(
                card_id=progo.id,
                price=price,
                title=f"Progo - OCM Serialized #{i}",
                treatment="OCM Serialized",
                listing_type="sold",
                sold_date=now - timedelta(days=i),
                scraped_at=now - timedelta(days=i),
                platform="ebay",
            ))
        # Active listing - should NOT affect floor
        prices.append(MarketPrice(
            card_id=progo.id,
            price=0.99,
            title="Progo - Classic Paper (Active)",
            treatment="Classic Paper",
            listing_type="active",
            scraped_at=now,
            platform="ebay",
        ))

    # Test Card Rare: Mixed treatments
    test_rare = card_map.get("test-card-rare")
    if test_rare:
        for i, price in enumerate([10.00, 12.00, 15.00, 18.00]):
            prices.append(MarketPrice(
                card_id=test_rare.id,
                price=price,
                title=f"Test Card Rare - Classic Paper #{i}",
                treatment="Classic Paper",
                listing_type="sold",
                sold_date=now - timedelta(days=i),
                scraped_at=now - timedelta(days=i),
                platform="ebay",
            ))

    # Sandura: High-value mythic
    sandura = card_map.get("sandura-of-heliosynth")
    if sandura:
        for i, price in enumerate([100.00, 120.00, 150.00, 180.00]):
            prices.append(MarketPrice(
                card_id=sandura.id,
                price=price,
                title=f"Sandura of Heliosynth - Classic Paper #{i}",
                treatment="Classic Paper",
                listing_type="sold",
                sold_date=now - timedelta(days=i),
                scraped_at=now - timedelta(days=i),
                platform="ebay",
            ))

    # Collector Booster Box: Sealed product
    box = card_map.get("collector-booster-box")
    if box:
        for i, price in enumerate([150.00, 160.00, 170.00, 180.00]):
            prices.append(MarketPrice(
                card_id=box.id,
                price=price,
                title=f"Collector Booster Box - Sealed #{i}",
                treatment="Sealed",
                listing_type="sold",
                sold_date=now - timedelta(days=i),
                scraped_at=now - timedelta(days=i),
                platform="ebay",
            ))

    # Add some OpenSea listings for platform diversity
    # Only add to sealed products, not Singles (Singles shouldn't have Digital treatment)
    if box:
        prices.append(MarketPrice(
            card_id=box.id,
            price=175.00,
            title=f"{box.name} - OpenSea NFT",
            treatment="Digital",
            listing_type="sold",
            sold_date=now - timedelta(days=5),
            scraped_at=now - timedelta(days=5),
            platform="opensea",
            url="https://opensea.io/assets/test/123",
        ))

    # Batch insert
    for p in prices:
        session.add(p)
    session.commit()

    return prices


def seed_users(session: Session) -> list:
    """Seed test users."""
    users_data = [
        {"email": "test@example.com", "password": "testpassword123", "is_superuser": False},
        {"email": "admin@example.com", "password": "adminpassword123", "is_superuser": True},
    ]

    users = []
    for data in users_data:
        existing = session.exec(select(User).where(User.email == data["email"])).first()
        if existing:
            users.append(existing)
        else:
            user = User(
                email=data["email"],
                hashed_password=security.get_password_hash(data["password"]),
                is_active=True,
                is_superuser=data["is_superuser"],
            )
            session.add(user)
            session.commit()
            session.refresh(user)
            users.append(user)

    return users


def seed_market_snapshots(session: Session, cards: list) -> list:
    """Seed market snapshots for cards."""
    now = datetime.utcnow()
    snapshots = []

    for card in cards[:5]:  # Only first 5 cards
        snapshot = MarketSnapshot(
            card_id=card.id,
            min_price=10.00 + card.id,
            max_price=20.00 + card.id,
            avg_price=15.00 + card.id,
            volume=50,
            timestamp=now,
        )
        session.add(snapshot)
        snapshots.append(snapshot)

    session.commit()
    return snapshots


def main():
    """Main seeding function."""
    print("Seeding test data for CI...")

    # Create tables first (in case alembic migrations are missing)
    create_tables()

    with Session(engine) as session:
        print("  - Seeding rarities...")
        rarities = seed_rarities(session)
        print(f"    Created/found {len(rarities)} rarities")

        print("  - Seeding cards...")
        cards = seed_cards(session, rarities)
        print(f"    Created/found {len(cards)} cards")

        print("  - Seeding market prices...")
        prices = seed_market_prices(session, cards)
        print(f"    Created {len(prices)} market prices")

        print("  - Seeding users...")
        users = seed_users(session)
        print(f"    Created/found {len(users)} users")

        print("  - Seeding market snapshots...")
        snapshots = seed_market_snapshots(session, cards)
        print(f"    Created {len(snapshots)} snapshots")

    print("Test data seeding complete!")


if __name__ == "__main__":
    main()
