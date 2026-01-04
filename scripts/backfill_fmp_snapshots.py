"""
Backfill FMP/Floor Price historical snapshots.

Uses historical sales data to reconstruct what floor prices would have been
at any point in time. This enables price trend analysis.

Usage:
    python scripts/backfill_fmp_snapshots.py              # Dry run
    python scripts/backfill_fmp_snapshots.py --execute    # Apply changes
    python scripts/backfill_fmp_snapshots.py --execute --start-date 2025-06-01  # From specific date
"""

import argparse
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from sqlalchemy import text
from sqlmodel import Session, select

from app.db import engine
from app.models.card import Card
from app.models.market import FMPSnapshot, MarketPrice
from app.services.pricing import FMP_AVAILABLE


def calculate_floor_at_date(
    session: Session,
    card_id: int,
    as_of_date: datetime,
    treatment: str | None = None,
    lookback_days: int = 30,
) -> tuple[float | None, float | None, int]:
    """
    Calculate floor price as it would have been on a specific date.

    Uses only sales that occurred before as_of_date within the lookback window.

    Returns:
        tuple of (floor_price, vwap, sales_count)
    """
    cutoff_start = as_of_date - timedelta(days=lookback_days)

    # Build query for sales in the window
    query = """
        WITH ranked_sales AS (
            SELECT
                price,
                ROW_NUMBER() OVER (ORDER BY price ASC) as rn,
                COUNT(*) OVER () as total_count
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'sold'
              AND is_bulk_lot = FALSE
              AND COALESCE(sold_date, scraped_at) >= :cutoff_start
              AND COALESCE(sold_date, scraped_at) < :as_of_date
    """

    params = {
        "card_id": card_id,
        "cutoff_start": cutoff_start,
        "as_of_date": as_of_date,
    }

    # Add treatment filter if specified
    if treatment:
        query += " AND COALESCE(NULLIF(product_subtype, ''), treatment) = :treatment"
        params["treatment"] = treatment

    query += """
        )
        SELECT
            AVG(price) FILTER (WHERE rn <= 4) as floor_price,
            AVG(price) as vwap,
            MAX(total_count) as sales_count
        FROM ranked_sales
    """

    result = session.execute(text(query), params).first()

    if result and result[2] and result[2] > 0:
        floor = round(result[0], 2) if result[0] else None
        vwap = round(result[1], 2) if result[1] else None
        return floor, vwap, result[2]

    return None, None, 0


def get_cards_with_sales(session: Session) -> list[tuple[int, str, str]]:
    """Get all cards that have sales data."""
    result = session.execute(
        text("""
            SELECT DISTINCT c.id, c.name, c.set_name
            FROM card c
            JOIN marketprice mp ON mp.card_id = c.id
            WHERE mp.listing_type = 'sold'
            ORDER BY c.id
        """)
    ).all()
    return [(r[0], r[1], r[2]) for r in result]


def get_treatments_for_card(
    session: Session, card_id: int, as_of_date: datetime, lookback_days: int = 30
) -> list[str]:
    """Get all treatments that have sales for a card in the given period."""
    cutoff_start = as_of_date - timedelta(days=lookback_days)

    result = session.execute(
        text("""
            SELECT DISTINCT COALESCE(NULLIF(product_subtype, ''), treatment) as variant
            FROM marketprice
            WHERE card_id = :card_id
              AND listing_type = 'sold'
              AND is_bulk_lot = FALSE
              AND COALESCE(sold_date, scraped_at) >= :cutoff_start
              AND COALESCE(sold_date, scraped_at) < :as_of_date
              AND COALESCE(NULLIF(product_subtype, ''), treatment) IS NOT NULL
        """),
        {"card_id": card_id, "cutoff_start": cutoff_start, "as_of_date": as_of_date},
    ).all()

    return [r[0] for r in result if r[0]]


def backfill_fmp_snapshots(
    execute: bool = False,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
):
    """Backfill FMP snapshots from historical data."""

    print("=" * 70)
    print("FMP SNAPSHOT BACKFILL")
    print("=" * 70)
    print(f"Mode: {'EXECUTE' if execute else 'DRY RUN (use --execute to apply)'}")
    print(f"FMP Available: {FMP_AVAILABLE}")
    print()

    with Session(engine) as session:
        # Determine date range
        if not start_date:
            earliest = session.execute(
                text("""
                    SELECT MIN(COALESCE(sold_date, scraped_at))
                    FROM marketprice WHERE listing_type = 'sold'
                """)
            ).scalar()
            # Start 30 days after earliest sale (need lookback window)
            start_date = earliest + timedelta(days=30)

        if not end_date:
            end_date = datetime.now(timezone.utc)

        # Make dates timezone-aware if needed
        if start_date.tzinfo is None:
            start_date = start_date.replace(tzinfo=timezone.utc)
        if end_date.tzinfo is None:
            end_date = end_date.replace(tzinfo=timezone.utc)

        print(f"Date range: {start_date.date()} to {end_date.date()}")

        # Get cards with sales
        cards = get_cards_with_sales(session)
        print(f"Cards with sales: {len(cards)}")
        print()

        # Check for existing snapshots
        existing_count = session.execute(
            text("SELECT COUNT(*) FROM fmpsnapshot")
        ).scalar()
        if existing_count > 0:
            print(f"WARNING: {existing_count} existing snapshots found")
            if execute:
                print("Skipping dates that already have snapshots...")
            print()

        # Generate snapshots day by day
        current_date = start_date
        total_snapshots = 0
        days_processed = 0

        while current_date <= end_date:
            # Use end of day for the snapshot
            snapshot_time = current_date.replace(hour=23, minute=59, second=59)

            # Check if we already have snapshots for this date
            if execute:
                existing = session.execute(
                    text("""
                        SELECT COUNT(*) FROM fmpsnapshot
                        WHERE DATE(snapshot_date) = :date
                    """),
                    {"date": current_date.date()},
                ).scalar()
                if existing > 0:
                    current_date += timedelta(days=1)
                    continue

            day_snapshots = 0

            for card_id, card_name, set_name in cards:
                # Calculate aggregate floor (all treatments)
                floor, vwap, sales_count = calculate_floor_at_date(
                    session, card_id, snapshot_time
                )

                if floor is not None and sales_count >= 1:
                    snapshot = FMPSnapshot(
                        card_id=card_id,
                        treatment=None,  # Aggregate
                        fmp=None,  # Would need FMP service with date support
                        floor_price=floor,
                        vwap=vwap,
                        sales_count=sales_count,
                        lookback_days=30,
                        snapshot_date=snapshot_time,
                    )

                    if execute:
                        session.add(snapshot)

                    day_snapshots += 1
                    total_snapshots += 1

                # Also calculate per-treatment floors
                treatments = get_treatments_for_card(session, card_id, snapshot_time)
                for treatment in treatments:
                    t_floor, t_vwap, t_count = calculate_floor_at_date(
                        session, card_id, snapshot_time, treatment=treatment
                    )

                    if t_floor is not None and t_count >= 1:
                        snapshot = FMPSnapshot(
                            card_id=card_id,
                            treatment=treatment,
                            fmp=None,
                            floor_price=t_floor,
                            vwap=t_vwap,
                            sales_count=t_count,
                            lookback_days=30,
                            snapshot_date=snapshot_time,
                        )

                        if execute:
                            session.add(snapshot)

                        day_snapshots += 1
                        total_snapshots += 1

            if day_snapshots > 0:
                print(f"  {current_date.date()}: {day_snapshots} snapshots")

            if execute and day_snapshots > 0:
                session.commit()

            days_processed += 1
            current_date += timedelta(days=1)

        print()
        print("=" * 70)
        print("SUMMARY")
        print("=" * 70)
        print(f"Days processed: {days_processed}")
        print(f"Total snapshots: {total_snapshots}")

        if not execute:
            print("\nThis was a DRY RUN. Use --execute to apply changes.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Backfill FMP historical snapshots")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually create snapshots (default is dry run)",
    )
    parser.add_argument(
        "--start-date",
        type=str,
        help="Start date (YYYY-MM-DD). Default: 30 days after earliest sale",
    )
    parser.add_argument(
        "--end-date",
        type=str,
        help="End date (YYYY-MM-DD). Default: today",
    )

    args = parser.parse_args()

    start = None
    end = None

    if args.start_date:
        start = datetime.strptime(args.start_date, "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    if args.end_date:
        end = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)

    backfill_fmp_snapshots(execute=args.execute, start_date=start, end_date=end)
