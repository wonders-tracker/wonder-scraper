#!/usr/bin/env python3
"""
Market Pattern Discovery

Use ML to discover patterns and relationships in the card market:
1. Treatment price hierarchies
2. Rarity effects on price
3. Card clustering (which cards behave similarly)
4. Price volatility patterns
5. Liquidity drivers
6. Deal detection (underpriced sales)

Usage:
    poetry run python scripts/discover_market_patterns.py
"""

import logging
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# DATA
# =============================================================================


def fetch_all_data(days: int = 180) -> pd.DataFrame:
    """Fetch sales with full card metadata."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = text("""
        SELECT
            mp.card_id,
            c.name as card_name,
            c.card_number,
            r.name as rarity,
            c.card_type,
            c.set_name,
            COALESCE(NULLIF(mp.product_subtype, ''), mp.treatment) as treatment,
            mp.price,
            COALESCE(mp.sold_date, mp.scraped_at) as sale_date,
            mp.platform
        FROM marketprice mp
        JOIN card c ON c.id = mp.card_id
        LEFT JOIN rarity r ON r.id = c.rarity_id
        WHERE mp.listing_type = 'sold'
          AND mp.is_bulk_lot = FALSE
          AND COALESCE(mp.sold_date, mp.scraped_at) >= :cutoff
          AND mp.price > 0.5
          AND mp.price < 2000
          AND c.card_number IS NOT NULL
    """)

    with Session(engine) as session:
        result = session.execute(query, {"cutoff": cutoff})
        rows = result.fetchall()

    df = pd.DataFrame(
        rows,
        columns=[
            "card_id",
            "card_name",
            "card_number",
            "rarity",
            "card_type",
            "set_name",
            "treatment",
            "price",
            "sale_date",
            "platform",
        ],
    )

    df["sale_date"] = pd.to_datetime(df["sale_date"], utc=True)
    df["treatment"] = df["treatment"].fillna("Classic Paper")
    df["rarity"] = df["rarity"].fillna("Unknown")
    df["card_type"] = df["card_type"].fillna("Unknown")

    # Normalize treatments
    df["treatment"] = df["treatment"].apply(normalize_treatment)

    return df


def normalize_treatment(t: str) -> str:
    """Normalize treatment names."""
    t = str(t).strip()
    if "Paper" in t or t in ("Base", "Unknown", "Classic Regular"):
        return "Classic Paper"
    if "Stone" in t:
        return "Stonefoil"
    if "Formless" in t:
        return "Formless Foil"
    if t == "Classic Foil" or (t.endswith("Foil") and "Formless" not in t and "Stone" not in t):
        return "Classic Foil"
    if "Serial" in t or "OCM" in t:
        return "Serialized"
    if "Preslab" in t or "TAG" in t:
        return "Graded/Preslab"
    if "Promo" in t or "Prerelease" in t:
        return "Promo"
    return t


# =============================================================================
# ANALYSIS 1: Treatment Hierarchy
# =============================================================================


def analyze_treatment_hierarchy(df: pd.DataFrame):
    """Discover treatment price relationships."""
    print("\n" + "=" * 70)
    print("1. TREATMENT PRICE HIERARCHY")
    print("=" * 70)

    # Get cards that have multiple treatments sold
    card_treatments = df.groupby(["card_id", "treatment"])["price"].agg(["median", "count", "std"]).reset_index()
    card_treatments.columns = ["card_id", "treatment", "median_price", "sale_count", "price_std"]

    # Pivot to get treatment prices per card
    pivot = card_treatments.pivot(index="card_id", columns="treatment", values="median_price")

    # Calculate pairwise ratios
    base_treatment = "Classic Paper"
    if base_treatment in pivot.columns:
        print(f"\nTreatment multipliers (vs {base_treatment}):")
        print("-" * 50)

        multipliers = {}
        for treatment in pivot.columns:
            if treatment == base_treatment:
                continue
            # Only use cards that have both treatments
            mask = pivot[base_treatment].notna() & pivot[treatment].notna()
            if mask.sum() >= 3:
                ratios = pivot.loc[mask, treatment] / pivot.loc[mask, base_treatment]
                multipliers[treatment] = {
                    "median": ratios.median(),
                    "mean": ratios.mean(),
                    "std": ratios.std(),
                    "cards": mask.sum(),
                }

        # Sort by multiplier
        for t, m in sorted(multipliers.items(), key=lambda x: x[1]["median"]):
            print(f"  {t:<20} {m['median']:>6.2f}x  (n={m['cards']}, std={m['std']:.2f})")

    # Overall treatment stats
    print("\nOverall treatment statistics:")
    print("-" * 50)
    treatment_stats = df.groupby("treatment").agg({"price": ["median", "mean", "std", "count"], "card_id": "nunique"})
    treatment_stats.columns = ["Median $", "Mean $", "Std $", "Sales", "Cards"]
    treatment_stats = treatment_stats.sort_values("Median $")
    print(treatment_stats.round(2).to_string())


# =============================================================================
# ANALYSIS 2: Rarity Effects
# =============================================================================


def analyze_rarity_effects(df: pd.DataFrame):
    """Analyze how rarity affects price."""
    print("\n" + "=" * 70)
    print("2. RARITY EFFECTS ON PRICE")
    print("=" * 70)

    # Filter to Classic Paper to isolate rarity effect
    paper_df = df[df["treatment"] == "Classic Paper"]

    print("\nRarity price distribution (Classic Paper only):")
    print("-" * 50)

    rarity_order = ["Common", "Uncommon", "Rare", "Epic", "Legendary", "Mythic"]
    rarity_stats = paper_df.groupby("rarity").agg(
        {"price": ["median", "mean", "min", "max", "count"], "card_id": "nunique"}
    )
    rarity_stats.columns = ["Median", "Mean", "Min", "Max", "Sales", "Cards"]

    # Reorder
    rarity_stats = rarity_stats.reindex([r for r in rarity_order if r in rarity_stats.index])
    print(rarity_stats.round(2).to_string())

    # Rarity multipliers
    if "Common" in rarity_stats.index:
        base = rarity_stats.loc["Common", "Median"]
        print("\nRarity multipliers (vs Common):")
        for rarity in rarity_stats.index:
            mult = rarity_stats.loc[rarity, "Median"] / base
            print(f"  {rarity:<12} {mult:>6.2f}x")


# =============================================================================
# ANALYSIS 3: Card Type Effects
# =============================================================================


def analyze_card_types(df: pd.DataFrame):
    """Analyze price patterns by card type."""
    print("\n" + "=" * 70)
    print("3. CARD TYPE ANALYSIS")
    print("=" * 70)

    # Filter to Classic Paper
    paper_df = df[df["treatment"] == "Classic Paper"]

    type_stats = paper_df.groupby("card_type").agg({"price": ["median", "mean", "count"], "card_id": "nunique"})
    type_stats.columns = ["Median $", "Mean $", "Sales", "Cards"]
    type_stats = type_stats.sort_values("Median $", ascending=False)

    print("\nPrice by card type (Classic Paper):")
    print("-" * 50)
    print(type_stats.round(2).to_string())


# =============================================================================
# ANALYSIS 4: Price Volatility
# =============================================================================


def analyze_volatility(df: pd.DataFrame):
    """Find which cards/treatments are most volatile."""
    print("\n" + "=" * 70)
    print("4. PRICE VOLATILITY ANALYSIS")
    print("=" * 70)

    # Calculate volatility per card+treatment
    vol_df = (
        df.groupby(["card_id", "card_name", "treatment"])
        .agg({"price": ["median", "std", "count", "min", "max"]})
        .reset_index()
    )
    vol_df.columns = ["card_id", "card_name", "treatment", "median", "std", "count", "min", "max"]

    # Coefficient of variation
    vol_df["cv"] = vol_df["std"] / vol_df["median"]
    vol_df["range_pct"] = (vol_df["max"] - vol_df["min"]) / vol_df["median"] * 100

    # Filter to items with enough sales
    vol_df = vol_df[vol_df["count"] >= 5]

    print("\nMost volatile (high price variation):")
    print("-" * 70)
    most_volatile = vol_df.nlargest(10, "cv")[["card_name", "treatment", "median", "cv", "range_pct", "count"]]
    most_volatile.columns = ["Card", "Treatment", "Median $", "CV", "Range %", "Sales"]
    print(most_volatile.round(2).to_string(index=False))

    print("\nMost stable (low price variation):")
    print("-" * 70)
    most_stable = vol_df.nsmallest(10, "cv")[["card_name", "treatment", "median", "cv", "range_pct", "count"]]
    most_stable.columns = ["Card", "Treatment", "Median $", "CV", "Range %", "Sales"]
    print(most_stable.round(2).to_string(index=False))

    # Volatility by treatment
    print("\nVolatility by treatment:")
    print("-" * 50)
    treatment_vol = vol_df.groupby("treatment")["cv"].agg(["median", "mean", "count"])
    treatment_vol.columns = ["Median CV", "Mean CV", "Cards"]
    treatment_vol = treatment_vol.sort_values("Median CV")
    print(treatment_vol.round(3).to_string())


# =============================================================================
# ANALYSIS 5: Liquidity Patterns
# =============================================================================


def analyze_liquidity(df: pd.DataFrame):
    """Analyze what drives card liquidity."""
    print("\n" + "=" * 70)
    print("5. LIQUIDITY ANALYSIS")
    print("=" * 70)

    # Sales velocity by card
    days_in_period = (df["sale_date"].max() - df["sale_date"].min()).days
    card_liquidity = (
        df.groupby(["card_id", "card_name", "rarity"])
        .agg({"price": ["count", "median"], "treatment": "nunique"})
        .reset_index()
    )
    card_liquidity.columns = ["card_id", "card_name", "rarity", "total_sales", "median_price", "treatments_sold"]
    card_liquidity["sales_per_month"] = card_liquidity["total_sales"] / (days_in_period / 30)

    print("\nMost liquid cards (highest sales velocity):")
    print("-" * 70)
    most_liquid = card_liquidity.nlargest(15, "sales_per_month")[
        ["card_name", "rarity", "sales_per_month", "median_price", "treatments_sold"]
    ]
    most_liquid.columns = ["Card", "Rarity", "Sales/Month", "Median $", "Treatments"]
    print(most_liquid.round(2).to_string(index=False))

    # Liquidity by rarity
    print("\nLiquidity by rarity:")
    print("-" * 50)
    rarity_liq = card_liquidity.groupby("rarity")["sales_per_month"].agg(["median", "mean", "sum"])
    rarity_liq.columns = ["Median Sales/Mo", "Mean Sales/Mo", "Total Sales"]
    rarity_liq = rarity_liq.sort_values("Median Sales/Mo", ascending=False)
    print(rarity_liq.round(2).to_string())

    # Liquidity vs Price correlation
    corr = card_liquidity["sales_per_month"].corr(card_liquidity["median_price"])
    print(f"\nCorrelation: Liquidity vs Price = {corr:.3f}")
    if corr < -0.3:
        print("  → Cheaper cards sell more often")
    elif corr > 0.3:
        print("  → Expensive cards sell more often")
    else:
        print("  → No strong relationship")


# =============================================================================
# ANALYSIS 6: Deal Detection
# =============================================================================


def analyze_deals(df: pd.DataFrame):
    """Find underpriced sales (deals)."""
    print("\n" + "=" * 70)
    print("6. DEAL DETECTION")
    print("=" * 70)

    # Calculate floor for each card+treatment
    floors = (
        df.groupby(["card_id", "card_name", "treatment"])
        .agg({"price": lambda x: np.mean(sorted(x)[:4]) if len(x) >= 4 else x.min()})
        .reset_index()
    )
    floors.columns = ["card_id", "card_name", "treatment", "floor_price"]

    # Merge back
    df_with_floor = df.merge(floors, on=["card_id", "card_name", "treatment"])

    # Calculate deal score (how far below floor)
    df_with_floor["deal_score"] = (df_with_floor["floor_price"] - df_with_floor["price"]) / df_with_floor["floor_price"]
    df_with_floor["discount_pct"] = df_with_floor["deal_score"] * 100

    # Best deals
    deals = df_with_floor[df_with_floor["deal_score"] > 0.2]  # At least 20% below floor
    deals = deals.sort_values("deal_score", ascending=False)

    print("\nRecent deals (>20% below floor):")
    print("-" * 80)
    if len(deals) > 0:
        recent_deals = deals.head(15)[["card_name", "treatment", "price", "floor_price", "discount_pct", "sale_date"]]
        recent_deals.columns = ["Card", "Treatment", "Paid", "Floor", "Discount %", "Date"]
        print(recent_deals.round(2).to_string(index=False))
    else:
        print("  No significant deals found")

    # Deal frequency by treatment
    print("\nDeal frequency by treatment:")
    print("-" * 50)
    df_with_floor["is_deal"] = df_with_floor["deal_score"] > 0.2
    deal_freq = df_with_floor.groupby("treatment").agg({"is_deal": ["sum", "mean"], "price": "count"})
    deal_freq.columns = ["Deals", "Deal Rate", "Total Sales"]
    deal_freq["Deal Rate"] = deal_freq["Deal Rate"] * 100
    deal_freq = deal_freq.sort_values("Deal Rate", ascending=False)
    print(deal_freq.round(1).to_string())


# =============================================================================
# ANALYSIS 7: Card Clustering
# =============================================================================


def analyze_card_clusters(df: pd.DataFrame):
    """Cluster cards by behavior patterns."""
    print("\n" + "=" * 70)
    print("7. CARD CLUSTERING (Similar Market Behavior)")
    print("=" * 70)

    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler

    # Build card feature matrix
    card_features = (
        df.groupby(["card_id", "card_name", "rarity"])
        .agg({"price": ["median", "std", "count", "min", "max"], "treatment": "nunique"})
        .reset_index()
    )
    card_features.columns = [
        "card_id",
        "card_name",
        "rarity",
        "median_price",
        "price_std",
        "sale_count",
        "min_price",
        "max_price",
        "treatment_count",
    ]

    # Derived features
    card_features["price_range"] = card_features["max_price"] - card_features["min_price"]
    card_features["cv"] = card_features["price_std"].fillna(0) / card_features["median_price"].replace(0, 1)

    # Filter cards with enough data
    card_features = card_features[card_features["sale_count"] >= 3]

    if len(card_features) < 10:
        print("Not enough cards with sufficient sales for clustering")
        return

    # Features for clustering
    feature_cols = ["median_price", "cv", "sale_count", "treatment_count"]
    X = card_features[feature_cols].fillna(0).values

    # Scale
    scaler = StandardScaler()
    X_scaled = scaler.fit_transform(X)

    # Cluster
    n_clusters = min(5, len(card_features) // 5)
    kmeans = KMeans(n_clusters=n_clusters, random_state=42, n_init=10)
    card_features["cluster"] = kmeans.fit_predict(X_scaled)

    # Describe clusters
    print(f"\nCard clusters (n={n_clusters}):")
    print("-" * 70)

    cluster_names = {
        0: "Budget Commons",
        1: "Mid-Tier Staples",
        2: "Premium Rares",
        3: "Chase Cards",
        4: "Ultra Premium",
    }

    for cluster_id in sorted(card_features["cluster"].unique()):
        cluster_cards = card_features[card_features["cluster"] == cluster_id]
        print(f"\nCluster {cluster_id}: {len(cluster_cards)} cards")
        print(f"  Median price: ${cluster_cards['median_price'].median():.2f}")
        print(f"  Avg sales: {cluster_cards['sale_count'].mean():.1f}")
        print(f"  Volatility (CV): {cluster_cards['cv'].median():.2f}")
        print(f"  Top cards: {', '.join(cluster_cards.nlargest(3, 'sale_count')['card_name'].tolist())}")


# =============================================================================
# ANALYSIS 8: Time Patterns
# =============================================================================


def analyze_time_patterns(df: pd.DataFrame):
    """Analyze temporal patterns in sales."""
    print("\n" + "=" * 70)
    print("8. TEMPORAL PATTERNS")
    print("=" * 70)

    df = df.copy()
    df["day_of_week"] = df["sale_date"].dt.day_name()
    df["hour"] = df["sale_date"].dt.hour
    df["week"] = df["sale_date"].dt.isocalendar().week

    # Day of week
    print("\nSales by day of week:")
    print("-" * 40)
    dow_stats = df.groupby("day_of_week").agg({"price": ["count", "median"]})
    dow_stats.columns = ["Sales", "Median $"]
    day_order = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    dow_stats = dow_stats.reindex([d for d in day_order if d in dow_stats.index])
    print(dow_stats.round(2).to_string())

    # Weekly trend
    print("\nWeekly sales trend (last 12 weeks):")
    print("-" * 40)
    weekly = df.groupby("week").agg({"price": ["count", "median", "sum"]}).tail(12)
    weekly.columns = ["Sales", "Median $", "Volume $"]
    print(weekly.round(2).to_string())


# =============================================================================
# MAIN
# =============================================================================


def main():
    print("=" * 70)
    print("MARKET PATTERN DISCOVERY")
    print("=" * 70)
    print("Analyzing card market relationships and patterns...\n")

    df = fetch_all_data(days=180)
    print(f"Loaded {len(df):,} sales from {df['card_id'].nunique()} cards")
    print(f"Treatments: {df['treatment'].nunique()}")
    print(f"Date range: {df['sale_date'].min().date()} to {df['sale_date'].max().date()}")

    # Run analyses
    analyze_treatment_hierarchy(df)
    analyze_rarity_effects(df)
    analyze_card_types(df)
    analyze_volatility(df)
    analyze_liquidity(df)
    analyze_deals(df)
    analyze_card_clusters(df)
    analyze_time_patterns(df)

    print("\n" + "=" * 70)
    print("ANALYSIS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
