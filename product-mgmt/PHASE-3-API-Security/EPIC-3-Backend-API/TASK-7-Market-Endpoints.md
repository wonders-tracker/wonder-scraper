# Task T7 — Market Data Endpoints

**Belongs to:** EPIC-3  
**Status:** Pending  

## Description
Create the API endpoints to fetch card data and market snapshots.

## Acceptance Criteria
-   [ ] Endpoints return JSON data matching Pydantic schemas.
-   [ ] Pagination is implemented for list views.
-   [ ] Latency is under 200ms for standard requests.

## Units of Work (UOW)

### UOW U11 — Card List Endpoint
-   **Type:** Backend
-   **Estimate:** 2 hours
-   **Dependencies:** U2
-   **Checklist:**
    -   [ ] Create `GET /cards`.
    -   [ ] Add query params (`page`, `limit`, `search`).
    -   [ ] Implement DB query with SQLModel.

### UOW U12 — Snapshot Endpoint
-   **Type:** Backend
-   **Estimate:** 2 hours
-   **Dependencies:** U2, U11
-   **Checklist:**
    -   [ ] Create `GET /cards/{id}/market`.
    -   [ ] Return latest `MarketSnapshot` for the card.
    -   [ ] Handle 404 if card/data not found.

## Code Reference
-   `app/api/cards.py`
-   `app/schemas/`: API Response models.

