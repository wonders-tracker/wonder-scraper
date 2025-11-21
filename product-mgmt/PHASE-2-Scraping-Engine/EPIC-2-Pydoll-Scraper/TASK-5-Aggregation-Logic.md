# Task T5 — Aggregation Logic

**Belongs to:** EPIC-2  
**Status:** Pending  

## Description
Process raw scraped prices to determine the Minimum, Maximum, Average, and Volume for a card.

## Acceptance Criteria
-   [ ] Outliers are handled (optional, simple min/max for now).
-   [ ] Math is correct (Average = Sum / Count).
-   [ ] Returns a clean Dictionary or Pydantic model ready for DB insertion.

## Units of Work (UOW)

### UOW U8 — Data Math Utils
-   **Type:** Backend
-   **Estimate:** 1 hour
-   **Dependencies:** None
-   **Checklist:**
    -   [ ] Create `app/services/math.py`.
    -   [ ] Implement `calculate_stats(prices: List[float])`.
    -   [ ] Add unit tests.

## Code Reference
-   `app/services/math.py`

