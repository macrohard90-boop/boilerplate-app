# Phase 3: Authentication System

**Estimate:** 5-6 hours
**Depends on:** Phase 2
**Category:** Security & identity

## Goal
Build the complete authentication and authorization system: JWT access/refresh tokens backed by Redis sessions, OAuth provider integrations, role-based access control (RBAC), machine-to-machine API key auth, and the full middleware chain. At the end of this phase, every API route can be protected with authentication, authorization, and audit logging.

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
