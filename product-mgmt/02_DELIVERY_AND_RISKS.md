# Delivery & Risk Plan

## Sprint Mapping

### **Sprint 1: The Backbone (Days 1-5)**
-   **Theme:** Data Ingestion & Schema.
-   **Priorities:** Database connection, PDF Parsing, Basic Scraper prototype.
-   **Must-Have UOWs:** U1, U2, U3, U4, U5.
-   **Demo Checkpoint:** Show the database populated with cards and a raw console log of eBay prices for one card.

### **Sprint 2: The Engine & API (Days 6-10)**
-   **Theme:** Data Flow.
-   **Priorities:** Scraping Loop, FastAPI Endpoints, Auth.
-   **Must-Have UOWs:** U6, U7, U8, U9, U10, U11.
-   **Demo Checkpoint:** Swagger UI showing secured data access.

### **Sprint 3: The Experience (Days 11-14)**
-   **Theme:** Visualization.
-   **Priorities:** Frontend UI, Deployment.
-   **Must-Have UOWs:** U13, U14, U15, U16.
-   **Demo Checkpoint:** Live URL on Vercel.

---

## Risks & Hidden Work

### 1. eBay Dom Structure Changes (High Impact)
-   **Risk:** Scraper breaks if eBay changes class names or HTML structure.
-   **Why it matters:** Data flow stops completely.
-   **Mitigation:** Write robust selectors (searching by text content where possible) and add "Broken Scraper" alerting in Phase 5.
-   **Belongs in:** Phase 2 / Maintenance.

### 2. Rate Limiting / IP Bans (Medium Impact)
-   **Risk:** Neon/Railway IP gets flagged by eBay.
-   **Why it matters:** Scraper gets blocked.
-   **Mitigation:** Ensure Pydoll uses random user agents. If blocked, implement a simple rotating proxy middleware.
-   **Belongs in:** Phase 2.

### 3. PDF Data Quality (Low Impact)
-   **Risk:** PDF formatting might be inconsistent or contain OCR errors.
-   **Why it matters:** Database "Truth" might be corrupted.
-   **Mitigation:** Manual review of the seed JSON before first insert.
-   **Belongs in:** Phase 1.

---

## Tech Debt (Planned)
-   **ORM Divergence:** Using **SQLModel** (Python) instead of Drizzle (TypeScript) as originally requested, to better fit the FastAPI backend.
-   **Sync/Async Mix:** Scraper will be Async, PDF parser likely Sync. Need to manage the event loop carefully in the script runners to avoid blocking.

