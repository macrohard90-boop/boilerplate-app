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

**Verdict: Option A is the answer for the described scenario.**

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
