# Task T6 — Auth System (JWT)

**Belongs to:** EPIC-3  
**Status:** Pending  

## Description
Implement a robust authentication system using JWTs.

## Acceptance Criteria
-   [ ] Users can register with email/password.
-   [ ] Passwords are hashed (bcrypt/Argon2).
-   [ ] Login returns a valid JWT Access Token.
-   [ ] Protected routes reject invalid/missing tokens.

## Units of Work (UOW)

### UOW U9 — User Model & Password Hashing
-   **Type:** Backend
-   **Estimate:** 2 hours
-   **Dependencies:** U2
-   **Checklist:**
    -   [ ] Add `User` model to `app/models/user.py`.
    -   [ ] Install `passlib[bcrypt]`.
    -   [ ] Implement `verify_password` and `get_password_hash`.

### UOW U10 — JWT Handler
-   **Type:** Backend
-   **Estimate:** 2 hours
-   **Dependencies:** U9
-   **Checklist:**
    -   [ ] Install `python-jose`.
    -   [ ] Implement `create_access_token`.
    -   [ ] Implement `get_current_user` dependency.
    -   [ ] Create `/auth/token` endpoint.

## Code Reference
-   `app/core/security.py`
-   `app/api/auth.py`

