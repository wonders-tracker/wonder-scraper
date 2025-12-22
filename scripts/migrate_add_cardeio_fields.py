#!/usr/bin/env python3
"""
Database migration to add Carde.io card fields.

This adds the following columns to the card table:
- card_type: Wonder, Item, Spell, Land, Token, Tracker
- orbital: Heliosynth, Thalwind, Petraia, Solfera, Boundless, Umbrathene
- orbital_color: Hex color code
- card_number: Card number from set (e.g., "143")
- cardeio_image_url: Official high-res image URL

Usage:
    python scripts/migrate_add_cardeio_fields.py
"""

import os
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine

load_dotenv()


MIGRATIONS = [
    """
    ALTER TABLE card
    ADD COLUMN IF NOT EXISTS card_type VARCHAR(50);
    """,
    """
    ALTER TABLE card
    ADD COLUMN IF NOT EXISTS orbital VARCHAR(50);
    """,
    """
    ALTER TABLE card
    ADD COLUMN IF NOT EXISTS orbital_color VARCHAR(10);
    """,
    """
    ALTER TABLE card
    ADD COLUMN IF NOT EXISTS card_number VARCHAR(20);
    """,
    """
    ALTER TABLE card
    ADD COLUMN IF NOT EXISTS cardeio_image_url TEXT;
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_card_card_type ON card(card_type);
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_card_orbital ON card(orbital);
    """,
]


def run_migrations():
    """Run all migrations."""
    print("Running Carde.io fields migration...")
    print()

    with Session(engine) as session:
        for i, migration in enumerate(MIGRATIONS, 1):
            migration_name = migration.strip().split("\n")[0].strip()
            print(f"[{i}/{len(MIGRATIONS)}] {migration_name[:60]}...")

            try:
                session.exec(text(migration))
                session.commit()
                print("  OK")
            except Exception as e:
                if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                    print("  SKIP (already exists)")
                else:
                    print(f"  ERROR: {e}")
                    raise

    print()
    print("Migration complete!")
    print()
    print("Next steps:")
    print("  1. Run dry-run: python scripts/enrich_cards_from_cardeio.py --dry-run")
    print("  2. Run for real: python scripts/enrich_cards_from_cardeio.py")


if __name__ == "__main__":
    run_migrations()
