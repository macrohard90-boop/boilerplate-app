# Phase 2: Database Schema & Migration System — Test Plan

**Phase:** 2 — Database Schema & Migration System
**Created:** 2026-02-15
**Last executed:** 2026-02-15
**Status:** All tests passing

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Section A: Migration System Tests](#section-a-migration-system-tests)
3. [Section B: Schema & Data Integrity Tests](#section-b-schema--data-integrity-tests)
4. [Section C: Health Endpoint Tests](#section-c-health-endpoint-tests)
5. [Section D: Manual Database Access](#section-d-manual-database-access)
6. [Section E: Re-run Checklist](#section-e-re-run-checklist)

---

## 1. Prerequisites

### Environment

- Docker Compose stack running: `docker compose up -d`
- All 5 services healthy: postgres, redis, fastapi, nextjs, nginx
- Verify with: `docker compose ps`

### Connection Details

| Service | Internal Host | Port | Credentials |
|---------|--------------|------|-------------|
| PostgreSQL | postgres | 5432 | User: `boilerplate`, Password: `change-me`, DB: `boilerplate_db` |
| Redis | redis | 6379 | No auth |
| FastAPI | fastapi | 8000 | — |
| Next.js | nextjs | 3000 | — |
| Nginx | nginx | 80/443 | — |

### Running Commands Against the Database

Scripts (`migrate.py`, `seed.py`) are not baked into the Docker image. Run them via volume mount:

```bash
docker run --rm \
  --network boilerplate-app_app-network \
  -v /home/rootuser/projects/boilerplate-app:/app \
  -w /app \
  -e DATABASE_URL=postgresql+asyncpg://boilerplate:change-me@postgres:5432/boilerplate_db \
  -e APP_TEMPLATE=ecommerce \
  -e ENABLE_TRACKING=true \
  python:3.11-slim \
  bash -c "pip install -q psycopg2-binary && python scripts/migrate.py <command>"
```

Shorthand for `psql` access:

```bash
docker exec boilerplate-app-postgres-1 psql -U boilerplate -d boilerplate_db -c "<SQL>"
```

---

## Section A: Migration System Tests

### Test A1: Migrate Up (Full)

**Command:**
```bash
python scripts/migrate.py up
```

**Expected result:**
- 5 migrations applied in order: 000, 001, 002 (ecommerce), 003, 004
- No errors
- Output shows each migration being applied

**Verification:**
```bash
python scripts/migrate.py status
```
All 5 migrations should show as applied with timestamps.

**Result:** [ ] Pass / [ ] Fail

---

### Test A2: Migrate Status

**Command:**
```bash
python scripts/migrate.py status
```

**Expected result:**
- Lists all 5 applied migrations with version numbers and applied_at timestamps
- Versions: 000, 001, 002, 003, 004

**Result:** [ ] Pass / [ ] Fail

---

### Test A3: Partial Rollback (down --to)

**Command:**
```bash
python scripts/migrate.py down --to 001
```

**Expected result:**
- Rolls back migrations 004, 003, 002 (in reverse order)
- Keeps migrations 000 and 001
- `migrate status` shows only 000 and 001 as applied

**Verification:**
```sql
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('ecommerce', 'gdpr', 'analytics');
```
Should return `0` (those schemas' tables are dropped).

```sql
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'core';
```
Should return `7` (core tables remain).

**Result:** [ ] Pass / [ ] Fail

---

### Test A4: Full Rollback (down)

**Command:**
```bash
python scripts/migrate.py down
```

**Expected result:**
- All migrations rolled back
- `migrate status` shows no applied migrations
- All schemas empty

**Verification:**
```sql
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema IN ('core', 'ecommerce', 'saas', 'gdpr', 'analytics');
```
Should return `0`.

**Result:** [ ] Pass / [ ] Fail

---

### Test A5: Re-apply After Full Rollback

**Command:**
```bash
python scripts/migrate.py up
```

**Expected result:**
- All 5 migrations re-applied cleanly
- No errors about existing tables or constraints

**Result:** [ ] Pass / [ ] Fail

---

## Section B: Schema & Data Integrity Tests

### Test B1: PG Schema Namespaces

**Command:**
```sql
SELECT schema_name FROM information_schema.schemata
WHERE schema_name IN ('core', 'ecommerce', 'saas', 'gdpr', 'analytics')
ORDER BY schema_name;
```

**Expected result:** 4 schemas present (ecommerce template): `analytics`, `core`, `ecommerce`, `gdpr`

**Result:** [ ] Pass / [ ] Fail

---

### Test B2: Table Counts Per Schema

**Command:**
```sql
SELECT table_schema, COUNT(*) AS table_count
FROM information_schema.tables
WHERE table_schema IN ('core', 'ecommerce', 'gdpr', 'analytics')
GROUP BY table_schema
ORDER BY table_schema;
```

**Expected result:**

| Schema | Count |
|--------|-------|
| analytics | 6 |
| core | 7 |
| ecommerce | 21 |
| gdpr | 7 |
| **Total** | **41** |

**Result:** [ ] Pass / [ ] Fail

---

### Test B3: Index Count

**Command:**
```sql
SELECT schemaname, COUNT(*) AS index_count
FROM pg_indexes
WHERE schemaname IN ('core', 'ecommerce', 'gdpr', 'analytics')
GROUP BY schemaname
ORDER BY schemaname;
```

**Expected result:** 174 total indexes across all schemas.

**Result:** [ ] Pass / [ ] Fail

---

### Test B4: Seed Data — Initial Load

**Command:**
```bash
python scripts/seed.py
```

**Expected result:** No errors. Verify data populated:

```sql
SELECT COUNT(*) FROM core.roles;          -- Expected: 3
SELECT COUNT(*) FROM core.users;          -- Expected: 3
SELECT COUNT(*) FROM core.permissions;    -- Expected: 17
SELECT COUNT(*) FROM ecommerce.products;  -- Expected: 10
SELECT COUNT(*) FROM ecommerce.categories; -- Expected: 5
```

**Result:** [ ] Pass / [ ] Fail

---

### Test B5: Seed Data — Reset and Re-seed

**Command:**
```bash
python scripts/seed.py --reset
```

**Expected result:**
- Tables truncated (CASCADE)
- Data re-inserted
- Same counts as Test B4

**Result:** [ ] Pass / [ ] Fail

---

### Test B6: updated_at Trigger

**Command:**
```sql
-- Record original timestamp
SELECT email, updated_at FROM core.users WHERE email = 'admin@example.com';

-- Wait and update
SELECT pg_sleep(1);
UPDATE core.users SET first_name = 'Trigger Test' WHERE email = 'admin@example.com';

-- Verify timestamp changed
SELECT email, first_name, updated_at FROM core.users WHERE email = 'admin@example.com';
```

**Expected result:** `updated_at` value is newer after the UPDATE (trigger fired automatically).

**Result:** [ ] Pass / [ ] Fail

---

### Test B7: CHECK Constraints — Cart Status

**Command:**
```sql
INSERT INTO ecommerce.cart (user_id, status)
VALUES ((SELECT id FROM core.users LIMIT 1), 'invalid_status');
```

**Expected result:** Error — `violates check constraint "cart_status_check"`

Valid values: `active`, `abandoned`, `recovered`, `converted`, `expired`

**Result:** [ ] Pass / [ ] Fail

---

### Test B8: CHECK Constraints — Consent Type

**Command:**
```sql
INSERT INTO gdpr.consent_records (user_id, consent_type, granted)
VALUES ((SELECT id FROM core.users LIMIT 1), 'invalid_consent', true);
```

**Expected result:** Error — `violates check constraint "consent_records_consent_type_check"`

Valid values: `marketing_email`, `transactional_email`, `third_party_sharing`, `analytics`, `cookies_analytics`, `cookies_marketing`

**Result:** [ ] Pass / [ ] Fail

---

### Test B9: CHECK Constraints — RFM Segment

**Command:**
```sql
INSERT INTO ecommerce.customer_metrics (user_id, rfm_segment)
VALUES ((SELECT id FROM core.users LIMIT 1), 'invalid_segment');
```

**Expected result:** Error — `violates check constraint "customer_metrics_rfm_segment_check"`

**Result:** [ ] Pass / [ ] Fail

---

### Test B10: Soft-Delete Columns

**Command:**
```sql
SELECT table_schema, table_name
FROM information_schema.columns
WHERE column_name = 'deleted_at'
ORDER BY table_schema, table_name;
```

**Expected result:** `deleted_at` present on `core.users` and `ecommerce.products`.

**Result:** [ ] Pass / [ ] Fail

---

### Test B11: Monetary Columns — INT Cents + Currency

**Command (verify currency columns):**
```sql
SELECT table_schema, table_name, column_name, data_type, character_maximum_length
FROM information_schema.columns
WHERE column_name = 'currency'
ORDER BY table_schema, table_name;
```

**Expected result:** All `currency` columns are `character(3)` (CHAR(3)).

**Command (verify money columns are integer):**
```sql
SELECT table_schema, table_name, column_name, data_type
FROM information_schema.columns
WHERE table_schema IN ('ecommerce', 'saas')
  AND (column_name LIKE '%price%' OR column_name LIKE '%amount%'
       OR column_name LIKE '%total%' OR column_name = 'subtotal'
       OR column_name = 'total_spent')
ORDER BY table_schema, table_name;
```

**Expected result:** All monetary columns are `integer` type.

**Result:** [ ] Pass / [ ] Fail

---

## Section C: Health Endpoint Tests

### Test C1: Combined Health Check

**Command (from inside Docker network):**
```bash
docker exec boilerplate-app-fastapi-1 python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health').read().decode())"
```

**Expected result:**
```json
{"status":"ok","services":{"redis":"ok","db":"ok"}}
```

**Result:** [ ] Pass / [ ] Fail

---

### Test C2: Database Health Check

**Command:**
```bash
docker exec boilerplate-app-fastapi-1 python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health/db').read().decode())"
```

**Expected result:**
```json
{"status":"ok"}
```

**Result:** [ ] Pass / [ ] Fail

---

### Test C3: Redis Health Check

**Command:**
```bash
docker exec boilerplate-app-fastapi-1 python -c \
  "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/api/health/redis').read().decode())"
```

**Expected result:**
```json
{"status":"ok"}
```

**Result:** [ ] Pass / [ ] Fail

---

## Section D: Manual Database Access

### D1: Access via WSL2 (Linux Terminal)

```bash
docker exec -it boilerplate-app-postgres-1 psql -U boilerplate -d boilerplate_db
```

No password required (local socket auth inside the container).

---

### D2: Access via Docker Desktop (Windows)

1. Open **Docker Desktop** on Windows
2. Go to **Containers** view
3. Click on **boilerplate-app-postgres-1**
4. Click the **Terminal** tab
5. Run:
   ```
   psql -U boilerplate -d boilerplate_db
   ```

No password required inside the container.

---

### D3: Access via PowerShell (Windows)

```powershell
docker exec -it boilerplate-app-postgres-1 psql -U boilerplate -d boilerplate_db
```

---

### D4: Access Frontend via Browser (Windows)

Nginx exposes port 80. Open in any Windows browser:

```
http://localhost
```

- `/` routes to Next.js frontend
- `/api/*` routes to FastAPI backend

Alternatively, in Docker Desktop click the **Open in browser** icon next to the **nginx** container.

---

### D5: Useful psql Commands

| Command | Description |
|---------|-------------|
| `\dn` | List all schemas |
| `\dt core.*` | List tables in core schema |
| `\dt ecommerce.*` | List tables in ecommerce schema |
| `\dt gdpr.*` | List tables in gdpr schema |
| `\dt analytics.*` | List tables in analytics schema |
| `\d core.users` | Show column details for a table |
| `\di` | List all indexes |
| `\q` | Quit psql |

### D6: Sample Queries

```sql
-- List all users
SELECT email, first_name, is_active FROM core.users;

-- List products with prices (convert cents to dollars)
SELECT name, base_price / 100.0 AS price_dollars, currency, is_active
FROM ecommerce.products LIMIT 5;

-- User count per role
SELECT r.name AS role, COUNT(u.id) AS user_count
FROM core.roles r
LEFT JOIN core.users u ON u.role_id = r.id
GROUP BY r.name;
```

---

## Section E: Re-run Checklist

Use this checklist when re-running tests after schema changes, migration updates, or seed data modifications.

### Quick Validation (5 minutes)

- [ ] `docker compose ps` — all 5 services healthy
- [ ] `migrate.py status` — expected migrations applied
- [ ] Health endpoints return ok (Tests C1-C3)
- [ ] Table counts match expected (Test B2)
- [ ] Seed data present (Test B4 counts)

### Full Regression (15 minutes)

- [ ] Full rollback: `migrate.py down` (Test A4)
- [ ] Re-apply: `migrate.py up` (Test A5)
- [ ] Verify schemas and table counts (Tests B1, B2)
- [ ] Verify index count (Test B3)
- [ ] Seed: `seed.py` (Test B4)
- [ ] Reset and re-seed: `seed.py --reset` (Test B5)
- [ ] Partial rollback: `migrate.py down --to 001` (Test A3)
- [ ] Re-apply: `migrate.py up` + `seed.py` (restore state)
- [ ] Trigger test (Test B6)
- [ ] CHECK constraint tests (Tests B7-B9)
- [ ] Health endpoints (Tests C1-C3)
- [ ] Monetary column verification (Test B11)

### After Schema Changes

- [ ] Run full regression above
- [ ] Compare table counts against this document — update if changed
- [ ] Compare index count — update if changed
- [ ] Verify new CHECK constraints reject invalid values
- [ ] Verify new tables have `updated_at` trigger (if applicable)
- [ ] Update this test plan with new tests for added tables/columns

---

## Test Execution Log

| Date | Executor | Scope | Result | Notes |
|------|----------|-------|--------|-------|
| 2026-02-15 | Claude Code | Full (A1-C3) | All 14 tests passed | Initial Phase 2 verification |
