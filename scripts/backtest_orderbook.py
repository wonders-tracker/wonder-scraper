#!/usr/bin/env python3
"""
OrderBook Accuracy Backtest Script

Validates OrderBook floor estimates against actual subsequent sales.
For each historical point in time, we:
1. Generate an OrderBook prediction using only data available at that time
2. Find the next actual sale that occurred after the prediction
3. Calculate the error (predicted - actual)

Outputs CSV data for analysis in Jupyter notebook.

Usage:
    python scripts/backtest_orderbook.py --days 90 --output data/orderbook_backtest.csv
    python scripts/backtest_orderbook.py --dry-run  # Preview without saving
"""

import argparse
import csv
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from sqlalchemy import text
from sqlmodel import Session

from app.db import engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


@dataclass
class BacktestResult:
    """Single backtest observation."""

    card_id: int
    card_name: str
    treatment: Optional[str]
    prediction_date: datetime
    predicted_floor: float
    confidence: float
    source: str  # "order_book" or "sales_fallback"
    total_listings: int
    next_sale_date: datetime
    next_sale_price: float
    error: float  # predicted - actual
    absolute_error: float
    percentage_error: float
    days_to_sale: int


def get_cards_with_sales(session: Session, min_sales: int = 10) -> list[dict]:
    """Get cards that have sufficient sales data for backtesting."""
    query = text("""
        SELECT
            c.id,
            c.name,
            COUNT(*) as sale_count
        FROM card c
        JOIN marketprice mp ON mp.card_id = c.id
        WHERE mp.listing_type = 'sold'
          AND mp.is_bulk_lot = FALSE
        GROUP BY c.id, c.name
        HAVING COUNT(*) >= :min_sales
        ORDER BY sale_count DESC
    """)
    result = session.execute(query, {"min_sales": min_sales})
    return [dict(row._mapping) for row in result.fetchall()]


def get_treatments_for_card(session: Session, card_id: int) -> list[str]:
    """Get distinct treatments with sales for a card."""
    query = text("""
        SELECT DISTINCT
            COALESCE(NULLIF(product_subtype, ''), treatment) as variant
        FROM marketprice
        WHERE card_id = :card_id
          AND listing_type = 'sold'
          AND is_bulk_lot = FALSE
          AND COALESCE(NULLIF(product_subtype, ''), treatment) IS NOT NULL
        ORDER BY variant
    """)
    result = session.execute(query, {"card_id": card_id})
    return [row[0] for row in result.fetchall() if row[0]]


def get_sales_timeline(
    session: Session, card_id: int, treatment: Optional[str], days: int
) -> list[dict]:
    """Get chronological sales for a card/treatment."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = text("""
        SELECT
            id,
            price,
            COALESCE(sold_date, scraped_at) as sale_date
        FROM marketprice
        WHERE card_id = :card_id
          AND listing_type = 'sold'
          AND is_bulk_lot = FALSE
          AND COALESCE(sold_date, scraped_at) >= :cutoff
          AND (:treatment IS NULL OR
               COALESCE(NULLIF(product_subtype, ''), treatment) = :treatment)
        ORDER BY COALESCE(sold_date, scraped_at) ASC
    """)
    result = session.execute(
        query, {"card_id": card_id, "cutoff": cutoff, "treatment": treatment}
    )
    return [dict(row._mapping) for row in result.fetchall()]


def simulate_orderbook_at_date(
    session: Session,
    card_id: int,
    treatment: Optional[str],
    as_of_date: datetime,
    lookback_days: int = 30,
) -> Optional[dict]:
    """
    Simulate what OrderBook would have predicted at a specific date.

    Algorithm v2: Uses LOWEST ASK as floor estimate (not bucket midpoint).
    Confidence based on listing count, spread, and recency.
    """
    from math import log2

    cutoff = as_of_date - timedelta(days=lookback_days)

    # Get active listings that existed at that time
    query = text("""
        SELECT
            price,
            scraped_at
        FROM marketprice
        WHERE card_id = :card_id
          AND listing_type = 'active'
          AND is_bulk_lot = FALSE
          AND scraped_at >= :cutoff
          AND scraped_at < :as_of_date
          AND (:treatment IS NULL OR
               COALESCE(NULLIF(product_subtype, ''), treatment) = :treatment)
        ORDER BY price ASC
    """)
    result = session.execute(
        query,
        {
            "card_id": card_id,
            "cutoff": cutoff,
            "as_of_date": as_of_date,
            "treatment": treatment,
        },
    )
    listings = [dict(row._mapping) for row in result.fetchall()]

    # v2: Accept even 1 listing (lowered from 3)
    if len(listings) < 1:
        # Fall back to recent sales
        return simulate_sales_fallback_at_date(
            session, card_id, treatment, as_of_date, lookback_days
        )

    prices = [row["price"] for row in listings]
    lowest_ask = min(prices)  # v2: Use lowest ask as floor!

    # Calculate spread
    if len(prices) > 1:
        spread_pct = ((max(prices) - min(prices)) / min(prices)) * 100
    else:
        spread_pct = 0.0

    # v2: New confidence calculation
    # 1. Listing count score (logarithmic)
    count_score = min(0.9, 0.3 + 0.2 * log2(max(1, len(prices))))

    # 2. Spread score
    if spread_pct <= 0:
        spread_score = 1.0
    elif spread_pct <= 20:
        spread_score = 1.0 - (spread_pct / 40)
    elif spread_pct <= 50:
        spread_score = 0.5 - ((spread_pct - 20) / 60)
    else:
        spread_score = max(0.0, 0.2 - (spread_pct - 50) / 500)

    # 3. Recency (simplified - assume all fresh for simulation)
    recency_score = 1.0

    # Weighted combination
    confidence = round(0.4 * count_score + 0.3 * spread_score + 0.3 * recency_score, 3)

    return {
        "floor_estimate": round(lowest_ask, 2),
        "confidence": confidence,
        "source": "order_book",
        "total_listings": len(prices),
    }


def simulate_sales_fallback_at_date(
    session: Session,
    card_id: int,
    treatment: Optional[str],
    as_of_date: datetime,
    lookback_days: int = 30,
) -> Optional[dict]:
    """Simulate sales fallback prediction at a specific date (v2 algorithm)."""
    from math import log2

    cutoff = as_of_date - timedelta(days=lookback_days)

    query = text("""
        SELECT
            price
        FROM marketprice
        WHERE card_id = :card_id
          AND listing_type = 'sold'
          AND is_bulk_lot = FALSE
          AND COALESCE(sold_date, scraped_at) >= :cutoff
          AND COALESCE(sold_date, scraped_at) < :as_of_date
          AND (:treatment IS NULL OR
               COALESCE(NULLIF(product_subtype, ''), treatment) = :treatment)
        ORDER BY price ASC
    """)
    result = session.execute(
        query,
        {
            "card_id": card_id,
            "cutoff": cutoff,
            "as_of_date": as_of_date,
            "treatment": treatment,
        },
    )
    prices = [row[0] for row in result.fetchall()]

    if not prices:
        return None

    # Use avg of 4 lowest as floor (matches floor_price service)
    sorted_prices = sorted(prices)
    floor_sample = sorted_prices[:4]
    floor_estimate = sum(floor_sample) / len(floor_sample)

    # v2: New confidence calculation with sales fallback penalty
    # Calculate spread
    if len(prices) > 1:
        spread_pct = ((max(prices) - min(prices)) / min(prices)) * 100
    else:
        spread_pct = 0.0

    # Listing count score
    count_score = min(0.9, 0.3 + 0.2 * log2(max(1, len(prices))))

    # Spread score
    if spread_pct <= 0:
        spread_score = 1.0
    elif spread_pct <= 20:
        spread_score = 1.0 - (spread_pct / 40)
    elif spread_pct <= 50:
        spread_score = 0.5 - ((spread_pct - 20) / 60)
    else:
        spread_score = max(0.0, 0.2 - (spread_pct - 50) / 500)

    recency_score = 1.0  # Assume recent for simulation

    # Base confidence with 0.5x sales fallback penalty
    base_confidence = 0.4 * count_score + 0.3 * spread_score + 0.3 * recency_score
    confidence = round(base_confidence * 0.5, 3)

    return {
        "floor_estimate": round(floor_estimate, 2),
        "confidence": confidence,
        "source": "sales_fallback",
        "total_listings": len(prices),
    }


def run_backtest(
    session: Session,
    days: int = 90,
    sample_interval_days: int = 7,
    min_sales_per_card: int = 10,
) -> list[BacktestResult]:
    """
    Run full backtest across all cards with sufficient data.

    Args:
        days: How far back to look for test data
        sample_interval_days: How often to sample predictions
        min_sales_per_card: Minimum sales required to include a card

    Returns:
        List of BacktestResult observations
    """
    results = []

    # Get eligible cards
    cards = get_cards_with_sales(session, min_sales_per_card)
    logger.info(f"Found {len(cards)} cards with >= {min_sales_per_card} sales")

    for card in cards:
        card_id = card["id"]
        card_name = card["name"]

        # Get treatments for this card
        treatments = get_treatments_for_card(session, card_id)
        if not treatments:
            treatments = [None]  # No treatment filter

        for treatment in treatments:
            # Get sales timeline
            sales = get_sales_timeline(session, card_id, treatment, days)

            if len(sales) < 5:
                continue

            # Sample prediction points (every N sales)
            for i in range(0, len(sales) - 1, max(1, len(sales) // 10)):
                sale = sales[i]
                prediction_date = sale["sale_date"]

                # Skip if prediction_date is None
                if prediction_date is None:
                    continue

                # Ensure timezone aware
                if prediction_date.tzinfo is None:
                    prediction_date = prediction_date.replace(tzinfo=timezone.utc)

                # Get prediction at this point in time
                prediction = simulate_orderbook_at_date(
                    session, card_id, treatment, prediction_date
                )

                if not prediction:
                    continue

                # Find next sale after prediction
                next_sale = None
                for future_sale in sales[i + 1 :]:
                    next_sale = future_sale
                    break

                if not next_sale:
                    continue

                next_sale_date = next_sale["sale_date"]
                if next_sale_date is None:
                    continue

                if next_sale_date.tzinfo is None:
                    next_sale_date = next_sale_date.replace(tzinfo=timezone.utc)

                next_sale_price = next_sale["price"]
                predicted_floor = prediction["floor_estimate"]

                error = predicted_floor - next_sale_price
                abs_error = abs(error)
                pct_error = (
                    (abs_error / next_sale_price * 100) if next_sale_price > 0 else 0
                )
                days_to_sale = (next_sale_date - prediction_date).days

                results.append(
                    BacktestResult(
                        card_id=card_id,
                        card_name=card_name,
                        treatment=treatment,
                        prediction_date=prediction_date,
                        predicted_floor=predicted_floor,
                        confidence=prediction["confidence"],
                        source=prediction["source"],
                        total_listings=prediction["total_listings"],
                        next_sale_date=next_sale_date,
                        next_sale_price=next_sale_price,
                        error=error,
                        absolute_error=abs_error,
                        percentage_error=pct_error,
                        days_to_sale=days_to_sale,
                    )
                )

    return results


def write_results_csv(results: list[BacktestResult], output_path: Path) -> None:
    """Write backtest results to CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "card_id",
                "card_name",
                "treatment",
                "prediction_date",
                "predicted_floor",
                "confidence",
                "source",
                "total_listings",
                "next_sale_date",
                "next_sale_price",
                "error",
                "absolute_error",
                "percentage_error",
                "days_to_sale",
            ]
        )

        for r in results:
            writer.writerow(
                [
                    r.card_id,
                    r.card_name,
                    r.treatment or "",
                    r.prediction_date.isoformat(),
                    r.predicted_floor,
                    r.confidence,
                    r.source,
                    r.total_listings,
                    r.next_sale_date.isoformat(),
                    r.next_sale_price,
                    round(r.error, 2),
                    round(r.absolute_error, 2),
                    round(r.percentage_error, 2),
                    r.days_to_sale,
                ]
            )


def print_summary(results: list[BacktestResult]) -> None:
    """Print summary statistics."""
    if not results:
        logger.info("No results to summarize")
        return

    import statistics

    errors = [r.error for r in results]
    abs_errors = [r.absolute_error for r in results]
    pct_errors = [r.percentage_error for r in results]

    # Overall stats
    mae = statistics.mean(abs_errors)
    rmse = (sum(e**2 for e in errors) / len(errors)) ** 0.5
    median_error = statistics.median(errors)
    median_abs_error = statistics.median(abs_errors)
    median_pct_error = statistics.median(pct_errors)

    logger.info("\n" + "=" * 60)
    logger.info("ORDERBOOK BACKTEST SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total observations: {len(results)}")
    logger.info(f"Unique cards: {len(set(r.card_id for r in results))}")
    logger.info("")
    logger.info("Overall Accuracy:")
    logger.info(f"  MAE (Mean Absolute Error):    ${mae:.2f}")
    logger.info(f"  RMSE (Root Mean Square Error): ${rmse:.2f}")
    logger.info(f"  Median Error:                  ${median_error:.2f}")
    logger.info(f"  Median Absolute Error:         ${median_abs_error:.2f}")
    logger.info(f"  Median % Error:                {median_pct_error:.1f}%")

    # By source
    order_book_results = [r for r in results if r.source == "order_book"]
    fallback_results = [r for r in results if r.source == "sales_fallback"]

    if order_book_results:
        ob_mae = statistics.mean([r.absolute_error for r in order_book_results])
        logger.info(f"\nOrderBook predictions: {len(order_book_results)}")
        logger.info(f"  MAE: ${ob_mae:.2f}")

    if fallback_results:
        fb_mae = statistics.mean([r.absolute_error for r in fallback_results])
        logger.info(f"\nSales Fallback predictions: {len(fallback_results)}")
        logger.info(f"  MAE: ${fb_mae:.2f}")

    # By confidence bucket
    logger.info("\nAccuracy by Confidence Level:")
    confidence_buckets = [
        ("Low (0-0.3)", 0, 0.3),
        ("Medium (0.3-0.6)", 0.3, 0.6),
        ("High (0.6-1.0)", 0.6, 1.0),
    ]

    for name, low, high in confidence_buckets:
        bucket_results = [r for r in results if low <= r.confidence < high]
        if bucket_results:
            bucket_mae = statistics.mean([r.absolute_error for r in bucket_results])
            bucket_pct = statistics.mean([r.percentage_error for r in bucket_results])
            logger.info(f"  {name}: n={len(bucket_results)}, MAE=${bucket_mae:.2f}, Avg %Err={bucket_pct:.1f}%")

    # Bias check
    overestimates = sum(1 for r in results if r.error > 0)
    underestimates = sum(1 for r in results if r.error < 0)
    logger.info(f"\nBias Check:")
    logger.info(f"  Overestimates (predicted > actual): {overestimates} ({overestimates/len(results)*100:.1f}%)")
    logger.info(f"  Underestimates (predicted < actual): {underestimates} ({underestimates/len(results)*100:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Backtest OrderBook floor predictions against actual sales"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=90,
        help="How many days of historical data to use (default: 90)",
    )
    parser.add_argument(
        "--min-sales",
        type=int,
        default=10,
        help="Minimum sales per card to include (default: 10)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/orderbook_backtest.csv",
        help="Output CSV path (default: data/orderbook_backtest.csv)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print summary only, don't save CSV",
    )

    args = parser.parse_args()

    logger.info("OrderBook Accuracy Backtest")
    logger.info(f"  Days: {args.days}")
    logger.info(f"  Min sales per card: {args.min_sales}")
    logger.info(f"  Output: {args.output}")
    logger.info("")

    with Session(engine) as session:
        results = run_backtest(
            session,
            days=args.days,
            min_sales_per_card=args.min_sales,
        )

        print_summary(results)

        if not args.dry_run and results:
            output_path = Path(args.output)
            write_results_csv(results, output_path)
            logger.info(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
