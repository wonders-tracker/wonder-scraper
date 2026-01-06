"""
Migration script to add slug column to card table and populate slugs for existing cards.
"""

from sqlmodel import Session, text, select
from app.db import engine
from app.models.card import Card, generate_slug


def migrate():
    with Session(engine) as session:
        print("Checking for slug column in card table...")
        try:
            session.exec(text("SELECT slug FROM card LIMIT 1"))
            print("Column 'slug' already exists.")
        except Exception:
            session.rollback()
            print("Column 'slug' not found. Adding it...")
            session.exec(text("ALTER TABLE card ADD COLUMN slug VARCHAR"))
            session.commit()
            print("Added 'slug' column.")

        # Populate slugs for all cards that don't have one
        print("\nPopulating slugs for existing cards...")
        cards = session.exec(select(Card)).all()

        # Track used slugs to handle duplicates
        used_slugs = set()
        updated = 0

        for card in cards:
            if card.slug:
                used_slugs.add(card.slug)
                continue

            # Generate base slug
            base_slug = generate_slug(card.name)
            slug = base_slug

            # Handle duplicates by appending a number
            counter = 2
            while slug in used_slugs:
                slug = f"{base_slug}-{counter}"
                counter += 1

            card.slug = slug
            used_slugs.add(slug)
            session.add(card)
            updated += 1
            print(f"  {card.name} -> {slug}")

        session.commit()
        print(f"\nUpdated {updated} cards with slugs.")

        # Create unique index on slug
        print("\nCreating unique index on slug column...")
        try:
            session.exec(text("CREATE UNIQUE INDEX IF NOT EXISTS ix_card_slug ON card (slug)"))
            session.commit()
            print("Created unique index on slug.")
        except Exception as e:
            session.rollback()
            print(f"Index may already exist: {e}")


if __name__ == "__main__":
    migrate()
