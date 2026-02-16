# Phase 8: SEO Module

**Estimate:** 2-3 hours
**Depends on:** Phase 5
**Category:** Discoverability & marketing

## Goal
Build the SEO module: dynamic meta tag management, automatic sitemap.xml generation, robots.txt configuration, Open Graph and Twitter Card tags, and JSON-LD structured data for products and organization. At the end of this phase, every page has proper SEO metadata and the site is fully discoverable by search engines.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` section 10 (Environment Variables — SEO section) and the project overview for SEO scope. The frontend (Phase 9) will consume these APIs to render meta tags server-side via Next.js.

## Deliverables

1. **Meta tag management** (modules/seo/services/ + routes/):
   - `GET /api/seo/meta/{path}` — meta tags for a given page path
   - `PUT /api/seo/meta/{path}` — set custom meta tags for a path (admin only)
   - Default meta tags generated from content (product name → title, description → meta description)
   - Override system: custom meta tags take priority over auto-generated
   - Fields: title, description, canonical URL, robots directives (index/noindex, follow/nofollow)
   - Character limits enforced: title ≤ 60 chars, description ≤ 160 chars

2. **Sitemap.xml generation** (modules/seo/services/ + routes/):
   - `GET /sitemap.xml` — dynamically generated XML sitemap
   - Includes: all active products, categories, static pages
   - Proper `<lastmod>`, `<changefreq>`, `<priority>` attributes
   - Products: priority 0.8, changefreq weekly
   - Categories: priority 0.6, changefreq weekly
   - Static pages (home, about, contact): priority 1.0/0.5, changefreq monthly
   - Sitemap index for large catalogs (>50,000 URLs): split into multiple sitemaps
   - Excludes soft-deleted products and inactive categories
   - Cache: regenerate on product/category change or on schedule (configurable)

3. **Robots.txt** (modules/seo/services/ + routes/):
   - `GET /robots.txt` — dynamically served robots.txt
   - Default rules: allow all crawlers, disallow admin paths (`/api/admin/*`)
   - Sitemap reference: `Sitemap: https://{DOMAIN}/sitemap.xml`
   - Configurable via admin endpoint or .env
   - Disallow sensitive paths: `/api/auth/*`, `/api/gdpr/*`, `/api/tracking/*`

4. **Open Graph tags** (modules/seo/services/):
   - Auto-generated OG tags for all pages:
     - `og:title`, `og:description`, `og:image`, `og:url`, `og:type`, `og:site_name`
   - Product pages: `og:type=product`, product image, price (using `product:price:amount` and `product:price:currency`)
   - Category pages: `og:type=website`, category description
   - Default OG image from `DEFAULT_OG_IMAGE` env var
   - Twitter Card tags: `twitter:card=summary_large_image`, `twitter:site` from `SOCIAL_HANDLES`

5. **JSON-LD structured data** (modules/seo/services/):
   - Product schema: `@type=Product` with name, description, image, price (offers), SKU, availability, reviews (aggregate rating)
   - Organization schema: `@type=Organization` with name, URL, logo, social profiles
   - BreadcrumbList schema: based on category hierarchy
   - WebSite schema: with SearchAction for site search
   - All structured data served via API for Next.js to embed as `<script type="application/ld+json">`

6. **SEO admin endpoints** (modules/seo/routes/):
   - `GET /api/admin/seo/meta` — list all custom meta tag overrides
   - `PUT /api/admin/seo/meta/{path}` — create/update meta tags for a path
   - `DELETE /api/admin/seo/meta/{path}` — remove custom override (revert to auto-generated)
   - `POST /api/admin/seo/sitemap/regenerate` — force sitemap regeneration
   - `GET /api/admin/seo/config` — current SEO configuration
   - `PUT /api/admin/seo/config` — update SEO settings (site name, default image, social handles)

7. **Canonical URL management** (modules/seo/services/):
   - Auto-generate canonical URLs for all pages
   - Handle duplicate content: product accessible via multiple category paths → single canonical
   - Pagination: `rel=prev`/`rel=next` for paginated listings
   - Trailing slash normalization

8. **SEO configuration** (modules/seo/config.py):
   - `SITE_NAME` — used in og:site_name and Organization schema
   - `DEFAULT_OG_IMAGE` — fallback OG image URL
   - `SOCIAL_HANDLES` — JSON of social media profiles (twitter, facebook, instagram)
   - `DOMAIN` — used for canonical URLs and sitemap
   - Sitemap cache TTL (default 1 hour)

## Acceptance Criteria
- [x] `GET /api/seo/meta/{path}` returns auto-generated meta tags for products and categories
- [x] Custom meta tag overrides take priority over auto-generated
- [x] `GET /sitemap.xml` returns valid XML sitemap with all active products and categories
- [x] Sitemap excludes soft-deleted and inactive items
- [x] `GET /robots.txt` returns proper robots directives with sitemap reference
- [x] Open Graph tags generated for product pages (type, image, price)
- [x] Twitter Card tags included with proper card type
- [x] JSON-LD Product schema includes name, price, availability, reviews
- [x] JSON-LD Organization schema includes site name and social profiles
- [x] JSON-LD BreadcrumbList reflects category hierarchy
- [x] Canonical URLs prevent duplicate content issues
- [x] Title ≤ 60 chars, description ≤ 160 chars enforced
- [x] Admin can override meta tags for any page
- [x] Sitemap regeneration can be triggered manually
- [x] All SEO admin endpoints require admin role

## Implementation Notes
- Sitemap generation: query products and categories tables, generate XML in-memory
- For large catalogs (>50k URLs): implement sitemap index with paginated sub-sitemaps
- OG image for products: use primary product image, fallback to DEFAULT_OG_IMAGE
- Price in structured data: convert INT cents to decimal string (e.g., 1999 → "19.99")
- Currency in structured data: use ISO 4217 code from product's currency column
- Availability mapping: in_stock if variant stock > 0, out_of_stock otherwise
- Cache sitemap in Redis to avoid regeneration on every request
- Next.js will consume these APIs in `generateMetadata()` for SSR

## Files to Create
- `modules/seo/services/meta_service.py` — Meta tag generation, override management
- `modules/seo/services/sitemap_service.py` — Sitemap XML generation, caching
- `modules/seo/services/structured_data_service.py` — JSON-LD schema generation
- `modules/seo/services/og_service.py` — Open Graph and Twitter Card tag generation
- `modules/seo/models/schemas.py` — Pydantic models for meta tags, SEO config
- `modules/seo/routes/seo_routes.py` — Public SEO endpoints (sitemap, robots, meta)
- `modules/seo/routes/admin_routes.py` — Admin SEO management endpoints
- `modules/seo/config.py` — SEO module configuration
- Modified: `backend/main.py` — Mount SEO routes
- Modified: `.env.template` — Add SITE_NAME, DEFAULT_OG_IMAGE, SOCIAL_HANDLES

## Files Created
- `modules/seo/__init__.py`
- `modules/seo/config.py`
- `modules/seo/models/__init__.py`
- `modules/seo/models/schemas.py`
- `modules/seo/services/__init__.py`
- `modules/seo/services/meta_service.py`
- `modules/seo/services/sitemap_service.py`
- `modules/seo/services/robots_service.py`
- `modules/seo/services/og_service.py`
- `modules/seo/services/structured_data_service.py`
- `modules/seo/routes/__init__.py`
- `modules/seo/routes/seo_routes.py`
- `modules/seo/routes/admin_routes.py`
- `migrations/007_seo_schema.sql`
- Modified: `backend/core/config.py` — Added site_name, default_og_image, social_handles, sitemap_cache_ttl
- Modified: `backend/main.py` — Added root-level /sitemap.xml and /robots.txt routes
- Modified: `docker/nginx.conf` — Added location rules for /sitemap.xml and /robots.txt → FastAPI
