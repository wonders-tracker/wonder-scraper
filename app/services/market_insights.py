"""
Market insights generator for Discord updates.

Uses the same data and format as the market report script.
Generates formatted reports for 2x daily Discord posts.
"""

import os
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from sqlmodel import Session
from sqlalchemy import text

from app.db import engine


def bar(value: float, max_value: float, width: int = 15) -> str:
    """Create ASCII bar for discord output."""
    if max_value == 0:
        return "░" * width
    fill_count = int((value / max_value) * width)
    return "█" * fill_count + "░" * (width - fill_count)


def format_currency(val: float) -> str:
    """Format value as currency."""
    return f"${val:,.2f}"


class MarketInsightsGenerator:
    """Generates market insights using the same format as the report script."""

    def gather_market_data(self, days: int = 1) -> Dict[str, Any]:
        """Gather market data for the report."""
        with Session(engine) as session:
            now = datetime.utcnow()
            period_start = now - timedelta(days=days)
            prev_period_start = period_start - timedelta(days=days)

            data = {
                "generated_at": now,
                "period_start": period_start,
                "period_end": now,
                "days": days,
            }

            # Total sales this period
            # Use COALESCE(sold_date, scraped_at) to include sales with NULL sold_date
            total = session.execute(text("""
                SELECT COUNT(*), COALESCE(SUM(price), 0), COALESCE(AVG(price), 0)
                FROM marketprice WHERE listing_type = 'sold' AND COALESCE(sold_date, scraped_at) >= :start
            """), {"start": period_start}).first()

            # Previous period for comparison
            prev_total = session.execute(text("""
                SELECT COUNT(*), COALESCE(SUM(price), 0)
                FROM marketprice WHERE listing_type = 'sold'
                AND COALESCE(sold_date, scraped_at) >= :prev_start AND COALESCE(sold_date, scraped_at) < :start
            """), {"start": period_start, "prev_start": prev_period_start}).first()

            data["summary"] = {
                "total_sales": total[0],
                "total_volume": total[1],
                "avg_price": total[2],
                "prev_sales": prev_total[0],
                "prev_volume": prev_total[1],
                "sales_change_pct": ((total[0] - prev_total[0]) / prev_total[0] * 100) if prev_total[0] > 0 else 0,
                "volume_change_pct": ((total[1] - prev_total[1]) / prev_total[1] * 100) if prev_total[1] > 0 else 0,
            }

            # Daily breakdown (for weekly reports)
            if days >= 7:
                daily = session.execute(text("""
                    SELECT DATE(COALESCE(sold_date, scraped_at)) as day, COUNT(*), SUM(price)
                    FROM marketprice WHERE listing_type = 'sold' AND COALESCE(sold_date, scraped_at) >= :start
                    GROUP BY DATE(COALESCE(sold_date, scraped_at)) ORDER BY day
                """), {"start": period_start}).all()
                data["daily"] = [{"date": row[0], "sales": row[1], "volume": row[2]} for row in daily]
            else:
                data["daily"] = []

            # By product type
            by_type = session.execute(text("""
                SELECT c.product_type, COUNT(*), SUM(mp.price)
                FROM marketprice mp JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold' AND COALESCE(mp.sold_date, mp.scraped_at) >= :start
                GROUP BY c.product_type ORDER BY SUM(mp.price) DESC
            """), {"start": period_start}).all()
            data["by_type"] = [{"type": row[0], "sales": row[1], "volume": row[2]} for row in by_type]

            # Top sellers by volume
            top_vol = session.execute(text("""
                SELECT c.name, c.product_type, COUNT(*), SUM(mp.price), AVG(mp.price)
                FROM marketprice mp JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold' AND COALESCE(mp.sold_date, mp.scraped_at) >= :start
                GROUP BY c.id, c.name, c.product_type ORDER BY SUM(mp.price) DESC LIMIT 5
            """), {"start": period_start}).all()
            data["top_volume"] = [
                {"name": row[0], "type": row[1], "sales": row[2], "volume": row[3], "avg": row[4]}
                for row in top_vol
            ]

            # Price trends (gainers) - compare to previous period
            gainers = session.execute(text("""
                WITH this_period AS (
                    SELECT card_id, AVG(price) as avg_price, COUNT(*) as cnt
                    FROM marketprice WHERE listing_type = 'sold' AND COALESCE(sold_date, scraped_at) >= :start
                    GROUP BY card_id HAVING COUNT(*) >= 2
                ),
                last_period AS (
                    SELECT card_id, AVG(price) as avg_price
                    FROM marketprice WHERE listing_type = 'sold'
                    AND COALESCE(sold_date, scraped_at) >= :prev_start AND COALESCE(sold_date, scraped_at) < :start
                    GROUP BY card_id
                )
                SELECT c.name, tp.avg_price, lp.avg_price,
                       ((tp.avg_price - lp.avg_price) / lp.avg_price * 100) as pct_change, tp.cnt
                FROM this_period tp
                JOIN last_period lp ON tp.card_id = lp.card_id
                JOIN card c ON tp.card_id = c.id
                WHERE lp.avg_price > 0
                ORDER BY pct_change DESC LIMIT 5
            """), {"start": period_start, "prev_start": prev_period_start}).all()
            data["gainers"] = [
                {"name": row[0], "current": row[1], "previous": row[2], "change_pct": row[3], "sales": row[4]}
                for row in gainers if row[3] > 0
            ]

            # Price trends (losers)
            losers = session.execute(text("""
                WITH this_period AS (
                    SELECT card_id, AVG(price) as avg_price, COUNT(*) as cnt
                    FROM marketprice WHERE listing_type = 'sold' AND COALESCE(sold_date, scraped_at) >= :start
                    GROUP BY card_id HAVING COUNT(*) >= 2
                ),
                last_period AS (
                    SELECT card_id, AVG(price) as avg_price
                    FROM marketprice WHERE listing_type = 'sold'
                    AND COALESCE(sold_date, scraped_at) >= :prev_start AND COALESCE(sold_date, scraped_at) < :start
                    GROUP BY card_id
                )
                SELECT c.name, tp.avg_price, lp.avg_price,
                       ((tp.avg_price - lp.avg_price) / lp.avg_price * 100) as pct_change, tp.cnt
                FROM this_period tp
                JOIN last_period lp ON tp.card_id = lp.card_id
                JOIN card c ON tp.card_id = c.id
                WHERE lp.avg_price > 0
                ORDER BY pct_change ASC LIMIT 5
            """), {"start": period_start, "prev_start": prev_period_start}).all()
            data["losers"] = [
                {"name": row[0], "current": row[1], "previous": row[2], "change_pct": row[3], "sales": row[4]}
                for row in losers if row[3] < 0
            ]

            # Hot deals - sold below floor
            deals = session.execute(text("""
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
                WHERE mp.listing_type = 'sold' AND COALESCE(mp.sold_date, mp.scraped_at) >= :start
                AND mp.price < f.floor * 0.80
                ORDER BY discount_pct DESC LIMIT 5
            """), {"start": period_start}).all()
            data["deals"] = [
                {"name": row[0], "sold_price": row[1], "floor": row[2], "discount_pct": row[3]}
                for row in deals
            ]

            # Market health
            active = session.execute(text("""
                SELECT COUNT(*), COALESCE(AVG(price), 0), COALESCE(MIN(price), 0), COALESCE(MAX(price), 0)
                FROM marketprice WHERE listing_type = 'active'
            """)).first()

            unique_cards = session.execute(text("""
                SELECT COUNT(DISTINCT card_id) FROM marketprice WHERE listing_type = 'active'
            """)).scalar()

            data["market_health"] = {
                "active_listings": active[0],
                "unique_cards": unique_cards,
                "avg_list_price": active[1],
                "min_price": active[2],
                "max_price": active[3],
            }

            return data

    def generate_insights(self, data: Dict[str, Any]) -> str:
        """Generate formatted market insights for Discord."""
        lines = []

        period_label = "24h" if data["days"] == 1 else f"{data['days']}-Day"
        s = data["summary"]

        # Header
        lines.append(f"**{period_label} Market Update** • {data['period_end'].strftime('%b %d, %Y')}")
        lines.append("")

        # Summary stats
        sales_arrow = "📈" if s["sales_change_pct"] >= 0 else "📉"
        vol_arrow = "📈" if s["volume_change_pct"] >= 0 else "📉"
        lines.append("```")
        lines.append("══════════════════════════════════════")
        lines.append("  MARKET SUMMARY")
        lines.append("══════════════════════════════════════")
        lines.append(f"  Sales:   {s['total_sales']:>5}  ({'+' if s['sales_change_pct'] >= 0 else ''}{s['sales_change_pct']:.1f}%)")
        lines.append(f"  Volume:  {format_currency(s['total_volume']):>10}  ({'+' if s['volume_change_pct'] >= 0 else ''}{s['volume_change_pct']:.1f}%)")
        lines.append(f"  Avg:     {format_currency(s['avg_price']):>10}")
        lines.append("```")

        # Product type breakdown
        if data["by_type"]:
            lines.append("```")
            lines.append("══════════════════════════════════════")
            lines.append("  BY PRODUCT TYPE")
            lines.append("══════════════════════════════════════")
            max_vol = max(t["volume"] for t in data["by_type"]) if data["by_type"] else 1
            total_vol = sum(t["volume"] for t in data["by_type"]) if data["by_type"] else 1
            for t in data["by_type"]:
                pct = (t["volume"] / total_vol * 100) if total_vol > 0 else 0
                lines.append(f"  {t['type']:8} │ {bar(t['volume'], max_vol)} │ {pct:4.1f}%")
            lines.append("```")

        # Top sellers
        if data["top_volume"]:
            lines.append("```")
            lines.append("══════════════════════════════════════")
            lines.append("  TOP SELLERS")
            lines.append("══════════════════════════════════════")
            max_vol = max(t["volume"] for t in data["top_volume"]) if data["top_volume"] else 1
            for i, t in enumerate(data["top_volume"][:5], 1):
                name = t["name"][:22]
                lines.append(f"  {i}. {name:22} │ {t['sales']:2}x │ {format_currency(t['volume']):>9}")
            lines.append("```")

        # Price movers
        if data["gainers"] or data["losers"]:
            lines.append("```")
            lines.append("══════════════════════════════════════")
            lines.append("  PRICE MOVERS")
            lines.append("══════════════════════════════════════")
            if data["gainers"]:
                for g in data["gainers"][:3]:
                    name = g["name"][:20]
                    lines.append(f"  ▲ {name:20} │ +{g['change_pct']:.1f}%")
            if data["losers"]:
                for l in data["losers"][:3]:
                    name = l["name"][:20]
                    lines.append(f"  ▼ {name:20} │ {l['change_pct']:.1f}%")
            lines.append("```")

        # Hot deals
        if data["deals"]:
            lines.append("```")
            lines.append("══════════════════════════════════════")
            lines.append("  🔥 HOT DEALS (below floor)")
            lines.append("══════════════════════════════════════")
            for d in data["deals"][:3]:
                name = d["name"][:22]
                lines.append(f"  {name:22} │ {format_currency(d['sold_price']):>7} │ {d['discount_pct']:.0f}% off")
            lines.append("```")

        # Market health footer
        h = data["market_health"]
        lines.append(f"*{h['active_listings']:,} active listings • {h['unique_cards']} unique cards*")

        return "\n".join(lines)


# Singleton
_insights_generator: Optional[MarketInsightsGenerator] = None


def get_insights_generator() -> MarketInsightsGenerator:
    """Get or create the insights generator singleton."""
    global _insights_generator
    if _insights_generator is None:
        _insights_generator = MarketInsightsGenerator()
    return _insights_generator
