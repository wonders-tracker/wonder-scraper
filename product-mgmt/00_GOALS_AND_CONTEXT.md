# Goals & Context

## Product Goals
1.  **Market Transparency:** Provide accurate, up-to-date pricing (Min, Max, Avg, Volume) for "Wonders of the First" TCG.
2.  **Automation:** Eliminate manual tracking by polling eBay hourly.
3.  **User Access:** Secure, authenticated access for users to view market data via a responsive web dashboard.

## Technical Goals
1.  **High-Performance Scraping:** Utilize `Pydoll` for lightweight, undetectable browser automation to scrape eBay.
2.  **Type-Safe Architecture:** Ensure strong typing from DB (Postgres) to API (FastAPI + Pydantic) to Frontend (TypeScript).
3.  **Serverless/Scalable:** Leverage Neon (Serverless PG) and Vercel/Railway for low-ops deployment.

## Constraints
-   **Scraping Cadence:** Hourly polling.
-   **Security:** JWT-based RBAC; Secure handling of DB credentials.
-   **Stack Specifics:** Python/FastAPI (Backend), TanStack Start (Frontend).

## Assumptions & Clarifications
1.  **ORM Choice:** Using **SQLModel** (Pydantic + SQLAlchemy) instead of Drizzle for the Python backend, as Drizzle is TypeScript-only.
2.  **PDF Parsing:** Text/tables will be extracted using `pdfplumber` or `pypdf` to seed the database initially.
3.  **eBay Anti-Bot:** Pydoll (CDP) will be used; proxy rotation strategy will be added if volume triggers blocks.

