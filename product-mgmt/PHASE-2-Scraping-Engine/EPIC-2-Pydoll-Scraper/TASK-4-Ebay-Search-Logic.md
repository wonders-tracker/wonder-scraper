# Task T4 — eBay Search & Parse Logic

**Belongs to:** EPIC-2  
**Status:** Pending  

## Description
Implement the specific logic to search for TCG cards on eBay and extract price data from the results list.

## Acceptance Criteria
-   [ ] Generates correct eBay search URLs for given card names.
-   [ ] Extracts Price, Title, and Sold Date (if available) from list items.
-   [ ] Handles "No results found" gracefully.

## Units of Work (UOW)

### UOW U6 — Search URL Builder
-   **Type:** Backend
-   **Estimate:** 1 hour
-   **Dependencies:** None
-   **Checklist:**
    -   [ ] Create `app/scraper/utils.py`.
    -   [ ] Implement `build_ebay_url(card_name, filters)`.
    -   [ ] Add unit tests for URL encoding/formatting.

### UOW U7 — DOM Parser
-   **Type:** Backend
-   **Estimate:** 3 hours
-   **Dependencies:** U5
-   **Checklist:**
    -   [ ] Analyze eBay HTML structure (identify selectors).
    -   [ ] Implement `parse_search_results(html_content)`.
    -   [ ] Extract Price strings and convert to float.
    -   [ ] Extract Date strings and convert to `datetime`.

## Code Reference
-   `app/scraper/ebay.py`
-   `app/scraper/utils.py`

