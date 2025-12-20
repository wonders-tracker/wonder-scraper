# TASK-003: OrderBookAnalyzer Service

**Epic:** EPIC-001 Order Book Floor Price Estimation
**Phase:** 2 - Backend Services
**Estimate:** 12-16 hours
**Dependencies:** TASK-002 (Algorithm validation)

## Objective

Implement production-ready `OrderBookAnalyzer` service class that performs order book depth analysis and floor estimation from active listings.

## Acceptance Criteria

- [ ] Service class with clean interface and type hints
- [ ] Adaptive bucketing algorithm from prototype
- [ ] Local outlier filtering (>2σ from neighbors)
- [ ] Confidence calculation with staleness penalty
- [ ] Handles edge cases: no listings, single listing, bimodal
- [ ] Unit tests with >90% coverage
- [ ] Performance: <100ms for typical cards (<100 listings)

## Units of Work

### U1: Create Service Skeleton (2h)
**File:** `app/services/order_book.py`

```python
from typing import Optional
from pydantic import BaseModel
from sqlmodel import Session

class BucketInfo(BaseModel):
    min_price: float
    max_price: float
    count: int
    midpoint: float

class OrderBookDepth(BaseModel):
    buckets: list[BucketInfo]
    deepest_bucket: BucketInfo
    floor_estimate: float
    confidence: float
    total_listings: int
    outliers_removed: int

class OrderBookAnalyzer:
    def __init__(self, db: Session):
        self.db = db

    def analyze(
        self,
        card_id: int,
        treatment: Optional[str] = None,
        product_subtype: Optional[str] = None,
        days: int = 30
    ) -> Optional[OrderBookDepth]:
        """Analyze order book depth for a card/variant."""
        pass
```

### U2: Implement _fetch_listings Method (2h)
- Query `MarketPrice` table filtered by:
  - `card_id`
  - `listing_type = 'active'`
  - Optional `treatment` filter
  - Optional `product_subtype` filter
  - `scraped_at` within `days` window
- Return list of `(price, scraped_at)` tuples
- Use parameterized queries (prevent SQL injection)

### U3: Implement Adaptive Bucketing (3h)
- Port from Jupyter prototype (TASK-001)
- Calculate bucket width: `max(5, min(50, range / sqrt(n)))`
- Create buckets with counts
- Handle edge cases:
  - All same price → single bucket
  - Large range → cap at $50 width
  - Small range → minimum $5 width

### U4: Implement Outlier Filtering (3h)
- Calculate price gaps between sorted listings
- Compute standard deviation of gaps
- Remove prices where gap to neighbor >2σ
- Log removed outliers at DEBUG level
- Return filtered list + count of removed

### U5: Implement Confidence Calculation (2h)
- `depth_ratio = deepest_bucket.count / total_listings`
- `stale_ratio = listings_older_than_14_days / total_listings`
- `confidence = depth_ratio * (1 - stale_ratio)`
- Clamp to [0.0, 1.0]

### U6: Wire Up analyze() Method (2h)
- Orchestrate: fetch → filter → bucket → find_deepest → confidence
- Handle edge cases:
  - `< 3 listings` → return None
  - `1 listing` → return that price with confidence=0.3
  - All outliers removed → return None
- Log summary at INFO level

### U7: Write Unit Tests (4h)
**File:** `tests/services/test_order_book.py`

Test cases:
- Normal distribution (10-20 listings)
- Bimodal distribution (two clusters)
- Single listing → low confidence
- No listings → None
- All outliers → None
- Stale data → reduced confidence
- Large price range → adaptive buckets
- Small price range → minimum bucket width

## Edge Cases from Research

Based on production data analysis:

| Case | Input | Expected Output |
|------|-------|-----------------|
| Card 411 outlier | $0.99 among $40+ | Filter outlier, floor ~$44 |
| Bulk lots | $0.65 "3X" deals | Filter or flag as bulk |
| Single listing | 1 active | Return price, confidence=0.3 |
| Dense cluster | 12 of 15 in one bucket | High confidence |

## Performance Requirements

- Query: <50ms for active listings fetch
- Algorithm: <50ms for bucketing + analysis
- Total: <100ms per card/variant
- Memory: <1MB per analysis (don't load all listings at once)

## Files Changed

- **New:** `app/services/order_book.py`
- **New:** `app/models/order_book.py` (Pydantic models)
- **New:** `tests/services/test_order_book.py`

## Notes

- Do NOT expose this service directly - it will be called by FloorPriceService
- Use existing database session patterns from `app/db.py`
- Follow existing service patterns (see `app/services/pricing.py`)
