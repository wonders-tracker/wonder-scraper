# Task T9 — Market Data Table

**Belongs to:** EPIC-4  
**Status:** Pending  

## Description
Implement the main dashboard view displaying the list of cards and their current market data.

## Acceptance Criteria
-   [ ] Table renders with correct columns.
-   [ ] Data is fetched from API.
-   [ ] Loading and Error states are handled.

## Units of Work (UOW)

### UOW U15 — Data Fetching Hook
-   **Type:** Frontend
-   **Estimate:** 1 hour
-   **Dependencies:** U13
-   **Checklist:**
    -   [ ] Setup QueryClient.
    -   [ ] Create `useCards` hook wrapping the API call.
    -   [ ] Type the response using TypeScript interfaces.

### UOW U16 — Table Component
-   **Type:** Frontend
-   **Estimate:** 4 hours
-   **Dependencies:** U15
-   **Checklist:**
    -   [ ] Install TanStack Table.
    -   [ ] Define columns (Name, Rarity, Min Price, Avg Price).
    -   [ ] Implement Sorting and Basic Filtering.
    -   [ ] Style with Tailwind.

## Code Reference
-   `frontend/app/routes/index.tsx`
-   `frontend/app/components/CardTable.tsx`

