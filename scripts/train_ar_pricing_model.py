#!/usr/bin/env python3
"""
Auto-Regressive Fair Market Price Model (v2)

GOAL: Predict what a card will sell for, given:
- Its recent sales history (AR features)
- Treatment premium/discount vs base
- Market liquidity signals
- Order book (what sellers are asking)

KEY DESIGN DECISIONS:
1. Cards only (no sealed product)
2. Predict RELATIVE to card's base price (not raw $)
3. Learn treatment multipliers from card-level data
4. Target = next sale price (true AR prediction)

Usage:
    poetry run python scripts/train_ar_pricing_model.py
    poetry run python scripts/train_ar_pricing_model.py --days 180
"""

import argparse
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sqlalchemy import text
from sqlmodel import Session

from app.db import engine

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# DATA COLLECTION
# =============================================================================

# Exclude sealed product - these aren't "cards"
EXCLUDED_TREATMENTS = {
    "Box",
    "Dragon Box",
    "Play Bundle",
    "Silver Pack",
    "Collector Bundle",
    "Collector Booster Pack",
    "Play Booster Pack",
    "Collector Booster Box",
    "Booster Pack",
    "Booster Box",
    "Bundle",
    "Pack",
}

# Core treatments we care about
CORE_TREATMENTS = {
    "Classic Paper",
    "Classic Foil",
    "Stonefoil",
    "Formless Foil",
    "Serialized",
    "OCM Serialized",
    "Alt Art",
    "Character Proof",
}


def fetch_sales_data(days: int = 180) -> pd.DataFrame:
    """Fetch card sales only (no sealed product)."""
    logger.info(f"Fetching sales data ({days} days)...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    query = text("""
        SELECT
            mp.id as sale_id,
            mp.card_id,
            c.name as card_name,
            c.card_number,
            r.name as rarity,
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
        ORDER BY mp.card_id, COALESCE(mp.sold_date, mp.scraped_at)
    """)

    with Session(engine) as session:
        result = session.execute(query, {"cutoff": cutoff})
        rows = result.fetchall()

    df = pd.DataFrame(
        rows,
        columns=[
            "sale_id",
            "card_id",
            "card_name",
            "card_number",
            "rarity",
            "treatment",
            "price",
            "sale_date",
            "platform",
        ],
    )

    df["sale_date"] = pd.to_datetime(df["sale_date"], utc=True)
    df["treatment"] = df["treatment"].fillna("Classic Paper")
    df["rarity"] = df["rarity"].fillna("Common")

    # Filter out sealed product
    df = df[~df["treatment"].isin(EXCLUDED_TREATMENTS)]

    # Normalize treatment names
    df["treatment"] = df["treatment"].apply(normalize_treatment)

    logger.info(f"  Loaded {len(df):,} card sales from {df['card_id'].nunique()} cards")
    logger.info(f"  Treatments: {df['treatment'].value_counts().to_dict()}")
    return df


def normalize_treatment(t: str) -> str:
    """Normalize treatment names to core categories."""
    t = t.strip()
    if "Paper" in t or t == "Base" or t == "Unknown":
        return "Classic Paper"
    if "Foil" in t and "Stone" in t:
        return "Stonefoil"
    if "Foil" in t and "Formless" in t:
        return "Formless Foil"
    if "Foil" in t:
        return "Classic Foil"
    if "Serial" in t:
        return "Serialized"
    if "Proof" in t:
        return "Character Proof"
    return t


def fetch_active_listings() -> pd.DataFrame:
    """Fetch current active listings for order book depth."""
    logger.info("Fetching active listings...")
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    query = text("""
        SELECT
            card_id,
            COALESCE(NULLIF(product_subtype, ''), treatment) as treatment,
            COUNT(*) as listing_count,
            MIN(price) as lowest_ask
        FROM marketprice
        WHERE listing_type = 'active'
          AND is_bulk_lot = FALSE
          AND scraped_at >= :cutoff
          AND price > 0.5
        GROUP BY card_id, COALESCE(NULLIF(product_subtype, ''), treatment)
    """)

    with Session(engine) as session:
        result = session.execute(query, {"cutoff": cutoff})
        rows = result.fetchall()

    df = pd.DataFrame(rows, columns=["card_id", "treatment", "listing_count", "lowest_ask"])
    df["treatment"] = df["treatment"].fillna("Classic Paper").apply(normalize_treatment)

    logger.info(f"  Loaded {len(df):,} card/treatment combos with listings")
    return df


# =============================================================================
# FEATURE ENGINEERING (v2 - Card-Relative)
# =============================================================================


def compute_card_base_prices(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute each card's 'base price' = floor of Classic Paper variant.
    All other prices are relative to this.
    """
    logger.info("Computing card base prices...")

    # Get Classic Paper floor for each card (avg of 4 lowest)
    paper_df = df[df["treatment"] == "Classic Paper"].copy()

    def floor_4(prices):
        sorted_p = sorted(prices)[:4]
        return np.mean(sorted_p) if sorted_p else np.nan

    card_base = paper_df.groupby("card_id")["price"].apply(floor_4).rename("card_base_price")

    # For cards without Classic Paper sales, use overall card median
    all_card_median = df.groupby("card_id")["price"].median().rename("card_median_price")

    df = df.merge(card_base, on="card_id", how="left")
    df = df.merge(all_card_median, on="card_id", how="left")

    # Fill missing base with median
    df["card_base_price"] = df["card_base_price"].fillna(df["card_median_price"])

    # Compute price relative to base
    df["price_relative"] = df["price"] / df["card_base_price"]

    logger.info(f"  Cards with base price: {df['card_base_price'].notna().sum()}")
    return df


def compute_treatment_multipliers(df: pd.DataFrame) -> dict:
    """
    Learn treatment multipliers from WITHIN-CARD comparisons.
    This avoids confounding card value with treatment value.
    """
    logger.info("Learning treatment multipliers...")

    # Only use cards that have both Classic Paper AND another treatment
    cards_with_paper = set(df[df["treatment"] == "Classic Paper"]["card_id"])
    multi_treatment = df[df["card_id"].isin(cards_with_paper)]

    # Compute median relative price by treatment
    treatment_mult = multi_treatment.groupby("treatment")["price_relative"].median().to_dict()

    # Normalize so Classic Paper = 1.0
    paper_mult = treatment_mult.get("Classic Paper", 1.0)
    treatment_mult = {k: v / paper_mult for k, v in treatment_mult.items()}

    logger.info(f"  Treatment multipliers: {treatment_mult}")
    return treatment_mult


def add_ar_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add auto-regressive features (relative to card base)."""
    logger.info("Adding AR features...")
    df = df.sort_values(["card_id", "treatment", "sale_date"]).copy()
    group_cols = ["card_id", "treatment"]

    # Lag features (relative prices)
    df["rel_lag1"] = df.groupby(group_cols)["price_relative"].shift(1)
    df["rel_lag2"] = df.groupby(group_cols)["price_relative"].shift(2)

    # Rolling stats on relative prices
    df["rel_roll_mean"] = df.groupby(group_cols)["price_relative"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=1).mean()
    )
    df["rel_roll_min"] = df.groupby(group_cols)["price_relative"].transform(
        lambda x: x.shift(1).rolling(4, min_periods=1).min()
    )
    df["rel_roll_std"] = df.groupby(group_cols)["price_relative"].transform(
        lambda x: x.shift(1).rolling(5, min_periods=2).std()
    )

    # Absolute price features (for context)
    df["price_lag1"] = df.groupby(group_cols)["price"].shift(1)
    df["floor_4"] = df.groupby(group_cols)["price"].transform(lambda x: x.shift(1).rolling(4, min_periods=1).min())

    # Sale sequence
    df["sale_seq"] = df.groupby(group_cols).cumcount()

    return df


def add_liquidity_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add liquidity metrics."""
    logger.info("Adding liquidity features...")
    df = df.sort_values(["card_id", "treatment", "sale_date"]).copy()
    group_cols = ["card_id", "treatment"]

    # Days since last sale
    df["prev_sale_date"] = df.groupby(group_cols)["sale_date"].shift(1)
    df["days_gap"] = (df["sale_date"] - df["prev_sale_date"]).dt.total_seconds() / 86400
    df["days_gap"] = df["days_gap"].fillna(30).clip(upper=90)

    # Inverse liquidity (higher = less liquid)
    df["illiquidity"] = np.log1p(df["days_gap"])

    # Card-level sales count
    card_sales = df.groupby("card_id").size().rename("card_sales_count")
    df = df.merge(card_sales, on="card_id", how="left")

    # Treatment-level sales count for this card
    treatment_sales = df.groupby(["card_id", "treatment"]).size().rename("treatment_sales_count")
    df = df.merge(treatment_sales, on=["card_id", "treatment"], how="left")

    return df


def add_rarity_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add rarity-based features."""
    logger.info("Adding rarity features...")

    # Rarity encoding (ordinal)
    rarity_order = {"Common": 1, "Uncommon": 2, "Rare": 3, "Epic": 4, "Legendary": 5, "Mythic": 6}
    df["rarity_code"] = df["rarity"].map(rarity_order).fillna(3)

    # Rarity average relative price
    rarity_rel = df.groupby("rarity")["price_relative"].median().rename("rarity_rel_median")
    df = df.merge(rarity_rel, on="rarity", how="left")

    return df


def add_order_book_features(sales_df: pd.DataFrame, listings_df: pd.DataFrame) -> pd.DataFrame:
    """Merge order book features."""
    logger.info("Adding order book features...")

    sales_df = sales_df.merge(
        listings_df[["card_id", "treatment", "listing_count", "lowest_ask"]], on=["card_id", "treatment"], how="left"
    )

    sales_df["listing_count"] = sales_df["listing_count"].fillna(0)
    sales_df["has_listings"] = (sales_df["listing_count"] > 0).astype(int)

    # Ask relative to card base
    sales_df["ask_relative"] = sales_df["lowest_ask"] / sales_df["card_base_price"]
    sales_df["ask_relative"] = sales_df["ask_relative"].fillna(sales_df["rel_lag1"])

    # Ask vs recent sales (deal indicator)
    sales_df["ask_vs_floor"] = sales_df["lowest_ask"] / sales_df["floor_4"]
    sales_df["ask_vs_floor"] = sales_df["ask_vs_floor"].fillna(1.0).clip(0.5, 3.0)

    return sales_df


def add_treatment_features(df: pd.DataFrame, treatment_mult: dict) -> pd.DataFrame:
    """Add treatment multiplier feature."""
    logger.info("Adding treatment features...")

    df["treatment_mult"] = df["treatment"].map(treatment_mult).fillna(1.0)

    # Treatment encoding for gradient boosting
    treatment_codes = {t: i for i, t in enumerate(sorted(df["treatment"].unique()))}
    df["treatment_code"] = df["treatment"].map(treatment_codes)

    return df


# =============================================================================
# MODEL TRAINING (v2)
# =============================================================================

# Features for predicting price
FEATURE_COLS = [
    # Card context
    "card_base_price",
    "rarity_code",
    # AR features (relative)
    "rel_lag1",
    "rel_roll_mean",
    "rel_roll_min",
    # AR features (absolute)
    "price_lag1",
    "floor_4",
    # Treatment
    "treatment_mult",
    "treatment_code",
    # Liquidity
    "illiquidity",
    "card_sales_count",
    "treatment_sales_count",
    # Order book
    "listing_count",
    "has_listings",
    "ask_relative",
    "ask_vs_floor",
]


def train_model(df: pd.DataFrame) -> tuple:
    """Train and evaluate model."""
    from sklearn.ensemble import GradientBoostingRegressor
    from sklearn.metrics import mean_absolute_error, mean_absolute_percentage_error, r2_score

    logger.info("Preparing training data...")

    # Filter to rows with at least 1 prior sale
    model_df = df[df["sale_seq"] >= 1].copy()

    # Drop rows with NaN in key features
    key_features = ["card_base_price", "price_lag1", "floor_4", "treatment_mult"]
    model_df = model_df.dropna(subset=key_features + ["price"])

    # Fill remaining NaNs
    for col in FEATURE_COLS:
        if col in model_df.columns:
            model_df[col] = model_df[col].fillna(model_df[col].median())

    logger.info(f"  {len(model_df):,} samples after filtering")

    if len(model_df) < 100:
        logger.error("Not enough data to train model!")
        return None, None, None

    # Time-based split (80/20)
    model_df = model_df.sort_values("sale_date")
    split_idx = int(len(model_df) * 0.8)

    train_df = model_df.iloc[:split_idx]
    test_df = model_df.iloc[split_idx:]

    X_train = train_df[FEATURE_COLS].values
    y_train = train_df["price"].values
    X_test = test_df[FEATURE_COLS].values
    y_test = test_df["price"].values

    logger.info(f"  Train: {len(train_df):,}, Test: {len(test_df):,}")
    logger.info(f"  Price range: ${y_test.min():.2f} - ${y_test.max():.2f}")

    # Train model
    logger.info("Training Gradient Boosting model...")
    model = GradientBoostingRegressor(
        n_estimators=200, max_depth=4, learning_rate=0.05, min_samples_leaf=10, subsample=0.8, random_state=42
    )
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    mae = mean_absolute_error(y_test, y_pred)
    mape = mean_absolute_percentage_error(y_test, y_pred) * 100
    r2 = r2_score(y_test, y_pred)

    # Baseline: floor_4 (our current algorithm)
    baseline_pred = test_df["floor_4"].values
    baseline_mae = mean_absolute_error(y_test, baseline_pred)
    baseline_mape = mean_absolute_percentage_error(y_test, baseline_pred) * 100

    # Baseline 2: naive (last sale price)
    naive_pred = test_df["price_lag1"].values
    naive_mae = mean_absolute_error(y_test, naive_pred)

    metrics = {
        "mae": mae,
        "mape": mape,
        "r2": r2,
        "baseline_mae": baseline_mae,
        "baseline_mape": baseline_mape,
        "naive_mae": naive_mae,
    }

    return model, metrics, test_df


def print_results(metrics: dict, model, test_df: pd.DataFrame):
    """Print training results."""
    print("\n" + "=" * 70)
    print("AUTO-REGRESSIVE PRICING MODEL v2 RESULTS")
    print("=" * 70)

    print(f"\n{'Method':<25} {'MAE':>10} {'MAPE':>10}")
    print("-" * 50)
    print(f"{'Naive (last sale)':<25} ${metrics['naive_mae']:>8.2f}")
    print(f"{'Floor (min of 4)':<25} ${metrics['baseline_mae']:>8.2f}  {metrics['baseline_mape']:>8.1f}%")
    print(f"{'ML Model':<25} ${metrics['mae']:>8.2f}  {metrics['mape']:>8.1f}%")

    improvement = (metrics["baseline_mae"] - metrics["mae"]) / metrics["baseline_mae"] * 100
    print(f"\nML vs Floor: {improvement:+.1f}% {'better' if improvement > 0 else 'worse'}")
    print(f"R² Score: {metrics['r2']:.3f}")

    # Feature importance
    if hasattr(model, "feature_importances_"):
        print("\nFeature Importance:")
        importance = sorted(zip(FEATURE_COLS, model.feature_importances_), key=lambda x: x[1], reverse=True)
        for feat, imp in importance[:8]:
            bar = "█" * int(imp * 50)
            print(f"  {feat:<22} {imp:.3f} {bar}")

    # Error by treatment
    test_df = test_df.copy()
    test_df["pred"] = model.predict(test_df[FEATURE_COLS].values)
    test_df["abs_error"] = np.abs(test_df["pred"] - test_df["price"])
    test_df["pct_error"] = test_df["abs_error"] / test_df["price"] * 100

    print("\nPerformance by Treatment:")
    treatment_stats = (
        test_df.groupby("treatment").agg({"abs_error": "mean", "pct_error": "median", "price": "count"}).round(2)
    )
    treatment_stats.columns = ["MAE", "Median %Err", "Count"]
    treatment_stats = treatment_stats.sort_values("MAE")
    print(treatment_stats.to_string())

    # Error by price range
    test_df["price_bucket"] = pd.cut(
        test_df["price"], bins=[0, 10, 25, 50, 100, 2000], labels=["<$10", "$10-25", "$25-50", "$50-100", ">$100"]
    )
    print("\nPerformance by Price Range:")
    price_stats = (
        test_df.groupby("price_bucket", observed=True)
        .agg({"abs_error": "mean", "pct_error": "median", "price": "count"})
        .round(2)
    )
    price_stats.columns = ["MAE", "Median %Err", "Count"]
    print(price_stats.to_string())


def save_model(model, treatment_mult: dict, output_dir: Path):
    """Save model and metadata to disk."""
    import joblib
    import json

    output_dir.mkdir(exist_ok=True)

    model_path = output_dir / "ar_pricing_model_v2.joblib"
    joblib.dump(model, model_path)

    features_path = output_dir / "ar_pricing_features.json"
    with open(features_path, "w") as f:
        json.dump(
            {
                "features": FEATURE_COLS,
                "treatment_multipliers": treatment_mult,
                "version": 2,
            },
            f,
            indent=2,
        )

    logger.info(f"\nModel saved to: {model_path}")


def main():
    parser = argparse.ArgumentParser(description="Train AR pricing model v2")
    parser.add_argument("--days", type=int, default=180, help="Days of history")
    parser.add_argument("--output", type=str, default="models", help="Output directory")
    args = parser.parse_args()

    print("=" * 70)
    print("AUTO-REGRESSIVE PRICING MODEL v2 TRAINER")
    print("=" * 70)
    print("Design: Card-relative features, proper treatment multipliers")
    print()

    # Fetch data
    sales_df = fetch_sales_data(days=args.days)
    listings_df = fetch_active_listings()

    if len(sales_df) < 100:
        logger.error("Not enough sales data!")
        return

    # Step 1: Compute card base prices
    sales_df = compute_card_base_prices(sales_df)

    # Step 2: Learn treatment multipliers from within-card comparisons
    treatment_mult = compute_treatment_multipliers(sales_df)

    # Step 3: Feature engineering
    sales_df = add_ar_features(sales_df)
    sales_df = add_liquidity_features(sales_df)
    sales_df = add_rarity_features(sales_df)
    sales_df = add_order_book_features(sales_df, listings_df)
    sales_df = add_treatment_features(sales_df, treatment_mult)

    # Train
    model, metrics, test_df = train_model(sales_df)

    if model is None:
        return

    # Results
    print_results(metrics, model, test_df)

    # Save
    save_model(model, treatment_mult, Path(args.output))


if __name__ == "__main__":
    main()
