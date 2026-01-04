# EPIC-001: Order Book Floor Price Estimation

## Objective

Build an order book analysis system to estimate floor prices from active listings when sales data is sparse or unavailable. This provides a hybrid floor price system: sales floor → ask floor → null, improving data completeness and user experience for cards with limited market activity.

## User Impact

**Problem:**
- Many cards (especially new releases, sealed products, rare variants) have few or no recent sales
- Users cannot estimate fair value without floor price reference
- Current system shows "No floor price available" for ~30-40% of card/variant combinations

**Solution:**
- Analyze active listing clusters (order book depth) to estimate floor prices
- Show confidence levels based on liquidity and data freshness
- Display source badges (Sales Floor vs Ask Floor) for transparency
- Provide depth chart visualization to show market liquidity

**Benefits:**
- Improved price discovery for low-volume cards
- Better portfolio valuation accuracy
- Enhanced market transparency
- Reduced user uncertainty when pricing cards

## Tech Scope

### Backend (FastAPI/SQLModel)
- `OrderBookAnalyzer` service - Bucket analysis, outlier filtering, depth calculation
- `FloorPriceService` - Hybrid floor price logic (sales → ask → null)
- API endpoints:
  - `GET /api/v1/cards/{id}/floor-price` - Hybrid floor with source
  - `GET /api/v1/cards/{id}/order-book` - Full order book data
  - `GET /api/v1/admin/floor-price-stats` - System-wide statistics
- Database: Queries against existing `marketprice` table
- Caching: In-memory TTLCache (5min for active listings)

### Frontend (React/TanStack)
- Order book depth chart (recharts bar chart)
- Floor price source badges (sales vs ask)
- Confidence indicators (high/medium/low)
- Admin stats dashboard

### Infrastructure
- In-memory caching (TTLCache) - no Redis required
- APScheduler for periodic cache warming
- Logging and alerting for anomaly detection

### Dependencies
- Existing: `marketprice` table, `card` table, scraper infrastructure
- New: None - `cachetools` already in use
- Frontend: `recharts` library (already in use)

---

## Research Findings - Production Data Quality

### Database Analysis (Dec 2025)
**Dataset:** 3,327 active listings, 2,410 sold listings

#### Treatment Coverage
| Metric | Value |
|--------|-------|
| Total active listings | 3,327 |
| With treatment | 3,326 (99.97%) |
| Null/empty treatment | 1 (0.03%) |

**Distribution:**
```
Classic Paper:           1,275 (38.3%)
Classic Foil:            1,042 (31.3%)
Formless Foil:             749 (22.5%)
Sealed:                     64 (1.9%)
OCM Serialized:             58 (1.7%)
Other:                     139 (4.2%)
```

#### Product Subtype
- **98.1% null** - Expected behavior
- Only 63 non-null values (all sealed products)
- Not an issue: subtype only applies to sealed products

#### Price Distribution
```
$0-10:     2,173 (65.3%) ████████████████████████████████████████████████
$10-20:      524 (15.7%) ████████████████████████
$20-30:      186 (5.6%)  ████████
$30-40:       88 (2.6%)  ████
$40-50:       60 (1.8%)  ███
$50+:        296 (8.9%)  █████████
```

### Spam and Data Quality Patterns

#### Low Price Analysis ($<1)
- **10 listings at $0.65**
- All are bulk lot deals ("3X - Wonders...")
- **Not spam** - legitimate bulk pricing
- Recommendation: Filter by checking for "3X", "LOT", "BULK" in title

#### Extreme Outliers
| Card | Listed Price | Median | Ratio | Treatment |
|------|-------------|--------|-------|-----------|
| 411 (Sealed) | $0.99 | $44.44 | 44.9x | Sealed |
| 27 | $18.75 | $704.57 | 37.6x | Classic Paper |
| 408 (Sealed) | $18.00 | $498.00 | 27.7x | Sealed |

- **Root cause:** Variant mixing (single packs vs booster boxes in sealed)
- **Solution:** Order book bucketing naturally handles this

#### Duplicate Listings
- Only **2 sellers with 2 duplicates each**
- Total: 4/3,327 = 0.12% duplication rate
- **Negligible** - no special handling needed

#### Seller Concentration
- **Max listings per seller:** 6
- **No manipulation concern** - well-distributed market

### Infrastructure Assessment

#### Current Stack
- **Cache:** In-memory TTLCache (no Redis)
- **Deployment:** Single-instance Railway
- **Database:** Neon PostgreSQL

#### Recommendation
- **In-memory TTLCache is sufficient**
- Current scale: 3,327 listings = ~500KB in memory
- 5-minute TTL prevents stale data
- Future: Add Redis if scaling to multi-instance

---

## Algorithm Specification

### Order Book Floor Estimation Algorithm

```
Visualization:
┌─────────────────────────────────────────────────┐
│ $5-10:   █ (1 listing) ← outlier filtered       │
│ $10-15:  ██ (2)                                 │
│ $15-20:  ███ (3)                                │
│ $20-25:  ████████████ (12) ← DEEPEST = FLOOR   │
│ $25-30:  ██████ (6)                             │
│ $30-35:  ███ (3)                                │
└─────────────────────────────────────────────────┘
estimated_floor = midpoint of deepest bucket = $22.50
```

```python
def estimate_ask_floor(card_id: int, treatment: str) -> Optional[AskFloor]:
    """
    Estimates floor price from active listing order book.
    Returns: AskFloor(price, confidence, bucket_depth, total_listings)
    """
    # 1. Fetch active listings
    listings = fetch_active_listings(card_id, treatment)
    if len(listings) < 3:
        return None  # Insufficient data

    # 2. Filter outliers (>2σ from neighbors)
    filtered = filter_local_outliers(listings)

    # 3. Create adaptive price buckets
    price_range = max(filtered) - min(filtered)
    bucket_width = max(5, min(50, price_range / sqrt(len(filtered))))
    buckets = create_buckets(filtered, bucket_width)

    # 4. Find deepest bucket (most liquidity)
    deepest_bucket = max(buckets, key=lambda b: b.depth)
    floor_estimate = deepest_bucket.midpoint

    # 5. Calculate confidence
    depth_ratio = deepest_bucket.depth / len(filtered)
    stale_ratio = count_stale_listings(filtered) / len(filtered)
    confidence = depth_ratio * (1 - stale_ratio)

    return AskFloor(
        price=floor_estimate,
        confidence=confidence,
        bucket_depth=deepest_bucket.depth,
        total_listings=len(filtered)
    )
```

### Hybrid Floor Price Logic

```
Decision Tree:
┌─────────────────────────────────────────────────┐
│ Has ≥4 sales in 30d?                            │
│   YES → Use SALES floor (avg of 4 lowest)       │
│   NO  ↓                                         │
├─────────────────────────────────────────────────┤
│ Has ≥5 active listings?                         │
│   YES → Use ASKS floor (order book algorithm)   │
│   NO  ↓                                         │
├─────────────────────────────────────────────────┤
│ Has ≥2 sales in 90d?                            │
│   YES → Use SALES floor (low confidence)        │
│   NO  → Return NULL                             │
└─────────────────────────────────────────────────┘
```

---

## Tasks

| ID | Task | Phase | Estimate | Dependencies |
|----|------|-------|----------|--------------|
| T001 | Jupyter algorithm prototype | 1 | 8-12h | None |
| T002 | Algorithm validation on prod data | 1 | 6-8h | T001 |
| T003 | OrderBookAnalyzer service | 2 | 12-16h | T002 |
| T004 | FloorPriceService hybrid logic | 2 | 10-14h | T003 |
| T005 | API endpoints | 2 | 8-12h | T004 |
| T006 | Caching layer | 2 | 6-8h | T004 |
| T007 | Order book depth chart | 3 | 10-14h | T005 |
| T008 | Floor price source badges | 3 | 6-8h | T005 |
| T009 | Card detail integration | 3 | 8-10h | T007, T008 |
| T010 | Admin stats dashboard | 3 | 8-12h | T005 |
| T011 | Logging instrumentation | 4 | 4-6h | T003, T006 |
| T012 | Anomaly detection & alerts | 4 | 6-8h | T011 |
| T013 | Documentation | 4 | 6-8h | All |
| T014 | End-to-end testing | 4 | 8-10h | T009 |

**Total: 102-138 hours (3-4 weeks)**

---

## Timeline

- **Phase 1 (Research/Prototyping):** 3-5 days
- **Phase 2 (Backend Services):** 1-1.5 weeks
- **Phase 3 (Frontend/Visualization):** 1 week
- **Phase 4 (Observability/Polish):** 3-5 days

**Critical Path:** T001 → T002 → T003 → T004 → T005 → T007 → T009 → T014

---

## Done-When (Exit Criteria)

### Backend
- [ ] `OrderBookAnalyzer` service implemented with tests (>90% coverage)
- [ ] `FloorPriceService` hybrid logic working correctly
- [ ] API endpoints returning correct data with <200ms p95 latency
- [ ] In-memory cache working with 5-minute TTL
- [ ] Outlier filtering tested on production data patterns

### Frontend
- [ ] Order book depth chart displays correctly for all card types
- [ ] Floor price source badges show (Sales Floor vs Ask Floor)
- [ ] Confidence indicators display with correct thresholds
- [ ] Mobile responsive on 320px viewport

### Quality
- [ ] Backend tests: >90% coverage
- [ ] No Ruff/TypeScript errors
- [ ] Admin stats dashboard functional

### Success Metrics
- **Target:** 80%+ cards have floor price (sales OR ask)
- **Target:** 90%+ of ask floors have confidence >0.5
- **Target:** <200ms p95 latency for floor price API

---

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Variant mixing in sealed | High (44.9x deviation seen) | Local outlier filtering (>2σ) |
| Algorithm overfitting | Medium | Adaptive bucket sizing, configurable thresholds |
| Cache invalidation | Low | Simple TTL-based eviction |
| User confusion (sales vs ask) | Medium | Clear UI badges, tooltips |

---

## Related Files

- **Tasks:** `tasks/TASK-001-*.md` through `tasks/TASK-014-*.md`
- **Research:** `notebooks/order_book_algorithm.ipynb` (Phase 1 output)
- **Services:** `app/services/order_book.py`, `app/services/floor_price.py`
- **API:** `app/api/floor_price.py`
- **Frontend:** `frontend/app/components/OrderBookDepthChart.tsx`

---

*Status: IN PROGRESS (Phase 2 Backend Complete)*
*Last Updated: 2025-12-31*

## Progress Update (2025-12-31)

### Completed Tasks
- **TASK-003:** OrderBookAnalyzer service - COMPLETED
  - `/Users/Cody/code_projects/wonder-scraper/app/services/order_book.py`
  - Unit tests: `/Users/Cody/code_projects/wonder-scraper/tests/test_order_book.py`
- **TASK-005 (partial):** API endpoint - COMPLETED
  - `GET /cards/{id}/order-book` endpoint added to `/Users/Cody/code_projects/wonder-scraper/app/api/cards.py`

### Integration with EPIC-002
- OrderBookAnalyzer excludes bulk lots (uses `is_bulk_lot` flag from EPIC-002)
- Sales fallback when active listings insufficient

### Remaining Work
- **TASK-004:** FloorPriceService hybrid logic (OSS stub exists, SaaS integration needed)
- **TASK-007:** Order book depth chart frontend component
- **Phase 4:** Observability and documentation
