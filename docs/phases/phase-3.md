# Phase 3: Authentication System

**Estimate:** 6-7 hours
**Depends on:** Phase 2
**Category:** Security & identity

## Goal
Build the complete authentication and authorization system: JWT access/refresh tokens backed by Redis sessions, OAuth provider integrations, role-based access control (RBAC), machine-to-machine API key auth, and the full middleware chain. Includes a lightweight frontend auth UI to visually verify all auth flows in the browser. At the end of this phase, every API route can be protected with authentication, authorization, and audit logging — and the auth system is verifiable end-to-end from a browser.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 3 (Session & Auth Architecture), 4 (Redis Key Architecture), 5 (Full Middleware Chain), and 12 (Security Measures) for the complete auth specification.

## Deliverables

1. **JWT token service** (modules/auth/services/):
   - Access token: signed JWT, 15-minute expiry (configurable via `JWT_EXPIRY`)
   - Refresh token: opaque token stored in Redis, 7-day TTL (configurable via `REFRESH_TOKEN_TTL`)
   - Token rotation: on refresh, old refresh token is invalidated, new pair issued
   - Claims: user_id, role, session_id, permissions, issued_at, expires_at

2. **Redis session management** (modules/auth/services/):
   - Session creation on login: store `{user_id, role, device, ip, created_at}` with TTL
   - Session registry per user: `user_sessions:{user_id}` SET in Redis
   - Concurrent session limit: configurable `MAX_SESSIONS_PER_USER` (default 5), evict oldest on overflow
   - Session invalidation on logout: delete session + refresh token from Redis
   - Session lookup: O(1) by session_id

3. **Registration & login endpoints** (modules/auth/routes/):
   - `POST /api/auth/register` — create user, hash password (bcrypt, cost 12), return tokens
   - `POST /api/auth/login` — validate credentials, create session, return access + refresh tokens
   - `POST /api/auth/refresh` — validate refresh token in Redis, rotate tokens
   - `POST /api/auth/logout` — invalidate session + refresh token
   - `POST /api/auth/forgot-password` — generate reset token (Redis, 1hr TTL)
   - `POST /api/auth/reset-password` — validate reset token, update password, invalidate all sessions
   - `POST /api/auth/verify-email` — validate verification token, set `is_verified = true`
   - Consistent error format: `{error, message, details}`

4. **OAuth provider integrations** (modules/auth/adapters/):
   - AuthProvider interface implementation for each provider
   - Google: `GET /api/auth/oauth/google` → redirect, `GET /api/auth/oauth/google/callback` → exchange code → create/link account
   - Apple: same flow with Apple-specific token handling
   - Microsoft/Azure AD: same flow
   - GitHub: same flow
   - Generic OIDC: configurable issuer URL, auto-discovery of endpoints
   - Account linking: if email matches existing verified user, link OAuth identity; otherwise create new user

5. **RBAC middleware** (modules/auth/services/):
   - Role hierarchy: admin > merchant > customer
   - Permission format: `resource:action` (e.g., `products:write`, `orders:read`, `admin:users`)
   - `require_auth()` — validates JWT, verifies session in Redis, attaches user context
   - `require_role(role)` — checks user has required role
   - `require_permission(permission)` — checks user has specific permission
   - User context: `{user_id, role, permissions, session_id}`

6. **M2M (Machine-to-Machine) auth** (modules/auth/services/):
   - `POST /api/auth/api-keys` — generate API key (hashed storage, raw shown once), assign scoped permissions
   - `DELETE /api/auth/api-keys/{id}` — revoke key
   - `GET /api/auth/api-keys` — list user's active keys
   - OAuth2 client credentials: `POST /api/auth/m2m/token` (client_id + client_secret → scoped token)
   - Rate limiting per key: Redis sliding window (`rate:key:{api_key_id}:{window}`)
   - Audit: every M2M action logged with key_id, endpoint, payload_hash

7. **Session isolation middleware chain** (backend/core/middleware.py):
   - 6-step pipeline per ARCHITECTURE.md §3.2:
     1. Extract JWT from Authorization header or httpOnly cookie
     2. Validate JWT signature and expiry
     3. Look up active session in Redis
     4. Verify session belongs to requesting user
     5. Attach verified user context to request
     6. All DB queries scoped by server-verified user_id
   - CSRF token support: generate on login, validate on state-changing requests

8. **Rate limiting** (backend/core/middleware.py):
   - Per-user: sliding window counter in Redis (`rate:user:{user_id}:{window}`)
   - Per-API-key: separate limits (`rate:key:{api_key_id}:{window}`)
   - Per-IP for unauthenticated endpoints (login, register)
   - Return `429 Too Many Requests` with `Retry-After` header

9. **Audit logging service** (modules/auth/services/):
   - Log to `core.audit_log`: user_id, api_key_id, action, resource, resource_id, ip_address, payload_hash
   - Sensitive operations: login, logout, password change, role change, API key creation
   - Payload hashing: SHA-256 of request body (never store raw sensitive data)

10. **Pydantic schemas** (modules/auth/models/):
    - Request/response models for all endpoints
    - Password validation: min 8 chars, uppercase + lowercase + digit
    - Token response: `{access_token, refresh_token, token_type, expires_in}`

11. **Lightweight frontend auth UI** (frontend/app/auth/ + frontend/components/):
    Minimal pages to visually verify all auth flows in the browser. These are intentionally
    simple — Phase 9 replaces them with the full production UI.

    **Pages:**
    - `/auth/login` — Email/password form + OAuth provider buttons (Google, GitHub, etc.)
      - Error display for invalid credentials
      - "Forgot password?" link
      - "Create account" link to register
    - `/auth/register` — Registration form (email, password, first_name, last_name)
      - Client-side password strength indicator (min 8, upper, lower, digit)
      - Error display for duplicate email, validation failures
      - Auto-login on successful registration
    - `/auth/forgot-password` — Email input form, triggers reset token generation
      - Success message: "If an account exists, a reset link has been sent"
    - `/auth/reset-password` — New password form (accessed via reset token URL param)
      - Token validation on page load, error if expired/invalid
    - `/protected` — Authenticated-only page showing verified user context:
      - User info: email, name, role
      - Session info: session_id, created_at, device/IP
      - Permissions list
      - Active sessions count
      - "This page proves auth works" banner

    **Shared components:**
    - `AuthNav` — Minimal navigation bar:
      - Logged out: Login / Register links
      - Logged in: User email, role badge, Logout button
    - `AuthProvider` (React Context) — Client-side auth state:
      - Stores access token in memory (NOT localStorage)
      - Refresh token in httpOnly cookie (set by backend)
      - `useAuth()` hook: `{user, isAuthenticated, login, logout, refresh}`
      - Auto-refresh: intercept 401 responses → call refresh → retry original request
      - On refresh failure: clear state, redirect to `/auth/login`

    **API client** (frontend/lib/api.ts):
    - Centralized fetch wrapper with base URL
    - Auto-attaches access token to Authorization header
    - 401 interceptor: attempt token refresh, retry once, redirect to login on failure
    - Parses backend error format `{error, message, details}`

    **Token flow in browser:**
    1. Login/register → backend sets refresh token as httpOnly cookie + returns access token in body
    2. Frontend stores access token in memory (React state)
    3. Every API call → attach access token in Authorization header
    4. On 401 → call `POST /api/auth/refresh` (cookie sent automatically) → get new access token
    5. On refresh failure → redirect to login
    6. Logout → call `POST /api/auth/logout` → clear memory state, backend clears cookie

    **Visual verification checklist (what you can test in browser):**
    - Register a new user → auto-redirected to /protected → see user info
    - Logout → redirected to /auth/login
    - Login with created credentials → back to /protected
    - Visit /protected while logged out → redirected to /auth/login
    - Login with wrong password → error message displayed
    - Register with existing email → error message displayed
    - OAuth button click → redirects to provider → callback → /protected
    - Wait 15+ min (JWT expiry) → next API call triggers silent refresh
    - Open 6 browser tabs, login in each → oldest session evicted

## Acceptance Criteria
- [ ] `POST /api/auth/register` creates user with bcrypt-hashed password
- [ ] `POST /api/auth/login` returns JWT access token + refresh token
- [ ] `POST /api/auth/refresh` rotates tokens and invalidates old refresh token
- [ ] `POST /api/auth/logout` clears session from Redis
- [ ] JWT expiry is enforced (expired token returns 401)
- [ ] Refresh token TTL is enforced (expired refresh returns 401)
- [ ] Concurrent session limit works (6th login evicts oldest session)
- [ ] OAuth flow works for at least one provider (Google recommended for testing)
- [ ] `require_auth()` blocks unauthenticated requests
- [ ] `require_role('admin')` blocks non-admin users
- [ ] `require_permission('products:write')` checks granular permissions
- [ ] API key generation returns raw key once, stores hashed
- [ ] API key auth works for protected routes with correct scopes
- [ ] Rate limiting returns 429 when limit exceeded
- [ ] CSRF token validated on POST/PUT/DELETE requests
- [ ] Audit log entries created for login, logout, password change
- [ ] Password reset flow works end-to-end
- [ ] All user_id values come from server-verified JWT, never client input
- [ ] All auth endpoints return consistent error format `{error, message, details}`
- [ ] Frontend: `/auth/login` page renders with email/password form and OAuth buttons
- [ ] Frontend: `/auth/register` page creates account and auto-redirects to /protected
- [ ] Frontend: `/protected` page shows user info (email, role, session) when authenticated
- [ ] Frontend: `/protected` redirects to /auth/login when not authenticated
- [ ] Frontend: Logout clears session and redirects to login
- [ ] Frontend: OAuth button redirects to provider, callback returns to /protected
- [ ] Frontend: Token refresh happens transparently on 401 (no manual re-login)
- [ ] Frontend: Invalid credentials show error message on login page
- [ ] Frontend: Password reset flow works end-to-end via browser

## Implementation Notes
- Password hashing: bcrypt with cost factor 12
- JWT library: `PyJWT` — keep dependency minimal
- Redis session keys: `session:{session_id}` with 7-day TTL
- Token in httpOnly cookie for browser clients, Authorization header for API clients
- OAuth callback URLs must be configurable per environment
- CSRF tokens stored in Redis with 1hr TTL, validated against session_id
- Account linking on OAuth: match by verified email, prompt if ambiguous
- All timestamps in UTC (TIMESTAMPTZ)

## Files to Create
- `modules/auth/config.py` — Auth module configuration and feature flags
- `modules/auth/services/token_service.py` — JWT creation, validation, refresh
- `modules/auth/services/session_service.py` — Redis session management
- `modules/auth/services/auth_service.py` — Registration, login, password reset logic
- `modules/auth/services/rbac_service.py` — Role and permission checking
- `modules/auth/services/api_key_service.py` — M2M key generation and validation
- `modules/auth/services/audit_service.py` — Audit log recording
- `modules/auth/adapters/google.py` — Google OAuth provider
- `modules/auth/adapters/apple.py` — Apple OAuth provider
- `modules/auth/adapters/microsoft.py` — Microsoft/Azure AD OAuth provider
- `modules/auth/adapters/github_oauth.py` — GitHub OAuth provider
- `modules/auth/adapters/oidc.py` — Generic OIDC provider
- `modules/auth/interfaces/auth_provider.py` — AuthProvider ABC
- `modules/auth/models/schemas.py` — Pydantic request/response models
- `modules/auth/routes/auth_routes.py` — Registration, login, logout, refresh, password reset
- `modules/auth/routes/oauth_routes.py` — OAuth redirect and callback endpoints
- `modules/auth/routes/api_key_routes.py` — API key CRUD endpoints
- `backend/core/middleware.py` — Session isolation chain, rate limiting, CSRF
- `backend/core/dependencies.py` — require_auth, require_role, require_permission
- Modified: `backend/main.py` — Register auth middleware, mount auth routes
- Modified: `backend/requirements.txt` — Add PyJWT, bcrypt, httpx
- Modified: `.env.template` — Add JWT_SECRET, OAuth credentials
- `frontend/app/auth/login/page.tsx` — Login page (email/password + OAuth buttons)
- `frontend/app/auth/register/page.tsx` — Registration page with validation
- `frontend/app/auth/forgot-password/page.tsx` — Forgot password form
- `frontend/app/auth/reset-password/page.tsx` — Reset password form (token from URL)
- `frontend/app/protected/page.tsx` — Authenticated-only page showing user context
- `frontend/components/AuthNav.tsx` — Minimal nav bar (login/register or user+logout)
- `frontend/lib/auth-context.tsx` — React Context for auth state + useAuth() hook
- `frontend/lib/api.ts` — API client with token handling and 401 refresh interceptor
- Modified: `frontend/app/layout.tsx` — Wrap with AuthProvider, add AuthNav
