#!/usr/bin/env python3
"""
Generate a static MDX blog post from weekly movers data.
Full-featured market reports with visualizations.

Usage:
    python scripts/generate_weekly_movers_post.py
    python scripts/generate_weekly_movers_post.py --date 2025-12-22
    python scripts/generate_weekly_movers_post.py --no-ai
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from dotenv import load_dotenv
from openai import OpenAI

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv()

from sqlmodel import Session, select, func
from app.db import engine
from app.discord_bot.stats import calculate_market_stats
from app.models.market import MarketPrice
from app.models.card import Card, Rarity


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_week_dates(date_str: str | None = None) -> tuple[datetime, datetime, str]:
    if date_str:
        target = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        target = datetime.now(timezone.utc)
    week_end = target.replace(hour=23, minute=59, second=59)
    week_start = (target - timedelta(days=6)).replace(hour=0, minute=0, second=0)
    return week_start, week_end, target.strftime("%Y-%m-%d")


def fmt_price(p: float) -> str:
    if p >= 1000:
        return f"${p:,.0f}"
    return f"${p:.2f}"


def fmt_pct(p: float, sign: bool = True) -> str:
    s = "+" if p >= 0 and sign else ""
    return f"{s}{p:.1f}%"


def ascii_bar(val: float, max_val: float, w: int = 20) -> str:
    if max_val <= 0:
        return "░" * w
    filled = int((val / max_val) * w)
    return "█" * filled + "░" * (w - filled)


def make_sparkline(values: list[float], width: int = 10) -> str:
    """Create ASCII sparkline from values."""
    if not values or len(values) < 2:
        return "─" * width
    chars = "▁▂▃▄▅▆▇█"
    min_v, max_v = min(values), max(values)
    if max_v == min_v:
        return "▄" * len(values)
    return "".join(chars[min(7, int(((v - min_v) / (max_v - min_v)) * 7.99))] for v in values)


def get_trend_indicator(pct: float) -> tuple[str, str, str]:
    """Returns (trend_word, trend_icon, css_class)."""
    if pct > 10:
        return "BULLISH", "▲", "text-green-500"
    elif pct < -10:
        return "BEARISH", "▼", "text-red-500"
    return "NEUTRAL", "─", "text-muted-foreground"


# =============================================================================
# DATA QUERIES
# =============================================================================


def get_top_sales(session: Session, start: datetime, end: datetime, limit: int = 10):
    """Get top individual sales by price."""
    return session.exec(
        select(MarketPrice, Card)
        .join(Card)
        .where(MarketPrice.listing_type == "sold")
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= start)
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= end)
        .order_by(MarketPrice.price.desc())
        .limit(limit)
    ).all()


def get_daily_volume(session: Session, start: datetime, end: datetime) -> list[tuple[str, int, float]]:
    """Get daily sales count and volume."""
    date_col = func.date(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at))
    results = session.exec(
        select(
            date_col.label("day"),
            func.count(MarketPrice.id).label("count"),
            func.sum(MarketPrice.price).label("volume"),
        )
        .where(MarketPrice.listing_type == "sold")
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= start)
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= end)
        .group_by(date_col)
        .order_by(date_col)
    ).all()
    return [(str(r[0]), r[1], float(r[2] or 0)) for r in results]


def get_weekly_stats_history(session: Session, end_date: datetime, weeks: int = 4) -> list[dict]:
    """Get stats for the past N weeks."""
    history = []
    for i in range(weeks):
        week_end = end_date - timedelta(days=7 * i)
        week_start = week_end - timedelta(days=6)
        week_start = week_start.replace(hour=0, minute=0, second=0)
        week_end = week_end.replace(hour=23, minute=59, second=59)

        stats = calculate_market_stats(session=session, period="weekly", start_date=week_start, end_date=week_end)
        history.append(
            {
                "week": i,
                "start": week_start,
                "end": week_end,
                "sales": stats.total_sales,
                "volume": stats.total_volume_usd,
                "avg_price": stats.avg_sale_price,
                "unique_cards": stats.unique_cards_traded,
            }
        )
    return history


def get_rarity_breakdown(session: Session, start: datetime, end: datetime) -> list[dict]:
    """Get sales breakdown by rarity."""
    results = session.exec(
        select(
            Rarity.name,
            func.count(MarketPrice.id).label("count"),
            func.sum(MarketPrice.price).label("volume"),
            func.avg(MarketPrice.price).label("avg_price"),
        )
        .join(Card, MarketPrice.card_id == Card.id)
        .join(Rarity, Card.rarity_id == Rarity.id)
        .where(MarketPrice.listing_type == "sold")
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= start)
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= end)
        .group_by(Rarity.name)
        .order_by(func.sum(MarketPrice.price).desc())
    ).all()
    return [
        {"rarity": r[0] or "Unknown", "count": r[1], "volume": float(r[2] or 0), "avg": float(r[3] or 0)}
        for r in results
    ]


def get_treatment_premiums(session: Session, start: datetime, end: datetime) -> dict:
    """Calculate treatment premiums (foil vs paper, etc.)."""
    results = session.exec(
        select(
            MarketPrice.treatment,
            func.avg(MarketPrice.price).label("avg_price"),
            func.count(MarketPrice.id).label("count"),
        )
        .where(MarketPrice.listing_type == "sold")
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= start)
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= end)
        .where(MarketPrice.treatment.isnot(None))
        .group_by(MarketPrice.treatment)
    ).all()

    premiums = {}
    avgs = {r[0]: float(r[1]) for r in results if r[1]}
    counts = {r[0]: r[2] for r in results}

    paper_avg = avgs.get("Classic Paper") or avgs.get("Paper") or avgs.get("Classic")
    foil_avg = avgs.get("Classic Foil") or avgs.get("Foil")

    if paper_avg and paper_avg > 0:
        if foil_avg:
            premiums["foil_vs_paper"] = {"mult": foil_avg / paper_avg, "foil": foil_avg, "paper": paper_avg}
        for t, avg in avgs.items():
            if "Serialized" in t or "Stonefoil" in t or "Formless" in t:
                premiums[t.lower().replace(" ", "_")] = {"mult": avg / paper_avg, "avg": avg, "base": paper_avg}

    return premiums


def get_price_history(session: Session, card_id: int, days: int = 30) -> list[float]:
    """Get daily average prices for a card over N days."""
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    date_col = func.date(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at))
    results = session.exec(
        select(
            date_col.label("day"),
            func.avg(MarketPrice.price).label("avg_price"),
        )
        .where(MarketPrice.card_id == card_id)
        .where(MarketPrice.listing_type == "sold")
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= start)
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= end)
        .group_by(date_col)
        .order_by(date_col)
    ).all()

    return [float(r[1]) for r in results if r[1]]


def get_hot_cards(session: Session, current_start: datetime, current_end: datetime) -> list[dict]:
    """Find cards with rising volume but stable prices (accumulation signal)."""
    # Get last 4 weeks of data per card
    weeks_data = defaultdict(lambda: {"volumes": [], "prices": []})

    for i in range(4):
        week_end = current_end - timedelta(days=7 * i)
        week_start = week_end - timedelta(days=6)

        results = session.exec(
            select(
                Card.id,
                Card.name,
                func.count(MarketPrice.id).label("count"),
                func.avg(MarketPrice.price).label("avg_price"),
            )
            .join(Card)
            .where(MarketPrice.listing_type == "sold")
            .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= week_start)
            .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= week_end)
            .group_by(Card.id, Card.name)
        ).all()

        for r in results:
            weeks_data[r[0]]["name"] = r[1]
            weeks_data[r[0]]["card_id"] = r[0]
            weeks_data[r[0]]["volumes"].insert(0, r[2])
            weeks_data[r[0]]["prices"].insert(0, float(r[3] or 0))

    hot_cards = []
    for card_id, data in weeks_data.items():
        vols = data["volumes"]
        prices = data["prices"]
        if len(vols) >= 3 and len(prices) >= 3:
            # Check if volume is increasing
            vol_trend = vols[-1] > vols[0] and sum(vols[-2:]) > sum(vols[:2])
            # Check if price is stable (within 15%)
            if prices[0] > 0:
                price_change = abs(prices[-1] - prices[0]) / prices[0]
                price_stable = price_change < 0.15

                if vol_trend and price_stable:
                    signal = "🔥 Strong" if vols[-1] >= 2 * vols[0] else "👀 Watch"
                    hot_cards.append(
                        {
                            "card_id": card_id,
                            "name": data["name"],
                            "vol_trend": "→".join(str(v) for v in vols),
                            "price_change": (prices[-1] - prices[0]) / prices[0] * 100 if prices[0] else 0,
                            "signal": signal,
                        }
                    )

    return sorted(hot_cards, key=lambda x: -len(x["vol_trend"]))[:5]


def get_outlier_sales(session: Session, start: datetime, end: datetime) -> list[dict]:
    """Find sales significantly above or below average."""
    # Get card averages
    card_avgs = {}
    avg_results = session.exec(
        select(
            Card.id,
            Card.name,
            func.avg(MarketPrice.price).label("avg_price"),
            func.count(MarketPrice.id).label("count"),
        )
        .join(Card)
        .where(MarketPrice.listing_type == "sold")
        .group_by(Card.id, Card.name)
        .having(func.count(MarketPrice.id) >= 3)
    ).all()

    for r in avg_results:
        card_avgs[r[0]] = {"name": r[1], "avg": float(r[2]), "count": r[3]}

    # Get this week's sales
    sales = session.exec(
        select(MarketPrice, Card)
        .join(Card)
        .where(MarketPrice.listing_type == "sold")
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= start)
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= end)
    ).all()

    outliers = []
    for sale, card in sales:
        if card.id in card_avgs:
            avg = card_avgs[card.id]["avg"]
            if avg > 0:
                deviation = (sale.price - avg) / avg
                if abs(deviation) > 0.4:  # 40% deviation
                    outliers.append(
                        {
                            "card_id": card.id,
                            "name": card.name,
                            "price": sale.price,
                            "avg": avg,
                            "deviation": deviation * 100,
                            "treatment": sale.treatment or "Paper",
                            "date": sale.sold_date.strftime("%m/%d") if sale.sold_date else "—",
                            "is_deal": deviation < 0,
                        }
                    )

    # Sort by absolute deviation, return top outliers
    return sorted(outliers, key=lambda x: -abs(x["deviation"]))[:6]


def get_monthly_heatmap(session: Session, end_date: datetime) -> list[list[int]]:
    """Get daily sales counts for the current month as a calendar grid."""
    # Get first day of month
    month_start = end_date.replace(day=1, hour=0, minute=0, second=0)

    date_col = func.date(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at))
    results = session.exec(
        select(
            date_col.label("day"),
            func.count(MarketPrice.id).label("count"),
        )
        .where(MarketPrice.listing_type == "sold")
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) >= month_start)
        .where(func.coalesce(MarketPrice.sold_date, MarketPrice.scraped_at) <= end_date)
        .group_by(date_col)
        .order_by(date_col)
    ).all()

    daily_counts = {str(r[0]): r[1] for r in results}

    # Build calendar grid (weeks x 7 days)
    weeks = []
    current = month_start
    week = [0] * current.weekday()  # Pad first week

    while current <= end_date:
        week.append(daily_counts.get(current.strftime("%Y-%m-%d"), 0))
        if len(week) == 7:
            weeks.append(week)
            week = []
        current += timedelta(days=1)

    if week:
        week.extend([0] * (7 - len(week)))  # Pad last week
        weeks.append(week)

    return weeks


# =============================================================================
# ANALYSIS GENERATION
# =============================================================================


def generate_template_analysis(stats) -> str:
    parts = []

    if stats.volume_trend_pct > 20:
        parts.append(
            f"This week saw robust trading activity with volume up {fmt_pct(stats.volume_trend_pct)} compared to the previous period. With {stats.total_sales:,} completed sales totaling {fmt_price(stats.total_volume_usd)}, the market is showing strong momentum."
        )
    elif stats.volume_trend_pct < -20:
        parts.append(
            f"Market activity cooled this week with volume down {fmt_pct(stats.volume_trend_pct, False)} from the previous period. The {stats.total_sales:,} completed sales generated {fmt_price(stats.total_volume_usd)} in total volume."
        )
    else:
        parts.append(
            f"The market maintained steady activity this week with {stats.total_sales:,} sales generating {fmt_price(stats.total_volume_usd)} in trading volume."
        )

    gainers = [m for m in stats.top_movers if m.get("pct_change", 0) > 0]
    losers = [m for m in stats.top_movers if m.get("pct_change", 0) < 0]

    if gainers:
        g = gainers[0]
        note = f" {g['reason']}." if g.get("reason") else ""
        if g.get("confidence") == "low":
            note = " However, with limited sales data, this movement should be viewed cautiously."
        parts.append(
            f"**{g['name']}** led the gainers with a {fmt_pct(g['pct_change'])} move to {fmt_price(g['current_price'])} on {g.get('volume', 0)} sale(s).{note}"
        )

    if losers:
        l = losers[0]
        note = f" {l['reason']}." if l.get("reason") else ""
        if l.get("confidence") == "low":
            note = " This may be noise from limited data."
        parts.append(
            f"On the downside, **{l['name']}** declined {fmt_pct(l['pct_change'], False)} to {fmt_price(l['current_price'])}.{note}"
        )

    return "\n\n".join(parts)


def generate_ai_analysis(stats, week_start, week_end) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return generate_template_analysis(stats)

    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    gainers = [m for m in stats.top_movers if m.get("pct_change", 0) > 0][:5]
    losers = [m for m in stats.top_movers if m.get("pct_change", 0) < 0][:5]

    data = {
        "total_sales": stats.total_sales,
        "total_volume": stats.total_volume_usd,
        "volume_trend": stats.volume_trend_pct,
        "treatment_breakdown": stats.treatment_breakdown,
        "gainers": [
            {
                "name": g["name"],
                "change": g["pct_change"],
                "sales": g.get("volume"),
                "reason": g.get("reason"),
                "confidence": g.get("confidence"),
            }
            for g in gainers
        ],
        "losers": [
            {
                "name": l["name"],
                "change": l["pct_change"],
                "sales": l.get("volume"),
                "reason": l.get("reason"),
                "confidence": l.get("confidence"),
            }
            for l in losers
        ],
    }

    try:
        print("  Generating AI analysis...")
        resp = client.chat.completions.create(
            model="openai/gpt-4o-mini",
            messages=[
                {
                    "role": "system",
                    "content": "Expert TCG market analyst. Skeptical of small samples. Write 2-3 short paragraphs.",
                },
                {
                    "role": "user",
                    "content": f"Analyze this week's WOTF market data. Be skeptical of low confidence moves.\n{json.dumps(data)}",
                },
            ],
            temperature=0.7,
            max_tokens=500,
        )
        return resp.choices[0].message.content.strip()
    except Exception as e:
        print(f"  AI analysis failed: {e}, using template")
        return generate_template_analysis(stats)


# =============================================================================
# MDX GENERATION
# =============================================================================


def generate_mdx_post(date_str: str | None = None, use_ai: bool = True) -> tuple[str, str]:
    week_start, week_end, date_string = get_week_dates(date_str)
    print(f"Generating weekly movers for {date_string}...")

    with Session(engine) as session:
        print("  Fetching market stats...")
        stats = calculate_market_stats(session=session, period="weekly", start_date=week_start, end_date=week_end)

        print("  Fetching top sales...")
        top_sales = get_top_sales(session, week_start, week_end, 5)

        print("  Fetching daily volume...")
        daily_data = get_daily_volume(session, week_start, week_end)

        print("  Fetching rarity breakdown...")
        rarity_data = get_rarity_breakdown(session, week_start, week_end)

        print("  Finding outliers...")
        outliers = get_outlier_sales(session, week_start, week_end)

        # Get sparklines for top 6 movers only
        print("  Fetching price histories...")
        for mover in stats.top_movers[:6]:
            history = get_price_history(session, mover["card_id"], 30)
            mover["sparkline"] = make_sparkline(history) if len(history) >= 3 else "─" * 10

    start_disp = week_start.strftime("%B %d")
    end_disp = week_end.strftime("%B %d, %Y")

    # Navigation dates
    prev_date = (week_start - timedelta(days=1)).strftime("%Y-%m-%d")
    next_date = (week_end + timedelta(days=7)).strftime("%Y-%m-%d")
    next_visible = week_end + timedelta(days=7) <= datetime.now(timezone.utc)

    analysis = generate_ai_analysis(stats, week_start, week_end) if use_ai else generate_template_analysis(stats)

    trend, trend_icon, trend_class = get_trend_indicator(stats.volume_trend_pct)

    # =================
    # BUILD SECTIONS
    # =================

    # Daily activity rows
    daily_rows = ""
    if daily_data:
        max_daily = max(d[1] for d in daily_data) or 1
        for day_str, count, volume in daily_data:
            day_name = datetime.strptime(day_str, "%Y-%m-%d").strftime("%a")
            bar = ascii_bar(count, max_daily, 10)
            daily_rows += f"""
<div className="flex items-center gap-2 py-0.5">
  <span className="w-8 text-muted-foreground">{day_name}</span>
  <code className="text-cyan-500/70">{bar}</code>
  <span className="w-8 text-right tabular-nums text-xs">{count}</span>
  <span className="w-16 text-right tabular-nums text-xs text-muted-foreground">{fmt_price(volume)}</span>
</div>"""

    # Navigation
    nav_prev = f'<a href="/blog/weekly-movers-{prev_date}" className="text-muted-foreground hover:text-foreground transition-colors">← Previous Week</a>'
    nav_next = (
        f'<a href="/blog/weekly-movers-{next_date}" className="text-muted-foreground hover:text-foreground transition-colors">Next Week →</a>'
        if next_visible
        else '<span className="text-muted-foreground/50">Latest Report</span>'
    )

    # Week summary line
    if stats.volume_trend_pct > 20:
        summary_line = f"Strong week. Volume up {fmt_pct(stats.volume_trend_pct)} with {stats.total_sales} sales across {stats.unique_cards_traded} unique cards."
    elif stats.volume_trend_pct < -20:
        summary_line = f"Market cooled significantly. Volume down {abs(stats.volume_trend_pct):.0f}% from last week with only {stats.total_sales} completed sales."
    elif stats.volume_trend_pct > 0:
        summary_line = f"Steady growth. Volume up {fmt_pct(stats.volume_trend_pct)} with {stats.total_sales} sales totaling {fmt_price(stats.total_volume_usd)}."
    else:
        summary_line = f"Quiet week. {stats.total_sales} sales for {fmt_price(stats.total_volume_usd)} total volume, down {abs(stats.volume_trend_pct):.0f}% from prior week."

    # Top 3 sales only
    top_3_sales = ""
    for sale, card in top_sales[:3]:
        treatment = sale.treatment or "Paper"
        top_3_sales += f"""
<a href="/cards/{card.id}" className="group">
  <div className="text-2xl font-mono font-bold group-hover:text-primary transition-colors">{fmt_price(sale.price)}</div>
  <div className="text-sm truncate">{card.name}</div>
  <div className="text-xs text-muted-foreground">{treatment}</div>
</a>"""

    # Daily bars - simplified
    daily_bars = ""
    if daily_data:
        max_daily = max(d[1] for d in daily_data) or 1
        for day_str, count, volume in daily_data:
            day_name = datetime.strptime(day_str, "%Y-%m-%d").strftime("%a")
            bar = ascii_bar(count, max_daily, 32)
            daily_bars += f"""
<div className="flex items-center gap-3">
  <span className="w-10 text-muted-foreground">{day_name}</span>
  <code className="text-primary/60 flex-1">{bar}</code>
  <span className="w-6 text-right tabular-nums">{count}</span>
  <span className="w-20 text-right tabular-nums text-muted-foreground">{fmt_price(volume)}</span>
</div>"""

    # Gainers - simplified, top 3 (deduplicated by card_id)
    seen_gainer_ids = set()
    gainers = []
    for m in stats.top_movers:
        if m.get("pct_change", 0) > 0 and m["card_id"] not in seen_gainer_ids:
            seen_gainer_ids.add(m["card_id"])
            gainers.append(m)
            if len(gainers) >= 3:
                break
    gainer_lines = ""
    for g in gainers:
        conf = "●" if g.get("confidence") == "high" else "○" if g.get("confidence") == "medium" else "◌"
        sparkline = g.get("sparkline", "─" * 10)
        gainer_lines += f"""
<div className="flex items-center gap-3 py-2">
  <span className="w-4 text-muted-foreground">{conf}</span>
  <a href="/cards/{g['card_id']}" className="flex-1 truncate hover:text-primary transition-colors">{g["name"]}</a>
  <code className="text-muted-foreground/40 hidden md:block">{sparkline}</code>
  <span className="w-20 text-right font-mono font-semibold text-green-500">{fmt_pct(g["pct_change"])}</span>
  <span className="w-20 text-right font-mono">→ {fmt_price(g["current_price"])}</span>
  <span className="w-16 text-right text-muted-foreground text-sm">{g.get("volume", 0)} sale{"s" if g.get("volume", 0) != 1 else ""}</span>
</div>"""

    # Losers - simplified, top 3 (deduplicated by card_id)
    seen_loser_ids = set()
    losers = []
    for m in stats.top_movers:
        if m.get("pct_change", 0) < 0 and m["card_id"] not in seen_loser_ids:
            seen_loser_ids.add(m["card_id"])
            losers.append(m)
            if len(losers) >= 3:
                break
    loser_lines = ""
    for l in losers:
        conf = "●" if l.get("confidence") == "high" else "○" if l.get("confidence") == "medium" else "◌"
        sparkline = l.get("sparkline", "─" * 10)
        loser_lines += f"""
<div className="flex items-center gap-3 py-2">
  <span className="w-4 text-muted-foreground">{conf}</span>
  <a href="/cards/{l['card_id']}" className="flex-1 truncate hover:text-primary transition-colors">{l["name"]}</a>
  <code className="text-muted-foreground/40 hidden md:block">{sparkline}</code>
  <span className="w-20 text-right font-mono font-semibold text-red-500">{fmt_pct(l["pct_change"])}</span>
  <span className="w-20 text-right font-mono">→ {fmt_price(l["current_price"])}</span>
  <span className="w-16 text-right text-muted-foreground text-sm">{l.get("volume", 0)} sale{"s" if l.get("volume", 0) != 1 else ""}</span>
</div>"""

    # Rarity breakdown - side by side with treatment
    rarity_bars = ""
    if rarity_data:
        max_rv = max(r["volume"] for r in rarity_data) or 1
        for r in rarity_data[:4]:
            bar = ascii_bar(r["count"], max(x["count"] for x in rarity_data), 12)
            rarity_bars += f"""
<div className="flex items-center gap-2">
  <span className="w-20 text-muted-foreground truncate">{r["rarity"]}</span>
  <code className="text-purple-500/50">{bar}</code>
  <span className="tabular-nums">{r["count"]}×</span>
</div>"""

    # Treatment breakdown
    treatment_bars = ""
    if stats.treatment_breakdown:
        max_tc = max(t["count"] for t in stats.treatment_breakdown.values())
        for t, d in sorted(stats.treatment_breakdown.items(), key=lambda x: -x[1]["count"])[:4]:
            bar = ascii_bar(d["count"], max_tc, 12)
            treatment_bars += f"""
<div className="flex items-center gap-2">
  <span className="w-28 text-muted-foreground truncate">{t}</span>
  <code className="text-green-500/50">{bar}</code>
  <span className="tabular-nums">{d["count"]}×</span>
</div>"""

    # Outliers - simplified
    outlier_lines = ""
    for o in outliers[:3]:
        icon = "▼" if o["is_deal"] else "▲"
        color = "text-green-500" if o["is_deal"] else "text-amber-500"
        outlier_lines += f"""
<div className="flex items-center gap-3 py-1">
  <span className="w-12 text-muted-foreground">{o["date"]}</span>
  <a href="/cards/{o['card_id']}" className="flex-1 truncate hover:text-primary transition-colors">{o["name"]}</a>
  <span className="font-mono font-bold">{fmt_price(o["price"])}</span>
  <span className="{color} font-mono">{icon} {fmt_pct(o["deviation"])} vs avg</span>
</div>"""

    # Outlier section (built separately to avoid nested f-strings)
    outlier_section = ""
    if outlier_lines:
        outlier_section = f"""<div className="border-t border-border/50 py-8 mb-8">
  <div className="text-muted-foreground uppercase tracking-widest text-xs mb-6">Outliers <span className="normal-case tracking-normal text-muted-foreground/60">- vs typical price</span></div>
  <div className="font-mono text-sm">
{outlier_lines}
  </div>
</div>"""

    # =================
    # ASSEMBLE MDX
    # =================

    mdx = f"""---
title: "Weekly Market Report: {start_disp} - {end_disp}"
slug: "weekly-movers-{date_string}"
description: "Wonders of the First TCG market report. {stats.total_sales:,} sales, {fmt_price(stats.total_volume_usd)} volume."
publishedAt: "{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}"
author: "cody"
category: "analysis"
tags: ["market-report", "weekly-movers", "price-tracking"]
readTime: 3
---

<div className="flex justify-between items-center font-mono text-sm mb-12">
  {nav_prev}
  {nav_next}
</div>

<div className="text-center mb-16">
  <div className="text-4xl md:text-6xl font-mono font-bold {trend_class} mb-2">{trend_icon} {trend}</div>
  <div className="text-5xl md:text-7xl font-mono font-bold mb-4">{fmt_price(stats.total_volume_usd)}</div>
  <div className="text-muted-foreground uppercase tracking-widest text-sm">volume</div>
  <div className="flex justify-center gap-8 mt-6 font-mono text-lg">
    <span>{stats.total_sales} sales</span>
    <span className="text-muted-foreground">·</span>
    <span>{fmt_price(stats.avg_sale_price)} avg</span>
    <span className="text-muted-foreground">·</span>
    <span className="{trend_class}">{fmt_pct(stats.volume_trend_pct)} vs last week</span>
  </div>
</div>

<div className="border-t border-border/50 py-8 mb-8">
  <div className="text-muted-foreground uppercase tracking-widest text-xs mb-4">The Week in One Line</div>
  <p className="text-lg">{summary_line}</p>
</div>

<div className="border-t border-border/50 py-8 mb-8">
  <div className="text-muted-foreground uppercase tracking-widest text-xs mb-6">Daily Activity</div>
  <div className="font-mono text-sm space-y-1">
{daily_bars}
  </div>
</div>

<div className="border-t border-border/50 py-8 mb-8">
  <div className="text-muted-foreground uppercase tracking-widest text-xs mb-6">Top Sales</div>
  <div className="grid grid-cols-3 gap-6 text-center">
{top_3_sales}
  </div>
</div>

<div className="border-t border-border/50 py-8 mb-8">
  <div className="text-muted-foreground uppercase tracking-widest text-xs mb-6">Movers<span className="ml-4 normal-case tracking-normal">● high · ○ med · ◌ low confidence</span></div>

  <div className="mb-6">
    <div className="text-green-500 text-sm font-mono mb-3">GAINERS</div>
    <div className="font-mono text-sm">
{gainer_lines}
    </div>
  </div>

  <div className="border-t border-border/30 pt-6">
    <div className="text-red-500 text-sm font-mono mb-3">LOSERS</div>
    <div className="font-mono text-sm">
{loser_lines}
    </div>
  </div>
</div>

<div className="border-t border-border/50 py-8 mb-8">
  <div className="text-muted-foreground uppercase tracking-widest text-xs mb-6">Breakdown</div>
  <div className="grid md:grid-cols-2 gap-8 font-mono text-sm">
    <div>
      <div className="text-muted-foreground text-xs mb-3">BY RARITY</div>
{rarity_bars}
    </div>
    <div>
      <div className="text-muted-foreground text-xs mb-3">BY TREATMENT</div>
{treatment_bars}
    </div>
  </div>
</div>

{outlier_section}

<div className="border-t border-border/50 py-8 mb-8">
  <div className="text-muted-foreground uppercase tracking-widest text-xs mb-4">Analysis</div>

{analysis}
</div>

<div className="border-t border-border/50 py-8">
  <div className="flex justify-between items-center font-mono text-sm">
    {nav_prev}
    {nav_next}
  </div>
</div>

<div className="mt-12 pt-8 border-t border-border/30 text-xs text-muted-foreground/60 font-mono">

**Data Notes** · Confidence: ● consistent data · ○ treatment mix changed · ◌ thin volume · Sparklines = 30d trend · Prices from completed eBay/Blokpax sales

</div>
"""
    return mdx, date_string


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", "-d")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-ai", action="store_true")
    args = parser.parse_args()

    try:
        content, date_string = generate_mdx_post(args.date, not args.no_ai)
    except Exception as e:
        import traceback

        print(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)

    if args.dry_run:
        print(content)
        return

    out = Path(__file__).parent.parent / "frontend/app/content/blog/posts" / f"{date_string}-weekly-movers.mdx"
    out.write_text(content)
    print(f"Saved: {out}")


if __name__ == "__main__":
    main()
