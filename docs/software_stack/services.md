# Services & Connectivity Reference

> Quick reference for all application services, their status expectations, and how to connect from the host machine (WSL2).

---

## Docker Compose Services

| Service | Image | Internal Port | Host Port | Health Check |
|---------|-------|---------------|-----------|--------------|
| PostgreSQL | postgres:16-alpine | 5432 | 5432 | `pg_isready -U boilerplate` |
| Redis | redis:7-alpine | 6379 | 6379 | `redis-cli ping` |
| FastAPI | python:3.11-slim | 8000 | — (via nginx) | `GET /api/health` |
| Next.js | node:20-alpine | 3000 | — (via nginx) | `wget http://localhost:3000/` |
| Nginx | nginx:alpine | 80, 443 | 80, 443 | `wget http://localhost/nginx-health` |
| PgBouncer | pgbouncer (commented out) | 6432 | — | Growth tier only |

---

## Host Access

### PostgreSQL

| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `5432` |
| User | `boilerplate` |
| Password | `change-me` |
| Database | `boilerplate_db` |
| Connection string (psql) | `postgresql://boilerplate:change-me@localhost:5432/boilerplate_db` |
| Connection string (async) | `postgresql+asyncpg://boilerplate:change-me@postgres:5432/boilerplate_db` |

```bash
# From WSL
psql -h localhost -U boilerplate -d boilerplate_db

# From Docker network (used by FastAPI)
psql -h postgres -U boilerplate -d boilerplate_db
```

### Redis

| Field | Value |
|-------|-------|
| Host | `localhost` |
| Port | `6379` |
| Password | *(none)* |
| Database | `0` |
| Connection string | `redis://localhost:6379/0` |
| Connection string (Docker network) | `redis://redis:6379/0` |

```bash
# From WSL
redis-cli -h localhost -p 6379

# From Docker network (used by FastAPI)
redis-cli -h redis -p 6379
```

### FastAPI Backend

| Field | Value |
|-------|-------|
| Direct (Docker network only) | `http://fastapi:8000` |
| Via Nginx (from host/browser) | `http://localhost/api/*` |
| Health check | `GET http://localhost/api/health` |
| API docs (Swagger) | `http://localhost/api/docs` |

### Next.js Frontend

| Field | Value |
|-------|-------|
| Direct (Docker network only) | `http://nextjs:3000` |
| Via Nginx (from host/browser) | `http://localhost/*` |

### Nginx Reverse Proxy

| Field | Value |
|-------|-------|
| HTTP | `http://localhost:80` |
| HTTPS | `https://localhost:443` |
| Routes `/api/*` to | `fastapi:8000` |
| Routes `/*` to | `nextjs:3000` |

---

## Auth Configuration

| Field | Value |
|-------|-------|
| JWT Secret | `change-me-to-a-long-random-string` |
| JWT Algorithm | `HS256` |
| Access token TTL | 900s (15 minutes) |
| Refresh token TTL | 604800s (7 days) |
| Max sessions per user | 5 |

---

## Seed Test Users

All users share the password: `Test1234!`

| Email | Role | Name |
|-------|------|------|
| `admin@example.com` | admin | Admin User |
| `merchant@example.com` | merchant | Merchant User |
| `customer@example.com` | customer | Customer User |

---

## Useful Commands

```bash
# Start all services
docker compose up -d

# Stop all services
docker compose down

# View logs
docker compose logs -f              # all services
docker compose logs -f fastapi      # single service

# Restart a single service
docker compose restart fastapi

# Run psql inside container
docker compose exec postgres psql -U boilerplate -d boilerplate_db

# Run redis-cli inside container
docker compose exec redis redis-cli

# Check service health
curl http://localhost/api/health
```
