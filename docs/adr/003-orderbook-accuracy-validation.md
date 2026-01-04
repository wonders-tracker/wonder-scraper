# ADR-003: OrderBook Accuracy Validation Results

**Status:** Validated + Fixed
**Date:** 2026-01-02
**Sprint:** Pricing Consolidation Sprint 1

## Context

The OrderBook algorithm estimates floor prices from active listings using bucket analysis. Before consolidating pricing logic into a unified `PricingService`, we needed to validate OrderBook accuracy against actual sales.

## Validation Methodology

1. Created backtest script (`scripts/backtest_orderbook.py`) to simulate historical predictions
2. For each card/treatment, predicted floor at point-in-time using only data available then
3. Compared predictions to the next actual sale that occurred
4. Calculated MAE, RMSE, and confidence calibration metrics

## Key Findings (v1 - Before Fixes)

### Overall Accuracy

| Metric | Value | Assessment |
|--------|-------|------------|
| MAE (Mean Absolute Error) | $45.35 | High (outlier-driven) |
| RMSE | $144.64 | Very high (extreme outliers) |
| Median Absolute Error | $9.17 | Acceptable |
| Median % Error | 34.4% | Moderate |

### Critical Issue: Confidence NOT Calibrated (v1)

| Confidence Level | Count | MAE |
|------------------|-------|-----|
| Low (0-0.3) | 179 | $35.66 |
| Medium (0.3-0.6) | 72 | $69.45 |

**v1 Problem:** Higher confidence = HIGHER error (backwards!)

## Fixes Implemented

### 1. MIN_LISTINGS: 3 → 1
The old threshold was too high, causing 100% fallback to sales.

### 2. Floor Estimate: Bucket Midpoint → Lowest Ask
The floor is literally the lowest price available. Using bucket midpoint was overcomplicating it.

### 3. Confidence Algorithm: Complete Rewrite

**Old formula (broken):**
```
confidence = depth_ratio × (1 - stale_ratio)
```

**New formula (v2):**
```
confidence = 0.4 × count_score + 0.3 × spread_score + 0.3 × recency_score

count_score = min(0.9, 0.3 + 0.2 × log2(listings))  # More listings = higher
spread_score = f(spread_pct)  # Tighter spread = higher
recency_score = 1.0 - (stale_ratio × 0.5)  # Fresher = higher
```

## Results After Fixes (v2)

### Confidence Calibration: NOW CORRECT

| Confidence Level | Count | MAE | Calibrated? |
|------------------|-------|-----|-------------|
| Low (0-0.3) | 28 | $108.88 | ✅ High error |
| Medium (0.3-0.6) | 223 | $40.28 | ✅ Lower error |

**v2 Result:** Higher confidence = LOWER error (correct!)

Low-confidence predictions are now correctly identified as unreliable.

## Files Modified

- `app/services/order_book.py` - Algorithm v2 implementation
  - `OrderBookConfig.MIN_LISTINGS`: 3 → 1
  - Added `lowest_ask` field to `OrderBookResult`
  - Added `spread_pct` field to `OrderBookResult`
  - New `_calculate_confidence_v2()` method
  - `estimate_floor()` now returns lowest_ask as floor

## Files Created

- `scripts/backtest_orderbook.py` - Backtest script
- `notebooks/orderbook_accuracy_analysis.ipynb` - Jupyter notebook for analysis
- `data/orderbook_backtest.csv` - v1 backtest results
- `data/orderbook_backtest_v2.csv` - v2 backtest results

## Decision

OrderBook v2 is improved but should still be used as **fallback only**:

1. **Primary:** Sales-based floor (avg of 4 lowest in 30 days)
2. **Fallback:** OrderBook (lowest ask with calibrated confidence)
3. **Confidence is meaningful:** Users can now trust confidence scores

## Next Steps

Proceed with Sprint 2: Core PricingService Implementation, using OrderBook v2 as fallback.
