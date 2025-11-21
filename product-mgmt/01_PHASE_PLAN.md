# Phase Plan

| Phase | Name | One-Line Summary |
| :--- | :--- | :--- |
| **1** | **Foundations & Data Ingestion** | Setup infra, database, and seed the system with the "Truth" (Card list). |
| **2** | **Scraping Engine Core** | Build the Pydoll scraper and aggregation logic to fetch real market data. |
| **3** | **API & Security Layer** | Expose data via secure FastAPI endpoints with JWT authentication. |
| **4** | **Frontend Intelligence Dashboard** | Build the TanStack Start UI to visualize the market data. |
| **5** | **Hardening & Deployment** | Automate scheduling, caching, and deploy to Railway/Vercel. |

## Phase Details

### Phase 1: Foundations & Data Ingestion
-   **Goal:** Establish the "Source of Truth" in Postgres and set up the repository structure.
-   **In-Scope:** Repo setup, DB schema design, PDF parsing script, Seeding `cards` and `rarities` tables.
-   **Out-of-Scope:** Scraping eBay, API endpoints, Frontend UI.
-   **Exit Criteria:** Local Python script can read the PDF and populate Neon DB with all card names and rarities.
-   **Timeline:** 3 Days

### Phase 2: Scraping Engine Core
-   **Goal:** Successfully extract and aggregate market data from eBay.
-   **In-Scope:** Pydoll setup, eBay search logic, HTML parsing, Data cleaning, Aggregation (Min/Max/Avg), History storage.
-   **Out-of-Scope:** UI, User Auth, API serving.
-   **Exit Criteria:** A script runs, scrapes eBay for a specific card, and inserts `market_data` rows into Neon.
-   **Timeline:** 1 Week

### Phase 3: API & Security Layer
-   **Goal:** Serve the data securely to the outside world.
-   **In-Scope:** FastAPI setup, JWT Auth flow, Endpoints for `GET /market-data`, `GET /analytics`.
-   **Out-of-Scope:** Frontend Components, Scheduler.
-   **Exit Criteria:** cURL requests with a valid JWT return JSON market data.
-   **Timeline:** 4 Days

### Phase 4: Frontend Intelligence Dashboard
-   **Goal:** User-facing visualization.
-   **In-Scope:** TanStack Start setup, TanStack Query integration, Data Tables (sorting/filtering), Auth forms.
-   **Out-of-Scope:** Advanced charting (start with tables), payment processing.
-   **Exit Criteria:** User can log in and see a table of cards with live eBay prices.
-   **Timeline:** 1 Week

### Phase 5: Hardening & Deployment
-   **Goal:** Production readiness and automation.
-   **In-Scope:** Dockerization, Railway Cron Jobs, Vercel Deploy, basic Caching.
-   **Out-of-Scope:** Complex CI/CD pipelines (basic only).
-   **Exit Criteria:** Live URL on Vercel displaying data that updates automatically every hour.
-   **Timeline:** 3 Days

