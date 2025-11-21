# Task T8 — Frontend Shell & Auth

**Belongs to:** EPIC-4  
**Status:** Pending  

## Description
Initialize the frontend application and implement the authentication flow.

## Acceptance Criteria
-   [ ] App runs locally on `localhost:3000`.
-   [ ] Users can log in via the UI.
-   [ ] JWT is stored securely (e.g., HTTPOnly cookie or memory + local storage if simple).
-   [ ] Unauthenticated users are redirected from protected routes.

## Units of Work (UOW)

### UOW U13 — Init TanStack Start
-   **Type:** Frontend
-   **Estimate:** 1 hour
-   **Dependencies:** None
-   **Checklist:**
    -   [ ] Scaffold TanStack Start project.
    -   [ ] Configure Tailwind CSS.
    -   [ ] Set up proxy to Backend API.

### UOW U14 — Login Form
-   **Type:** Frontend
-   **Estimate:** 3 hours
-   **Dependencies:** U13
-   **Checklist:**
    -   [ ] Create `routes/login.tsx`.
    -   [ ] Build form with validation (React Hook Form or similar).
    -   [ ] Integrate with `/auth/token` endpoint.
    -   [ ] Handle success (redirect) and error (toast) states.

## Code Reference
-   `frontend/app/routes/login.tsx`
-   `frontend/app/utils/auth.ts`

