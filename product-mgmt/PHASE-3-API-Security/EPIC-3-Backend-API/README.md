# EPIC-3: Backend API

**Phase:** 3 - API & Security Layer  
**Status:** Pending  

## Objective
Expose the scraped market data via a secure REST API using FastAPI.

## User Impact
Frontend application and external tools can consume the data.

## Tech Scope
-   **Framework:** FastAPI
-   **Auth:** JWT (JSON Web Tokens)
-   **Security:** OAuth2 Password Bearer

## Dependencies
-   EPIC-1 (DB Models), EPIC-2 (Data exists to be served).

## Completion Checklist
- [ ] FastAPI app initialized.
- [ ] User registration and login flow works.
- [ ] JWT tokens are generated and validated.
- [ ] Public/Protected endpoints are correctly configured.
- [ ] Swagger/Redoc UI is accessible.

## Code Reference
-   `app/main.py`: App entrypoint.
-   `app/api/`: Route handlers.
-   `app/core/security.py`: Auth logic.

## Required Documentation
-   `/*** API_REFERENCE.md */` (General usage guide).

