"""
AI-powered market insights generator for Discord updates.

Analyzes market data and generates human-readable insights about:
- Price trends (movers, shakers)
- Deals (cards selling below floor)
- Volume leaders
- Market health metrics
"""

import os
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from sqlmodel import Session, select, text
from openai import OpenAI
from dotenv import load_dotenv

from app.db import engine
from app.models.card import Card
from app.models.market import MarketPrice, MarketSnapshot

load_dotenv()


class MarketInsightsGenerator:
    """Generates AI-powered market insights from price data."""

    def __init__(self):
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            print("WARNING: OPENROUTER_API_KEY not set, market insights will be basic")
            self.client = None
        else:
            self.client = OpenAI(
                base_url="https://openrouter.ai/api/v1",
                api_key=api_key
            )
            self.model = "openai/gpt-4o-mini"

    def gather_market_data(self) -> Dict[str, Any]:
        """Gather market data for analysis using efficient bulk queries."""
        with Session(engine) as session:
            now = datetime.utcnow()
            day_ago = now - timedelta(days=1)
            week_ago = now - timedelta(days=7)

            # Get all cards
            cards = session.exec(select(Card)).all()
            card_map = {c.id: c for c in cards}

            # BULK: Get last sale per card (single query)
            last_sales = session.execute(text("""
                SELECT DISTINCT ON (card_id) card_id, price
                FROM marketprice
                WHERE listing_type = 'sold' AND sold_date IS NOT NULL
                ORDER BY card_id, sold_date DESC
            """)).all()
            last_sale_map = {r[0]: r[1] for r in last_sales}

            # BULK: Get 7-day average per card (single query)
            avg_7d_results = session.execute(text("""
                SELECT card_id, AVG(price) as avg_price
                FROM marketprice
                WHERE listing_type = 'sold' AND sold_date >= :week_ago
                GROUP BY card_id
            """), {"week_ago": week_ago}).all()
            avg_7d_map = {r[0]: r[1] for r in avg_7d_results}

            # BULK: Get floor prices (single query)
            floors = session.execute(text("""
                SELECT card_id, MIN(price) as floor
                FROM marketprice
                WHERE listing_type = 'active'
                GROUP BY card_id
            """)).all()
            floor_map = {r[0]: r[1] for r in floors}

            # Recent sales for deals analysis
            recent_sales = session.execute(text("""
                SELECT card_id, price, sold_date, treatment
                FROM marketprice
                WHERE listing_type = 'sold'
                AND scraped_at >= :day_ago
                ORDER BY sold_date DESC
                LIMIT 100
            """), {"day_ago": day_ago}).all()

            # Build price changes list
            price_changes = []
            for card in cards:
                last_sale = last_sale_map.get(card.id)
                avg_7d = avg_7d_map.get(card.id)
                floor = floor_map.get(card.id)

                if last_sale and avg_7d and avg_7d > 0:
                    pct_change = ((last_sale - avg_7d) / avg_7d) * 100
                    price_changes.append({
                        "name": card.name,
                        "product_type": card.product_type if hasattr(card, 'product_type') else 'Single',
                        "last_sale": last_sale,
                        "avg_7d": avg_7d,
                        "pct_change": pct_change,
                        "floor": floor
                    })

            # Sort by change magnitude
            gainers = sorted([p for p in price_changes if p["pct_change"] > 5],
                           key=lambda x: x["pct_change"], reverse=True)[:10]
            losers = sorted([p for p in price_changes if p["pct_change"] < -5],
                          key=lambda x: x["pct_change"])[:10]

            # Deals: cards that sold significantly below floor
            deals = []
            for sale in recent_sales:
                card = card_map.get(sale[0])
                if not card:
                    continue

                # Use pre-fetched floor from bulk query
                floor = floor_map.get(sale[0])

                if floor and sale[1] < floor * 0.85:  # Sold 15%+ below floor
                    deals.append({
                        "name": card.name,
                        "sold_price": sale[1],
                        "floor": floor,
                        "discount_pct": ((floor - sale[1]) / floor) * 100,
                        "treatment": sale[3]
                    })

            deals = sorted(deals, key=lambda x: x["discount_pct"], reverse=True)[:10]

            # Volume leaders (most sales in 24h)
            volume_24h = session.execute(text("""
                SELECT card_id, COUNT(*) as sales, SUM(price) as volume_usd
                FROM marketprice
                WHERE listing_type = 'sold'
                AND scraped_at >= :day_ago
                GROUP BY card_id
                ORDER BY sales DESC
                LIMIT 10
            """), {"day_ago": day_ago}).all()

            volume_leaders = []
            for v in volume_24h:
                card = card_map.get(v[0])
                if card:
                    volume_leaders.append({
                        "name": card.name,
                        "sales": v[1],
                        "volume_usd": v[2]
                    })

            # Overall market stats
            total_sales_24h = session.execute(text("""
                SELECT COUNT(*), SUM(price) FROM marketprice
                WHERE listing_type = 'sold' AND scraped_at >= :day_ago
            """), {"day_ago": day_ago}).first()

            total_listings = session.execute(text("""
                SELECT COUNT(*) FROM marketprice WHERE listing_type = 'active'
            """)).scalar()

            return {
                "timestamp": now.isoformat(),
                "gainers": gainers,
                "losers": losers,
                "deals": deals,
                "volume_leaders": volume_leaders,
                "market_stats": {
                    "sales_24h": total_sales_24h[0] or 0,
                    "volume_usd_24h": total_sales_24h[1] or 0,
                    "active_listings": total_listings or 0
                }
            }

    def generate_insights(self, data: Dict[str, Any]) -> str:
        """Generate AI-powered market insights from gathered data."""
        if not self.client:
            return self._generate_basic_insights(data)

        prompt = f"""You are a market analyst for "Wonders of the First" trading card game.
Generate a concise, engaging Discord market update based on this data.

**Market Data (Last 24 Hours):**

📈 **Top Gainers** (price vs 7-day avg):
{self._format_movers(data['gainers'])}

📉 **Top Losers**:
{self._format_movers(data['losers'])}

🔥 **Hot Deals** (sold below floor):
{self._format_deals(data['deals'])}

📊 **Volume Leaders**:
{self._format_volume(data['volume_leaders'])}

**Overall Stats:**
- Sales (24h): {data['market_stats']['sales_24h']}
- Volume (24h): ${data['market_stats']['volume_usd_24h']:,.2f}
- Active Listings: {data['market_stats']['active_listings']}

---

Write a Discord market update with:
1. A catchy opening line about the market mood (1 sentence)
2. 2-3 key highlights (gainers, losers, or deals worth mentioning)
3. A brief volume/activity summary
4. One actionable insight or thing to watch

Keep it under 400 words. Use emojis sparingly. Be informative but engaging.
Format for Discord (use **bold**, bullet points, etc.)."""

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a knowledgeable TCG market analyst who writes concise, insightful updates for Discord."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=600
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"AI insights generation failed: {e}")
            return self._generate_basic_insights(data)

    def _format_movers(self, movers: List[Dict]) -> str:
        if not movers:
            return "None significant"
        lines = []
        for m in movers[:5]:
            lines.append(f"- {m['name']}: {m['pct_change']:+.1f}% (${m['last_sale']:.2f} vs ${m['avg_7d']:.2f} avg)")
        return "\n".join(lines)

    def _format_deals(self, deals: List[Dict]) -> str:
        if not deals:
            return "None found"
        lines = []
        for d in deals[:5]:
            lines.append(f"- {d['name']}: ${d['sold_price']:.2f} ({d['discount_pct']:.0f}% below ${d['floor']:.2f} floor)")
        return "\n".join(lines)

    def _format_volume(self, leaders: List[Dict]) -> str:
        if not leaders:
            return "No recent sales"
        lines = []
        for v in leaders[:5]:
            lines.append(f"- {v['name']}: {v['sales']} sales (${v['volume_usd']:.2f})")
        return "\n".join(lines)

    def _generate_basic_insights(self, data: Dict[str, Any]) -> str:
        """Generate basic insights without AI."""
        lines = ["**Wonders Market Update**\n"]

        stats = data['market_stats']
        lines.append(f"📊 **24h Activity**: {stats['sales_24h']} sales | ${stats['volume_usd_24h']:,.2f} volume | {stats['active_listings']} listings\n")

        if data['gainers']:
            lines.append("📈 **Top Gainers**:")
            for g in data['gainers'][:3]:
                lines.append(f"  • {g['name']}: {g['pct_change']:+.1f}%")
            lines.append("")

        if data['losers']:
            lines.append("📉 **Dropping**:")
            for l in data['losers'][:3]:
                lines.append(f"  • {l['name']}: {l['pct_change']:+.1f}%")
            lines.append("")

        if data['deals']:
            lines.append("🔥 **Recent Deals**:")
            for d in data['deals'][:3]:
                lines.append(f"  • {d['name']}: ${d['sold_price']:.2f} ({d['discount_pct']:.0f}% below floor)")

        return "\n".join(lines)


# Singleton
_insights_generator: Optional[MarketInsightsGenerator] = None


def get_insights_generator() -> MarketInsightsGenerator:
    """Get or create the insights generator singleton."""
    global _insights_generator
    if _insights_generator is None:
        _insights_generator = MarketInsightsGenerator()
    return _insights_generator
