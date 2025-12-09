#!/usr/bin/env python3
"""
Generate seller pricing analysis report: How accurately do sellers price their items?

This report analyzes the VARIANCE in seller pricing for identical items (same card + treatment),
revealing how much "gut feeling" pricing differs from market reality.

Key insight: When the same exact item sells for $20 one day and $200 the next,
someone is wildly mispricing - either leaving money on the table or overcharging.

Usage:
    python scripts/generate_pricing_analysis.py
    python scripts/generate_pricing_analysis.py --days 30
    python scripts/generate_pricing_analysis.py --print
"""

import argparse
from datetime import datetime, timedelta
from pathlib import Path

from sqlmodel import Session
from sqlalchemy import text

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db import engine


def format_currency(val: float) -> str:
    """Format value as currency."""
    if val is None:
        return "N/A"
    return f"${val:,.2f}"


def format_pct(val: float) -> str:
    """Format as percentage."""
    if val is None:
        return "N/A"
    return f"{val:.1f}%"


def format_pct_change(val: float) -> str:
    """Format as percentage change with +/- sign."""
    if val is None:
        return "N/A"
    if val > 0:
        return f"+{val:.0f}%"
    return f"{val:.0f}%"


def bar_txt(value: float, max_value: float, width: int = 25, filled: str = "█", empty: str = "░") -> str:
    """Create ASCII bar for txt output."""
    if max_value == 0:
        return empty * width
    fill_count = int((value / max_value) * width)
    return filled * fill_count + empty * (width - fill_count)


def generate_pricing_analysis(days: int = 90) -> dict:
    """
    Analyze seller pricing accuracy by examining price variance for identical items.

    METHODOLOGY:
    - SINGLES ONLY - Packs, boxes, bundles have too much variance in quantity/contents
    - Compare sales of the SAME card + SAME treatment to each other
    - Calculate price spread, variance, and outliers within each group
    - Show how "gut feeling" pricing creates massive price disparities
    - Compare current asking prices to recent actual sale prices
    """
    with Session(engine) as session:
        now = datetime.utcnow()
        period_start = now - timedelta(days=days)

        data = {
            "generated_at": now,
            "period_start": period_start,
            "period_end": now,
            "days": days,
        }

        # Exclusion filter for:
        # - Slabs (PSA, CGC, BGS, TAG graded)
        # - Non-WOTF cards (MTG, Yu-Gi-Oh, Pokemon)
        # Note: Alt Art now has its own treatment, no need to exclude
        exclusion_filter = """
            AND mp.title NOT ILIKE '%psa %'
            AND mp.title NOT ILIKE '%psa-%'
            AND mp.title NOT ILIKE '% psa%'
            AND mp.title NOT ILIKE '%cgc %'
            AND mp.title NOT ILIKE '%cgc-%'
            AND mp.title NOT ILIKE '% cgc%'
            AND mp.title NOT ILIKE '%bgs %'
            AND mp.title NOT ILIKE '%bgs-%'
            AND mp.title NOT ILIKE '% bgs%'
            AND mp.title NOT ILIKE '%graded%'
            AND mp.title NOT ILIKE '%slab%'
            AND mp.title NOT ILIKE '%cert:%'
            AND mp.title NOT ILIKE '%cert #%'
            AND mp.title NOT ILIKE '%(cert:%'
            AND mp.title NOT ILIKE '%tag slab%'
            AND mp.title NOT ILIKE '%tag grade%'
            AND mp.title NOT ILIKE '%war of the spark%'
            AND mp.title NOT ILIKE '%yu-gi-oh%'
            AND mp.title NOT ILIKE '%yugioh%'
            AND mp.title NOT ILIKE '% ra03-%'
            AND mp.title NOT ILIKE '%pokemon tcg%'
        """

        # Get data quality stats - SINGLES ONLY (excluding slabs)
        quality_stats = session.execute(text(f"""
            SELECT
                COUNT(*) as total_sold,
                COUNT(CASE WHEN mp.treatment IS NOT NULL AND mp.treatment != '' THEN 1 END) as has_treatment,
                COUNT(CASE WHEN mp.seller_name IS NOT NULL AND mp.seller_name != '' THEN 1 END) as has_seller,
                COUNT(DISTINCT mp.card_id) as unique_cards
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            WHERE mp.listing_type = 'sold'
            AND mp.sold_date >= :start
            AND mp.platform = 'ebay'
            AND c.product_type = 'Single'
            {exclusion_filter}
        """), {"start": period_start}).first()

        data["data_quality"] = {
            "total_sales": quality_stats[0],
            "with_treatment": quality_stats[1],
            "treatment_coverage": (quality_stats[1] / quality_stats[0] * 100) if quality_stats[0] > 0 else 0,
            "with_seller": quality_stats[2],
            "seller_coverage": (quality_stats[2] / quality_stats[0] * 100) if quality_stats[0] > 0 else 0,
            "unique_cards": quality_stats[3],
        }

        # PRICE VARIANCE ANALYSIS - The core story (SINGLES ONLY, no slabs)
        # How much do prices vary for the SAME item?
        variance_stats = session.execute(text(f"""
            WITH sale_stats AS (
                SELECT
                    mp.card_id,
                    mp.treatment,
                    c.name,
                    COUNT(*) as sales,
                    MIN(mp.price) as min_price,
                    MAX(mp.price) as max_price,
                    AVG(mp.price) as avg_price,
                    STDDEV(mp.price) as price_stddev,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.platform = 'ebay'
                AND mp.sold_date >= :start
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.card_id, mp.treatment, c.name
                HAVING COUNT(*) >= 3
            )
            SELECT
                COUNT(*) as items_analyzed,
                AVG((max_price - min_price) / NULLIF(avg_price, 0) * 100) as avg_spread_pct,
                COUNT(CASE WHEN (max_price - min_price) / NULLIF(avg_price, 0) >= 1.0 THEN 1 END) as items_100pct_spread,
                COUNT(CASE WHEN (max_price - min_price) / NULLIF(avg_price, 0) >= 0.5 THEN 1 END) as items_50pct_spread,
                MAX((max_price - min_price) / NULLIF(avg_price, 0) * 100) as max_spread_pct
            FROM sale_stats
        """), {"start": period_start}).first()

        data["variance_summary"] = {
            "items_analyzed": variance_stats[0] or 0,
            "avg_spread_pct": variance_stats[1] or 0,
            "items_100pct_spread": variance_stats[2] or 0,
            "items_50pct_spread": variance_stats[3] or 0,
            "max_spread_pct": variance_stats[4] or 0,
        }

        # WORST PRICING - Items with highest price variance (same card+treatment, SINGLES ONLY, no slabs)
        worst_pricing = session.execute(text(f"""
            WITH sale_stats AS (
                SELECT
                    mp.card_id,
                    mp.treatment,
                    c.name,
                    COUNT(*) as sales,
                    MIN(mp.price) as min_price,
                    MAX(mp.price) as max_price,
                    AVG(mp.price) as avg_price,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price,
                    (MAX(mp.price) - MIN(mp.price)) / NULLIF(AVG(mp.price), 0) * 100 as spread_pct
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.platform = 'ebay'
                AND mp.sold_date >= :start
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.card_id, mp.treatment, c.name
                HAVING COUNT(*) >= 3
            )
            SELECT name, treatment, sales, min_price, max_price, avg_price, median_price, spread_pct
            FROM sale_stats
            ORDER BY spread_pct DESC
            LIMIT 20
        """), {"start": period_start}).all()

        data["worst_pricing"] = [
            {
                "name": row[0],
                "treatment": row[1],
                "sales": row[2],
                "min_price": row[3],
                "max_price": row[4],
                "avg_price": row[5],
                "median_price": float(row[6]) if row[6] else row[5],
                "spread_pct": row[7],
            }
            for row in worst_pricing
        ]

        # OUTLIER SALES - Individual sales way above/below median for that item (SINGLES ONLY, no slabs)
        outliers = session.execute(text(f"""
            WITH item_medians AS (
                SELECT
                    mp.card_id,
                    mp.treatment,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price,
                    COUNT(*) as sale_count
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.platform = 'ebay'
                AND mp.sold_date >= :start
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.card_id, mp.treatment
                HAVING COUNT(*) >= 3
            )
            SELECT
                c.name,
                mp.treatment,
                mp.price as sold_price,
                im.median_price,
                (mp.price - im.median_price) / NULLIF(im.median_price, 0) * 100 as deviation_pct,
                mp.sold_date,
                mp.seller_name,
                im.sale_count,
                CASE
                    WHEN mp.price > im.median_price THEN 'overpaid'
                    ELSE 'underpaid'
                END as direction
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN item_medians im ON mp.card_id = im.card_id AND mp.treatment = im.treatment
            WHERE mp.listing_type = 'sold'
            AND mp.sold_date >= :start
            AND mp.treatment IS NOT NULL
            AND mp.treatment != ''
            AND c.product_type = 'Single'
            {exclusion_filter}
            AND im.median_price > 0
            AND ABS((mp.price - im.median_price) / im.median_price) >= 0.5
            ORDER BY ABS((mp.price - im.median_price) / im.median_price) DESC
            LIMIT 30
        """), {"start": period_start}).all()

        data["outliers"] = [
            {
                "name": row[0],
                "treatment": row[1],
                "sold_price": row[2],
                "median": float(row[3]) if row[3] else 0,
                "deviation_pct": row[4],
                "date": row[5],
                "seller": row[6],
                "sample_size": row[7],
                "direction": row[8],
            }
            for row in outliers
        ]

        # CURRENT LISTINGS VS REALITY - Are today's sellers pricing accurately? (SINGLES ONLY, no slabs)
        current_vs_reality = session.execute(text(f"""
            WITH recent_sales AS (
                SELECT
                    mp.card_id,
                    mp.treatment,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_sold,
                    AVG(mp.price) as avg_sold,
                    COUNT(*) as sale_count
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.platform = 'ebay'
                AND mp.sold_date >= NOW() - INTERVAL '30 days'
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.card_id, mp.treatment
                HAVING COUNT(*) >= 2
            ),
            current_listings AS (
                SELECT
                    mp.card_id,
                    mp.treatment,
                    MIN(mp.price) as floor_price,
                    AVG(mp.price) as avg_ask,
                    COUNT(*) as listing_count
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'active'
                AND mp.platform = 'ebay'
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.card_id, mp.treatment
            )
            SELECT
                c.name,
                rs.treatment,
                rs.sale_count,
                rs.median_sold,
                rs.avg_sold,
                cl.floor_price,
                cl.avg_ask,
                cl.listing_count,
                (cl.floor_price - rs.median_sold) / NULLIF(rs.median_sold, 0) * 100 as floor_gap_pct,
                (cl.avg_ask - rs.avg_sold) / NULLIF(rs.avg_sold, 0) * 100 as avg_gap_pct
            FROM recent_sales rs
            JOIN current_listings cl ON rs.card_id = cl.card_id AND rs.treatment = cl.treatment
            JOIN card c ON rs.card_id = c.id
            WHERE cl.floor_price > 0 AND rs.median_sold > 0
            ORDER BY ABS((cl.floor_price - rs.median_sold) / NULLIF(rs.median_sold, 0) * 100) DESC
            LIMIT 20
        """)).all()

        data["current_vs_reality"] = [
            {
                "name": row[0],
                "treatment": row[1],
                "recent_sales": row[2],
                "median_sold": float(row[3]) if row[3] else 0,
                "avg_sold": row[4],
                "floor_price": row[5],
                "avg_ask": row[6],
                "listing_count": row[7],
                "floor_gap_pct": row[8],
                "avg_gap_pct": row[9],
            }
            for row in current_vs_reality
        ]

        # VARIANCE BY TREATMENT TYPE (SINGLES ONLY, no slabs)
        by_treatment = session.execute(text(f"""
            WITH sale_stats AS (
                SELECT
                    mp.treatment,
                    mp.card_id,
                    COUNT(*) as sales,
                    MIN(mp.price) as min_price,
                    MAX(mp.price) as max_price,
                    AVG(mp.price) as avg_price
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.platform = 'ebay'
                AND mp.sold_date >= :start
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.treatment, mp.card_id
                HAVING COUNT(*) >= 2
            )
            SELECT
                treatment,
                COUNT(DISTINCT card_id) as unique_items,
                SUM(sales) as total_sales,
                AVG((max_price - min_price) / NULLIF(avg_price, 0) * 100) as avg_spread_pct,
                COUNT(CASE WHEN (max_price - min_price) / NULLIF(avg_price, 0) >= 1.0 THEN 1 END) as items_100pct_spread
            FROM sale_stats
            GROUP BY treatment
            ORDER BY SUM(sales) DESC
        """), {"start": period_start}).all()

        data["by_treatment"] = [
            {
                "treatment": row[0],
                "unique_items": row[1],
                "total_sales": row[2],
                "avg_spread_pct": row[3] if row[3] else 0,
                "items_100pct_spread": row[4] or 0,
            }
            for row in by_treatment
        ]

        # MONEY LEFT ON TABLE - Sales significantly below median (seller underpriced) - SINGLES ONLY, no slabs
        money_left = session.execute(text(f"""
            WITH item_medians AS (
                SELECT
                    mp.card_id,
                    mp.treatment,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price,
                    COUNT(*) as sale_count
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.platform = 'ebay'
                AND mp.sold_date >= :start
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.card_id, mp.treatment
                HAVING COUNT(*) >= 3
            )
            SELECT
                SUM(im.median_price - mp.price) as total_left_on_table,
                COUNT(*) as underprice_count,
                AVG((im.median_price - mp.price) / NULLIF(im.median_price, 0) * 100) as avg_underprice_pct
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN item_medians im ON mp.card_id = im.card_id AND mp.treatment = im.treatment
            WHERE mp.listing_type = 'sold'
            AND mp.sold_date >= :start
            AND mp.treatment IS NOT NULL
            AND mp.treatment != ''
            AND c.product_type = 'Single'
            {exclusion_filter}
            AND mp.price < im.median_price * 0.7
            AND im.median_price > 5
        """), {"start": period_start}).first()

        data["money_left_on_table"] = {
            "total_amount": money_left[0] or 0,
            "transaction_count": money_left[1] or 0,
            "avg_underprice_pct": money_left[2] or 0,
        }

        # OVERPAY ANALYSIS - Sales significantly above median (buyer overpaid) - SINGLES ONLY, no slabs
        overpay = session.execute(text(f"""
            WITH item_medians AS (
                SELECT
                    mp.card_id,
                    mp.treatment,
                    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY mp.price) as median_price,
                    COUNT(*) as sale_count
                FROM marketprice mp
                JOIN card c ON mp.card_id = c.id
                WHERE mp.listing_type = 'sold'
                AND mp.platform = 'ebay'
                AND mp.sold_date >= :start
                AND mp.treatment IS NOT NULL
                AND mp.treatment != ''
                AND c.product_type = 'Single'
                {exclusion_filter}
                GROUP BY mp.card_id, mp.treatment
                HAVING COUNT(*) >= 3
            )
            SELECT
                SUM(mp.price - im.median_price) as total_overpaid,
                COUNT(*) as overpay_count,
                AVG((mp.price - im.median_price) / NULLIF(im.median_price, 0) * 100) as avg_overpay_pct
            FROM marketprice mp
            JOIN card c ON mp.card_id = c.id
            JOIN item_medians im ON mp.card_id = im.card_id AND mp.treatment = im.treatment
            WHERE mp.listing_type = 'sold'
            AND mp.sold_date >= :start
            AND mp.treatment IS NOT NULL
            AND mp.treatment != ''
            AND c.product_type = 'Single'
            {exclusion_filter}
            AND mp.price > im.median_price * 1.5
            AND im.median_price > 5
        """), {"start": period_start}).first()

        data["overpay_analysis"] = {
            "total_amount": overpay[0] or 0,
            "transaction_count": overpay[1] or 0,
            "avg_overpay_pct": overpay[2] or 0,
        }

        return data


def generate_txt_report(data: dict) -> str:
    """Generate plain text pricing analysis report with narrative."""
    lines = []

    # Header
    lines.append("")
    lines.append("+" + "=" * 78 + "+")
    lines.append("|" + "  WONDERS OF THE FIRST - SELLER PRICING REALITY CHECK  ".center(78) + "|")
    lines.append("|" + "  Single Cards Only (Treatment-Matched Analysis)  ".center(78) + "|")
    lines.append("|" + f"  {data['period_start'].strftime('%b %d')} - {data['period_end'].strftime('%b %d, %Y')} ({data['days']} days)  ".center(78) + "|")
    lines.append("+" + "=" * 78 + "+")

    # The Story
    lines.append("")
    lines.append("=" * 80)
    lines.append("  THE STORY")
    lines.append("=" * 80)
    lines.append("  Most eBay sellers price by gut feeling. This report reveals just how wildly")
    lines.append("  off those instincts often are.")
    lines.append("")
    lines.append("  When the EXACT SAME CARD (same name, same treatment) sells for $20 one day")
    lines.append("  and $200 the next, someone is badly mispricing. Either the $20 seller left")
    lines.append("  $180 on the table, or the $200 buyer got fleeced.")
    lines.append("")
    lines.append("  This analysis compares sales of IDENTICAL single cards to each other -")
    lines.append("  same card name + same treatment (e.g., 'Moonfire Crystal Mouse Formless")
    lines.append("  Foil' vs other 'Moonfire Crystal Mouse Formless Foil' sales only).")
    lines.append("")
    lines.append("  NOTE: Sealed product (boxes, packs, bundles) and graded slabs (PSA, CGC, BGS)")
    lines.append("  are excluded - too much variance in quantity/contents/condition.")

    # Data Quality
    dq = data["data_quality"]
    lines.append("")
    lines.append("=" * 80)
    lines.append("  DATA ANALYZED")
    lines.append("=" * 80)
    lines.append(f"  Total eBay Sales:              {dq['total_sales']:,}")
    lines.append(f"  Unique Cards Sold:             {dq['unique_cards']:,}")
    lines.append(f"  Sales with Treatment Data:     {dq['with_treatment']:,} ({dq['treatment_coverage']:.1f}%)")

    # The Headline Numbers
    vs = data["variance_summary"]
    ml = data["money_left_on_table"]
    op = data["overpay_analysis"]
    lines.append("")
    lines.append("=" * 80)
    lines.append("  THE BOTTOM LINE")
    lines.append("=" * 80)
    lines.append(f"  Items with 3+ sales analyzed:  {vs['items_analyzed']:,}")
    lines.append(f"  Average price spread:          {vs['avg_spread_pct']:.0f}%")
    lines.append(f"    (How much min/max prices differ for the same item)")
    lines.append("")
    lines.append(f"  Items with 100%+ spread:       {vs['items_100pct_spread']:,}")
    lines.append(f"    (Same item sold for DOUBLE or more in price range)")
    lines.append("")
    lines.append(f"  Items with 50%+ spread:        {vs['items_50pct_spread']:,}")
    lines.append(f"    (Significant pricing inconsistency)")
    lines.append("")
    if vs['max_spread_pct']:
        lines.append(f"  Worst spread:                  {vs['max_spread_pct']:.0f}%")

    # Money Impact
    lines.append("")
    lines.append("=" * 80)
    lines.append("  THE COST OF BAD PRICING")
    lines.append("=" * 80)
    lines.append("")
    lines.append("  SELLERS WHO UNDERPRICED (sold 30%+ below median):")
    lines.append(f"    Transactions:                {ml['transaction_count']:,}")
    lines.append(f"    Total left on table:         {format_currency(ml['total_amount'])}")
    lines.append(f"    Average underpriced by:      {ml['avg_underprice_pct']:.0f}%")
    lines.append("")
    lines.append("  BUYERS WHO OVERPAID (paid 50%+ above median):")
    lines.append(f"    Transactions:                {op['transaction_count']:,}")
    lines.append(f"    Total overpaid:              {format_currency(op['total_amount'])}")
    lines.append(f"    Average overpaid by:         {op['avg_overpay_pct']:.0f}%")

    # Worst Pricing Examples
    if data["worst_pricing"]:
        lines.append("")
        lines.append("=" * 80)
        lines.append("  HALL OF SHAME: WORST PRICING CONSISTENCY")
        lines.append("=" * 80)
        lines.append("  These cards had the wildest price swings (same card + same treatment):")
        lines.append("")
        lines.append(f"  {'Card':<26} {'Treatment':<24} {'Sales':>5} {'Low':>9} {'High':>10} {'Spread':>8}")
        lines.append("  " + "-" * 86)
        for i, w in enumerate(data["worst_pricing"][:15], 1):
            name = w['name'][:24]
            treat = w['treatment'][:22]
            lines.append(f"  {name:<26} {treat:<24} {w['sales']:>5} {format_currency(w['min_price']):>9} {format_currency(w['max_price']):>10} {w['spread_pct']:>7.0f}%")

    # Outlier Sales
    if data["outliers"]:
        lines.append("")
        lines.append("=" * 80)
        lines.append("  BIGGEST OUTLIERS: SOMEONE GOT BURNED")
        lines.append("=" * 80)
        lines.append("  Individual sales 50%+ away from the median for that item:")
        lines.append("")

        # Split into overpaid and underpaid
        overpaid = [o for o in data["outliers"] if o["direction"] == "overpaid"][:8]
        underpaid = [o for o in data["outliers"] if o["direction"] == "underpaid"][:8]

        if overpaid:
            lines.append("  BUYERS WHO OVERPAID:")
            lines.append(f"  {'Card':<50} {'Paid':>10} {'Median':>10} {'Diff':>8}")
            lines.append("  " + "-" * 82)
            for o in overpaid:
                name = f"{o['name'][:24]} ({o['treatment'][:22]})"
                lines.append(f"  {name:<50} {format_currency(o['sold_price']):>10} {format_currency(o['median']):>10} {format_pct_change(o['deviation_pct']):>8}")

        if underpaid:
            lines.append("")
            lines.append("  SELLERS WHO LEFT MONEY ON TABLE:")
            lines.append(f"  {'Card':<50} {'Sold':>10} {'Median':>10} {'Diff':>8}")
            lines.append("  " + "-" * 82)
            for o in underpaid:
                name = f"{o['name'][:24]} ({o['treatment'][:22]})"
                lines.append(f"  {name:<50} {format_currency(o['sold_price']):>10} {format_currency(o['median']):>10} {format_pct_change(o['deviation_pct']):>8}")

    # Current Listings vs Reality
    if data["current_vs_reality"]:
        lines.append("")
        lines.append("=" * 80)
        lines.append("  REALITY CHECK: CURRENT LISTINGS VS ACTUAL SALES")
        lines.append("=" * 80)
        lines.append("  Comparing what sellers are ASKING now vs what actually SOLD (last 30 days):")
        lines.append("")
        lines.append(f"  {'Card':<32} {'Treatment':<16} {'Sold@':>8} {'Ask@':>8} {'Gap':>8}")
        lines.append("  " + "-" * 76)
        for c in data["current_vs_reality"][:12]:
            name = c['name'][:30]
            treat = c['treatment'][:14]
            gap = format_pct_change(c['floor_gap_pct'])
            lines.append(f"  {name:<32} {treat:<16} {format_currency(c['median_sold']):>8} {format_currency(c['floor_price']):>8} {gap:>8}")

    # By Treatment
    if data["by_treatment"]:
        lines.append("")
        lines.append("=" * 80)
        lines.append("  PRICING CONSISTENCY BY TREATMENT")
        lines.append("=" * 80)
        lines.append("  Which treatments have the most chaotic pricing?")
        lines.append("")
        lines.append(f"  {'Treatment':<24} {'Cards':>6} {'Sales':>7} {'Avg Spread':>12} {'100%+ Spread':>13}")
        lines.append("  " + "-" * 66)
        for t in data["by_treatment"]:
            lines.append(f"  {t['treatment'][:22]:<24} {t['unique_items']:>6} {t['total_sales']:>7} {t['avg_spread_pct']:>11.0f}% {t['items_100pct_spread']:>13}")

    # Takeaway
    lines.append("")
    lines.append("=" * 80)
    lines.append("  KEY TAKEAWAYS")
    lines.append("=" * 80)
    lines.append("")
    lines.append("  1. GUT PRICING IS WILDLY INCONSISTENT")
    lines.append(f"     The same item regularly sells for {vs['avg_spread_pct']:.0f}% different prices.")
    lines.append(f"     {vs['items_100pct_spread']} items had sales ranging from X to 2X or more.")
    lines.append("")
    lines.append("  2. REAL MONEY IS BEING LEFT ON THE TABLE")
    lines.append(f"     {ml['transaction_count']} sellers underpriced by 30%+ = {format_currency(ml['total_amount'])} lost.")
    lines.append("")
    lines.append("  3. BUYERS ARE OVERPAYING")
    lines.append(f"     {op['transaction_count']} buyers paid 50%+ over median = {format_currency(op['total_amount'])} extra.")
    lines.append("")
    lines.append("  4. DATA BEATS GUT FEELING")
    lines.append("     Check recent sold prices before listing. Check median before buying.")
    lines.append("     The spread between informed and uninformed pricing is enormous.")

    # Footer
    lines.append("")
    lines.append("-" * 80)
    lines.append(f"  Generated: {data['generated_at'].strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("  Data Source: eBay sold listings via WondersTrader.com")
    lines.append("-" * 80)
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate eBay pricing analysis report")
    parser.add_argument("--days", "-d", type=int, default=90, help="Days to analyze (default: 90)")
    parser.add_argument("--output", "-o", default="data/marketReports", help="Output directory")
    parser.add_argument("--print", "-p", action="store_true", help="Print report to terminal")

    args = parser.parse_args()

    print(f"Generating pricing analysis for last {args.days} days...")

    data = generate_pricing_analysis(args.days)

    # Create output directory
    script_dir = Path(__file__).parent.parent
    output_dir = script_dir / args.output
    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate and save
    report = generate_txt_report(data)
    date_str = datetime.utcnow().strftime("%Y-%m-%d")
    output_path = output_dir / f"{date_str}-pricing-analysis.txt"
    output_path.write_text(report)

    print(f"Saved: {output_path}")

    if args.print:
        print(report)

    # Print summary
    vs = data["variance_summary"]
    ml = data["money_left_on_table"]
    op = data["overpay_analysis"]
    print(f"\nSummary:")
    print(f"  Items analyzed (3+ sales): {vs['items_analyzed']:,}")
    print(f"  Avg price spread: {vs['avg_spread_pct']:.0f}%")
    print(f"  Items with 100%+ spread: {vs['items_100pct_spread']:,}")
    print(f"  Money left on table: ${ml['total_amount']:,.2f} ({ml['transaction_count']} transactions)")
    print(f"  Buyer overpay: ${op['total_amount']:,.2f} ({op['transaction_count']} transactions)")


if __name__ == "__main__":
    main()
