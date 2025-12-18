# TASK-004: FloorPriceService Hybrid Logic

**Epic:** EPIC-001 Order Book Floor Price Estimation
**Phase:** 2 - Backend Services
**Estimate:** 10-14 hours
**Dependencies:** TASK-003 (OrderBookAnalyzer)

## Objective

Implement `FloorPriceService` that provides hybrid floor pricing with fallback logic: sales floor → ask floor → null.

## Acceptance Criteria

- [ ] Service returns floor price with source metadata (SALES, ASK, NONE)
- [ ] Implements correct fallback priority
- [ ] Confidence levels appropriate for each source
- [ ] Integration with OrderBookAnalyzer
- [ ] Backward compatible with existing floor price consumers
- [ ] Unit + integration tests with >90% coverage

## Units of Work

### U1: Create FloorPriceResult Model (1h)
**File:** `app/models/floor_price.py`

```python
from enum import Enum
from typing import Optional
from pydantic import BaseModel

class FloorPriceSource(str, Enum):
    SALES = "SALES"      # Avg of 4 lowest sales
    ASK = "ASK"          # Order book estimate
    NONE = "NONE"        # No data available

class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"        # ≥4 sales OR ask confidence >0.7
    MEDIUM = "MEDIUM"    # 2-3 sales OR ask confidence 0.4-0.7
    LOW = "LOW"          # <2 sales OR ask confidence <0.4

class FloorPriceResult(BaseModel):
    price: Optional[float]
    source: FloorPriceSource
    confidence: ConfidenceLevel
    confidence_score: float  # Raw 0-1 score
    metadata: dict = {}      # Source-specific details
```

### U2: Create FloorPriceService Class (2h)
**File:** `app/services/floor_price.py`

```python
class FloorPriceService:
    def __init__(
        self,
        db: Session,
        order_book_analyzer: OrderBookAnalyzer
    ):
        self.db = db
        self.analyzer = order_book_analyzer

    def get_floor_price(
        self,
        card_id: int,
        treatment: Optional[str] = None,
        product_subtype: Optional[str] = None,
        days: int = 90
    ) -> FloorPriceResult:
        """Get hybrid floor price with fallback logic."""
        pass
```

### U3: Implement Sales Floor Calculation (2h)
- Port existing logic from `app/api/cards.py`
- Query avg of 4 lowest sales in period
- Filter by treatment/product_subtype if provided
- Return `(price, count)` tuple
- Use `COALESCE(sold_date, scraped_at)` for date filtering

### U4: Implement Ask Floor Integration (2h)
- Call `OrderBookAnalyzer.analyze()`
- Extract floor_estimate and confidence
- Map confidence to ConfidenceLevel enum:
  - `>0.7` → HIGH
  - `0.4-0.7` → MEDIUM
  - `<0.4` → LOW

### U5: Implement Fallback Logic (3h)
```python
def get_floor_price(...) -> FloorPriceResult:
    # 1. Try sales floor (primary)
    sales = self._get_sales_floor(card_id, treatment, product_subtype, days)
    if sales and sales.count >= 4:
        return FloorPriceResult(
            price=sales.price,
            source=FloorPriceSource.SALES,
            confidence=ConfidenceLevel.HIGH,
            confidence_score=1.0,
            metadata={"sales_count": sales.count}
        )

    # 2. Try ask floor (fallback)
    ask = self.analyzer.analyze(card_id, treatment, product_subtype)
    if ask and ask.confidence > 0.3:
        return FloorPriceResult(
            price=ask.floor_estimate,
            source=FloorPriceSource.ASK,
            confidence=self._map_confidence(ask.confidence),
            confidence_score=ask.confidence,
            metadata={
                "bucket_depth": ask.deepest_bucket.count,
                "total_listings": ask.total_listings
            }
        )

    # 3. Try sales floor with fewer sales
    if sales and sales.count >= 2:
        return FloorPriceResult(
            price=sales.price,
            source=FloorPriceSource.SALES,
            confidence=ConfidenceLevel.LOW,
            confidence_score=sales.count / 4,
            metadata={"sales_count": sales.count}
        )

    # 4. No data
    return FloorPriceResult(
        price=None,
        source=FloorPriceSource.NONE,
        confidence=ConfidenceLevel.LOW,
        confidence_score=0.0,
        metadata={}
    )
```

### U6: Write Integration Tests (4h)
**File:** `tests/services/test_floor_price.py`

Test scenarios:
- Card with 10 sales → SALES source, HIGH confidence
- Card with 0 sales, 20 listings → ASK source
- Card with 2 sales, 5 listings → ASK or SALES depending on confidence
- Card with 0 sales, 2 listings → ASK with LOW confidence
- Card with 0 sales, 0 listings → NONE
- Sealed product with subtype filter
- Treatment filter applied correctly

## Decision Tree Visualization

```
┌────────────────────────────────────────┐
│ sales_count >= 4?                      │
│   YES → SALES, HIGH confidence         │
│   NO  ↓                                │
├────────────────────────────────────────┤
│ ask_confidence > 0.3?                  │
│   YES → ASK, mapped confidence         │
│   NO  ↓                                │
├────────────────────────────────────────┤
│ sales_count >= 2?                      │
│   YES → SALES, LOW confidence          │
│   NO  ↓                                │
├────────────────────────────────────────┤
│ Return NONE                            │
└────────────────────────────────────────┘
```

## Files Changed

- **New:** `app/services/floor_price.py`
- **New:** `app/models/floor_price.py`
- **New:** `tests/services/test_floor_price.py`
- **Modified:** `app/api/cards.py` (optional: use new service)

## Notes

- This service will be used by API endpoints (TASK-005)
- Keep backward compatibility with existing `floor_price` field
- Add new `floor_price_result` field with full metadata
