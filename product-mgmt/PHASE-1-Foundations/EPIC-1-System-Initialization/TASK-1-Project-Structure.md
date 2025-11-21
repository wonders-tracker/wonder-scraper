# Task T1 — Project Structure & DB Config

**Belongs to:** EPIC-1 (System Initialization)  
**Status:** Pending  

## Description
Initialize the Git repository, set up the Python environment using Poetry, and configure the connection to the Neon Postgres database using SQLModel.

## Acceptance Criteria
- [ ] `git status` shows a clean repo with correct `.gitignore`.
- [ ] `poetry run python` works without errors.
- [ ] Environment variables are loaded from `.env`.
- [ ] A test script can successfully connect to Neon and execute `SELECT 1`.

## Units of Work (UOW)

### UOW U1 — Init Repo & Env
-   **Type:** Infra
-   **Estimate:** 1 hour
-   **Dependencies:** None
-   **Checklist:**
    -   [ ] Run `git init`.
    -   [ ] Create `.gitignore` (Python/Mac/Cursor).
    -   [ ] Initialize Poetry project.
    -   [ ] Install `sqlmodel`, `psycopg2-binary`, `python-dotenv`.
    -   [ ] Create `.env` and `.env.example`.

### UOW U2 — Define SQLModel Schema
-   **Type:** Backend
-   **Estimate:** 2 hours
-   **Dependencies:** U1
-   **Checklist:**
    -   [ ] Create `app/models/card.py` (Card, Rarity models).
    -   [ ] Create `app/models/market.py` (MarketSnapshot model).
    -   [ ] Create `app/db.py` (Engine configuration).
    -   [ ] Create `scripts/init_db.py` to run `SQLModel.metadata.create_all(engine)`.
    -   [ ] Verify tables exist in Neon dashboard.

## Code Reference
-   `app/db.py`
-   `app/models/*.py`
-   `.env`

