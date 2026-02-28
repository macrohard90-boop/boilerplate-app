# Multi-Domain, Multi-Locale Feasibility Study

**Date:** 2026-02-28
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

---

## Architecture Options

### Option A: Single Deployment, Multi-Domain (Recommended)

One Next.js + one FastAPI + one database serves ALL domains. Middleware detects which domain the request comes from and routes to the correct locale.

```
example.com     → middleware → /en/...     (English)
example.ca      → middleware → /en/...     (English, default)
example.ca/fr   → middleware → /fr/...     (French)
example.es      → middleware → /es/...     (Spanish)
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

**Verdict: Option A is the answer for the described scenario.**

---

## What Would Need to Change

### Frontend (Biggest Effort)

| Change | Effort | Details |
|--------|--------|---------|
| Install `next-intl` | Small | The de facto i18n library for Next.js 14/15 App Router |
| Create `middleware.ts` | Medium | Detect domain → map to locale → rewrite URL |
| Wrap all routes in `[locale]/` | Medium | Every page becomes `/[locale]/products`, `/[locale]/cart`, etc. |
| Extract all hardcoded strings | **Large** | Every component has English text. Create `messages/en.json`, `messages/fr.json`, `messages/es.json` |
| Locale switcher component | Small | Dropdown or flag icons to switch language |
| hreflang meta tags | Small | `next-intl` has helpers for this |

**Key files affected:**
- `frontend/app/layout.tsx` — root layout, `lang` attribute
- `frontend/app/page.tsx` — homepage (hardcoded: "Discover What's Next", "Browse Products", etc.)
- `frontend/components/Header.tsx` — navigation ("Products", "Sign in", "Get Started", etc.)
- `frontend/app/products/page.tsx` — sort labels, tab names
- `frontend/app/cart/page.tsx` — "Shopping Cart", "Your cart is empty", etc.
- `frontend/app/checkout/page.tsx` — checkout flow text
- Every admin page

### Database

| Change | Effort | Details |
|--------|--------|---------|
| Product `name`/`description` to JSONB | Medium | `"T-Shirt"` becomes `{"en": "T-Shirt", "fr": "T-shirt", "es": "Camiseta"}` |
| Category names to JSONB | Small | Same pattern |
| Migration + backfill | Small | Convert existing English values to `{"en": "..."}` format |

**JSONB approach (recommended over translation tables):**
```sql
-- Products table change
ALTER TABLE ecommerce.products
  ALTER COLUMN name TYPE JSONB USING jsonb_build_object('en', name),
  ALTER COLUMN description TYPE JSONB USING jsonb_build_object('en', description);
```

**Why JSONB > separate translation table:**
- Faster queries (no JOINs)
- Simpler schema (fewer tables)
- PostgreSQL full-text search works on JSONB
- Easy to add new languages (just add key)

**Alternative:** Keep product names in English only and only translate UI chrome (buttons, labels, navigation). Many international sites do this.

### Backend

| Change | Effort | Details |
|--------|--------|---------|
| Accept `locale` query param | Small | Product endpoints return name in requested locale |
| CORS allow multiple origins | Small | Allow `.com`, `.ca`, `.es` domains |
| Sitemap per locale | Medium | Generate separate sitemaps with hreflang |

### Nginx / DNS

| Change | Effort | Details |
|--------|--------|---------|
| DNS A records for each domain | Small | Point all domains to same VPS IP |
| Nginx server blocks per domain | Small | Or keep wildcard and let Next.js middleware handle it |
| SSL certs per domain | Small | Separate Let's Encrypt certs (free, auto-renewing) |

```nginx
# Example: multi-domain nginx config
server {
    listen 80;
    server_name example.com example.ca example.es;

    location / {
        proxy_pass http://nextjs:3000;
        proxy_set_header Host $host;  # Preserves domain for middleware detection
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Stripe / Payments

One Stripe account handles all currencies. No separate accounts needed.

| Approach | How It Works |
|----------|-------------|
| **Adaptive Pricing** | Stripe auto-detects customer location and shows local currency. You set USD price, Stripe converts. |
| **Fixed local prices** | You manually set CAD price for `.ca`, EUR price for `.es`. More control over margins. |

Stripe supports 135+ currencies from a single account.

---

## Translation Workflow

The hardest ongoing cost isn't the code — it's **maintaining translations**. Every new feature, page, or product needs translations in all languages.

| Option | Cost | Quality | Effort |
|--------|------|---------|--------|
| Manual translation (you/team) | Free | High | High |
| Translation service (Weglot, Lokalise) | $15-50/month | High | Low |
| AI translation (Claude/GPT → human review) | Low | Medium-High | Medium |
| Community/crowdsource | Free | Variable | Medium |

---

## SEO Implications

Multi-domain is the **strongest signal** to Google for country targeting:

- **Separate domains** (`.com`, `.ca`, `.es`) → strongest country targeting
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

**Important:** Google treats hreflang as hints, not guarantees. Content quality and relevance still matter most.

---

## Compliance Considerations

| Area | What It Means |
|------|--------------|
| **GDPR (EU)** | If `.es` serves EU customers, EU data residency rules may apply. The existing GDPR module helps but may need per-locale consent flows. |
| **VAT** | EU sales may require VAT calculation. Stripe Tax or manual rates. |
| **Canadian bilingual requirements** | Quebec law requires French availability for `.ca` customers. |
| **Cookie consent** | May need per-locale cookie banners (different legal requirements). |

---

## Total Effort Estimate

| Component | Days | Notes |
|-----------|------|-------|
| next-intl setup + middleware | 1 | Library install, domain → locale mapping |
| Route restructuring (`[locale]/`) | 1 | Wrap all routes |
| String extraction + translation files | 2-3 | The bulk of the work |
| Database JSONB migration | 0.5 | Products + categories |
| Backend locale support | 0.5 | Query params, CORS, sitemap |
| Nginx + SSL | 0.5 | Multi-domain config |
| Testing all locales | 1 | Verify every page in every language |
| **Total** | **6-8 days** | |

---

## Key Decision Points

1. **Core feature or optional module?** Should every boilerplate deployment support multi-locale, or is this a toggle?
2. **Translate product data or UI only?** Product names in JSONB vs English-only products with translated UI chrome.
3. **When to build?** This is a significant refactor — best done when the UI is stable (after deployment).
4. **Who translates?** You need a translation workflow for ongoing content.

---

## Files Referenced

| File | Relevance |
|------|-----------|
| `frontend/next.config.js` | No i18n config (needs adding) |
| `frontend/app/layout.tsx` | Hardcoded `lang="en"` |
| `frontend/app/page.tsx` | Hardcoded English throughout |
| `frontend/components/Header.tsx` | All navigation text hardcoded |
| `backend/core/config.py` | Single `domain` setting |
| `backend/main.py` | CORS single origin, `/api/config` endpoint |
| `docker/nginx.conf` | Wildcard `server_name _` |
| `modules/seo/services/sitemap_service.py` | No hreflang support |
| `modules/seo/services/meta_service.py` | No alternate locale URLs |
