# TASK-012: Order Book UI Integration

**Epic:** EPIC-001 Order Book Floor Price Estimation
**Priority:** P1
**Status:** Pending
**Owner:** TBD
**Estimate:** 6-8 hours

---

## Objective
Display floor price estimates from the OrderBookAnalyzer in the frontend UI. Show floor prices with confidence scores, broken down by treatment, on the card detail page.

## User Impact
- **Price discovery:** See estimated floor prices based on active listing liquidity
- **Confidence transparency:** Understand data quality behind estimates
- **Treatment comparison:** Compare floor prices across Classic Paper, Foil, Stonefoil, etc.

## Design Decisions
Based on requirements gathering:
- **Placement:** Both hero section (summary) AND dedicated pricing section (detailed)
- **Confidence display:** Percentage badge (e.g., "Floor: $12.50 (85% confidence)")
- **Treatment filter:** Show all treatments in a table/grid
- **Depth chart:** Separate task (TASK-007) - not included here

---

## Tech Scope

### API Endpoint
Already exists: `GET /api/v1/cards/{id}/order-book`

Response includes:
```json
{
  "card_id": 123,
  "card_name": "Dragonmaster Cai",
  "treatment": null,
  "floor_estimate": 12.50,
  "confidence": 0.85,
  "source": "active_listings",
  "total_listings": 24,
  "deepest_bucket": { "min_price": 10, "max_price": 15, "count": 8 },
  "buckets": [...]
}
```

Need to add: `GET /api/v1/cards/{id}/order-book/by-treatment`
Returns floor estimates for each treatment:
```json
{
  "card_id": 123,
  "treatments": [
    { "treatment": "Classic Paper", "floor_estimate": 8.50, "confidence": 0.92, "listings": 18 },
    { "treatment": "Classic Foil", "floor_estimate": 15.00, "confidence": 0.78, "listings": 8 },
    { "treatment": "Stonefoil", "floor_estimate": 45.00, "confidence": 0.45, "listings": 3 }
  ]
}
```

### Frontend Components

#### 1. FloorPriceBadge (Hero Section)
Simple inline display for card hero:
```tsx
// components/FloorPriceBadge.tsx
<div className="flex items-center gap-2">
  <span className="text-2xl font-bold">${floorEstimate.toFixed(2)}</span>
  <span className="text-sm text-muted-foreground">
    Floor ({(confidence * 100).toFixed(0)}% confidence)
  </span>
</div>
```

#### 2. FloorPriceByTreatment (Pricing Section)
Table showing all treatments:
```
Treatment          Floor      Confidence   Listings
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Classic Paper      $8.50      92%          18
Classic Foil       $15.00     78%          8
Stonefoil          $45.00     45%          3
Formless Foil      —          —            0
```

#### 3. ConfidenceIndicator
Reusable confidence display:
```tsx
// components/ConfidenceIndicator.tsx
interface ConfidenceIndicatorProps {
  confidence: number; // 0-1
  showLabel?: boolean;
}

// Colors:
// >= 0.7: green (high confidence)
// >= 0.4: yellow (medium confidence)
// < 0.4: red (low confidence)
```

---

## Units of Work

### UOW-012-1: Add By-Treatment API Endpoint
**Type:** backend
**Estimate:** 1 hour
**Dependencies:** None

**Exact Action:**
Add endpoint to `app/api/cards.py`:
```python
@router.get("/{card_id}/order-book/by-treatment")
def read_card_order_book_by_treatment(
    card_id: str,
    session: Session = Depends(get_session),
    days: int = Query(default=30, ge=1, le=90),
) -> Any:
    """Get order book floor analysis for each treatment."""
    card = get_card_by_id_or_slug(session, card_id)
    analyzer = get_order_book_analyzer(session)

    treatments = ["Classic Paper", "Classic Foil", "Stonefoil",
                  "Formless Foil", "Prerelease", "Promo"]

    results = []
    for treatment in treatments:
        result = analyzer.estimate_floor(
            card_id=ensure_int(card.id),
            treatment=treatment,
            days=days,
        )
        if result:
            results.append({
                "treatment": treatment,
                "floor_estimate": result.floor_estimate,
                "confidence": result.confidence,
                "listings": result.total_listings,
                "source": result.source,
            })
        else:
            results.append({
                "treatment": treatment,
                "floor_estimate": None,
                "confidence": 0,
                "listings": 0,
                "source": None,
            })

    return {"card_id": card.id, "card_name": card.name, "treatments": results}
```

**Acceptance Checks:**
- [ ] Endpoint returns floor for each treatment
- [ ] Handles treatments with no listings gracefully
- [ ] Respects `days` parameter

---

### UOW-012-2: Create FloorPriceBadge Component
**Type:** frontend
**Estimate:** 1 hour
**Dependencies:** None

**Exact Action:**
Create `frontend/app/components/FloorPriceBadge.tsx`:
```tsx
interface FloorPriceBadgeProps {
  floorEstimate: number | null;
  confidence: number;
  source?: string;
  className?: string;
}

export function FloorPriceBadge({
  floorEstimate,
  confidence,
  source,
  className,
}: FloorPriceBadgeProps) {
  if (floorEstimate === null) {
    return (
      <div className={cn("text-muted-foreground", className)}>
        <span>Floor: Insufficient data</span>
      </div>
    );
  }

  const confidenceColor =
    confidence >= 0.7 ? "text-green-600" :
    confidence >= 0.4 ? "text-yellow-600" :
    "text-red-600";

  return (
    <div className={cn("flex items-center gap-2", className)}>
      <span className="text-2xl font-bold">
        ${floorEstimate.toFixed(2)}
      </span>
      <span className={cn("text-sm", confidenceColor)}>
        ({(confidence * 100).toFixed(0)}% confidence)
      </span>
    </div>
  );
}
```

**Acceptance Checks:**
- [ ] Displays floor price prominently
- [ ] Shows confidence percentage with color coding
- [ ] Handles null floor gracefully

---

### UOW-012-3: Create FloorPriceByTreatment Component
**Type:** frontend
**Estimate:** 2 hours
**Dependencies:** UOW-012-1

**Exact Action:**
Create `frontend/app/components/FloorPriceByTreatment.tsx`:

- Fetch data from `/api/v1/cards/{id}/order-book/by-treatment`
- Display as responsive table/grid
- Show treatment, floor, confidence, listing count
- Color-code confidence
- Handle loading and empty states

**Acceptance Checks:**
- [ ] Table shows all treatments
- [ ] Confidence color-coded
- [ ] Handles treatments with no data
- [ ] Loading skeleton while fetching
- [ ] Mobile responsive (cards instead of table on small screens)

---

### UOW-012-4: Integrate into Card Detail Page
**Type:** frontend
**Estimate:** 2 hours
**Dependencies:** UOW-012-2, UOW-012-3

**Exact Action:**
Modify `frontend/app/routes/cards.$cardId.tsx`:

1. **Hero section:** Add FloorPriceBadge below card name
2. **Pricing section:** Add FloorPriceByTreatment component
3. **Data fetching:** Add query for order book data
4. **Tab/section:** Consider adding "Pricing" tab if not exists

**Acceptance Checks:**
- [ ] Floor price visible in hero
- [ ] Treatment breakdown in pricing section
- [ ] Data fetches on page load
- [ ] No layout shifts during loading

---

### UOW-012-5: Add Confidence Tooltip
**Type:** frontend
**Estimate:** 1 hour
**Dependencies:** UOW-012-2

**Exact Action:**
Add tooltip explaining confidence calculation:

"Confidence is based on:
- Number of active listings (more = higher)
- Data freshness (recent = higher)
- Price clustering (tighter = higher)

Source: {active_listings | sales_fallback}"

**Acceptance Checks:**
- [ ] Tooltip appears on hover/click
- [ ] Explains confidence factors
- [ ] Shows data source

---

## Testing Plan

### API Tests
```python
def test_order_book_by_treatment_endpoint():
    response = client.get("/api/v1/cards/1/order-book/by-treatment")
    assert response.status_code == 200
    data = response.json()
    assert "treatments" in data
    assert len(data["treatments"]) > 0
```

### Manual Testing
1. Navigate to card with good data (e.g., Dragonmaster Cai)
2. Verify floor price in hero section
3. Verify treatment breakdown table
4. Test card with sparse data
5. Test mobile responsiveness

---

## Done-When
- [ ] API endpoint `/order-book/by-treatment` working
- [ ] FloorPriceBadge in card hero section
- [ ] FloorPriceByTreatment table in pricing section
- [ ] Confidence color-coded with tooltip
- [ ] Loading states implemented
- [ ] Mobile responsive
- [ ] No TypeScript errors

---

## Notes
- OrderBookAnalyzer service already complete (TASK-003)
- Base API endpoint already exists (`/order-book`)
- Depth chart visualization deferred to TASK-007
- Consider caching API responses (order book data doesn't change frequently)
