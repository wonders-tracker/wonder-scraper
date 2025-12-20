# TASK-001: Jupyter Algorithm Prototype

**Epic:** EPIC-001 Order Book Floor Price Estimation
**Phase:** 1 - Research & Prototyping
**Estimate:** 8-12 hours
**Dependencies:** None

## Objective

Build and validate the order book bucketing algorithm in a Jupyter notebook before implementing in production code.

## Acceptance Criteria

- [ ] Notebook connects to production database (read-only)
- [ ] Algorithm handles adaptive bucket sizing (width = range/√n, min $5, max $50)
- [ ] Local outlier filtering implemented (>2σ from nearest neighbors)
- [ ] Confidence calculation working (depth_ratio × (1 - stale_ratio))
- [ ] Tested on 20+ cards including edge cases
- [ ] Results documented with visualizations

## Units of Work

### U1: Notebook Setup (2h)
- Create `notebooks/order_book_algorithm.ipynb`
- Set up database connection using `app.db.engine`
- Add helper functions for fetching active listings
- Add matplotlib/plotly for visualizations

### U2: Implement Bucketing Algorithm (3h)
- Create `bucket_prices(prices, bucket_width)` function
- Implement adaptive bucket width calculation
- Return dict of {(min, max): count}
- Test with simple examples

### U3: Implement Outlier Filtering (2h)
- Create `filter_local_outliers(prices)` function
- Calculate standard deviation of price gaps
- Remove prices where gap to nearest neighbor >2σ
- Log removed outliers for debugging

### U4: Implement Depth Detection (1h)
- Create `find_deepest_bucket(buckets)` function
- Return bucket with max count
- Tie-breaker: choose lower price bucket
- Return midpoint as floor estimate

### U5: Implement Confidence Scoring (1h)
- Calculate depth_ratio = deepest_count / total_listings
- Calculate stale_ratio = listings >14 days old / total
- Combine: confidence = depth_ratio × (1 - stale_ratio)
- Return float 0-1

### U6: Test on Production Data (3h)
- Run on 20+ cards including:
  - High volume cards (>50 listings)
  - Low volume cards (<10 listings)
  - Sealed products (subtype variants)
  - Cards with known outliers (Card 411)
- Screenshot results
- Document accuracy vs sales floor where available

## Test Cards

Based on research findings, test on:
- **Card 411 (Sealed):** Known outlier at $0.99 vs $44 median
- **Card 27:** High value card with $704 median
- **High volume:** Classic Paper commons
- **Low volume:** OCM Serialized, Promo cards
- **Sealed:** Existence Sealed Pack (multiple subtypes)

## Output

- `notebooks/order_book_algorithm.ipynb` - Complete notebook
- Screenshots of bucket visualizations
- Table of test results (card_id, estimated_floor, actual_floor, accuracy)
- List of edge cases and how algorithm handles them

## Notes

- Use read-only database access
- Do not modify production data
- Algorithm parameters will be tuned in TASK-002
