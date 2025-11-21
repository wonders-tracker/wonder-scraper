# Task T2 — Reference Data Seeding

**Belongs to:** EPIC-1 (System Initialization)  
**Status:** Pending  

## Description
Parse the provided PDF checklist (`data/Base-Set-WoTF-Existence-Checklist-Google-Sheets.pdf`) to extract the official list of Cards and Rarities, then seed this data into the Postgres database.

## Acceptance Criteria
-   [ ] PDF text is accurately extracted (no garbled characters).
-   [ ] A JSON file of the extracted data is generated for verification.
-   [ ] The `cards` and `rarities` tables in Postgres are populated.
-   [ ] Row counts in DB match the PDF item count.

## Units of Work (UOW)

### UOW U3 — PDF Parser Prototype
-   **Type:** Data
-   **Estimate:** 3 hours
-   **Dependencies:** U1
-   **Checklist:**
    -   [ ] Install `pdfplumber`.
    -   [ ] Write `scripts/parse_pdf.py`.
    -   [ ] Iterate on parsing logic to handle PDF table structure.
    -   [ ] Output `data/seeds/cards.json`.

### UOW U4 — Seeding Script
-   **Type:** Backend
-   **Estimate:** 1 hour
-   **Dependencies:** U2, U3
-   **Checklist:**
    -   [ ] Write `scripts/seed_db.py`.
    -   [ ] Load `data/seeds/cards.json`.
    -   [ ] Upsert data into `cards` table (prevent duplicates).
    -   [ ] Log success/failure counts.

## Code Reference
-   `scripts/parse_pdf.py`
-   `scripts/seed_db.py`
-   `data/Base-Set-WoTF-Existence-Checklist-Google-Sheets.pdf`

