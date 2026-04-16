# Cloud Deployment Log — Google Cloud Setup

> First cloud deployment of the boilerplate app.
> Started: 2026-04-16
> **Status: LIVE at http://34.30.88.59**

## VM Details
- **Provider:** Google Cloud (Compute Engine)
- **Instance:** `instance-20260416-162856`
- **Region:** us-central1
- **Machine:** e2-medium (2 vCPU, 1 shared core, 4GB RAM)
- **OS:** Debian GNU/Linux 12 (bookworm)
- **Disk:** 10GB boot (should have been 30GB — may need to expand later)
- **External IP:** 34.30.88.59
- **Firewall:** HTTP + HTTPS allowed
- **VM User:** adrian_radoi
- **Repo path on VM:** `/home/adrian_radoi/boilerplate-app`

## Step 1: VM Created
- [x] Created via Google Cloud Console
- [x] SSH access works (browser SSH button)

## Step 2: Docker Installed
- [x] `sudo apt update && sudo apt upgrade -y`
- [x] `curl -fsSL https://get.docker.com | sudo sh`
- [x] `sudo apt install -y docker-compose-plugin git`
- [x] `sudo usermod -aG docker $USER`
- [x] Logged out and back in
- [x] `docker ps` works without sudo
- Docker version: 29.4.0
- Docker Compose version: 5.1.3

## Step 3: Clone Repo
- [x] Create GitHub Personal Access Token (classic, repo scope)
- [x] `git clone https://github.com/macrohard90-boop/boilerplate-app.git`
- [x] `cd boilerplate-app`
- Note: Password field is invisible when pasting token — that's normal Linux behavior

## Step 4: Configure .env
- [x] Run `bash scripts/setup.sh` (domain=34.30.88.59, template=ecommerce)
- [x] APP_ENV=production, DEBUG=false
- [x] URLs point to http://34.30.88.59 (not https — no SSL)
- [x] INSTALL_CLI_ADVISOR=false
- [x] ENABLE_SEO_ADVISOR=false, ENABLE_GEO_ADVISOR=false
- [x] LOG_LEVEL=WARNING
- [ ] Stripe test keys (not yet configured)
- Used `sed` one-liner to batch-edit .env instead of nano (faster, less error-prone)

## Step 5: Build and Start
- [x] `docker compose build` — first build took ~3.5 minutes
- [x] `docker compose up -d` — all 5 containers started
- [x] `docker compose exec fastapi python scripts/migrate.py up` — 21 migrations applied
- [x] `docker compose exec fastapi python scripts/seed.py` — common + ecommerce seeds applied
- [x] All services healthy (postgres, redis, fastapi, nextjs, nginx)

## Step 6: Verify
- [x] `http://34.30.88.59` loads in browser
- [ ] `http://34.30.88.59/api/health` returns OK
- [ ] Can log in as admin@example.com / Admin1234!
- [ ] Products page loads
- [ ] Admin dashboard loads

## Step 7: Stripe Webhooks (Not yet)
- [ ] Add webhook endpoint in Stripe Dashboard
- [ ] Set STRIPE_WEBHOOK_SECRET in .env
- [ ] Test payment flow

## Issues & Solutions

### Issue 1: `scripts/migrate.py` not found in container
- **Cause:** `docker/backend.Dockerfile` only copied `backend/` and `modules/`, not `scripts/` or `migrations/`
- **Fix:** Added `COPY scripts/ /app/scripts/` and `COPY migrations/ /app/migrations/` to Dockerfile
- **Commit:** `2cd22b3`

### Issue 2: 14 migration files missing `-- UP` / `-- DOWN` markers
- **Cause:** Migration files 007-021 were created without the markers that `migrate.py` requires
- **Fix:** Added `-- UP` and `-- DOWN` markers with proper rollback SQL to all 14 files
- **Commit:** `712b08c`

### Issue 3: `seeds/` directory not found in container
- **Cause:** Same as Issue 1 — Dockerfile didn't copy `seeds/`
- **Fix:** Added `COPY seeds/ /app/seeds/` to Dockerfile
- **Commit:** `e285761`

### Issue 4: SSH browser tab — Ctrl+C/W intercepted by browser
- **Workaround:** Use Ctrl+Shift+C/V for copy/paste in browser SSH terminal. Ctrl+W closes the browser tab, not search in nano.

### Issue 5: Git clone directory disappeared
- **Cause:** `rm -rf boilerplate-app` was run to fix a partial clone, then commands were run from the deleted directory
- **Fix:** Re-cloned the repo

## How to Update the Cloud
When you make changes locally and push to GitHub:
```bash
# On the cloud VM (SSH in first):
cd /home/adrian_radoi/boilerplate-app
git pull   # enter GitHub username + token
docker compose build
docker compose up -d
```

---
