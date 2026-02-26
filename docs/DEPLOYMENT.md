# Deployment Guide — New App in 24 Hours

## Overview

This document is the master checklist for deploying a new instance of this boilerplate application. Each deployment is a completely independent product (its own VPS, database, codebase, and domain). This is NOT a multi-tenant setup.

**Estimated total time:** 2-4 hours (excluding domain DNS propagation)

---

## Prerequisites

| Requirement | Notes |
|-------------|-------|
| VPS (Ubuntu 22.04+ / ARM64 or x86_64) | Any provider: DigitalOcean, Hetzner, Linode, etc. |
| Domain name | Pointed at your VPS IP |
| SSH access to VPS | Root or sudo user |
| Stripe account | Free to create, test mode for development |
| GitHub account | For OAuth (optional) |
| Google Cloud account | Free tier, for OAuth (optional) |
| Azure account | Free tier, for OAuth (optional) |

---

## Deployment Checklist

### Phase 1: VPS Setup (~20 minutes)

- [ ] **Provision VPS** — Ubuntu 22.04+, minimum 2GB RAM / 1 vCPU
- [ ] **SSH in** and update packages:
  ```bash
  apt update && apt upgrade -y
  ```
- [ ] **Install Docker + Docker Compose:**
  ```bash
  curl -fsSL https://get.docker.com | sh
  ```
- [ ] **Install Git:**
  ```bash
  apt install -y git
  ```
- [ ] **Clone the repository:**
  ```bash
  git clone git@github.com:YOUR_ORG/YOUR_REPO.git /opt/app
  cd /opt/app
  ```

### Phase 2: Environment Configuration (~15 minutes)

- [ ] **Copy the environment template:**
  ```bash
  cp .env.template .env
  ```
- [ ] **Generate secrets** (run each, paste into `.env`):
  ```bash
  # SECRET_KEY
  openssl rand -hex 32
  # JWT_SECRET
  openssl rand -hex 64
  # POSTGRES_PASSWORD
  openssl rand -hex 24
  ```
- [ ] **Update domain/URL settings in `.env`:**
  ```env
  DOMAIN=yourdomain.com
  FRONTEND_URL=https://yourdomain.com
  BACKEND_URL=https://yourdomain.com
  APP_NAME=Your App Name
  APP_ENV=production
  DEBUG=false
  ```
- [ ] **Set email provider** (replace placeholder):
  ```env
  EMAIL_PROVIDER=mailgun   # or sendgrid, postmark
  FROM_EMAIL=noreply@yourdomain.com
  FROM_NAME=Your App Name
  SMTP_HOST=smtp.mailgun.org
  SMTP_PORT=587
  SMTP_USER=your_smtp_user
  SMTP_PASSWORD=your_smtp_password
  ```

### Phase 3: Stripe Setup (~10 minutes)

> Detailed instructions: [docs/guides/stripe-setup.md](guides/stripe-setup.md)

- [ ] **Create Stripe account** at https://dashboard.stripe.com/register
- [ ] **Get API keys** from Developers > API keys (use **live keys** for production)
- [ ] **Add to `.env`:**
  ```env
  STRIPE_SECRET_KEY=sk_live_...
  STRIPE_PUBLISHABLE_KEY=pk_live_...
  ```
- [ ] **Set up webhook endpoint** in Stripe dashboard:
  - URL: `https://yourdomain.com/api/payments/webhook`
  - Events: `payment_intent.succeeded`, `payment_intent.payment_failed`, `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_succeeded`, `invoice.payment_failed`
- [ ] **Add webhook secret to `.env`:**
  ```env
  STRIPE_WEBHOOK_SECRET=whsec_...
  ```

### Phase 4: OAuth Providers (~10 minutes)

> Detailed instructions: [docs/guides/oauth-setup.md](guides/oauth-setup.md)

Providers auto-enable when their env vars are populated. Skip any you don't need.

**GitHub (~2 min):**
- [ ] Create OAuth App at https://github.com/settings/developers
- [ ] Callback URL: `https://yourdomain.com/api/auth/oauth/github/callback`
- [ ] Add `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET` to `.env`

**Google (~3 min):**
- [ ] Create OAuth credentials at https://console.cloud.google.com/apis/credentials
- [ ] Configure consent screen, add redirect URI: `https://yourdomain.com/api/auth/oauth/google/callback`
- [ ] Add `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` to `.env`
- [ ] Submit consent screen for verification (allows all users, not just test users)

**Microsoft (~5 min):**
- [ ] Register app at https://portal.azure.com/#view/Microsoft_AAD_RegisteredApplications
- [ ] Redirect URI: `https://yourdomain.com/api/auth/oauth/microsoft/callback`
- [ ] Add `MICROSOFT_CLIENT_ID` and `MICROSOFT_CLIENT_SECRET` to `.env`
- [ ] Set calendar reminder: Microsoft secrets expire (max 24 months)

**Apple (~10 min, optional — requires $99/year developer program):**
- [ ] See [docs/guides/oauth-setup.md](guides/oauth-setup.md) for full Apple setup steps
- [ ] Requires HTTPS callback URL (no localhost testing)

### Phase 5: SSL/TLS Setup (~10 minutes)

- [ ] **Install Certbot:**
  ```bash
  apt install -y certbot
  ```
- [ ] **Get SSL certificate:**
  ```bash
  certbot certonly --standalone -d yourdomain.com
  ```
- [ ] **Update Nginx config** to use SSL certificates (update `docker/nginx.conf` or mount certs)
- [ ] **Set up auto-renewal:**
  ```bash
  echo "0 3 * * * certbot renew --quiet --deploy-hook 'docker compose restart nginx'" | crontab -
  ```

### Phase 6: Launch (~5 minutes)

- [ ] **Build and start all services:**
  ```bash
  docker compose up -d --build
  ```
- [ ] **Run database migrations:**
  ```bash
  docker compose exec fastapi python -m alembic upgrade head
  ```
- [ ] **Seed initial data** (admin user, roles, default products):
  ```bash
  docker compose exec fastapi python -m backend.seed
  ```
- [ ] **Verify services are running:**
  ```bash
  docker compose ps
  ```

### Phase 7: Verification (~10 minutes)

- [ ] **Frontend loads:** Visit `https://yourdomain.com`
- [ ] **API responds:** `curl https://yourdomain.com/api/health`
- [ ] **Registration works:** Create a test account
- [ ] **Login works:** Log in with the test account
- [ ] **OAuth works:** Test each enabled provider's "Sign in with" button
- [ ] **Stripe works:** Check that registration created a Stripe customer (Stripe dashboard > Customers)
- [ ] **Checkout works:** Add item to cart, complete test purchase
- [ ] **Webhook works:** Check Stripe dashboard > Developers > Webhooks for successful deliveries
- [ ] **Admin panel works:** Log in as admin, verify dashboard loads

---

## Post-Launch

### Monitoring
- [ ] Set up log rotation for Docker logs
- [ ] Monitor disk space (Docker images accumulate)
- [ ] Set up uptime monitoring (UptimeRobot, Hetrix, etc.)

### Backups
- [ ] Set up PostgreSQL backups:
  ```bash
  # Daily backup cron
  0 2 * * * docker compose exec -T postgres pg_dump -U boilerplate boilerplate_db | gzip > /backups/db-$(date +\%Y\%m\%d).sql.gz
  ```
- [ ] Set up backup retention policy (keep last 30 days)

### Security
- [ ] Change default admin password
- [ ] Configure firewall (UFW): allow only 22, 80, 443
  ```bash
  ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw enable
  ```
- [ ] Disable root SSH login, use key-based auth only

---

## Environment Variable Reference

All configuration is in `.env`. See `.env.template` for the full list with comments.

| Category | Required Variables | Guide |
|----------|-------------------|-------|
| App | `SECRET_KEY`, `JWT_SECRET`, `APP_NAME`, `DOMAIN` | `.env.template` |
| Database | `POSTGRES_PASSWORD`, `DATABASE_URL` | `.env.template` |
| Stripe | `STRIPE_SECRET_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET` | [Stripe Setup](guides/stripe-setup.md) |
| OAuth | Provider-specific `CLIENT_ID` + `CLIENT_SECRET` | [OAuth Setup](guides/oauth-setup.md) |
| Email | `EMAIL_PROVIDER`, `FROM_EMAIL`, SMTP credentials | `.env.template` |

---

## Updating an Existing Deployment

```bash
cd /opt/app
git pull origin main
docker compose up -d --build
docker compose exec fastapi python -m alembic upgrade head
```

---

## Troubleshooting

| Issue | Check |
|-------|-------|
| Services won't start | `docker compose logs --tail 50` |
| Database connection error | Verify `POSTGRES_PASSWORD` matches in `.env`, check `docker compose logs postgres` |
| OAuth "redirect_uri_mismatch" | Callback URL in provider console must match `BACKEND_URL` exactly |
| Stripe webhook failures | Check webhook secret, verify URL is publicly accessible |
| SSL certificate issues | `certbot certificates` to check expiry, `certbot renew` to renew |
| 502 Bad Gateway | FastAPI may still be starting — wait 30s, check `docker compose logs fastapi` |
