"""Blog API endpoints for weekly movers and content."""
from typing import Any
from datetime import datetime, timedelta, timezone
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from sqlmodel import Session
from sqlalchemy import text

from app.db import get_session
from app.discord_bot.stats import calculate_market_stats

router = APIRouter()
logger = logging.getLogger(__name__)


def get_week_dates(date_str: str) -> tuple[datetime, datetime]:
    """Parse date string and return week start/end dates."""
    target_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    # Week ends on the target date
    week_end = target_date.replace(hour=23, minute=59, second=59)
    # Week starts 7 days before
    week_start = (target_date - timedelta(days=6)).replace(hour=0, minute=0, second=0)
    return week_start, week_end


@router.get("/weekly-movers")
def list_weekly_movers(
    session: Session = Depends(get_session),
    limit: int = Query(default=20, le=52),
) -> Any:
    """
    List available weekly movers reports.
    Returns summaries for each available week.
    """
    # Get distinct weeks with sales data (group by week ending Sunday)
    query = text("""
        WITH weekly_data AS (
            SELECT
                DATE(COALESCE(sold_date, scraped_at)) as sale_date,
                price,
                card_id
            FROM marketprice
            WHERE listing_type = 'sold'
            AND COALESCE(sold_date, scraped_at) >= NOW() - INTERVAL '365 days'
        ),
        weeks AS (
            SELECT DISTINCT
                DATE_TRUNC('week', sale_date + INTERVAL '1 day')::date - INTERVAL '1 day' as week_end
            FROM weekly_data
        )
        SELECT week_end
        FROM weeks
        WHERE week_end <= CURRENT_DATE
        ORDER BY week_end DESC
        LIMIT :limit
    """)

    results = session.execute(query, {"limit": limit}).all()

    weeks = []
    for row in results:
        week_end = row[0]
        if isinstance(week_end, str):
            week_end = datetime.strptime(week_end, "%Y-%m-%d")
        week_start = week_end - timedelta(days=6)

        # Get quick stats for this week
        stats_query = text("""
            SELECT
                COUNT(*) as total_sales,
                COALESCE(SUM(price), 0) as total_volume
            FROM marketprice
            WHERE listing_type = 'sold'
            AND DATE(COALESCE(sold_date, scraped_at)) BETWEEN :start AND :end
        """)
        stats = session.execute(stats_query, {
            "start": week_start.strftime("%Y-%m-%d"),
            "end": week_end.strftime("%Y-%m-%d") if isinstance(week_end, datetime) else week_end
        }).first()

        weeks.append({
            "date": week_end.strftime("%Y-%m-%d") if isinstance(week_end, datetime) else week_end,
            "week_start": week_start.strftime("%Y-%m-%d"),
            "week_end": week_end.strftime("%Y-%m-%d") if isinstance(week_end, datetime) else week_end,
            "total_sales": stats[0] if stats else 0,
            "total_volume": float(stats[1]) if stats else 0,
            "top_gainer": None,  # Would require additional query - keep simple for list view
            "top_loser": None,
        })

    return weeks


@router.get("/weekly-movers/latest")
def get_latest_weekly_movers(
    session: Session = Depends(get_session),
) -> Any:
    """
    Get the most recent weekly movers report.
    """
    # Get the most recent week end date
    query = text("""
        SELECT MAX(DATE_TRUNC('week', COALESCE(sold_date, scraped_at) + INTERVAL '1 day')::date - INTERVAL '1 day')
        FROM marketprice
        WHERE listing_type = 'sold'
        AND COALESCE(sold_date, scraped_at) >= NOW() - INTERVAL '30 days'
    """)
    result = session.execute(query).scalar()

    if not result:
        return JSONResponse(content={"error": "No data available"}, status_code=404)

    date_str = result.strftime("%Y-%m-%d") if isinstance(result, datetime) else str(result)
    return get_weekly_movers_by_date(date_str, session)


@router.get("/weekly-movers/{date}")
def get_weekly_movers_by_date(
    date: str,
    session: Session = Depends(get_session),
) -> Any:
    """
    Get weekly movers data for a specific week.

    Args:
        date: Week ending date in YYYY-MM-DD format
    """
    try:
        week_start, week_end = get_week_dates(date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    # Use existing stats calculation logic
    try:
        stats = calculate_market_stats(
            session=session,
            period="weekly",
            start_date=week_start,
            end_date=week_end,
        )
    except Exception as e:
        logger.error(f"Error calculating market stats: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate market stats")

    # Format response
    gainers = []
    losers = []

    for mover in stats.top_movers:
        pct_change = mover.get("pct_change", 0) or 0
        item = {
            "card_id": mover.get("card_id"),
            "name": mover.get("name"),
            "current_price": mover.get("current_price", 0),
            "prev_price": mover.get("prev_price", 0),
            "pct_change": pct_change,
        }
        if pct_change >= 0:
            gainers.append(item)
        else:
            losers.append(item)

    # Sort and limit
    gainers = sorted(gainers, key=lambda x: x["pct_change"], reverse=True)[:10]
    losers = sorted(losers, key=lambda x: x["pct_change"])[:10]

    volume_leaders = [
        {
            "card_id": v.get("card_id"),
            "name": v.get("name"),
            "sales_count": v.get("sales_count", 0),
            "total_volume": v.get("total_volume", 0),
            "avg_price": v.get("avg_price", 0),
        }
        for v in stats.top_volume
    ]

    new_highs = [
        {
            "card_id": h.get("card_id"),
            "name": h.get("name"),
            "current_price": h.get("price", 0),
            "prev_price": h.get("prev_high", 0),
        }
        for h in stats.new_highs
    ]

    new_lows = [
        {
            "card_id": low.get("card_id"),
            "name": low.get("name"),
            "current_price": low.get("price", 0),
            "prev_price": low.get("prev_low", 0),
        }
        for low in stats.new_lows
    ]

    return {
        "date": date,
        "week_start": week_start.strftime("%Y-%m-%d"),
        "week_end": week_end.strftime("%Y-%m-%d"),
        "total_sales": stats.total_sales,
        "total_volume": stats.total_volume_usd,
        "avg_sale_price": stats.avg_sale_price,
        "gainers": gainers,
        "losers": losers,
        "volume_leaders": volume_leaders,
        "new_highs": new_highs,
        "new_lows": new_lows,
    }
