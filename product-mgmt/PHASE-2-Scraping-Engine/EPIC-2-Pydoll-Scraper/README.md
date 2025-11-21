# EPIC-2: Pydoll Scraper Implementation

**Phase:** 2 - Scraping Engine Core  
**Status:** Pending  

## Objective
Build the core scraping engine using Pydoll (and Chrome DevTools Protocol) to fetch real-time market data from eBay.

## User Impact
Enables the application to provide actual intelligence and pricing data.

## Tech Scope
-   **Library:** Pydoll
-   **Browser:** Chromium (Headless)
-   **Parsing:** BeautifulSoup (if needed for HTML chunks) or Pydoll selectors.

## Dependencies
-   EPIC-1 (Database must handle the data).

## Completion Checklist
- [ ] Pydoll installed and launching Chromium successfully.
- [ ] Search logic correctly finds specific cards on eBay.
- [ ] Data extraction (Price, Date, Title) is accurate.
- [ ] Aggregation logic converts raw prices to Market Snapshots.
- [ ] Scraper runs without crashing on basic blocking.

## Code Reference
-   `app/scraper/`: Core scraper logic.
-   `app/services/aggregator.py`: Math/Stats logic.

## Required Documentation
-   `/*** PLAYBOOK.md */` (Troubleshooting scraper blocks/captchas).

