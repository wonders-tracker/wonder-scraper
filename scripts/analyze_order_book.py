#!/usr/bin/env python3
"""
Bid-Ask Order Book Analysis

Visualizes order book depth from eBay and Blokpax data with ASCII charts.

Usage:
    python scripts/analyze_order_book.py
    python scripts/analyze_order_book.py --card-id 123
    python scripts/analyze_order_book.py --card-name "Dragonmaster Cai"
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from datetime import datetime, timedelta, timezone
from argparse import ArgumentParser
from sqlalchemy import text
from app.db import engine


# =============================================================================
# Query Functions
# =============================================================================

def get_asks(card_id: int, platform: str = "ebay", days: int = 30) -> list[dict]:
    """Get active listings (ASK side) for a platform."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT price, treatment, title, scraped_at, platform
        FROM marketprice
        WHERE card_id = :card_id
          AND listing_type = 'active'
          AND scraped_at >= :cutoff
          AND is_bulk_lot = FALSE
          AND platform = :platform
        ORDER BY price ASC
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"card_id": card_id, "cutoff": cutoff, "platform": platform})
        return [dict(row._mapping) for row in result.fetchall()]


def get_ebay_highest_bid(card_id: int) -> float | None:
    """Get eBay highest bid from snapshots (limited BID data)."""
    query = text("""
        SELECT highest_bid
        FROM marketsnapshot
        WHERE card_id = :card_id
          AND highest_bid IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"card_id": card_id}).fetchone()
        return float(result[0]) if result else None


def get_sales(card_id: int, platform: str = "ebay", days: int = 30) -> list[dict]:
    """Get sold listings (BID side - proven buyer demand) for a platform."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT price, treatment, title, COALESCE(sold_date, scraped_at) as sold_date, platform
        FROM marketprice
        WHERE card_id = :card_id
          AND listing_type = 'sold'
          AND COALESCE(sold_date, scraped_at) >= :cutoff
          AND is_bulk_lot = FALSE
          AND platform = :platform
        ORDER BY price DESC
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"card_id": card_id, "cutoff": cutoff, "platform": platform})
        return [dict(row._mapping) for row in result.fetchall()]


def get_platforms_for_card(card_id: int) -> list[str]:
    """Get list of platforms that have data for this card."""
    query = text("""
        SELECT DISTINCT platform
        FROM marketprice
        WHERE card_id = :card_id AND platform IS NOT NULL
        ORDER BY platform
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"card_id": card_id})
        return [row[0] for row in result.fetchall()]


def get_blokpax_asks(asset_id: str) -> list[dict]:
    """Get Blokpax active listings (ASK side)."""
    query = text("""
        SELECT price_usd as price, seller_address, quantity, created_at
        FROM blokpaxlisting
        WHERE asset_id = :asset_id
          AND status = 'active'
        ORDER BY price_usd ASC
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"asset_id": asset_id})
        return [dict(row._mapping) for row in result.fetchall()]


def get_blokpax_bids(asset_id: str) -> list[dict]:
    """Get Blokpax open offers (BID side)."""
    query = text("""
        SELECT price_usd as price, buyer_address, quantity, created_at
        FROM blokpaxoffer
        WHERE asset_id = :asset_id
          AND status = 'open'
        ORDER BY price_usd DESC
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"asset_id": asset_id})
        return [dict(row._mapping) for row in result.fetchall()]


def get_blokpax_sales_by_card(card_id: int, days: int = 90) -> list[dict]:
    """Get Blokpax sales for a card (BID side - proven demand)."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    query = text("""
        SELECT price_usd as price, asset_name as title, filled_at as sold_date
        FROM blokpaxsale
        WHERE card_id = :card_id
          AND filled_at >= :cutoff
        ORDER BY price_usd DESC
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"card_id": card_id, "cutoff": cutoff})
        return [dict(row._mapping) for row in result.fetchall()]


def get_blokpax_asset_for_card(card_id: int) -> dict | None:
    """Find Blokpax asset linked to a card."""
    query = text("""
        SELECT external_id, name
        FROM blokpax_asset
        WHERE card_id = :card_id
        LIMIT 1
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"card_id": card_id}).fetchone()
        return dict(result._mapping) if result else None


def find_card(card_id: int | None = None, card_name: str | None = None) -> dict | None:
    """Find a card by ID or name."""
    if card_id:
        query = text("SELECT id, name FROM card WHERE id = :id")
        params = {"id": card_id}
    elif card_name:
        query = text("SELECT id, name FROM card WHERE LOWER(name) LIKE LOWER(:name) LIMIT 1")
        params = {"name": f"%{card_name}%"}
    else:
        return None

    with engine.connect() as conn:
        result = conn.execute(query, params).fetchone()
        return dict(result._mapping) if result else None


def get_top_cards_by_listings(limit: int = 10) -> list[dict]:
    """Get cards with most active listings."""
    query = text("""
        SELECT c.id, c.name, COUNT(*) as listing_count
        FROM card c
        JOIN marketprice mp ON mp.card_id = c.id
        WHERE mp.listing_type = 'active'
          AND mp.scraped_at >= NOW() - INTERVAL '30 days'
        GROUP BY c.id, c.name
        ORDER BY listing_count DESC
        LIMIT :limit
    """)
    with engine.connect() as conn:
        result = conn.execute(query, {"limit": limit})
        return [dict(row._mapping) for row in result.fetchall()]


# =============================================================================
# ASCII Visualization
# =============================================================================

def create_price_buckets(prices: list[float], num_buckets: int = 8) -> list[dict]:
    """Create price buckets for visualization."""
    if not prices:
        return []

    min_p, max_p = min(prices), max(prices)
    if min_p == max_p:
        return [{"min": min_p, "max": max_p, "count": len(prices), "mid": min_p}]

    bucket_width = (max_p - min_p) / num_buckets
    buckets = []

    for i in range(num_buckets):
        bucket_min = min_p + i * bucket_width
        bucket_max = min_p + (i + 1) * bucket_width
        if i == num_buckets - 1:
            count = sum(1 for p in prices if bucket_min <= p <= bucket_max)
        else:
            count = sum(1 for p in prices if bucket_min <= p < bucket_max)
        buckets.append({
            "min": round(bucket_min, 2),
            "max": round(bucket_max, 2),
            "mid": round((bucket_min + bucket_max) / 2, 2),
            "count": count
        })

    return buckets


def render_ascii_order_book(
    bids: list[dict],
    asks: list[dict],
    title: str = "Order Book",
    width: int = 70,
    num_buckets: int = 8
) -> str:
    """Render ASCII order book with bids on left, asks on right."""
    bid_prices = [b["price"] for b in bids if b.get("price")]
    ask_prices = [a["price"] for a in asks if a.get("price")]

    bid_buckets = create_price_buckets(bid_prices, num_buckets)
    ask_buckets = create_price_buckets(ask_prices, num_buckets)

    max_count = max(
        max((b["count"] for b in bid_buckets), default=0),
        max((b["count"] for b in ask_buckets), default=0),
        1
    )

    bar_width = (width - 24) // 2

    lines = []
    lines.append(f"\n{'=' * width}")
    lines.append(f"{title:^{width}}")
    lines.append(f"{'=' * width}")

    # Stats
    best_bid = max(bid_prices) if bid_prices else 0
    best_ask = min(ask_prices) if ask_prices else 0
    spread = best_ask - best_bid if best_bid and best_ask else 0
    spread_pct = (spread / best_ask * 100) if best_ask else 0

    lines.append(f"  Best Bid: ${best_bid:>8.2f}   |   Best Ask: ${best_ask:<8.2f}")
    lines.append(f"  Spread:   ${spread:>8.2f} ({spread_pct:.1f}%)")
    lines.append(f"  Bid Depth: {len(bid_prices):>5}      |   Ask Depth: {len(ask_prices):<5}")
    lines.append(f"{'-' * width}")
    lines.append(f"{'BID (Buyers)':^{width//2}}|{'ASK (Sellers)':^{width//2}}")
    lines.append(f"{'-' * width}")

    bid_buckets_rev = list(reversed(bid_buckets))
    max_rows = max(len(bid_buckets_rev), len(ask_buckets))

    for i in range(max_rows):
        # Bid side
        if i < len(bid_buckets_rev):
            b = bid_buckets_rev[i]
            bar_len = int(b["count"] / max_count * bar_width)
            bid_bar = '█' * bar_len
            bid_str = f"${b['mid']:>6.2f} {bid_bar:>{bar_width}} {b['count']:>3}"
        else:
            bid_str = " " * (width // 2 - 1)

        # Ask side
        if i < len(ask_buckets):
            a = ask_buckets[i]
            bar_len = int(a["count"] / max_count * bar_width)
            ask_bar = '█' * bar_len
            ask_str = f"{a['count']:>3} {ask_bar:<{bar_width}} ${a['mid']:<6.2f}"
        else:
            ask_str = " " * (width // 2 - 1)

        lines.append(f"{bid_str}|{ask_str}")

    lines.append(f"{'=' * width}\n")

    return "\n".join(lines)


def render_depth_chart(bids: list[dict], asks: list[dict], width: int = 70) -> str:
    """Render cumulative depth chart."""
    bid_prices = sorted([b["price"] for b in bids if b.get("price")], reverse=True)
    ask_prices = sorted([a["price"] for a in asks if a.get("price")])

    if not bid_prices and not ask_prices:
        return "No data for depth chart"

    lines = []
    lines.append(f"\n{'=' * width}")
    lines.append(f"{'CUMULATIVE DEPTH CHART':^{width}}")
    lines.append(f"{'=' * width}")

    all_prices = bid_prices + ask_prices
    if not all_prices:
        return "No price data"

    min_p, max_p = min(all_prices), max(all_prices)
    price_range = max_p - min_p or 1

    max_depth = max(len(bid_prices), len(ask_prices), 1)
    num_levels = 12
    bar_width = width - 25

    lines.append(f"{'Price':>10} {'BID Depth':^{bar_width//2}}|{'ASK Depth':^{bar_width//2}}")
    lines.append(f"{'-' * width}")

    for i in range(num_levels):
        price_level = max_p - (i * price_range / (num_levels - 1))

        bid_cum = sum(1 for p in bid_prices if p >= price_level)
        ask_cum = sum(1 for p in ask_prices if p <= price_level)

        bid_bar_len = int(bid_cum / max_depth * (bar_width // 2 - 2))
        ask_bar_len = int(ask_cum / max_depth * (bar_width // 2 - 2))

        bid_bar = '█' * bid_bar_len
        ask_bar = '█' * ask_bar_len

        lines.append(f"${price_level:>8.2f} {bid_bar:>{bar_width//2-1}}|{ask_bar:<{bar_width//2-1}}")

    lines.append(f"{'=' * width}")
    lines.append(f"  Total BID: {len(bid_prices):>5}  |  Total ASK: {len(ask_prices):<5}")

    return "\n".join(lines)


def analyze_spread(bids: list[dict], asks: list[dict], highest_bid_override: float | None = None) -> dict:
    """Analyze bid-ask spread and market efficiency."""
    bid_prices = [b["price"] for b in bids if b.get("price")]
    ask_prices = [a["price"] for a in asks if a.get("price")]

    best_bid = max(bid_prices) if bid_prices else highest_bid_override
    best_ask = min(ask_prices) if ask_prices else None

    if not best_bid or not best_ask:
        return {"error": "Insufficient data for spread analysis"}

    spread = best_ask - best_bid
    spread_pct = (spread / best_ask) * 100
    mid_price = (best_bid + best_ask) / 2

    if spread_pct < 5:
        efficiency = "HIGH (tight spread)"
    elif spread_pct < 10:
        efficiency = "MEDIUM"
    elif spread_pct < 20:
        efficiency = "LOW (wide spread)"
    else:
        efficiency = "VERY LOW (illiquid)"

    return {
        "best_bid": best_bid,
        "best_ask": best_ask,
        "spread": spread,
        "spread_pct": spread_pct,
        "mid_price": mid_price,
        "bid_depth": len(bid_prices),
        "ask_depth": len(ask_prices),
        "efficiency": efficiency
    }


# =============================================================================
# Main
# =============================================================================

def main():
    parser = ArgumentParser(description="Analyze bid-ask order book")
    parser.add_argument("--card-id", type=int, help="Card ID to analyze")
    parser.add_argument("--card-name", type=str, help="Card name to search")
    parser.add_argument("--days", type=int, default=90, help="Lookback days (default: 90)")
    parser.add_argument("--list", action="store_true", help="List top cards by listings")
    args = parser.parse_args()

    print("\n" + "=" * 70)
    print("BID-ASK ORDER BOOK ANALYSIS")
    print("=" * 70)

    # List top cards
    if args.list or (not args.card_id and not args.card_name):
        print("\nTop cards by active listing count:")
        print("-" * 50)
        top_cards = get_top_cards_by_listings(15)
        for card in top_cards:
            print(f"  [{card['id']:>3}] {card['name']:<40} ({card['listing_count']} listings)")

        if not args.card_id and not args.card_name:
            print("\nUsage: python scripts/analyze_order_book.py --card-id <ID>")
            print("       python scripts/analyze_order_book.py --card-name \"Card Name\"")
            if top_cards:
                args.card_id = top_cards[0]["id"]
                print(f"\nUsing top card: {top_cards[0]['name']}")
            else:
                return

    # Find card
    card = find_card(args.card_id, args.card_name)
    if not card:
        print(f"\nCard not found!")
        return

    card_id = card["id"]
    card_name = card["name"]

    print(f"\n{'=' * 70}")
    print(f"Analyzing: {card_name} (ID: {card_id})")
    print(f"{'=' * 70}")

    # =========================================================================
    # Platform Data (eBay, OpenSea, Blokpax via marketprice)
    # =========================================================================
    platforms = get_platforms_for_card(card_id)
    print(f"\nPlatforms with data: {', '.join(platforms) if platforms else 'None'}")

    all_asks = []
    all_sales = []

    for platform in platforms:
        print(f"\n--- {platform.upper()} Data ---")

        asks = get_asks(card_id, platform, args.days)
        sales = get_sales(card_id, platform, args.days)

        all_asks.extend(asks)
        all_sales.extend(sales)

        print(f"  ASK side: {len(asks)} active listings")
        print(f"  BID side: {len(sales)} recent sales (proven demand)")

        if platform == "ebay":
            ebay_highest_bid = get_ebay_highest_bid(card_id)
            if ebay_highest_bid:
                print(f"            highest_bid = ${ebay_highest_bid:.2f}")

        if asks:
            print(f"\n  ASK range: ${min(a['price'] for a in asks):.2f} - ${max(a['price'] for a in asks):.2f}")
            print(f"  Lowest 5 asks:")
            for a in asks[:5]:
                treatment = a.get('treatment') or 'N/A'
                print(f"    ${a['price']:>8.2f}  {treatment:<20}")

        if sales:
            print(f"\n  BID range: ${min(s['price'] for s in sales):.2f} - ${max(s['price'] for s in sales):.2f}")
            print(f"  Highest 5 sales:")
            for s in sales[:5]:
                treatment = s.get('treatment') or 'N/A'
                print(f"    ${s['price']:>8.2f}  {treatment:<20}")

        # Platform order book visualization
        if asks or sales:
            print(render_ascii_order_book(
                bids=sales,
                asks=asks,
                title=f"{platform.upper()} Order Book: {card_name}"
            ))

    # Combined view if multiple platforms
    if len(platforms) > 1 and (all_asks or all_sales):
        print(render_ascii_order_book(
            bids=all_sales,
            asks=all_asks,
            title=f"COMBINED Order Book: {card_name}"
        ))

    # =========================================================================
    # Blokpax Data (from dedicated tables)
    # =========================================================================
    print("\n--- Blokpax Data ---")

    # Get Blokpax sales from blokpaxsale table (linked by card_id)
    bpx_sales = get_blokpax_sales_by_card(card_id, args.days)

    # Get asset-level data if linked
    bpx_asset = get_blokpax_asset_for_card(card_id)
    bpx_asks = []
    bpx_bids = []

    if bpx_asset:
        bpx_asks = get_blokpax_asks(bpx_asset["external_id"])
        bpx_bids = get_blokpax_bids(bpx_asset["external_id"])
        print(f"  Asset: {bpx_asset['name']}")

    print(f"  ASK side: {len(bpx_asks)} active listings")
    print(f"  BID side: {len(bpx_sales)} sales + {len(bpx_bids)} open offers")

    if bpx_sales:
        print(f"\n  Sales price range: ${min(s['price'] for s in bpx_sales):.2f} - ${max(s['price'] for s in bpx_sales):.2f}")
        print(f"  Recent sales:")
        for s in bpx_sales[:5]:
            print(f"    ${s['price']:>8.2f}  {s.get('title', 'N/A')[:40]}")

    # Combine sales + offers for bid side
    bpx_all_bids = bpx_sales + bpx_bids

    if bpx_all_bids or bpx_asks:
        print(render_ascii_order_book(
            bids=bpx_all_bids,
            asks=bpx_asks,
            title=f"Blokpax Order Book: {card_name}"
        ))

        # Add to combined totals
        all_sales.extend(bpx_sales)
    else:
        print("  No Blokpax data found")

    # =========================================================================
    # Depth Chart (Combined)
    # =========================================================================
    if all_sales and all_asks:
        print(render_depth_chart(all_sales, all_asks))

    # =========================================================================
    # Spread Analysis
    # =========================================================================
    print("\n--- Spread Analysis ---")

    combined_spread = analyze_spread(all_sales, all_asks)
    print(f"\nCombined (All Platforms - Sales vs Asks):")
    if "error" not in combined_spread:
        print(f"  Best Bid (highest sale): ${combined_spread['best_bid']:>8.2f}")
        print(f"  Best Ask (lowest list):  ${combined_spread['best_ask']:>8.2f}")
        print(f"  Spread:                  ${combined_spread['spread']:>8.2f} ({combined_spread['spread_pct']:.1f}%)")
        print(f"  Mid Price:               ${combined_spread['mid_price']:>8.2f}")
        print(f"  Efficiency:              {combined_spread['efficiency']}")
    else:
        print(f"  {combined_spread['error']}")

    if bpx_all_bids or bpx_asks:
        bpx_spread = analyze_spread(bpx_all_bids, bpx_asks)
        print(f"\nBlokpax:")
        if "error" not in bpx_spread:
            print(f"  Best Bid:   ${bpx_spread['best_bid']:>8.2f}")
            print(f"  Best Ask:   ${bpx_spread['best_ask']:>8.2f}")
            print(f"  Spread:     ${bpx_spread['spread']:>8.2f} ({bpx_spread['spread_pct']:.1f}%)")
            print(f"  Mid Price:  ${bpx_spread['mid_price']:>8.2f}")
            print(f"  Efficiency: {bpx_spread['efficiency']}")
        else:
            print(f"  {bpx_spread['error']}")

    # =========================================================================
    # Summary
    # =========================================================================
    print("\n" + "=" * 70)
    print("ORDER BOOK DATA SOURCES")
    print("=" * 70)
    print("\neBay / OpenSea (via marketprice table):")
    print("  ASK: Active listings (listing_type='active')")
    print("  BID: Recent sales as proven demand (listing_type='sold')")
    print("\nBlokpax (separate tables):")
    print("  ASK: Active listings (blokpaxlisting.status='active')")
    print("  BID: Open offers (blokpaxoffer.status='open')")
    print("\nInterpretation:")
    print("  - Sales show PROVEN demand at specific price points")
    print("  - Negative spread = asks below recent sales (buying opportunity)")
    print("  - Positive spread = asks above recent sales (overpriced)")
    print("  - Mid price = fair value estimate")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
