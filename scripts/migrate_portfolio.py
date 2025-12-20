#!/usr/bin/env python3
"""
Portfolio Migration Script

Migrates from quantity-based PortfolioItem to individual PortfolioCard records.
Each PortfolioItem with quantity=N becomes N individual PortfolioCard rows.

Usage:
    python scripts/migrate_portfolio.py              # Dry run (preview changes)
    python scripts/migrate_portfolio.py --execute    # Actually run migration
    python scripts/migrate_portfolio.py --verify     # Verify migration integrity
"""

import sys
import os
import argparse
from datetime import datetime, timezone

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlmodel import Session, select, func, text
from app.db import engine, create_db_and_tables
from app.models.portfolio import PortfolioItem, PortfolioCard


def count_existing_data(session: Session) -> dict:
    """Count records in both tables for verification."""
    old_items = session.exec(select(func.count()).select_from(PortfolioItem)).one()
    old_quantity_sum = session.exec(
        select(func.coalesce(func.sum(PortfolioItem.quantity), 0))
    ).one()

    new_cards = session.exec(select(func.count()).select_from(PortfolioCard)).one()

    return {
        "portfolio_items": old_items,
        "total_quantity": old_quantity_sum,
        "portfolio_cards": new_cards,
    }


def migrate_portfolio_items(session: Session, dry_run: bool = True) -> dict:
    """
    Migrate PortfolioItem records to PortfolioCard.

    For each PortfolioItem with quantity=N, creates N PortfolioCard records.
    """
    # Get all portfolio items
    items = session.exec(select(PortfolioItem)).all()

    stats = {
        "items_processed": 0,
        "cards_created": 0,
        "skipped": 0,
        "errors": [],
    }

    for item in items:
        try:
            # Check if already migrated (cards exist for this user+card)
            existing = session.exec(
                select(func.count())
                .select_from(PortfolioCard)
                .where(PortfolioCard.user_id == item.user_id)
                .where(PortfolioCard.card_id == item.card_id)
                .where(PortfolioCard.deleted_at.is_(None))
            ).one()

            if existing > 0:
                print(f"  Skipping item {item.id} (user={item.user_id}, card={item.card_id}) - already migrated ({existing} cards exist)")
                stats["skipped"] += 1
                continue

            # Create N individual cards
            for i in range(item.quantity):
                card = PortfolioCard(
                    user_id=item.user_id,
                    card_id=item.card_id,
                    treatment="Classic Paper",  # Default - user can update later
                    source="Other",  # Unknown source from old data
                    purchase_price=item.purchase_price,
                    purchase_date=item.acquired_at.date() if item.acquired_at else None,
                    grading=None,  # Raw by default
                    notes=f"Migrated from legacy portfolio (original qty: {item.quantity})" if i == 0 else None,
                    created_at=item.acquired_at or datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )

                if not dry_run:
                    session.add(card)

                stats["cards_created"] += 1

            stats["items_processed"] += 1
            print(f"  {'[DRY RUN] ' if dry_run else ''}Migrated item {item.id}: {item.quantity} card(s) for user={item.user_id}, card={item.card_id}")

        except Exception as e:
            stats["errors"].append(f"Item {item.id}: {str(e)}")
            print(f"  ERROR on item {item.id}: {e}")

    if not dry_run:
        session.commit()
        print("\nChanges committed to database.")

    return stats


def verify_migration(session: Session) -> bool:
    """
    Verify migration integrity by comparing counts.
    """
    counts = count_existing_data(session)

    print("\n=== Migration Verification ===")
    print(f"Portfolio Items (old):     {counts['portfolio_items']}")
    print(f"Total Quantity (old):      {counts['total_quantity']}")
    print(f"Portfolio Cards (new):     {counts['portfolio_cards']}")

    if counts['total_quantity'] == counts['portfolio_cards']:
        print("\n[OK] Migration complete - counts match!")
        return True
    elif counts['portfolio_cards'] > counts['total_quantity']:
        print("\n[WARNING] More cards than expected - possible duplicate migration")
        return False
    else:
        diff = counts['total_quantity'] - counts['portfolio_cards']
        print(f"\n[PENDING] {diff} cards still need to be migrated")
        return False


def main():
    parser = argparse.ArgumentParser(description="Migrate portfolio from quantity-based to individual cards")
    parser.add_argument("--execute", action="store_true", help="Actually run the migration (default is dry run)")
    parser.add_argument("--verify", action="store_true", help="Only verify migration status")
    parser.add_argument("--create-table", action="store_true", help="Create portfoliocard table if not exists")
    args = parser.parse_args()

    print("=" * 60)
    print("Portfolio Migration Script")
    print("=" * 60)

    # Create table if requested
    if args.create_table:
        print("\nCreating database tables...")
        create_db_and_tables()
        print("Tables created/verified.")

    with Session(engine) as session:
        # Show current state
        counts = count_existing_data(session)
        print(f"\nCurrent State:")
        print(f"  Portfolio Items (old table): {counts['portfolio_items']}")
        print(f"  Total Quantity to migrate:   {counts['total_quantity']}")
        print(f"  Portfolio Cards (new table): {counts['portfolio_cards']}")

        if args.verify:
            verify_migration(session)
            return

        if counts['portfolio_items'] == 0:
            print("\nNo portfolio items to migrate.")
            return

        dry_run = not args.execute

        if dry_run:
            print("\n[DRY RUN MODE] - No changes will be made. Use --execute to apply.")
        else:
            print("\n[EXECUTE MODE] - Changes will be committed to database!")
            response = input("Are you sure? (yes/no): ")
            if response.lower() != "yes":
                print("Aborted.")
                return

        print("\nStarting migration...")
        stats = migrate_portfolio_items(session, dry_run=dry_run)

        print("\n=== Migration Summary ===")
        print(f"Items processed: {stats['items_processed']}")
        print(f"Cards created:   {stats['cards_created']}")
        print(f"Skipped:         {stats['skipped']}")
        print(f"Errors:          {len(stats['errors'])}")

        if stats['errors']:
            print("\nErrors:")
            for err in stats['errors']:
                print(f"  - {err}")

        # Verify
        if not dry_run:
            verify_migration(session)


if __name__ == "__main__":
    main()
