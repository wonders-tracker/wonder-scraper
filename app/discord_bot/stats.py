"""
Market stats calculation for Discord reports.
"""
import csv
import io
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from dataclasses import dataclass

from sqlmodel import Session, select, func, desc
from app.db import engine
from app.models.card import Card, Rarity
from app.models.market import MarketSnapshot, MarketPrice


@dataclass
class MarketStats:
    """Container for market statistics."""
    period: str
    total_sales: int
    total_volume_usd: float
    unique_cards_traded: int
    avg_sale_price: float
    top_movers: List[Dict[str, Any]]
    top_volume: List[Dict[str, Any]]
    new_highs: List[Dict[str, Any]]
    new_lows: List[Dict[str, Any]]
    generated_at: datetime
    # Trend data
    prev_total_sales: int = 0
    prev_total_volume_usd: float = 0.0
    volume_trend_pct: float = 0.0
    sales_trend_pct: float = 0.0
    # Actionable insights
    insights: List[Dict[str, Any]] = None
    # Breakdown by product type
    product_breakdown: Dict[str, Dict[str, Any]] = None  # {type: {count, volume, avg_price}}
    # Breakdown by treatment
    treatment_breakdown: Dict[str, Dict[str, Any]] = None  # {treatment: {count, volume, avg_price}}


def get_period_bounds(period: str) -> tuple[datetime, datetime]:
    """Get start and end datetime for a period."""
    now = datetime.utcnow()
    if period == "daily":
        start = now - timedelta(days=1)
    elif period == "weekly":
        start = now - timedelta(days=7)
    elif period == "monthly":
        start = now - timedelta(days=30)
    else:
        start = now - timedelta(days=1)
    return start, now


def _generate_insights(
    session,
    sales: List,
    top_movers: List[Dict],
    top_volume: List[Dict],
    new_highs: List[Dict],
    new_lows: List[Dict],
    avg_price: float,
    volume_trend_pct: float,
    sales_trend_pct: float,
    period: str
) -> List[Dict[str, Any]]:
    """Generate actionable market insights based on data."""
    insights = []

    # Insight 1: Volume/activity trend
    if volume_trend_pct > 20:
        insights.append({
            "type": "bullish",
            "icon": "📈",
            "title": "Market Heating Up",
            "text": f"Volume is up {volume_trend_pct:.0f}% vs last {period}. Consider selling high-value cards while demand is strong."
        })
    elif volume_trend_pct < -20:
        insights.append({
            "type": "bearish",
            "icon": "📉",
            "title": "Market Cooling Down",
            "text": f"Volume is down {abs(volume_trend_pct):.0f}% vs last {period}. Good time to buy if you're patient - less competition."
        })
    elif sales_trend_pct > 15:
        insights.append({
            "type": "neutral",
            "icon": "📊",
            "title": "More Activity",
            "text": f"Sales up {sales_trend_pct:.0f}% but prices stable. Market is active - good liquidity for buyers and sellers."
        })

    # Insight 2: Best buying opportunities (cards that dropped significantly)
    buy_opportunities = [m for m in top_movers if m.get("pct_change", 0) < -15]
    if buy_opportunities:
        best_buy = min(buy_opportunities, key=lambda x: x["pct_change"])
        insights.append({
            "type": "opportunity",
            "icon": "💰",
            "title": "Buy Opportunity",
            "text": f"**{best_buy['name']}** dropped {abs(best_buy['pct_change']):.0f}% to ${best_buy['current_price']:.2f}. Could be a dip worth buying."
        })

    # Insight 3: Hot cards with momentum
    hot_cards = [m for m in top_movers if m.get("pct_change", 0) > 15 and m.get("volume", 0) >= 2]
    if hot_cards:
        hottest = max(hot_cards, key=lambda x: x["pct_change"])
        insights.append({
            "type": "trending",
            "icon": "🔥",
            "title": "Hot Card Alert",
            "text": f"**{hottest['name']}** is up {hottest['pct_change']:.0f}% with {hottest.get('volume', 0)} sales. Momentum is building."
        })

    # Insight 4: New all-time highs signal
    if new_highs:
        insights.append({
            "type": "milestone",
            "icon": "🏆",
            "title": "New Records Set",
            "text": f"{len(new_highs)} card(s) hit all-time highs. **{new_highs[0]['name']}** reached ${new_highs[0]['price']:.2f}."
        })

    # Insight 5: Underpriced cards (current ask significantly below recent avg sale)
    # Compute LIVE lowest_ask from MarketPrice table instead of stale snapshot
    underpriced = []
    for card in session.exec(select(Card)).all():
        # Get LIVE lowest_ask from active listings in MarketPrice
        live_ask_result = session.exec(
            select(func.min(MarketPrice.price))
            .where(MarketPrice.card_id == card.id)
            .where(MarketPrice.listing_type == "active")
        ).first()
        live_lowest_ask = live_ask_result if live_ask_result else None

        # Get avg_price from snapshot (this is fine - it's historical aggregate)
        snapshot = session.exec(
            select(MarketSnapshot)
            .where(MarketSnapshot.card_id == card.id)
            .order_by(desc(MarketSnapshot.timestamp))
            .limit(1)
        ).first()

        # Use live lowest_ask, fallback to snapshot only if no active listings
        lowest_ask = live_lowest_ask if live_lowest_ask is not None else (snapshot.lowest_ask if snapshot else None)
        avg_price = snapshot.avg_price if snapshot else None

        if not lowest_ask or lowest_ask <= 0:
            continue
        if not avg_price or avg_price <= 0:
            continue

        # If current ask is 20%+ below avg sold price
        discount_pct = ((avg_price - lowest_ask) / avg_price) * 100
        if discount_pct > 20 and lowest_ask >= 5:  # Min $5 to avoid junk
            underpriced.append({
                "name": card.name,
                "ask": lowest_ask,
                "avg": avg_price,
                "discount": discount_pct
            })

    if underpriced and len(insights) < 4:
        underpriced.sort(key=lambda x: x["discount"], reverse=True)
        best = underpriced[0]
        insights.append({
            "type": "deal",
            "icon": "🎯",
            "title": "Below-Market Listing",
            "text": f"**{best['name']}** listed at ${best['ask']:.2f} ({best['discount']:.0f}% below ${best['avg']:.2f} avg). Could be a quick flip."
        })

    # Insight 6: High volume concentration (one card dominating)
    if top_volume and sales:
        top_card_volume = top_volume[0].get("total_volume", 0)
        total_vol = sum(s.price for s in sales)
        if total_vol > 0:
            concentration = (top_card_volume / total_vol) * 100
            if concentration > 30:
                insights.append({
                    "type": "info",
                    "icon": "👀",
                    "title": "Concentrated Volume",
                    "text": f"**{top_volume[0]['name']}** accounts for {concentration:.0f}% of all volume. Watch for price swings."
                })

    # Ensure we have at least 3 insights
    if len(insights) < 3:
        if avg_price > 50:
            insights.append({
                "type": "info",
                "icon": "💎",
                "title": "Premium Market",
                "text": f"Average sale price is ${avg_price:.2f}. High-value trades dominating this period."
            })
        elif avg_price > 0:
            insights.append({
                "type": "info",
                "icon": "📦",
                "title": "Accessible Market",
                "text": f"Average sale price is ${avg_price:.2f}. Good entry point for new collectors."
            })

    # Cap at 3 insights for clean display
    return insights[:3]


def calculate_market_stats(period: str = "daily") -> MarketStats:
    """Calculate market statistics for a given period."""
    start_time, end_time = get_period_bounds(period)

    with Session(engine) as session:
        # Get all sold listings in period
        sales = session.exec(
            select(MarketPrice)
            .where(MarketPrice.listing_type == "sold")
            .where(MarketPrice.sold_date >= start_time)
            .where(MarketPrice.sold_date <= end_time)
        ).all()

        total_sales = len(sales)
        total_volume_usd = sum(s.price for s in sales) if sales else 0
        unique_cards = len(set(s.card_id for s in sales)) if sales else 0
        avg_price = total_volume_usd / total_sales if total_sales > 0 else 0

        # Calculate product type breakdown (Singles, Boxes, Packs, Lots)
        product_breakdown = {}
        for sale in sales:
            card = session.get(Card, sale.card_id)
            if card:
                ptype = card.product_type or "Single"
                if ptype not in product_breakdown:
                    product_breakdown[ptype] = {"count": 0, "volume": 0.0}
                product_breakdown[ptype]["count"] += 1
                product_breakdown[ptype]["volume"] += sale.price

        # Calculate avg_price for each product type
        for ptype in product_breakdown:
            cnt = product_breakdown[ptype]["count"]
            product_breakdown[ptype]["avg_price"] = product_breakdown[ptype]["volume"] / cnt if cnt > 0 else 0

        # Calculate treatment breakdown (Classic Paper, Foil, Full Art, etc.)
        treatment_breakdown = {}
        for sale in sales:
            treatment = sale.treatment or "Classic Paper"
            if treatment not in treatment_breakdown:
                treatment_breakdown[treatment] = {"count": 0, "volume": 0.0}
            treatment_breakdown[treatment]["count"] += 1
            treatment_breakdown[treatment]["volume"] += sale.price

        # Calculate avg_price for each treatment
        for treatment in treatment_breakdown:
            cnt = treatment_breakdown[treatment]["count"]
            treatment_breakdown[treatment]["avg_price"] = treatment_breakdown[treatment]["volume"] / cnt if cnt > 0 else 0

        # Get previous period for comparison
        prev_start = start_time - (end_time - start_time)

        # Calculate previous period stats for trends
        prev_sales = session.exec(
            select(MarketPrice)
            .where(MarketPrice.listing_type == "sold")
            .where(MarketPrice.sold_date >= prev_start)
            .where(MarketPrice.sold_date < start_time)
        ).all()

        prev_total_sales = len(prev_sales)
        prev_total_volume = sum(s.price for s in prev_sales) if prev_sales else 0

        # Calculate trend percentages with meaningful thresholds
        # Only show trends if previous period had enough data to be meaningful
        MIN_SALES_FOR_TREND = 5  # Require at least 5 sales in previous period
        MAX_TREND_PCT = 100  # Cap at ±100% to avoid crazy numbers like -500%

        if prev_total_volume > 0 and prev_total_sales >= MIN_SALES_FOR_TREND:
            volume_trend_pct = ((total_volume_usd - prev_total_volume) / prev_total_volume * 100)
            volume_trend_pct = max(-MAX_TREND_PCT, min(MAX_TREND_PCT, volume_trend_pct))
        else:
            volume_trend_pct = 0  # Not enough data for meaningful comparison

        if prev_total_sales >= MIN_SALES_FOR_TREND:
            sales_trend_pct = ((total_sales - prev_total_sales) / prev_total_sales * 100)
            sales_trend_pct = max(-MAX_TREND_PCT, min(MAX_TREND_PCT, sales_trend_pct))
        else:
            sales_trend_pct = 0  # Not enough data for meaningful comparison

        # Calculate top movers (biggest % change)
        top_movers = []
        cards = session.exec(select(Card)).all()

        for card in cards:
            # Current period avg
            current_sales = [s for s in sales if s.card_id == card.id]
            if not current_sales:
                continue
            current_avg = sum(s.price for s in current_sales) / len(current_sales)

            # Previous period avg
            prev_sales = session.exec(
                select(MarketPrice)
                .where(MarketPrice.card_id == card.id)
                .where(MarketPrice.listing_type == "sold")
                .where(MarketPrice.sold_date >= prev_start)
                .where(MarketPrice.sold_date < start_time)
            ).all()

            if not prev_sales:
                continue
            prev_avg = sum(s.price for s in prev_sales) / len(prev_sales)

            if prev_avg > 0:
                pct_change = ((current_avg - prev_avg) / prev_avg) * 100
                top_movers.append({
                    "card_id": card.id,
                    "name": card.name,
                    "current_price": current_avg,
                    "prev_price": prev_avg,
                    "pct_change": pct_change,
                    "volume": len(current_sales)
                })

        # Sort by absolute change, get top 5 gainers and losers
        top_movers.sort(key=lambda x: x["pct_change"], reverse=True)
        gainers = top_movers[:5]
        losers = list(reversed(top_movers[-5:])) if len(top_movers) >= 5 else []

        # Top volume
        card_volumes = {}
        for s in sales:
            if s.card_id not in card_volumes:
                card_volumes[s.card_id] = {"count": 0, "total": 0}
            card_volumes[s.card_id]["count"] += 1
            card_volumes[s.card_id]["total"] += s.price

        top_volume = []
        for card_id, data in sorted(card_volumes.items(), key=lambda x: x[1]["count"], reverse=True)[:5]:
            card = session.get(Card, card_id)
            if card:
                top_volume.append({
                    "card_id": card_id,
                    "name": card.name,
                    "sales_count": data["count"],
                    "total_volume": data["total"],
                    "avg_price": data["total"] / data["count"]
                })

        # New all-time highs
        new_highs = []
        for card in cards:
            current_sales = [s for s in sales if s.card_id == card.id]
            if not current_sales:
                continue

            max_current = max(s.price for s in current_sales)

            # Check historical max
            hist_max = session.exec(
                select(func.max(MarketPrice.price))
                .where(MarketPrice.card_id == card.id)
                .where(MarketPrice.listing_type == "sold")
                .where(MarketPrice.sold_date < start_time)
            ).first()

            if hist_max is None or max_current > hist_max:
                new_highs.append({
                    "card_id": card.id,
                    "name": card.name,
                    "price": max_current,
                    "prev_high": hist_max or 0
                })

        new_highs.sort(key=lambda x: x["price"], reverse=True)
        new_highs = new_highs[:5]

        # New lows (similar logic)
        new_lows = []
        for card in cards:
            current_sales = [s for s in sales if s.card_id == card.id]
            if not current_sales:
                continue

            min_current = min(s.price for s in current_sales)

            hist_min = session.exec(
                select(func.min(MarketPrice.price))
                .where(MarketPrice.card_id == card.id)
                .where(MarketPrice.listing_type == "sold")
                .where(MarketPrice.sold_date < start_time)
            ).first()

            if hist_min is None or min_current < hist_min:
                new_lows.append({
                    "card_id": card.id,
                    "name": card.name,
                    "price": min_current,
                    "prev_low": hist_min or 0
                })

        new_lows.sort(key=lambda x: x["price"])
        new_lows = new_lows[:5]

        # Generate actionable insights
        insights = _generate_insights(
            session=session,
            sales=sales,
            top_movers=gainers + losers,
            top_volume=top_volume,
            new_highs=new_highs,
            new_lows=new_lows,
            avg_price=avg_price,
            volume_trend_pct=volume_trend_pct,
            sales_trend_pct=sales_trend_pct,
            period=period
        )

        return MarketStats(
            period=period,
            total_sales=total_sales,
            total_volume_usd=total_volume_usd,
            unique_cards_traded=unique_cards,
            avg_sale_price=avg_price,
            top_movers=gainers + losers,
            top_volume=top_volume,
            new_highs=new_highs,
            new_lows=new_lows,
            generated_at=datetime.utcnow(),
            prev_total_sales=prev_total_sales,
            prev_total_volume_usd=prev_total_volume,
            volume_trend_pct=volume_trend_pct,
            sales_trend_pct=sales_trend_pct,
            insights=insights,
            product_breakdown=product_breakdown,
            treatment_breakdown=treatment_breakdown
        )


def generate_csv_report(period: str = "daily") -> tuple[str, bytes]:
    """Generate a CSV report of all market data for the period."""
    start_time, end_time = get_period_bounds(period)

    with Session(engine) as session:
        # Get all sales in period with card info
        sales = session.exec(
            select(MarketPrice, Card)
            .join(Card)
            .where(MarketPrice.listing_type == "sold")
            .where(MarketPrice.sold_date >= start_time)
            .where(MarketPrice.sold_date <= end_time)
            .order_by(desc(MarketPrice.sold_date))
        ).all()

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            "Date", "Card Name", "Set", "Rarity", "Price", "Treatment",
            "Seller", "Condition", "Platform", "URL"
        ])

        for sale, card in sales:
            # Get rarity name
            rarity = session.get(Rarity, card.rarity_id) if card.rarity_id else None
            rarity_name = rarity.name if rarity else "Unknown"

            writer.writerow([
                sale.sold_date.strftime("%Y-%m-%d %H:%M") if sale.sold_date else "",
                card.name,
                card.set_name,
                rarity_name,
                f"${sale.price:.2f}",
                sale.treatment or "Classic Paper",
                sale.seller_name or "Unknown",
                sale.condition or "Not Specified",
                sale.platform,
                sale.url or ""
            ])

        csv_content = output.getvalue().encode('utf-8')
        filename = f"wonders_market_{period}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.csv"

        return filename, csv_content


def format_stats_embed(stats: MarketStats) -> Dict[str, Any]:
    """Format stats for Discord embed."""
    period_label = stats.period.capitalize()
    period_text = '24 hours' if stats.period == 'daily' else '7 days' if stats.period == 'weekly' else '30 days'

    # Build trend indicators for overview
    # Only show trends if they're non-zero (meaning we had enough prior data)
    volume_trend = ""
    if stats.volume_trend_pct > 0:
        volume_trend = f" ↑{stats.volume_trend_pct:.0f}%"
    elif stats.volume_trend_pct < 0:
        volume_trend = f" ↓{abs(stats.volume_trend_pct):.0f}%"

    sales_trend = ""
    if stats.sales_trend_pct > 0:
        sales_trend = f" ↑{stats.sales_trend_pct:.0f}%"
    elif stats.sales_trend_pct < 0:
        sales_trend = f" ↓{abs(stats.sales_trend_pct):.0f}%"

    # Add context about previous period if we have meaningful data
    prev_context = ""
    if stats.prev_total_sales >= 5:
        prev_context = f"\n*vs {stats.prev_total_sales} sales (${stats.prev_total_volume_usd:,.0f}) prior {stats.period}*"

    # Top gainers section
    gainers_text = ""
    for m in stats.top_movers[:5]:
        if m["pct_change"] > 0:
            gainers_text += f"**{m['name']}**: ${m['current_price']:.2f} (+{m['pct_change']:.1f}%)\n"
    gainers_text = gainers_text or "No significant gainers"

    # Top losers section
    losers_text = ""
    for m in stats.top_movers[5:]:
        if m["pct_change"] < 0:
            losers_text += f"**{m['name']}**: ${m['current_price']:.2f} ({m['pct_change']:.1f}%)\n"
    losers_text = losers_text or "No significant losers"

    # Top volume
    volume_text = ""
    for v in stats.top_volume[:5]:
        volume_text += f"**{v['name']}**: {v['sales_count']} sales (${v['total_volume']:.2f})\n"
    volume_text = volume_text or "No sales data"

    # New records
    highs_text = "\n".join([f"**{h['name']}**: ${h['price']:.2f}" for h in stats.new_highs[:3]]) or "None"
    lows_text = "\n".join([f"**{l['name']}**: ${l['price']:.2f}" for l in stats.new_lows[:3]]) or "None"

    # Build insights text
    insights_text = ""
    if stats.insights:
        for insight in stats.insights:
            insights_text += f"{insight['icon']} **{insight['title']}**: {insight['text']}\n\n"
    insights_text = insights_text.strip() or "No actionable insights for this period."

    # Build comprehensive market breakdown (product types + treatments in one field)
    breakdown_text = ""

    # Product type breakdown with emojis
    product_icons = {"Single": "🎴", "Box": "📦", "Pack": "🎁", "Lot": "🔢"}
    if stats.product_breakdown:
        breakdown_text += "**By Product Type:**\n"
        # Sort by count descending
        sorted_products = sorted(stats.product_breakdown.items(), key=lambda x: x[1]["count"], reverse=True)
        for ptype, data in sorted_products:
            icon = product_icons.get(ptype, "📋")
            breakdown_text += f"{icon} {ptype}: {data['count']} sold (${data['volume']:,.2f})\n"
        breakdown_text += "\n"

    # Treatment breakdown with emojis
    treatment_icons = {
        # Card treatments
        "Classic Paper": "📄",
        "Classic Foil": "✨",
        "Stonefoil": "🪨",
        "Formless Foil": "🌀",
        "OCM Serialized": "🔢",
        "Prerelease": "🎭",
        "Promo": "🎁",
        "Proof/Sample": "🧪",
        "Error/Errata": "⚠️",
        # Sealed product treatments
        "Factory Sealed": "🏭",
        "Sealed": "📦",
        "New": "🆕",
        "Unopened": "🔒",
        "Open Box": "📂",
        "Used": "♻️",
    }
    if stats.treatment_breakdown:
        breakdown_text += "**By Treatment:**\n"
        # Sort by count descending
        sorted_treatments = sorted(stats.treatment_breakdown.items(), key=lambda x: x[1]["count"], reverse=True)
        for treatment, data in sorted_treatments:
            icon = treatment_icons.get(treatment, "🃏")
            breakdown_text += f"{icon} {treatment}: {data['count']} (avg ${data['avg_price']:.2f})\n"

    breakdown_text = breakdown_text.strip() or "No breakdown data available"

    fields = [
        {
            "name": "Overview",
            "value": f"**Total Sales**: {stats.total_sales}{sales_trend}\n**Volume**: ${stats.total_volume_usd:,.2f}{volume_trend}\n**Cards Traded**: {stats.unique_cards_traded}\n**Avg Price**: ${stats.avg_sale_price:.2f}{prev_context}",
            "inline": False
        },
        {
            "name": "Market Breakdown",
            "value": breakdown_text,
            "inline": False
        },
        {
            "name": "Actionable Insights",
            "value": insights_text,
            "inline": False
        },
        {
            "name": "Top Gainers",
            "value": gainers_text,
            "inline": True
        },
        {
            "name": "Top Losers",
            "value": losers_text,
            "inline": True
        },
        {
            "name": "Most Active",
            "value": volume_text,
            "inline": False
        },
        {
            "name": "New All-Time Highs",
            "value": highs_text,
            "inline": True
        },
        {
            "name": "New All-Time Lows",
            "value": lows_text,
            "inline": True
        }
    ]

    return {
        "title": f"Wonders Market {period_label} Report",
        "description": f"Market stats for the past {period_text}",
        "color": 0x10B981,  # Emerald green
        "fields": fields,
        "footer": {
            "text": f"Generated at {stats.generated_at.strftime('%Y-%m-%d %H:%M UTC')}"
        },
        "timestamp": stats.generated_at.isoformat()
    }
