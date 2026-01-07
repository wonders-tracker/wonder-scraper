#!/usr/bin/env python3
"""
Generate weekly/daily market reports for Wonders of the First.

Usage:
    python scripts/generate_market_report.py --type weekly --format txt
    python scripts/generate_market_report.py --type daily --format md
    python scripts/generate_market_report.py --type weekly --format all
    python scripts/generate_market_report.py --type daily --days 3

Arguments:
    --type      Report type: 'weekly' (7 days) or 'daily' (1 day)
    --format    Output format: 'txt', 'md', or 'all' (both)
    --days      Custom number of days to look back (overrides --type)
    --output    Custom output directory (default: data/marketReports)
"""

import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlmodel import Session
from sqlalchemy import text

# Add parent to path for imports
import sys

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine


def bar_txt(value: float, max_value: float, width: int = 25, filled: str = "█", empty: str = "░") -> str:
    """Create ASCII bar for txt output."""
    if max_value == 0:
        return empty * width
    fill_count = int((value / max_value) * width)
    return filled * fill_count + empty * (width - fill_count)


def bar_md(value: float, max_value: float, width: int = 20) -> str:
    """Create unicode bar for markdown output."""
    if max_value == 0:
        return "░" * width
    fill_count = int((value / max_value) * width)
    return "█" * fill_count + "░" * (width - fill_count)


def format_currency(val: float) -> str:
    """Format value as currency."""
    return f"${val:,.2f}"


def generate_report_data(days: int = 7) -> dict:
    """Gather all market data for the report."""
    with Session(engine) as session:
        now = datetime.now(timezone.utc)
        period_start = now - timedelta(days=days)
        prev_period_start = period_start - timedelta(days=days)

        data = {
            "generated_at": now,
            "period_start": period_start,
            "period_end": now,
            "days": days,
        }

        # Total sales this period
        total = session.execute(
            text("""
            SELECT COUNT(*), COALESCE(SUM(price), 0), COALESCE(AVG(price), 0)
            FROM marketprice WHERE listing_type = 'sold' AND sold_date >= :start
        """),
            {"start": period_start},
        ).first()

        # Previous period for comparison
        prev_total = session.execute(
            text("""
            SELECT COUNT(*), COALESCE(SUM(price), 0)
            FROM marketprice WHERE listing_type = 'sold'
            AND sold_date >= :prev_start AND sold_date < :start
        """),
            {"start": period_start, "prev_start": prev_period_start},
        ).first()

        data["summary"] = {
            "total_sales": total[0],
            "total_volume": total[1],
            "avg_price": total[2],
            "prev_sales": prev_total[0],
            "prev_volume": prev_total[1],
            "sales_change_pct": ((total[0] - prev_total[0]) / prev_total[0] * 100) if prev_total[0] > 0 else 0,
            "volume_change_pct": ((total[1] - prev_total[1]) / prev_total[1] * 100) if prev_total[1] > 0 else 0,
        }

        # Daily breakdown
        daily = session.execute(
            text("""
            SELECT DATE(sold_date) as day, COUNT(*), SUM(price)
            FROM marketprice WHERE listing_type = 'sold' AND sold_date >= :start
            GROUP BY DATE(sold_date) ORDER BY day
        """),
            {"start": period_start},
        ).all()
        data["daily"] = [{"date": row[0], "sales": row[1], "volume": row[2]} for row in daily]

        # By product type
        by_type = session.execute(
            text("""
            SELECT c.product_type, COUNT(*), SUM(mp.price)
            FROM marketprice mp JOIN card c ON mp.card_id = c.id
            WHERE mp.listing_type = 'sold' AND mp.sold_date >= :start
            GROUP BY c.product_type ORDER BY SUM(mp.price) DESC
        """),
            {"start": period_start},
        ).all()
        data["by_type"] = [{"type": row[0], "sales": row[1], "volume": row[2]} for row in by_type]

        # Top sellers by volume
        top_vol = session.execute(
            text("""
            SELECT c.name, c.product_type, COUNT(*), SUM(mp.price), AVG(mp.price)
            FROM marketprice mp JOIN card c ON mp.card_id = c.id
            WHERE mp.listing_type = 'sold' AND mp.sold_date >= :start
            GROUP BY c.id, c.name, c.product_type ORDER BY SUM(mp.price) DESC LIMIT 10
        """),
            {"start": period_start},
        ).all()
        data["top_volume"] = [
            {"name": row[0], "type": row[1], "sales": row[2], "volume": row[3], "avg": row[4]} for row in top_vol
        ]

        # Price trends (gainers)
        gainers = session.execute(
            text("""
            WITH this_period AS (
                SELECT card_id, AVG(price) as avg_price, COUNT(*) as cnt
                FROM marketprice WHERE listing_type = 'sold' AND sold_date >= :start
                GROUP BY card_id HAVING COUNT(*) >= 2
            ),
            last_period AS (
                SELECT card_id, AVG(price) as avg_price
                FROM marketprice WHERE listing_type = 'sold'
                AND sold_date >= :prev_start AND sold_date < :start
                GROUP BY card_id
            )
            SELECT c.name, tp.avg_price, lp.avg_price,
                   ((tp.avg_price - lp.avg_price) / lp.avg_price * 100) as pct_change, tp.cnt
            FROM this_period tp
            JOIN last_period lp ON tp.card_id = lp.card_id
            JOIN card c ON tp.card_id = c.id
            WHERE lp.avg_price > 0
            ORDER BY pct_change DESC LIMIT 5
        """),
            {"start": period_start, "prev_start": prev_period_start},
        ).all()
        data["gainers"] = [
            {"name": row[0], "current": row[1], "previous": row[2], "change_pct": row[3], "sales": row[4]}
            for row in gainers
            if row[3] > 0
        ]

        # Price trends (losers)
        losers = session.execute(
            text("""
            WITH this_period AS (
                SELECT card_id, AVG(price) as avg_price, COUNT(*) as cnt
                FROM marketprice WHERE listing_type = 'sold' AND sold_date >= :start
                GROUP BY card_id HAVING COUNT(*) >= 2
            ),
            last_period AS (
                SELECT card_id, AVG(price) as avg_price
                FROM marketprice WHERE listing_type = 'sold'
                AND sold_date >= :prev_start AND sold_date < :start
                GROUP BY card_id
            )
            SELECT c.name, tp.avg_price, lp.avg_price,
                   ((tp.avg_price - lp.avg_price) / lp.avg_price * 100) as pct_change, tp.cnt
            FROM this_period tp
            JOIN last_period lp ON tp.card_id = lp.card_id
            JOIN card c ON tp.card_id = c.id
            WHERE lp.avg_price > 0
            ORDER BY pct_change ASC LIMIT 5
        """),
            {"start": period_start, "prev_start": prev_period_start},
        ).all()
        data["losers"] = [
            {"name": row[0], "current": row[1], "previous": row[2], "change_pct": row[3], "sales": row[4]}
            for row in losers
            if row[3] < 0
        ]

        # Hot deals
        deals = session.execute(
            text("""
            WITH floors AS (
                SELECT card_id, MIN(price) as floor
                FROM marketprice WHERE listing_type = 'active'
                GROUP BY card_id
            )
            SELECT c.name, mp.price as sold_price, f.floor,
                   ((f.floor - mp.price) / f.floor * 100) as discount_pct
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN floors f ON mp.card_id = f.card_id
            WHERE mp.listing_type = 'sold' AND mp.sold_date >= :start
            AND mp.price < f.floor * 0.80
            ORDER BY discount_pct DESC LIMIT 8
        """),
            {"start": period_start},
        ).all()
        data["deals"] = [
            {"name": row[0], "sold_price": row[1], "floor": row[2], "discount_pct": row[3]} for row in deals
        ]

        # Market health
        active = session.execute(
            text("""
            SELECT COUNT(*), COALESCE(AVG(price), 0), COALESCE(MIN(price), 0), COALESCE(MAX(price), 0)
            FROM marketprice WHERE listing_type = 'active'
        """)
        ).first()

        unique_cards = session.execute(
            text("""
            SELECT COUNT(DISTINCT card_id) FROM marketprice WHERE listing_type = 'active'
        """)
        ).scalar()

        data["market_health"] = {
            "active_listings": active[0],
            "unique_cards": unique_cards,
            "avg_list_price": active[1],
            "min_price": active[2],
            "max_price": active[3],
        }

        return data


def generate_txt_report(data: dict) -> str:
    """Generate plain text report with ASCII art."""
    lines = []

    period_type = "WEEKLY" if data["days"] == 7 else f"{data['days']}-DAY"

    # Header
    lines.append("")
    lines.append("+" + "=" * 72 + "+")
    lines.append("|" + f"  WONDERS OF THE FIRST - {period_type} MARKET REPORT  ".center(72) + "|")
    lines.append(
        "|"
        + f"  {data['period_start'].strftime('%b %d')} - {data['period_end'].strftime('%b %d, %Y')}  ".center(72)
        + "|"
    )
    lines.append("+" + "=" * 72 + "+")

    # Summary
    s = data["summary"]
    lines.append("")
    lines.append("=" * 74)
    lines.append("  MARKET SUMMARY")
    lines.append("=" * 74)
    lines.append(
        f"  Total Sales:      {s['total_sales']:,} transactions    ({'+' if s['sales_change_pct'] >= 0 else ''}{s['sales_change_pct']:.1f}% vs prev period)"
    )
    lines.append(
        f"  Total Volume:     {format_currency(s['total_volume']):>12}       ({'+' if s['volume_change_pct'] >= 0 else ''}{s['volume_change_pct']:.1f}% vs prev period)"
    )
    lines.append(f"  Average Price:    {format_currency(s['avg_price']):>12}")

    # Daily breakdown
    if data["daily"]:
        lines.append("")
        lines.append("=" * 74)
        lines.append("  DAILY SALES VOLUME")
        lines.append("=" * 74)
        max_vol = max(d["volume"] for d in data["daily"])
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for d in data["daily"]:
            day_name = day_names[d["date"].weekday()]
            lines.append(
                f"  {d['date'].strftime('%m/%d')} {day_name} | {bar_txt(d['volume'], max_vol)} | {d['sales']:2} sales | {format_currency(d['volume']):>10}"
            )

    # By product type
    if data["by_type"]:
        lines.append("")
        lines.append("=" * 74)
        lines.append("  SALES BY PRODUCT TYPE")
        lines.append("=" * 74)
        max_vol = max(t["volume"] for t in data["by_type"])
        total_vol = sum(t["volume"] for t in data["by_type"])
        for t in data["by_type"]:
            pct = (t["volume"] / total_vol * 100) if total_vol > 0 else 0
            lines.append(
                f"  {t['type']:8} | {bar_txt(t['volume'], max_vol)} | {t['sales']:2} sales | {format_currency(t['volume']):>10} ({pct:4.1f}%)"
            )

    # Top sellers
    if data["top_volume"]:
        lines.append("")
        lines.append("=" * 74)
        lines.append("  TOP 10 SELLERS BY VOLUME")
        lines.append("=" * 74)
        max_vol = max(t["volume"] for t in data["top_volume"])
        for i, t in enumerate(data["top_volume"], 1):
            name = t["name"][:28]
            lines.append(
                f"  {i:2}. {name:28} | {bar_txt(t['volume'], max_vol, 20)} | {t['sales']:2}x | {format_currency(t['volume']):>10}"
            )

    # Price movers
    lines.append("")
    lines.append("=" * 74)
    lines.append("  BIGGEST PRICE MOVERS (vs previous period)")
    lines.append("=" * 74)

    lines.append("  GAINERS:")
    if data["gainers"]:
        for g in data["gainers"]:
            lines.append(
                f"    [+] {g['name'][:30]:30} | {format_currency(g['previous']):>8} -> {format_currency(g['current']):>8} | +{g['change_pct']:.1f}%"
            )
    else:
        lines.append("    No significant gainers with enough data")

    lines.append("")
    lines.append("  LOSERS:")
    if data["losers"]:
        for l in data["losers"]:
            lines.append(
                f"    [-] {l['name'][:30]:30} | {format_currency(l['previous']):>8} -> {format_currency(l['current']):>8} | {l['change_pct']:.1f}%"
            )
    else:
        lines.append("    No significant losers with enough data")

    # Hot deals
    lines.append("")
    lines.append("=" * 74)
    lines.append("  HOT DEALS (sold below floor)")
    lines.append("=" * 74)
    if data["deals"]:
        for d in data["deals"]:
            lines.append(
                f"  [$] {d['name'][:32]:32} | {format_currency(d['sold_price']):>8} (floor: {format_currency(d['floor'])}) | {d['discount_pct']:.0f}% off"
            )
    else:
        lines.append("  No significant deals found this period")

    # Market health
    h = data["market_health"]
    lines.append("")
    lines.append("=" * 74)
    lines.append("  MARKET HEALTH")
    lines.append("=" * 74)
    lines.append(f"  Active Listings:     {h['active_listings']:,}")
    lines.append(f"  Unique Cards Listed: {h['unique_cards']:,}")
    lines.append(f"  Avg List Price:      {format_currency(h['avg_list_price'])}")
    lines.append(f"  Price Range:         {format_currency(h['min_price'])} - {format_currency(h['max_price'])}")

    # Footer
    lines.append("")
    lines.append("-" * 74)
    lines.append(f"  Report generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("-" * 74)
    lines.append("")

    return "\n".join(lines)


def generate_md_report(data: dict) -> str:
    """Generate markdown report."""
    lines = []

    period_type = "Weekly" if data["days"] == 7 else f"{data['days']}-Day"

    # Header
    lines.append(f"# Wonders of the First - {period_type} Market Report")
    lines.append(f"**{data['period_start'].strftime('%B %d')} - {data['period_end'].strftime('%B %d, %Y')}**")
    lines.append("")

    # Summary
    s = data["summary"]
    lines.append("## Market Summary")
    lines.append("")
    lines.append("| Metric | Value | vs Previous |")
    lines.append("|--------|-------|-------------|")
    lines.append(
        f"| Total Sales | {s['total_sales']:,} | {'+' if s['sales_change_pct'] >= 0 else ''}{s['sales_change_pct']:.1f}% |"
    )
    lines.append(
        f"| Total Volume | {format_currency(s['total_volume'])} | {'+' if s['volume_change_pct'] >= 0 else ''}{s['volume_change_pct']:.1f}% |"
    )
    lines.append(f"| Average Price | {format_currency(s['avg_price'])} | - |")
    lines.append("")

    # Daily breakdown
    if data["daily"]:
        lines.append("## Daily Sales Volume")
        lines.append("")
        lines.append("| Date | Sales | Volume | Trend |")
        lines.append("|------|-------|--------|-------|")
        max_vol = max(d["volume"] for d in data["daily"])
        day_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for d in data["daily"]:
            day_name = day_names[d["date"].weekday()]
            trend = bar_md(d["volume"], max_vol, 15)
            lines.append(
                f"| {d['date'].strftime('%m/%d')} ({day_name}) | {d['sales']} | {format_currency(d['volume'])} | `{trend}` |"
            )
        lines.append("")

    # By product type
    if data["by_type"]:
        lines.append("## Sales by Product Type")
        lines.append("")
        lines.append("| Type | Sales | Volume | % of Total |")
        lines.append("|------|-------|--------|------------|")
        total_vol = sum(t["volume"] for t in data["by_type"])
        type_emoji = {"Single": "🃏", "Box": "📦", "Pack": "🎴", "Proof": "💎", "Lot": "📚"}
        for t in data["by_type"]:
            pct = (t["volume"] / total_vol * 100) if total_vol > 0 else 0
            emoji = type_emoji.get(t["type"], "•")
            lines.append(f"| {emoji} {t['type']} | {t['sales']} | {format_currency(t['volume'])} | {pct:.1f}% |")
        lines.append("")

    # Top sellers
    if data["top_volume"]:
        lines.append("## Top 10 Sellers by Volume")
        lines.append("")
        lines.append("| Rank | Card | Sales | Volume | Avg Price |")
        lines.append("|------|------|-------|--------|-----------|")
        for i, t in enumerate(data["top_volume"], 1):
            lines.append(
                f"| {i} | {t['name'][:35]} | {t['sales']} | {format_currency(t['volume'])} | {format_currency(t['avg'])} |"
            )
        lines.append("")

    # Price movers
    lines.append("## Price Movers")
    lines.append("")

    lines.append("### 📈 Gainers")
    lines.append("")
    if data["gainers"]:
        lines.append("| Card | Previous | Current | Change |")
        lines.append("|------|----------|---------|--------|")
        for g in data["gainers"]:
            lines.append(
                f"| {g['name'][:35]} | {format_currency(g['previous'])} | {format_currency(g['current'])} | **+{g['change_pct']:.1f}%** |"
            )
    else:
        lines.append("*No significant gainers with enough data*")
    lines.append("")

    lines.append("### 📉 Losers")
    lines.append("")
    if data["losers"]:
        lines.append("| Card | Previous | Current | Change |")
        lines.append("|------|----------|---------|--------|")
        for l in data["losers"]:
            lines.append(
                f"| {l['name'][:35]} | {format_currency(l['previous'])} | {format_currency(l['current'])} | **{l['change_pct']:.1f}%** |"
            )
    else:
        lines.append("*No significant losers with enough data*")
    lines.append("")

    # Hot deals
    lines.append("## 🔥 Hot Deals (Sold Below Floor)")
    lines.append("")
    if data["deals"]:
        lines.append("| Card | Sold Price | Floor | Discount |")
        lines.append("|------|------------|-------|----------|")
        for d in data["deals"]:
            lines.append(
                f"| {d['name'][:35]} | {format_currency(d['sold_price'])} | {format_currency(d['floor'])} | **{d['discount_pct']:.0f}% off** |"
            )
    else:
        lines.append("*No significant deals found this period*")
    lines.append("")

    # Market health
    h = data["market_health"]
    lines.append("## Market Health")
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append(f"| Active Listings | {h['active_listings']:,} |")
    lines.append(f"| Unique Cards Listed | {h['unique_cards']:,} |")
    lines.append(f"| Avg List Price | {format_currency(h['avg_list_price'])} |")
    lines.append(f"| Price Range | {format_currency(h['min_price'])} - {format_currency(h['max_price'])} |")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append(f"*Report generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}*")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate market reports for Wonders of the First")
    parser.add_argument(
        "--type",
        "-t",
        choices=["weekly", "daily"],
        default="weekly",
        help="Report type: 'weekly' (7 days) or 'daily' (1 day)",
    )
    parser.add_argument(
        "--format", "-f", choices=["txt", "md", "all"], default="all", help="Output format: 'txt', 'md', or 'all'"
    )
    parser.add_argument("--days", "-d", type=int, help="Custom number of days (overrides --type)")
    parser.add_argument("--output", "-o", default="data/marketReports", help="Output directory")
    parser.add_argument("--print", "-p", action="store_true", help="Also print report to terminal")

    args = parser.parse_args()

    # Determine days
    if args.days:
        days = args.days
        report_type = f"{days}d"
    elif args.type == "daily":
        days = 1
        report_type = "daily"
    else:
        days = 7
        report_type = "weekly"

    print(f"Generating {report_type} market report...")

    # Gather data
    data = generate_report_data(days)

    # Create output directory
    script_dir = Path(__file__).parent.parent
    output_dir = script_dir / args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate filename base
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    base_name = f"{date_str}-{report_type}"

    saved_files = []

    # Generate and save txt
    if args.format in ["txt", "all"]:
        txt_report = generate_txt_report(data)
        txt_path = output_dir / f"{base_name}.txt"
        txt_path.write_text(txt_report)
        saved_files.append(str(txt_path))
        print(f"Saved: {txt_path}")

        if args.print:
            print("\n" + txt_report)

    # Generate and save md
    if args.format in ["md", "all"]:
        md_report = generate_md_report(data)
        md_path = output_dir / f"{base_name}.md"
        md_path.write_text(md_report)
        saved_files.append(str(md_path))
        print(f"Saved: {md_path}")

        if args.print and args.format == "md":
            print("\n" + md_report)

    print("\nReport generation complete!")
    print(f"Period: {data['period_start'].strftime('%Y-%m-%d')} to {data['period_end'].strftime('%Y-%m-%d')}")
    print(f"Total Sales: {data['summary']['total_sales']} | Volume: {format_currency(data['summary']['total_volume'])}")

    return saved_files


if __name__ == "__main__":
    main()
