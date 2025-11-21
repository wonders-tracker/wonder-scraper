# Task T3 — Pydoll Integration

**Belongs to:** EPIC-2  
**Status:** Pending  

## Description
Set up the Pydoll environment and create a reusable browser context manager.

## Acceptance Criteria
-   [ ] Pydoll successfully launches a browser instance.
-   [ ] Browser navigates to a target URL (e.g., eBay).
-   [ ] Browser closes cleanly after execution (no zombie processes).

## Units of Work (UOW)

### UOW U5 — Basic Pydoll Setup
-   **Type:** Backend
-   **Estimate:** 2 hours
-   **Dependencies:** U1
-   **Checklist:**
    -   [ ] Install `pydoll` (and any system deps for Chromium).
    -   [ ] Create `app/scraper/browser.py` (Context Manager).
    -   [ ] Implement `get_page_content(url)` generic function.
    -   [ ] Test with a simple script `scripts/test_browser.py`.

## Code Reference
-   `app/scraper/browser.py`

