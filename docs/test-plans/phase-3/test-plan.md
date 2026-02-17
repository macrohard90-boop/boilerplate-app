# Phase 3: Authentication System — Test Plan

**Phase:** 3 — Authentication System
**Created:** 2026-02-16
**Last executed:** —
**Status:** Not yet executed

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Section A: Registration & Login](#section-a-registration--login)
3. [Section B: Token Refresh & Rotation](#section-b-token-refresh--rotation)
4. [Section C: JWT Claims Verification](#section-c-jwt-claims-verification)
5. [Section D: Session Management](#section-d-session-management)
6. [Section E: RBAC & Permissions](#section-e-rbac--permissions)
7. [Section F: M2M API Key Auth](#section-f-m2m-api-key-auth)
8. [Section G: Password Reset Flow](#section-g-password-reset-flow)
9. [Section H: Rate Limiting](#section-h-rate-limiting)
10. [Section I: CSRF Protection](#section-i-csrf-protection)
11. [Section J: Audit Logging](#section-j-audit-logging)
12. [Section K: Browser Tests (Manual)](#section-k-browser-tests-manual)
13. [Section L: Re-run Checklist](#section-l-re-run-checklist)

---

## 1. Prerequisites

### Environment

- Docker Compose stack running: `docker compose up -d`
- All 5 services healthy: postgres, redis, fastapi, nextjs, nginx
- Verify with: `docker compose ps`
- Seed data loaded (test users exist)

### Connection Details

| Service | Host (from WSL) | Port | Credentials |
|---------|-----------------|------|-------------|
| PostgreSQL | localhost | 5432 | User: `boilerplate`, Password: `change-me`, DB: `boilerplate_db` |
| Redis | localhost | 6379 | No auth |
| FastAPI | via nginx | 80 | — |
| Next.js | via nginx | 80 | — |
| Nginx | localhost | 80/443 | — |

### Test Users (from seed data)

All passwords: `Test1234!`

| Email | Role | Permissions |
|-------|------|-------------|
| `admin@example.com` | admin | Full access (users, products, orders, analytics, settings) |
| `merchant@example.com` | merchant | products:read/write, orders:read/write, analytics:read |
| `customer@example.com` | customer | products:read, orders:read |

### Helper: Python Test Runner

Many tests below use Python to avoid bash escaping issues with passwords. All commands can be pasted directly into a WSL terminal.

---

## Section A: Registration & Login

### Test A1: Register New User

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'testuser@example.com','password':'Test1234!','first_name':'Test','last_name':'User'}).encode()
req = urllib.request.Request('http://localhost/api/auth/register', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
body = json.loads(resp.read().decode())
print('Status: 201' if body.get('access_token') else 'FAIL')
print('Has access_token:', bool(body.get('access_token')))
print('Has csrf_token:', bool(body.get('csrf_token')))
print('token_type:', body.get('token_type'))
print('expires_in:', body.get('expires_in'))
"
```

**Expected result:**
- Status: 201
- Response contains `access_token`, `csrf_token`, `token_type: bearer`, `expires_in: 900`

**Result:** [ ] Pass / [ ] Fail

---

### Test A2: Register Duplicate Email

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'admin@example.com','password':'Test1234!','first_name':'Dup','last_name':'User'}).encode()
req = urllib.request.Request('http://localhost/api/auth/register', data=data, headers={'Content-Type':'application/json'})
try:
    urllib.request.urlopen(req)
    print('FAIL: Should have returned 409')
except urllib.error.HTTPError as e:
    body = json.loads(e.read().decode())
    print(f'Status: {e.code}')
    print(f'Error format: {list(body.get(\"detail\", {}).keys())}')
"
```

**Expected result:**
- Status: 409
- Error format contains: `error`, `message`, `details`

**Result:** [ ] Pass / [ ] Fail

---

### Test A3: Register Weak Password

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'weak@example.com','password':'weak','first_name':'Weak','last_name':'Pass'}).encode()
req = urllib.request.Request('http://localhost/api/auth/register', data=data, headers={'Content-Type':'application/json'})
try:
    urllib.request.urlopen(req)
    print('FAIL: Should have returned 422')
except urllib.error.HTTPError as e:
    print(f'Status: {e.code} (expected 422)')
"
```

**Expected result:** Status 422 (validation error)

**Result:** [ ] Pass / [ ] Fail

---

### Test A4: Login with Valid Credentials

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
body = json.loads(resp.read().decode())
print('Status: 200')
print('Has access_token:', bool(body.get('access_token')))
print('Has csrf_token:', bool(body.get('csrf_token')))
print('expires_in:', body.get('expires_in'))
# Check Set-Cookie header for refresh token
cookie = resp.headers.get('Set-Cookie', '')
print('Has refresh_token cookie:', 'refresh_token=' in cookie)
print('Cookie httpOnly:', 'HttpOnly' in cookie or 'httponly' in cookie)
"
```

**Expected result:**
- Status: 200
- Has access_token, csrf_token, expires_in: 900
- refresh_token set as httpOnly cookie

**Result:** [ ] Pass / [ ] Fail

---

### Test A5: Login with Wrong Password

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'admin@example.com','password':'WrongPass1'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
try:
    urllib.request.urlopen(req)
    print('FAIL: Should have returned 401')
except urllib.error.HTTPError as e:
    body = json.loads(e.read().decode())
    print(f'Status: {e.code}')
    print(f'Error: {body.get(\"detail\", {}).get(\"error\")}')
"
```

**Expected result:** Status: 401, Error: `unauthorized`

**Result:** [ ] Pass / [ ] Fail

---

### Test A6: Login with Non-existent Email

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'nonexistent@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
try:
    urllib.request.urlopen(req)
    print('FAIL: Should have returned 401')
except urllib.error.HTTPError as e:
    print(f'Status: {e.code} (expected 401)')
"
```

**Expected result:** Status: 401 (same error as wrong password — no email enumeration)

**Result:** [ ] Pass / [ ] Fail

---

### Test A7: GET /me with Valid Token

**Command:**
```bash
python3 -c "
import urllib.request, json
# Login
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access_token']

# Call /me
req2 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {token}'})
resp2 = urllib.request.urlopen(req2)
me = json.loads(resp2.read().decode())
print('Email:', me['user']['email'])
print('Role:', me['user']['role'])
print('Is verified:', me['user']['is_verified'])
print('Has permissions:', len(me['user']['permissions']) > 0)
print('Has session:', me['session'] is not None)
print('Auth type:', me['auth_type'])
print('Has auth_time:', me.get('auth_time') is not None)
print('Has amr:', len(me.get('amr', [])) > 0)
"
```

**Expected result:**
- Email: admin@example.com, Role: admin, Is verified: True
- Has permissions, session, auth_type: jwt
- auth_time and amr present

**Result:** [ ] Pass / [ ] Fail

---

### Test A8: GET /me without Token

**Command:**
```bash
python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost/api/auth/me')
try:
    urllib.request.urlopen(req)
    print('FAIL: Should have returned 401')
except urllib.error.HTTPError as e:
    print(f'Status: {e.code} (expected 401)')
"
```

**Expected result:** Status: 401

**Result:** [ ] Pass / [ ] Fail

---

## Section B: Token Refresh & Rotation

### Test B1: Refresh Token Rotation

**Command:**
```bash
python3 -c "
import urllib.request, json, http.cookiejar
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login
data = json.dumps({'email':'customer@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = opener.open(req)
body1 = json.loads(resp.read().decode())
token1 = body1['access_token']
print('Login OK, got token1')

# Refresh
req2 = urllib.request.Request('http://localhost/api/auth/refresh', method='POST', headers={'Content-Type':'application/json'})
resp2 = opener.open(req2)
body2 = json.loads(resp2.read().decode())
token2 = body2['access_token']
print('Refresh OK, got token2')
print('Tokens differ:', token1 != token2)

# Use new token on /me
req3 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {token2}'})
resp3 = opener.open(req3)
me = json.loads(resp3.read().decode())
print('/me with new token works:', me['user']['email'] == 'customer@example.com')
"
```

**Expected result:**
- Login OK, Refresh OK
- Tokens differ: True
- /me with new token works: True

**Result:** [ ] Pass / [ ] Fail

---

### Test B2: Old Refresh Token Rejected After Rotation

**Command:**
```bash
python3 -c "
import urllib.request, json, http.cookiejar

# First session — login and capture cookie
cj1 = http.cookiejar.CookieJar()
opener1 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj1))
data = json.dumps({'email':'customer@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
opener1.open(req)

# Save the old cookie value
old_cookies = list(cj1)
print('Got refresh cookie')

# Refresh once (invalidates old refresh token)
req2 = urllib.request.Request('http://localhost/api/auth/refresh', method='POST', headers={'Content-Type':'application/json'})
opener1.open(req2)
print('Refreshed once (old token now invalid)')

# Try using original cookie jar (which still has old cookie) — should fail
# We need to use the old cookie. Create a new opener with the pre-refresh cookies
cj2 = http.cookiejar.CookieJar()
opener2 = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj2))
for c in old_cookies:
    cj2.set_cookie(c)

req3 = urllib.request.Request('http://localhost/api/auth/refresh', method='POST', headers={'Content-Type':'application/json'})
try:
    opener2.open(req3)
    print('FAIL: Old refresh token should be rejected')
except urllib.error.HTTPError as e:
    print(f'Old refresh token rejected: {e.code} (expected 401)')
"
```

**Expected result:** Old refresh token rejected with 401

**Result:** [ ] Pass / [ ] Fail

---

### Test B3: Expired/Invalid Token Returns 401

**Command:**
```bash
python3 -c "
import urllib.request, json
req = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': 'Bearer invalid.token.here'})
try:
    urllib.request.urlopen(req)
    print('FAIL')
except urllib.error.HTTPError as e:
    body = json.loads(e.read().decode())
    print(f'Status: {e.code} (expected 401)')
    print(f'Message: {body.get(\"detail\", {}).get(\"message\")}')
"
```

**Expected result:** Status: 401, Message: Invalid or expired token

**Result:** [ ] Pass / [ ] Fail

---

## Section C: JWT Claims Verification

### Test C1: New Token Contains All Required Claims

**Command:**
```bash
python3 -c "
import urllib.request, json, base64
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access_token']

# Decode payload
payload_b64 = token.split('.')[1] + '=='
claims = json.loads(base64.urlsafe_b64decode(payload_b64))
print(json.dumps(claims, indent=2))

# Verify required claims
required = ['iss','sub','aud','iat','exp','jti','sid','role','permissions','auth_time','amr','consent','token_type']
missing = [k for k in required if k not in claims]
print()
print('Missing claims:', missing if missing else 'NONE (all present)')
print('iss format correct:', claims['iss'].startswith('https://api.'))
print('aud is list:', isinstance(claims['aud'], list))
print('jti is string:', isinstance(claims['jti'], str) and len(claims['jti']) > 0)
print('sid is UUID-like:', len(claims['sid']) == 36)
print('amr is list:', isinstance(claims['amr'], list))
print('consent is list:', isinstance(claims['consent'], list))
print('token_type:', claims['token_type'])
"
```

**Expected result:**
- All 13 required claims present (none missing)
- `iss`: `https://api.localhost`
- `aud`: list containing `https://api.localhost`
- `jti`: non-empty string
- `sid`: UUID format (36 chars)
- `amr`: `["pwd"]`
- `consent`: `[]` (no GDPR records yet)
- `token_type`: `access`

**Result:** [ ] Pass / [ ] Fail

---

### Test C2: Refresh Preserves auth_time and amr

**Command:**
```bash
python3 -c "
import urllib.request, json, base64, http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login
data = json.dumps({'email':'customer@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = opener.open(req)
token1 = json.loads(resp.read().decode())['access_token']

# Decode original
p1 = token1.split('.')[1] + '=='
c1 = json.loads(base64.urlsafe_b64decode(p1))

# Refresh
req2 = urllib.request.Request('http://localhost/api/auth/refresh', method='POST', headers={'Content-Type':'application/json'})
resp2 = opener.open(req2)
token2 = json.loads(resp2.read().decode())['access_token']

# Decode refreshed
p2 = token2.split('.')[1] + '=='
c2 = json.loads(base64.urlsafe_b64decode(p2))

print('auth_time preserved:', c1['auth_time'] == c2['auth_time'])
print('amr preserved:', c1['amr'] == c2['amr'])
print('jti changed:', c1['jti'] != c2['jti'])
print('sid preserved:', c1['sid'] == c2['sid'])
"
```

**Expected result:**
- auth_time preserved: True
- amr preserved: True
- jti changed: True (new unique ID per token)
- sid preserved: True (same session)

**Result:** [ ] Pass / [ ] Fail

---

### Test C3: Issuer/Audience Validation Rejects Tampered Tokens

**Command:**
```bash
python3 -c "
import urllib.request, json
from jose import jwt

# Create a token with wrong issuer
fake_token = jwt.encode(
    {'sub': 'fake', 'iss': 'https://evil.com', 'aud': ['https://api.localhost'],
     'exp': 9999999999, 'sid': 'fake', 'role': 'admin', 'permissions': []},
    'change-me-to-a-long-random-string', algorithm='HS256'
)
req = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {fake_token}'})
try:
    urllib.request.urlopen(req)
    print('FAIL: Tampered token should be rejected')
except urllib.error.HTTPError as e:
    print(f'Wrong issuer rejected: {e.code} (expected 401)')

# Create a token with wrong audience
fake_token2 = jwt.encode(
    {'sub': 'fake', 'iss': 'https://api.localhost', 'aud': ['https://api.evil.com'],
     'exp': 9999999999, 'sid': 'fake', 'role': 'admin', 'permissions': []},
    'change-me-to-a-long-random-string', algorithm='HS256'
)
req2 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {fake_token2}'})
try:
    urllib.request.urlopen(req2)
    print('FAIL: Wrong audience should be rejected')
except urllib.error.HTTPError as e:
    print(f'Wrong audience rejected: {e.code} (expected 401)')
"
```

**Expected result:** Both tampered tokens rejected with 401

**Result:** [ ] Pass / [ ] Fail

---

## Section D: Session Management

### Test D1: Logout Invalidates Session

**Command:**
```bash
python3 -c "
import urllib.request, json, http.cookiejar

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

# Login
data = json.dumps({'email':'customer@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = opener.open(req)
token = json.loads(resp.read().decode())['access_token']
print('Logged in')

# Logout
req2 = urllib.request.Request('http://localhost/api/auth/logout', method='POST', headers={'Content-Type':'application/json'})
resp2 = opener.open(req2)
print('Logged out:', json.loads(resp2.read().decode())['message'])

# Try using old access token
req3 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {token}'})
try:
    opener.open(req3)
    print('FAIL: Old token should be rejected after logout')
except urllib.error.HTTPError as e:
    print(f'Old token rejected after logout: {e.code} (expected 401)')
"
```

**Expected result:**
- Logout succeeds
- Old access token returns 401 (session deleted from Redis)

**Result:** [ ] Pass / [ ] Fail

---

### Test D2: Concurrent Session Limit (6th Login Evicts Oldest)

**Command:**
```bash
python3 -c "
import urllib.request, json

tokens = []
for i in range(6):
    data = json.dumps({'email':'customer@example.com','password':'Test1234!'}).encode()
    req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
    resp = urllib.request.urlopen(req)
    body = json.loads(resp.read().decode())
    tokens.append(body['access_token'])
    print(f'Login {i+1} OK')

# First token (oldest) should now be invalidated
req = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {tokens[0]}'})
try:
    urllib.request.urlopen(req)
    print('FAIL: Oldest session should be evicted')
except urllib.error.HTTPError as e:
    print(f'Oldest session evicted: {e.code} (expected 401)')

# Latest token should still work
req2 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {tokens[5]}'})
resp2 = urllib.request.urlopen(req2)
print('Latest session works:', resp2.getcode() == 200)
"
```

**Expected result:**
- 6 logins succeed
- Token from login 1 returns 401 (evicted)
- Token from login 6 returns 200

**Result:** [ ] Pass / [ ] Fail

---

### Test D3: Session Count Visible in /me

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'merchant@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access_token']

req2 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {token}'})
resp2 = urllib.request.urlopen(req2)
me = json.loads(resp2.read().decode())
print('Active sessions count:', me['active_sessions_count'])
print('Count > 0:', me['active_sessions_count'] > 0)
"
```

**Expected result:** active_sessions_count is > 0

**Result:** [ ] Pass / [ ] Fail

---

## Section E: RBAC & Permissions

### Test E1: Admin Can Access Admin-Only Route

**Command:**
```bash
python3 -c "
import urllib.request, json

# Login as admin
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access_token']

# Access /me (requires auth)
req2 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {token}'})
resp2 = urllib.request.urlopen(req2)
me = json.loads(resp2.read().decode())
print('Admin role:', me['user']['role'])
print('Has users:write:', 'users:write' in me['user']['permissions'])
print('Has settings:write:', 'settings:write' in me['user']['permissions'])
"
```

**Expected result:** Role: admin, has users:write and settings:write

**Result:** [ ] Pass / [ ] Fail

---

### Test E2: Customer Permissions Are Restricted

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'customer@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access_token']

req2 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization': f'Bearer {token}'})
resp2 = urllib.request.urlopen(req2)
me = json.loads(resp2.read().decode())
perms = me['user']['permissions']
print('Role:', me['user']['role'])
print('Permissions:', perms)
print('Has products:read:', 'products:read' in perms)
print('Has products:write:', 'products:write' in perms)
print('Has users:write:', 'users:write' in perms)
"
```

**Expected result:**
- Role: customer
- Has products:read: True
- Has products:write: False
- Has users:write: False

**Result:** [ ] Pass / [ ] Fail

---

### Test E3: Role Hierarchy (admin > merchant > customer)

**Command:**
```bash
python3 -c "
import urllib.request, json, base64
roles = {}
for email in ['admin@example.com','merchant@example.com','customer@example.com']:
    data = json.dumps({'email': email, 'password':'Test1234!'}).encode()
    req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
    resp = urllib.request.urlopen(req)
    token = json.loads(resp.read().decode())['access_token']
    p = token.split('.')[1] + '=='
    claims = json.loads(base64.urlsafe_b64decode(p))
    roles[claims['role']] = len(claims['permissions'])
    print(f'{claims[\"role\"]}: {len(claims[\"permissions\"])} permissions')

print('admin > merchant:', roles['admin'] > roles['merchant'])
print('merchant > customer:', roles['merchant'] > roles['customer'])
"
```

**Expected result:**
- admin: 10 permissions, merchant: 5, customer: 2
- admin > merchant: True, merchant > customer: True

**Result:** [ ] Pass / [ ] Fail

---

## Section F: M2M API Key Auth

### Test F1: Create API Key

**Command:**
```bash
python3 -c "
import urllib.request, json

# Login as admin
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
body = json.loads(resp.read().decode())
token = body['access_token']
csrf = body['csrf_token']

# Create API key
key_data = json.dumps({'name':'test-key','scopes':['products:read','orders:read'],'rate_limit':100}).encode()
req2 = urllib.request.Request('http://localhost/api/auth/api-keys', data=key_data,
    headers={'Content-Type':'application/json','Authorization':f'Bearer {token}','X-CSRF-Token':csrf})
resp2 = urllib.request.urlopen(req2)
key = json.loads(resp2.read().decode())
print('Status: 201')
print('Has raw_key:', bool(key.get('raw_key')))
print('Key starts with ba_:', key['raw_key'].startswith('ba_'))
print('Name:', key['name'])
print('Scopes:', key['scopes'])
"
```

**Expected result:**
- Status: 201
- raw_key starts with `ba_`
- Name: test-key, Scopes: ['products:read', 'orders:read']

**Result:** [ ] Pass / [ ] Fail

---

### Test F2: API Key Auth on Protected Route

**Command:**
```bash
python3 -c "
import urllib.request, json

# Login and create key (from F1)
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
body = json.loads(resp.read().decode())
token, csrf = body['access_token'], body['csrf_token']

key_data = json.dumps({'name':'test-key-2','scopes':['products:read'],'rate_limit':100}).encode()
req2 = urllib.request.Request('http://localhost/api/auth/api-keys', data=key_data,
    headers={'Content-Type':'application/json','Authorization':f'Bearer {token}','X-CSRF-Token':csrf})
resp2 = urllib.request.urlopen(req2)
raw_key = json.loads(resp2.read().decode())['raw_key']

# Use API key on /me
req3 = urllib.request.Request('http://localhost/api/auth/me', headers={'Authorization':f'Bearer {raw_key}'})
resp3 = urllib.request.urlopen(req3)
me = json.loads(resp3.read().decode())
print('API key auth works:', me['auth_type'] == 'api_key')
print('Email:', me['user']['email'])
"
```

**Expected result:**
- API key auth works: True (auth_type: api_key)
- Email: admin@example.com

**Result:** [ ] Pass / [ ] Fail

---

### Test F3: List and Delete API Keys

**Command:**
```bash
python3 -c "
import urllib.request, json

# Login
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
body = json.loads(resp.read().decode())
token, csrf = body['access_token'], body['csrf_token']

# List keys
req2 = urllib.request.Request('http://localhost/api/auth/api-keys', headers={'Authorization':f'Bearer {token}'})
resp2 = urllib.request.urlopen(req2)
keys = json.loads(resp2.read().decode())
print(f'API keys found: {len(keys)}')
if keys:
    key_id = keys[0]['id']
    print(f'First key: {keys[0][\"name\"]} (active: {keys[0][\"is_active\"]})')

    # Delete key
    req3 = urllib.request.Request(f'http://localhost/api/auth/api-keys/{key_id}', method='DELETE',
        headers={'Authorization':f'Bearer {token}','X-CSRF-Token':csrf})
    resp3 = urllib.request.urlopen(req3)
    print('Delete response:', json.loads(resp3.read().decode())['message'])
"
```

**Expected result:**
- Lists API keys (count > 0 if F1/F2 ran)
- Delete succeeds

**Result:** [ ] Pass / [ ] Fail

---

## Section G: Password Reset Flow

### Test G1: Forgot Password (Token Generation)

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'customer@example.com'}).encode()
req = urllib.request.Request('http://localhost/api/auth/forgot-password', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
body = json.loads(resp.read().decode())
print('Response:', body['message'])
print('Matches expected:', 'If an account exists' in body['message'])
"
```

**Expected result:** Message: "If an account exists, a reset link has been sent" (no email enumeration)

**Verification:** Check FastAPI logs for the reset token:
```bash
docker compose logs fastapi 2>&1 | grep "Password reset token" | tail -1
```

**Result:** [ ] Pass / [ ] Fail

---

### Test G2: Reset Password with Valid Token

**Command:**
```bash
python3 -c "
import urllib.request, json

# Trigger forgot password
data = json.dumps({'email':'customer@example.com'}).encode()
req = urllib.request.Request('http://localhost/api/auth/forgot-password', data=data, headers={'Content-Type':'application/json'})
urllib.request.urlopen(req)
print('Reset token generated — check docker compose logs fastapi for token')
print('Then run:')
print()
print('python3 -c \"')
print('import urllib.request, json')
print('data = json.dumps({\\\"token\\\":\\\"<PASTE_TOKEN_HERE>\\\",\\\"new_password\\\":\\\"NewPass1234!\\\"}).encode()')
print('req = urllib.request.Request(\\\"http://localhost/api/auth/reset-password\\\", data=data, headers={\\\"Content-Type\\\":\\\"application/json\\\"})')
print('resp = urllib.request.urlopen(req)')
print('print(json.loads(resp.read().decode()))')
print('\"')
"
```

**Steps:**
1. Run the command above to generate reset token
2. Run `docker compose logs fastapi 2>&1 | grep "Password reset token" | tail -1` to get the token
3. Run the reset command with the token
4. Login with new password to verify

**Expected result:**
- Reset succeeds: "Password reset successfully"
- All existing sessions invalidated
- Login works with new password

**Result:** [ ] Pass / [ ] Fail

---

### Test G3: Reset Password with Invalid/Expired Token

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'token':'invalid-token-here','new_password':'NewPass1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/reset-password', data=data, headers={'Content-Type':'application/json'})
try:
    urllib.request.urlopen(req)
    print('FAIL: Should have returned 400')
except urllib.error.HTTPError as e:
    print(f'Status: {e.code} (expected 400)')
    body = json.loads(e.read().decode())
    print(f'Message: {body.get(\"detail\", {}).get(\"message\")}')
"
```

**Expected result:** Status: 400, Message: "Invalid or expired reset token"

**Result:** [ ] Pass / [ ] Fail

---

## Section H: Rate Limiting

### Test H1: Rate Limit Returns 429

**Command:**
```bash
python3 -c "
import urllib.request, json

hit_429 = False
for i in range(150):
    data = json.dumps({'email':'fake@example.com','password':'wrong'}).encode()
    req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
    try:
        urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if e.code == 429:
            print(f'Rate limited at request {i+1}')
            retry_after = e.headers.get('Retry-After')
            print(f'Retry-After header: {retry_after}')
            hit_429 = True
            break
        # 401 is expected for wrong password, continue
if not hit_429:
    print('WARNING: Did not hit rate limit in 150 requests')
"
```

**Expected result:**
- Rate limit hit (429) before 150 requests
- Retry-After header present

**Result:** [ ] Pass / [ ] Fail

---

## Section I: CSRF Protection

### Test I1: POST Without CSRF Token Rejected

**Command:**
```bash
python3 -c "
import urllib.request, json

# Login
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())['access_token']

# Try creating API key WITHOUT CSRF token
key_data = json.dumps({'name':'no-csrf','scopes':[],'rate_limit':100}).encode()
req2 = urllib.request.Request('http://localhost/api/auth/api-keys', data=key_data,
    headers={'Content-Type':'application/json','Authorization':f'Bearer {token}'})
try:
    urllib.request.urlopen(req2)
    print('FAIL: Should have been rejected without CSRF')
except urllib.error.HTTPError as e:
    print(f'Status: {e.code} (expected 403)')
    body = json.loads(e.read().decode())
    print(f'Message: {body.get(\"detail\", {}).get(\"message\")}')
"
```

**Expected result:** Status: 403, Message: "Missing CSRF token"

**Result:** [ ] Pass / [ ] Fail

---

### Test I2: POST With Valid CSRF Token Accepted

**Command:**
```bash
python3 -c "
import urllib.request, json

# Login (get both access token and CSRF token)
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
resp = urllib.request.urlopen(req)
body = json.loads(resp.read().decode())
token, csrf = body['access_token'], body['csrf_token']

# Create API key WITH CSRF token
key_data = json.dumps({'name':'csrf-test','scopes':[],'rate_limit':100}).encode()
req2 = urllib.request.Request('http://localhost/api/auth/api-keys', data=key_data,
    headers={'Content-Type':'application/json','Authorization':f'Bearer {token}','X-CSRF-Token':csrf})
resp2 = urllib.request.urlopen(req2)
print(f'Status: {resp2.getcode()} (expected 201)')
"
```

**Expected result:** Status: 201

**Result:** [ ] Pass / [ ] Fail

---

## Section J: Audit Logging

### Test J1: Login Creates Audit Entry

**Command:**
```bash
python3 -c "
import urllib.request, json
data = json.dumps({'email':'admin@example.com','password':'Test1234!'}).encode()
req = urllib.request.Request('http://localhost/api/auth/login', data=data, headers={'Content-Type':'application/json'})
urllib.request.urlopen(req)
print('Login done')
"
```

**Verification:**
```bash
docker exec boilerplate-app-postgres-1 psql -U boilerplate -d boilerplate_db -c \
  "SELECT action, resource, ip_address, created_at FROM core.audit_log WHERE action = 'user.login' ORDER BY created_at DESC LIMIT 3;"
```

**Expected result:** Recent `user.login` entry with IP address and timestamp

**Result:** [ ] Pass / [ ] Fail

---

### Test J2: Registration Creates Audit Entry

**Verification:**
```bash
docker exec boilerplate-app-postgres-1 psql -U boilerplate -d boilerplate_db -c \
  "SELECT action, resource, ip_address, created_at FROM core.audit_log WHERE action = 'user.register' ORDER BY created_at DESC LIMIT 3;"
```

**Expected result:** `user.register` entries present

**Result:** [ ] Pass / [ ] Fail

---

### Test J3: Password Reset Creates Audit Entry

**Verification (run after Test G2):**
```bash
docker exec boilerplate-app-postgres-1 psql -U boilerplate -d boilerplate_db -c \
  "SELECT action, resource, ip_address, created_at FROM core.audit_log WHERE action = 'user.password_reset' ORDER BY created_at DESC LIMIT 3;"
```

**Expected result:** `user.password_reset` entry present

**Result:** [ ] Pass / [ ] Fail

---

## Section K: Browser Tests (Manual)

Open `http://localhost` in a browser (Edge/Chrome on Windows).

---

### Scenario K1: Happy Path — Register and Access Protected Page

1. Navigate to `http://localhost/auth/register`
2. Fill in: email (new unique email), password (`Test1234!`), first name, last name
3. Observe password strength indicator updates as you type
4. Click Register
5. Verify auto-redirect to `/protected`
6. Verify `/protected` displays: email, role (customer), session info, permissions
7. Verify "This page proves auth works" banner visible

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K2: Happy Path — Login with Seed User

1. Navigate to `http://localhost/auth/login`
2. Enter: `admin@example.com` / `Test1234!`
3. Click Login
4. Verify redirect to `/protected`
5. Verify role shows "admin" and all admin permissions listed

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K3: Logout Flow

1. From `/protected`, click Logout in the nav bar
2. Verify redirect to `/auth/login`
3. Navigate directly to `http://localhost/protected`
4. Verify redirect back to `/auth/login` (not authenticated)

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K4: Error Handling — Invalid Credentials

1. Navigate to `http://localhost/auth/login`
2. Enter wrong password
3. Verify error message displayed on the page (not a raw JSON dump)
4. Enter non-existent email
5. Verify same error message style (no email enumeration leak)

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K5: Error Handling — Duplicate Registration

1. Navigate to `http://localhost/auth/register`
2. Register with `admin@example.com` (already exists)
3. Verify error message about duplicate email displayed

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K6: Forgot Password Flow

1. From `/auth/login`, click "Forgot password?" link
2. Verify navigates to `/auth/forgot-password`
3. Enter `customer@example.com`, submit
4. Verify success message: "If an account exists, a reset link has been sent"
5. Check `docker compose logs fastapi` for the reset token
6. Navigate to `/auth/reset-password?token=<TOKEN>`
7. Enter new password, submit
8. Verify success, login with new password works

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K7: Protected Page Redirect (Unauthenticated)

1. Clear browser cookies/storage (or open incognito)
2. Navigate directly to `http://localhost/protected`
3. Verify redirect to `/auth/login`
4. Login with valid credentials
5. Verify redirect back to `/protected`

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K8: OAuth Buttons Present (Visual Only)

1. Navigate to `http://localhost/auth/login`
2. Verify OAuth provider buttons visible (Google, GitHub, Microsoft, Apple)
3. Click any OAuth button
4. Verify redirect occurs (will 404 at provider since no credentials configured — this is expected)

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K9: Navigation Bar State

1. While logged out: verify nav shows Login / Register links
2. Login with any user
3. Verify nav shows: user email, role badge, Logout button
4. Logout
5. Verify nav returns to logged-out state

**Result:** [ ] Pass / [ ] Fail

---

### Scenario K10: Silent Token Refresh

1. Login as any user
2. Open browser DevTools → Network tab
3. Wait or manually shorten JWT_EXPIRY for testing
4. Make an action that triggers an API call
5. Look for a `POST /api/auth/refresh` call in the network tab
6. Verify user stays on the page (no redirect to login)

**Result:** [ ] Pass / [ ] Fail

---

## Section L: Re-run Checklist

### Quick Validation (5 minutes)

- [ ] `docker compose ps` — all 5 services healthy
- [ ] Login with seed user works (Test A4)
- [ ] /me returns full context including auth_time, amr, consent (Test A7)
- [ ] JWT contains all 13 required claims (Test C1)
- [ ] Browser: login and /protected work (Scenario K2)

### Full Regression (30 minutes)

- [ ] Registration: new user, duplicate, weak password (Tests A1-A3)
- [ ] Login: valid, wrong password, non-existent (Tests A4-A6)
- [ ] /me: with and without token (Tests A7-A8)
- [ ] Token refresh and rotation (Tests B1-B3)
- [ ] JWT claims: all present, refresh preserves auth_time, iss/aud validation (Tests C1-C3)
- [ ] Session: logout invalidates, concurrent limit, count (Tests D1-D3)
- [ ] RBAC: admin vs customer permissions, role hierarchy (Tests E1-E3)
- [ ] API keys: create, use, list, delete (Tests F1-F3)
- [ ] Password reset: generate, use, invalid token (Tests G1-G3)
- [ ] Rate limiting: 429 returned (Test H1)
- [ ] CSRF: rejected without, accepted with (Tests I1-I2)
- [ ] Audit log: login, register, password reset entries (Tests J1-J3)
- [ ] Browser: all K scenarios (K1-K10)

### After Auth Changes

- [ ] Run full regression above
- [ ] Verify JWT claims structure matches docs (Test C1)
- [ ] Verify token refresh preserves auth_time/amr (Test C2)
- [ ] Verify all 3 seed user roles have correct permissions (Test E3)
- [ ] Update this test plan with new tests if claims or endpoints changed

---

## Section M: Admin User Management (Post-Build 2026-02-17)

### Test M1: List Users (Paginated)

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| M1 | List all users | `GET /api/auth/admin/users` with admin token | 200 with `{ items: [...], total: 3, page: 1, page_size: 20 }` |
| M2 | Search by email | `GET /api/auth/admin/users?search=admin` | `total: 1`, item email matches "admin@example.com" |
| M3 | Search by name | `GET /api/auth/admin/users?search=Customer` | `total: 1`, item matches customer user |
| M4 | Filter by role | `GET /api/auth/admin/users?role=customer` | `total: 1`, only customer role returned |
| M5 | Filter by status (active) | `GET /api/auth/admin/users?status=active` | Only `is_active=true` and `deleted_at=null` users |
| M6 | Filter by status (deleted) | `GET /api/auth/admin/users?status=deleted` | Only users with `deleted_at` set |
| M7 | Pagination | `GET /api/auth/admin/users?page=1&page_size=1` | `items` has 1 entry, `total: 3` |

### Test M2: User Detail

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| M8 | Get user detail | `GET /api/auth/admin/users/{user_id}` | 200 with user fields + `is_merchant: bool` |
| M9 | Non-existent user | `GET /api/auth/admin/users/00000000-0000-0000-0000-000000000000` | 404 |
| M10 | is_merchant flag (non-merchant) | Get detail for admin user | `is_merchant: false` |

### Test M3: Role Change

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| M11 | Change customer to admin | `PUT /api/auth/admin/users/{customer_id}/role` with `{"role": "admin"}` | 200, `"Role updated to admin"` |
| M12 | Revert to customer | `PUT /api/auth/admin/users/{customer_id}/role` with `{"role": "customer"}` | 200, role reverted |
| M13 | Invalid role rejected | `PUT .../role` with `{"role": "bogus"}` | 400, `"Role 'bogus' does not exist"` |
| M14 | Self-demotion blocked | Admin changes own role | 400, `"Cannot change your own role"` |
| M15 | Merchant role change blocked | Change role for user with merchant_account | 400, `"Cannot change role for merchant accounts"` |
| M16 | Sessions revoked on role change | Login as customer, admin changes role, old token used | Old token returns 401 |

### Test M4: Activate/Deactivate

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| M17 | Deactivate user | `PUT .../status` with `{"is_active": false}` | 200, `"User deactivated"` |
| M18 | Reactivate user | `PUT .../status` with `{"is_active": true}` | 200, `"User activated"` |
| M19 | Self-deactivation blocked | Admin deactivates self | 400, `"Cannot change your own status"` |
| M20 | Sessions revoked on deactivation | Deactivate user, check their sessions | Sessions cleared from Redis |

### Test M5: Soft Delete

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| M21 | Soft delete user | `DELETE /api/auth/admin/users/{customer_id}` | 200, `"User deleted"` |
| M22 | Deleted user has deleted_at set | `GET .../users/{id}` after delete | `deleted_at` is non-null, `is_active: false` |
| M23 | Double delete blocked | Delete same user again | 400, `"User is already deleted"` |
| M24 | Self-delete blocked | Admin deletes self | 400, `"Cannot delete yourself"` |
| M25 | Sessions revoked on delete | Delete user, check sessions | Sessions cleared from Redis |

### Test M6: Authorization

| # | Test | Method | Expected Result |
|---|------|--------|-----------------|
| M26 | Requires admin role | `GET /api/auth/admin/users` with customer token | 403 |
| M27 | Requires authentication | `GET /api/auth/admin/users` with no token | 401 |

---

## Updated Summary (with Post-Build Tests)

| Section | Tests |
|---------|-------|
| A: Core Auth | 8 |
| B: Token Refresh | 3 |
| C: JWT Claims | 3 |
| D: Session Management | 3 |
| E: RBAC & Permissions | 3 |
| F: M2M API Key Auth | 3 |
| G: Password Reset | 3 |
| H: Rate Limiting | 1 |
| I: CSRF Protection | 2 |
| J: Audit Logging | 3 |
| K: Browser Tests | 10 |
| M: Admin User Management (post-build) | 27 |
| **Total** | **69** |

Original 42 tests. 27 new tests added for admin user management endpoints (2026-02-17).

---

## Test Execution Log

| Date | Executor | Scope | Result | Notes |
|------|----------|-------|--------|-------|
| — | — | — | — | — |
