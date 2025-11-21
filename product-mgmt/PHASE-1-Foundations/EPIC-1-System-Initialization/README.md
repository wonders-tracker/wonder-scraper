# EPIC-1: System Initialization

**Phase:** 1 - Foundations  
**Status:** Pending  

## Objective
Scaffold project, configure environment, and establish the database connection to Neon. This is the bedrock for all future development.

## User Impact
None directly (Foundation layer). Enables developers to run the app.

## Tech Scope
-   **Language:** Python 3.11+
-   **Dependency Manager:** Poetry
-   **Database:** Neon (Serverless Postgres)
-   **ORM:** SQLModel (Pydantic + SQLAlchemy)

## Dependencies
-   None

## Completion Checklist
- [ ] Project repository initialized with `.gitignore`
- [ ] Poetry environment active and dependencies installed
- [ ] SQLModel connected to Neon DB
- [ ] Database schema (Cards, Rarities) defined
- [ ] Tables created in Neon via migration/create_all

## Code Reference
-   `pyproject.toml`: Dependency definitions.
-   `app/db.py`: Database connection logic.
-   `app/models/`: SQLModel definitions.

## Required Documentation
-   `/*** ARCHITECTURE.md */` (Service boundaries)
-   `/*** DATA_MODEL.md */` (Schema diagrams)

