# Multi-Domain, Multi-Locale Feasibility Study

**Date:** 2026-02-28 (initial), 2026-03-02 (deep dive)
**Status:** Research complete, implementation deferred
**Audience:** App owner / deployer

---

## Scenario

Purchase multiple domains for the same brand:
- `.com` — English
- `.ca` — English + French
- `.es` — Spanish

All domains interlinked, sharing the same product catalog, admin panel, and user base.

---

## How Multi-Domain Physically Works

### What happens when someone types `example.com` in their browser

```
User types example.com
        |
        v
Browser asks DNS: "What IP address is example.com?"
        |
        v
DNS responds: "It's 145.23.67.89"
        |
        v
Browser connects to 145.23.67.89 port 443 (HTTPS)
        |
        v
Your server at that IP receives the request
        |
        v
Nginx reads the Host header: "example.com"
        |
        v
Routes to your Next.js app
```

A domain is just a **human-readable name that points to an IP address**. Your VPS has one IP address. You can point as many domains as you want to that same IP.

### Step by step — what you'd physically do

**Step 1: Buy the domains**

Go to a domain registrar (Namecheap, Cloudflare, GoDaddy) and purchase:
- `yourbrand.com` (~$12/year)
- `yourbrand.ca` (~$15/year)
- `yourbrand.es` (~$10/year)

You now own three domain names. They don't point anywhere yet.

**Step 2: Point them all to the same server**

In each domain registrar's dashboard, set DNS A records:

```
yourbrand.com    A    145.23.67.89    (your VPS IP)
yourbrand.ca     A    145.23.67.89    (same IP)
yourbrand.es     A    145.23.67.89    (same IP)
```

Now all three domains resolve to your single VPS. This takes 5 minutes to configure and a few hours to propagate worldwide.

**Step 3: Nginx accepts all three domains**

Update nginx config to list the domains (or keep the existing wildcard):

```nginx
server {
    listen 80;
    server_name yourbrand.com yourbrand.ca yourbrand.es;

    location / {
        proxy_pass http://nextjs:3000;
        proxy_set_header Host $host;  # Passes "yourbrand.ca" to Next.js
    }
}
```

When someone visits `yourbrand.ca`, nginx passes the request to Next.js with the header `Host: yourbrand.ca`. The Next.js middleware reads that header and knows "this is the Canadian site, show English + French."

**Step 4: SSL certificates (HTTPS)**

Each domain needs its own certificate. Let's Encrypt gives them for free:

```bash
certbot --nginx -d yourbrand.com
certbot --nginx -d yourbrand.ca
certbot --nginx -d yourbrand.es
```

Three commands, done. Auto-renews every 90 days.

**Step 5: Next.js middleware detects which domain**

```typescript
// middleware.ts — this is where the "magic" happens
import { NextRequest } from 'next/server';

export function middleware(request: NextRequest) {
  const host = request.headers.get('host');  // "yourbrand.ca"

  // Map domain to locale
  if (host.includes('.es')) locale = 'es';
  else if (host.includes('.ca')) locale = 'en'; // default, /fr available
  else locale = 'en';

  // Rewrite URL to include locale
  // yourbrand.ca/products  -> internally routes to /en/products
  // yourbrand.es/products  -> internally routes to /es/products
}
```

### The full picture — one VPS, three domains

```
yourbrand.com --+
                |     +---------+     +---------+     +----------+
yourbrand.ca  --+---->|  nginx  |---->| Next.js |---->| FastAPI  |
                |     | (port 80|     | (reads  |     | (same DB |
yourbrand.es --+     |  + 443) |     |  Host   |     |  for all)|
                      +---------+     |  header)|     +----------+
                                      +---------+

All three domains hit the SAME server, SAME app, SAME database.
The only difference is which language the UI renders in.
```

You're not "hosting three websites." You're hosting **one website** that looks at the incoming domain name and says "this person came from `.es`, show them Spanish." It's like one restaurant with three doors — the English door, the French door, and the Spanish door — but inside it's the same kitchen, same menu, same staff.

### What it costs

| Item | Cost | Frequency |
|------|------|-----------|
| `.com` domain | ~$12 | per year |
| `.ca` domain | ~$15 | per year |
| `.es` domain | ~$10 | per year |
| SSL certificates | Free | Let's Encrypt |
| Extra server resources | $0 | Same VPS, same app |
| **Total** | **~$37/year** | Just the domain registrations |

No extra servers, extra databases, or extra Docker containers needed. The multi-locale code work (52-68 hours from this document) is about teaching the app to read translations from JSON files instead of having "Shopping Cart" hardcoded. The domain part itself is just DNS records and a few lines of nginx config.

---

## Current State of the App

**0% multi-locale ready.** Everything is single-domain, single-language English:

| Aspect | Status | Details |
|--------|--------|---------|
| i18n library | Not installed | No `next-intl`, `react-i18next`, or similar |
| Hardcoded text | All English | Every component has hardcoded English strings |
| Root layout `lang` | Hardcoded `"en"` | `frontend/app/layout.tsx` line 26 |
| Middleware | Missing | No `middleware.ts` for locale/domain detection |
| Route segments | No `[locale]` | All routes are single-language |
| Database translations | Not supported | `products.name` is plain `VARCHAR`, not JSONB |
| Nginx domain routing | Wildcard only | `server_name _` accepts all domains, no per-domain logic |
| CORS | Single origin | Locked to one `frontend_url` |
| SEO hreflang | Not implemented | No alternate language tags in sitemap or meta |
| Site/tenant concept | Not in schema | No `site_id`, `domain`, or `locale` columns |

### Codebase String Audit

**~392 hardcoded English strings** across **70+ frontend files**:

| Area | Files | Strings | Examples |
|------|-------|---------|---------|
| Frontend pages | 48 | ~140 | "Discover What's Next", "Browse Products", "Shopping Cart" |
| Frontend components | 22 | ~60 | "Products", "Sign in", "Get Started", "Accept All" |
| Toast/error messages | Scattered | ~86 | "Failed to add to cart", "Discount applied!", "Invalid discount code" |
| Backend HTTP errors | 10+ routes | ~98 | "Product not found", "Invalid or expired refresh token" |
| Checkout page alone | 1 (494 lines) | ~25 | "Shipping Address", "Billing Address", "Order Review", "Payment" |
| Auth pages | 2 | ~27 | "Welcome back", "Create Account", "Too short", "Weak", "Strong" |
| Admin pages | 15+ | ~150 | Nav labels, form fields, table headers, modal text |

**Email templates:** Not built yet (`modules/notifications/` is empty). When added, they'll need locale awareness too.

---

## Architecture Options

### Option A: Single Deployment, Multi-Domain (Recommended)

One Next.js + one FastAPI + one database serves ALL domains. Middleware detects which domain the request comes from and routes to the correct locale.

```
                    +----------------------------+
                    |       nginx (1 VPS)        |
                    |  SSL certs per domain      |
                    +-------------+--------------+
                                  |
                    +-------------v--------------+
                    |     Next.js middleware      |
                    |  Detects domain -> locale   |
                    |                             |
                    |  example.com  -> en         |
                    |  example.ca   -> en (+ /fr) |
                    |  example.es   -> es         |
                    +-------------+--------------+
                                  |
              +-------------------v-------------------+
              |         /[locale]/...                  |
              |   /en/products  /fr/products  /es/     |
              |   Same components, different strings   |
              +-------------------+-------------------+
                                  |
                    +-------------v--------------+
                    |   FastAPI (shared backend)  |
                    |   One PostgreSQL database    |
                    |   Same products/orders/users |
                    +-----------------------------+
```

**Why this fits:** Same products, same admin, same brand. One deployment = one VPS cost, one admin panel, one product catalog.

**Pros:**
- Lowest infrastructure cost (one deployment)
- Shared catalog, consistent pricing logic
- Easier user handoffs between domains (single session)
- Simpler CI/CD (one pipeline)

**Cons:**
- Single point of failure across all domains
- All domains use same database (regulatory complexity if EU + US data residency)
- Scaling: all domains share compute resources

**Best for:** 2-5 related domains with same branding/catalog.

### Option B: Separate VPS Per Domain (Current Boilerplate Model)

Each domain is a completely independent deployment with its own database. This is what the boilerplate is designed for.

**Problem:** If you want domains to share the same product catalog, user accounts, and order history, separate VPSes don't work — you'd be manually duplicating products across databases.

**Best for:** Completely independent brands/clients (not the multi-locale scenario).

### Option C: Shared Backend, Separate Frontends

One FastAPI + PostgreSQL serves as the API. Multiple Next.js instances (one per domain) connect to the same backend.

**Best for:** When domains have significantly different UIs. Overkill for the multi-locale scenario.

**Verdict: Option A is the answer for the described scenario — but it needs infrastructure hardening for production use.**

---

## Scalability, Redundancy & Uptime: Separation of Concerns

### How Large-Scale Sites Actually Work

Companies like Amazon don't run "separate websites" for `.com`, `.ca`, `.es`. They run **one distributed system** that renders differently based on who's asking.

```
User visits amazon.es
        |
        v
CDN (300+ edge locations worldwide)
        |
        v
Load Balancer (routes to nearest healthy region)
        |
        v
+------------------+     +------------------+     +------------------+
|   US-East        |     |   EU-West        |     |   CA-Central     |
|   Cluster        |     |   Cluster        |     |   Cluster        |
|   (50+ servers)  |     |   (50+ servers)  |     |   (20+ servers)  |
+------------------+     +------------------+     +------------------+
        |                         |                         |
        v                         v                         v
    Regional DB               Regional DB               Regional DB
    (replicated)              (replicated)              (replicated)
```

Key principles that scale down to any size:

1. **There is no "the server."** Multiple servers exist. Any one can die and nobody notices.
2. **The code is identical everywhere.** Same app deployed to every server. The request context (domain, IP, cookies) determines language/currency/catalog.
3. **Data is replicated, not shared.** Product catalog syncs across regions. Each region has its own database replica.
4. **Separation of concern is at the service level**, not the domain level.

### The Core Principle: Separate Compute from Data

The real separation of concern isn't "one server per domain." It's separating your disposable compute from your persistent data:

```
        Domains are just doors
              |
    +---------+---------+
    |         |         |
 .com       .ca       .es
    |         |         |
    +---------+---------+
              |
              v
    +-------------------+
    |    CDN / Edge     |  <-- Cloudflare (free) handles 70%+ of requests
    |   (static assets, |      Images, CSS, JS, cached pages never
    |    cached pages)  |      touch your server
    +-------------------+
              |
              v  (only dynamic requests pass through)
    +-------------------+
    |   Load Balancer   |  <-- Routes to healthy server
    +-------------------+
         |          |
         v          v
    +--------+  +--------+
    | App 1  |  | App 2  |   <-- Identical Docker stacks
    | (VPS)  |  | (VPS)  |       Either can serve any domain
    +--------+  +--------+
         |          |
         +----+-----+
              |
              v
    +-------------------+
    |  Managed Database |  <-- NOT on either VPS
    |   (separate)      |     DigitalOcean/Hetzner managed DB
    +-------------------+
```

The database is NOT on the application server. The application servers are stateless and interchangeable. If App 1 dies, the load balancer sends everything to App 2. Neither server "owns" any domain.

### Current Architecture vs Separated Architecture

**Current (everything on one VPS — single point of failure):**

```
One VPS
├── nginx        (reverse proxy)
├── nextjs       (frontend)
├── fastapi      (backend)
├── postgres     (database)     <-- THE RISK
└── redis        (cache/sessions) <-- and this
```

Everything lives and dies together. Server crash = all domains down + potential data loss.

**Separated (compute is disposable, data is protected):**

```
VPS 1 (App Server)              VPS 2 (App Server)
├── nginx                       ├── nginx
├── nextjs                      ├── nextjs
├── fastapi                     ├── fastapi
└── redis (local cache only)    └── redis (local cache only)

         Managed Services (separate infrastructure)
         ├── PostgreSQL (managed, auto-failover, daily backups)
         └── Redis (managed, persistent sessions)
```

App servers are disposable — blow one away and spin up a new one in minutes. Data is safe on managed infrastructure with automatic backups and failover built in.

### Infrastructure Tiers

#### Tier 1: Basic Resilience (~$15-20/month extra)

| Component | What | Why |
|-----------|------|-----|
| **Cloudflare (free)** | CDN + DDoS protection in front of all domains | 70%+ of requests served from edge. Free. |
| **Managed PostgreSQL** | DigitalOcean/Hetzner managed DB ($7-15/mo) | Automatic backups, failover replicas, data survives VPS death |
| **Docker restart policies** | `restart: unless-stopped` on all containers | Auto-recovery from container crashes |
| **External monitoring** | UptimeRobot (free) | Know when things break, get alerted |

Solves 80% of real-world downtime causes (container crashes, DB corruption, accidental data loss). Your data is safe even if the VPS burns down.

#### Tier 2: High Availability (~$40-60/month extra)

| Component | What | Why |
|-----------|------|-----|
| **2x small VPS** | Identical Docker stacks ($5-10/mo each) | Either can serve any domain |
| **Cloudflare load balancing** | Routes to healthy server ($5/mo) | Automatic failover if one VPS stops responding |
| **Managed Redis** | Persistent sessions on separate infra | Sessions survive app server restarts |
| **Rolling deploys** | Update App 1, then App 2 | Zero-downtime deployments |

With this setup, if your primary VPS goes down, the load balancer routes all traffic to the standby. All three domains survive. Downtime goes from "hours" to "minutes."

#### Tier 3: Full Redundancy (~$100-200/month extra)

| Component | What | Why |
|-----------|------|-----|
| **Container orchestration** | Docker Swarm or Kubernetes across 2-3 nodes | Auto-scaling, self-healing, rolling deploys |
| **Multi-region** | VPS in US + EU | Survives datacenter outages, lower latency, EU data residency compliance |
| **CDN for dynamic content** | Cloudflare Workers / Vercel Edge | Even dynamic pages served from edge |
| **Managed everything** | Managed DB, managed Redis, managed containers | Your job is code, not ops |

Enterprise-grade. Overkill for most small businesses, but the answer if uptime is mission-critical.

### Recommended Path

**Start with Tier 1.** For ~$15/month extra you eliminate the most common failure modes. The single biggest wins:

1. **Cloudflare free plan** — most traffic never touches your server
2. **Managed database** — your data is safe regardless of what happens to the VPS
3. **Monitoring** — know when things break before customers tell you

**Upgrade to Tier 2 when** the cost of 30 minutes of downtime exceeds $60/month in lost revenue. That's your signal.

**Tier 3 is for** when you have compliance requirements (EU data residency for `.es`) or when revenue demands five-nines uptime.

### Risk Assessment Summary

| Risk | Option A (bare) | Option A + Tier 1 | Option A + Tier 2 |
|------|----------------|-------------------|-------------------|
| VPS crash | All domains down, possible data loss | All domains down, **data safe** | Auto-failover, minimal downtime |
| Bad deploy | All domains affected | All domains affected | Rolling deploy, zero downtime |
| DDoS attack | Server overwhelmed | Cloudflare absorbs it | Cloudflare absorbs it |
| DB corruption | Manual recovery from backups (if you have them) | Managed DB auto-recovery | Managed DB auto-recovery |
| Traffic spike | All domains slow | All domains slow (but CDN helps) | Load balanced across servers |
| Datacenter outage | All domains down | All domains down | Multi-region survives it (Tier 3) |

---

## Optimal Solution: Detailed Technical Design

### Core Insight: Externalize Strings Now, Translate Later

The most expensive part isn't adding languages — it's **retrofitting externalized strings into an app that has hardcoded text everywhere**. If you bake in the infrastructure while the app is still being built, adding French/Spanish later is just creating JSON files and hiring a translator.

If you wait until the app has 100+ pages and 1000+ strings, you're looking at weeks of tedious extraction work.

### The Tech Stack

| Component | Choice | Why |
|-----------|--------|-----|
| **i18n library** | `next-intl` | De facto standard for Next.js App Router. 1M+ weekly downloads. ~2KB bundle. Native Server Component support. |
| **Routing** | `[locale]` dynamic segment + middleware | Middleware detects domain, maps to locale, rewrites URL |
| **Translation files** | JSON per namespace (`common.json`, `products.json`, `checkout.json`) | Organized by page/feature, not one giant file |
| **Fallback chain** | `fr-CA -> fr -> en -> raw key` | 3-level fallback prevents broken UI if a translation is missing |
| **Currency** | Domain = currency | `example.com` = USD, `example.ca` = CAD, `example.es` = EUR |
| **Translation management** | Document Crowdin/Lokalise integration, don't bake in | Clients choose their own TMS |
| **Rendering** | ISR for product pages, SSR for cart/checkout | Best performance balance |

### Why next-intl Over Alternatives

| Library | Weekly Downloads | App Router Support | Server Components | Verdict |
|---------|-----------------|-------------------|-------------------|---------|
| **next-intl** | 1,007,272 | Native | Yes (`getTranslations()`) | Best choice |
| LinguiJS | 443,896 | Requires CLI extraction step | Partial | More friction |
| next-i18next | Legacy | Built for Pages Router | No | Don't use |
| Built-in Next.js | N/A | Removed in App Router | N/A | Officially recommends third-party |

### File Structure

```
frontend/
  messages/
    en.json          <-- all English strings (source of truth)
    fr.json          <-- French (added by client when needed)
    es.json          <-- Spanish (added by client when needed)
  app/
    [locale]/        <-- ALL customer-facing routes go here
      page.tsx       <-- homepage
      products/
      cart/
      checkout/
      auth/
    admin/           <-- stays OUTSIDE [locale] -- English only
  middleware.ts      <-- domain detection + locale routing
  i18n.ts            <-- next-intl configuration
```

### Domain-to-Locale Configuration

Configured via environment variables at deployment time:

| Domain | Default Locale | Available Locales | Currency |
|--------|---------------|-------------------|----------|
| `example.com` | `en` | `en` | USD |
| `example.ca` | `en` | `en`, `fr` | CAD |
| `example.es` | `es` | `es` | EUR |

Middleware detection priority:
1. Locale prefix in pathname (e.g., `example.ca/fr/products`)
2. Cookie (if user previously switched language)
3. `Accept-Language` header
4. Domain's default locale fallback

---

## What Gets Translated vs What Doesn't

This is the critical decision most people get wrong.

| Layer | Translate? | Why |
|-------|-----------|-----|
| **UI chrome** (buttons, labels, navigation, error messages) | YES | This is what the customer sees. "Add to Cart" becomes "Ajouter au panier" |
| **Product names** | NO (initially) | IKEA, Zara, H&M don't translate most product names. "Classic T-Shirt" stays "Classic T-Shirt" in French Canada. Add translation support as an optional JSONB field for clients who need it. |
| **Product descriptions** | OPTIONAL | High-value products benefit from translated descriptions. Make it an optional JSONB field in the database. |
| **Admin panel** | NO | Admin is internal. Staff speaks the business language. This is the industry standard. |
| **Email templates** | LATER | Not built yet anyway. When they are, they'll need locale awareness. |
| **Backend error messages** | NO (frontend maps them) | API errors like "Product not found" stay English. The frontend maps error codes to localized user-facing messages. Don't translate raw API responses. |

### Database Schema for Translations

**JSONB approach (recommended over translation tables):**
```sql
-- Products table change
ALTER TABLE ecommerce.products
  ALTER COLUMN name TYPE JSONB USING jsonb_build_object('en', name),
  ALTER COLUMN description TYPE JSONB USING jsonb_build_object('en', description);
```

**Why JSONB > separate translation table:**
- Faster queries (no JOINs needed)
- Simpler schema (fewer tables)
- PostgreSQL full-text search works on JSONB
- Easy to add new languages (just add a key)
- Query: `WHERE name->>'en' LIKE '%fish%'`

**Alternative:** Keep product data in English only and only translate UI chrome. Many international sites do this successfully.

---

## Stripe / Payments

One Stripe account handles all currencies. No separate accounts needed.

| Approach | How It Works | Best For |
|----------|-------------|----------|
| **Adaptive Pricing** | Stripe auto-detects customer location and shows local currency. You set USD price, Stripe converts. | Don't know customer's location upfront |
| **Fixed local prices** | You manually set CAD price for `.ca`, EUR price for `.es`. More control over margins. | Precise margin control |

Stripe supports 135+ currencies from a single account. Their 2025 recommendation is Adaptive Pricing for most e-commerce.

---

## Translation Workflow

The hardest ongoing cost isn't the code — it's **maintaining translations**. Every new feature, page, or product needs translations in all languages.

| Option | Cost | Quality | Effort |
|--------|------|---------|--------|
| Manual translation (you/team) | Free | High | High |
| Translation service (Weglot, Lokalise) | $15-50/month | High | Low |
| AI translation (Claude/GPT then human review) | Low | Medium-High | Medium |
| Community/crowdsource | Free | Variable | Medium |

### Translation Management at Scale (500+ keys)

**Top TMS platforms (2025-2026):**

| Platform | Best For | Key Feature |
|----------|----------|-------------|
| **Crowdin** | Automation-first teams | Auto-PRs when translations approved, GitHub integration |
| **Lokalise** | Startups/scale-ups | Developer-friendly, collaborative editor |
| **Phrase** | Enterprise | AI/machine translation, glossaries, workflow automation |
| **Transifex** | Agile teams | Continuous localization, powerful API |

**Workflow:**
1. Push source strings (English JSON) to TMS
2. Translators work in TMS editor (with context, screenshots, terminology)
3. QA checks run automatically (missing variables, truncation, formatting)
4. On approval, TMS creates auto-PR to your repo
5. Merge and deploy — users see new translations

### Handling Missing Translations

Best practice fallback chain:
```
Requested locale (e.g., fr-CA)
  -> [not found] -> Parent locale (fr)
  -> [not found] -> Default locale (en)
  -> [not found] -> Raw key (show "buttons.submit" in dev, never in prod)
```

---

## SEO Implications

Multi-domain is the **strongest signal** to Google for country targeting:

- **Separate domains** (`.com`, `.ca`, `.es`) = strongest country targeting signal
- **hreflang tags** tell Google which version to show each user:
  ```html
  <link rel="alternate" hreflang="en-US" href="https://example.com/products" />
  <link rel="alternate" hreflang="en-CA" href="https://example.ca/products" />
  <link rel="alternate" hreflang="fr-CA" href="https://example.ca/fr/products" />
  <link rel="alternate" hreflang="es-ES" href="https://example.es/products" />
  <link rel="alternate" hreflang="x-default" href="https://example.com/products" />
  ```
- **Separate sitemaps** per domain, submitted to Google Search Console individually
- **Self-referential canonicals** prevent duplicate content penalties

**Critical hreflang rules:**
1. Self-referential required — the page must link to itself
2. Bidirectional — if A links to B, then B must link to A
3. Valid locale codes — use ISO 639-1 (language) + ISO 3166-1 (region). Use `en-GB` not `en-UK`.
4. Implementation methods (pick ONE): HTML `<link>` tags, HTTP headers, or XML sitemap

**Important:** Google treats hreflang as hints, not guarantees. Content quality and relevance still matter most.

---

## Nginx / DNS Configuration

### Multi-Domain Routing

```nginx
# All domains point to same VPS IP via DNS A records
# Nginx preserves the Host header so Next.js middleware can detect domain

server {
    listen 80;
    server_name example.com example.ca example.es;

    location / {
        proxy_pass http://nextjs:3000;
        proxy_set_header Host $host;  # Critical: preserves domain for middleware
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    }

    location /api {
        proxy_pass http://fastapi:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### SSL Certificates

Separate Let's Encrypt certs per domain (free, auto-renewing):
```bash
certbot certonly --dns-cloudflare -d "example.com"
certbot certonly --dns-cloudflare -d "example.ca"
certbot certonly --dns-cloudflare -d "example.es"
```

Each cert is independent — renewal of one doesn't affect others.

---

## Compliance Considerations

| Area | What It Means |
|------|--------------|
| **GDPR (EU)** | If `.es` serves EU customers, EU data residency rules may apply. The existing GDPR module helps but may need per-locale consent flows. |
| **VAT** | EU sales may require VAT calculation. Stripe Tax or manual rates. See `docs/decisions/shipping-and-tax-analysis.md`. |
| **Canadian bilingual requirements** | Quebec law (Bill 96) requires French availability for `.ca` customers. This makes the `.ca` + French locale a legal requirement, not optional. |
| **Cookie consent** | May need per-locale cookie banners (different legal requirements per country). |
| **Data residency** | EU data staying in EU. If your VPS is in the US, you may need a separate EU-hosted database for `.es` customers (upgrades to Option B or a geo-partitioned database). |

---

## Performance: SSR vs SSG for Multi-Locale

| Rendering | TTFB | Use For |
|-----------|------|---------|
| **SSG (Static)** | 20-50ms | Product catalog, homepage, category pages |
| **ISR (Incremental Static)** | 20-50ms (cached), 100-300ms (regenerating) | Product pages that change occasionally |
| **SSR (Server-Side)** | 100-300ms | Cart, checkout, user profile (needs session) |

**The hybrid approach:** Use ISR for product catalog pages (pre-render at build time per locale, regenerate every 1-3 hours). Use SSR for dynamic pages (cart, checkout, dashboard).

next-intl Server Components with `getTranslations()` support `generateStaticParams()` for static pre-rendering per locale. Bundle overhead is ~2KB.

---

## Effort Breakdown (Honest Numbers)

### By Phase

| Phase | What | Hours | Notes |
|-------|------|-------|-------|
| **1. Infrastructure** | Install next-intl, create middleware, set up `[locale]` routes, configure domain mapping | 8-10 | One-time foundational work |
| **2. Customer-facing strings** | Extract ~200 strings from homepage, products, cart, checkout, auth, header, footer | 16-20 | The bulk of the work — tedious but mechanical |
| **3. Toast/error messages** | Extract ~86 toast messages, create error message catalog | 10-12 | Scattered across many files |
| **4. Database support** | Optional JSONB translation columns for products/categories | 4-6 | Migration + backend query changes |
| **5. SEO** | hreflang tags, per-locale sitemaps, canonical URLs | 4-6 | next-intl has helpers |
| **6. Nginx + SSL** | Multi-domain server blocks, Let's Encrypt per domain | 2-4 | Straightforward config |
| **7. Testing** | Verify every page in every locale, check fallbacks | 8-10 | Important — broken translations kill UX |
| **Total (customer-facing)** | | **52-68 hours** | ~2-3 weeks of focused work |

### Additional (if needed)

| Add-on | Hours | Notes |
|--------|-------|-------|
| Admin panel translation | 18-20 | 15+ pages with heavy UI text. Recommended: skip initially. |
| Email templates (when built) | 8-10 | Per template type |
| Per additional language | 8-12 | Professional translation of JSON files |

**Phase 1+2 alone** (infrastructure + customer-facing strings) gets you 80% of the value in ~30 hours. You could ship a working bilingual site in a week.

### By Priority

| Priority | Area | Effort | Impact |
|----------|------|--------|--------|
| 1 | i18n infrastructure (next-intl + middleware + routes) | 8-10 hrs | Unlocks everything else |
| 2 | Checkout flow (25+ strings, 494 lines) | 6-8 hrs | Highest conversion impact |
| 3 | Homepage + Header + Footer | 4-6 hrs | First impression |
| 4 | Auth pages (login/register) | 3-4 hrs | User onboarding |
| 5 | Product pages + cart | 6-8 hrs | Shopping flow |
| 6 | Toast/notification messages | 10-12 hrs | Polish |
| 7 | SEO (hreflang, sitemaps) | 4-6 hrs | Search ranking |
| 8 | Database JSONB migration | 4-6 hrs | Product data translation |

---

## Optimal Timing

**Build it after the UI stabilizes, before deployment.**

- If you extract strings now while still adding features, you'll have to extract new strings for every feature you add.
- If you wait until after deployment, you're retrofitting a live production app.
- The sweet spot is after Phase 11 (deployment) is planned but before you go live — the UI is settled, the features are done, and you can do one clean pass to externalize everything.

---

## Key Decision Points

1. **Core feature or optional module?** Should every boilerplate deployment support multi-locale, or is this a toggle? Recommendation: bake in the infrastructure (externalized strings), let multi-domain be a deployment-time configuration.
2. **Translate product data or UI only?** Start with UI only. Make product JSONB optional for clients who need it.
3. **Admin panel?** Keep English-only. Industry standard. Bolt on later if a client needs it.
4. **When to build?** After UI stabilizes, before deployment. The infrastructure setup (Phase 1) is low-cost and high-value.
5. **Who translates?** Document Crowdin/Lokalise integration. Don't bake a specific TMS into the template.

---

## The Bottom Line

This is a **competitive advantage** if built into the boilerplate. Most e-commerce templates are English-only. A template that's "drop in your domain, add your translations, you're global" is significantly more valuable.

The technical implementation is well-understood (next-intl + middleware + domain routing). The effort is moderate (52-68 hours for customer-facing). The hardest part is the mechanical string extraction, not the architecture.

---

## Files Referenced

| File | Relevance |
|------|-----------|
| `frontend/next.config.js` | No i18n config (needs adding) |
| `frontend/app/layout.tsx` | Hardcoded `lang="en"` |
| `frontend/app/page.tsx` | Hardcoded English throughout (~8 strings) |
| `frontend/components/Header.tsx` | All navigation text hardcoded (~10 strings) |
| `frontend/app/checkout/page.tsx` | Heaviest page (~25 strings, 494 lines) |
| `frontend/app/auth/login/page.tsx` | ~12 hardcoded strings |
| `frontend/app/auth/register/page.tsx` | ~15 hardcoded strings |
| `frontend/app/products/[slug]/page.tsx` | ~12 hardcoded strings |
| `frontend/app/cart/page.tsx` | ~10 hardcoded strings |
| `frontend/components/Footer.tsx` | ~10 hardcoded strings |
| `frontend/components/CookieBanner.tsx` | ~8 hardcoded strings |
| `backend/core/config.py` | Single `domain` setting |
| `backend/main.py` | CORS single origin, `/api/config` endpoint |
| `docker/nginx.conf` | Wildcard `server_name _` |
| `modules/seo/services/sitemap_service.py` | No hreflang support |
| `modules/seo/services/meta_service.py` | No alternate locale URLs |
| `modules/notifications/` | Empty — email templates not built yet |
