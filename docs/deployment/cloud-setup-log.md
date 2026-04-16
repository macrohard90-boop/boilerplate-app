# Cloud Deployment Log — Google Cloud Setup

> First cloud deployment of the boilerplate app.
> Started: 2026-04-16

## VM Details
- **Provider:** Google Cloud (Compute Engine)
- **Instance:** `instance-20260416-162856`
- **Region:** us-central1
- **Machine:** e2-medium (2 vCPU, 1 shared core, 4GB RAM)
- **OS:** Debian GNU/Linux 12 (bookworm)
- **Disk:** 10GB boot (should have been 30GB — may need to expand later)
- **External IP:** 34.30.88.59
- **Firewall:** HTTP + HTTPS allowed

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
- [ ] Create GitHub Personal Access Token (repo scope)
- [ ] `git clone https://github.com/macrohard90-boop/boilerplate-app.git`
- [ ] `cd boilerplate-app`

## Step 4: Configure .env
- [ ] Run `bash scripts/setup.sh` (enter IP as domain, choose ecommerce template)
- [ ] Verify APP_ENV=production, DEBUG=false
- [ ] Verify URLs point to 34.30.88.59
- [ ] Set INSTALL_CLI_ADVISOR=false
- [ ] Disable SEO/GEO advisor (no Claude auth on cloud)
- [ ] Add Stripe test keys (if available)

## Step 5: Build and Start
- [ ] `docker compose build` (first build, expect ~5-10 min)
- [ ] `docker compose up -d`
- [ ] `docker compose exec fastapi python scripts/migrate.py up`
- [ ] `docker compose exec fastapi python scripts/seed.py`
- [ ] `docker compose ps` — all services healthy

## Step 6: Verify
- [ ] `http://34.30.88.59` loads in browser
- [ ] `http://34.30.88.59/api/health` returns OK
- [ ] Can log in as admin@example.com / Admin1234!
- [ ] Products page loads
- [ ] Admin dashboard loads

## Step 7: Stripe Webhooks (Optional — do later)
- [ ] Add webhook endpoint in Stripe Dashboard
- [ ] Set STRIPE_WEBHOOK_SECRET in .env
- [ ] Test payment flow

## Issues & Solutions

*(Documenting problems and fixes as they come up)*

---
