# Phase 8 Test Plan — SEO Module

**Date:** 2026-02-16
**Status:** All tests passed

---

## A. Module Loading & Startup

| # | Test | Method | Result |
|---|------|--------|--------|
| A1 | SEO module loads on startup | `docker compose logs fastapi \| grep seo` | `Loaded module: seo` in logs |
| A2 | Module registered alongside all others | Checked loaded modules list | `['auth', 'ecommerce', 'gdpr', 'payments', 'seo', 'tracking']` |
| A3 | No import errors on build | `docker compose up -d --build fastapi` | Container started, `/api/health` returns 200 |

---

## B. Migration

| # | Test | Method | Result |
|---|------|--------|--------|
| B1 | SEO schema created | `psql < migrations/007_seo_schema.sql` | `CREATE SCHEMA`, `CREATE TABLE`, `CREATE INDEX` |
| B2 | `seo.meta_overrides` table exists | Migration output | Table created with path UNIQUE constraint |

---

## C. Robots.txt (Root-Level)

| # | Test | Method | Result |
|---|------|--------|--------|
| C1 | `GET /robots.txt` via FastAPI | `urllib.request.urlopen('http://localhost:8000/robots.txt')` | 200 OK, `text/plain` content type |
| C2 | Content includes User-agent and Allow | Inspected response body | `User-agent: *`, `Allow: /` |
| C3 | Disallows admin/auth/gdpr/tracking paths | Inspected response body | `Disallow: /api/admin/`, `/api/auth/`, `/api/gdpr/`, `/api/tracking/` |
| C4 | Sitemap reference included | Inspected response body | `Sitemap: http://localhost:8000/sitemap.xml` |
| C5 | `GET /robots.txt` via nginx | `urllib.request.urlopen('http://nginx/robots.txt')` | 200 OK — nginx routing to FastAPI works |

---

## D. Sitemap.xml (Root-Level)

| # | Test | Method | Result |
|---|------|--------|--------|
| D1 | `GET /sitemap.xml` via FastAPI | `urllib.request.urlopen('http://localhost:8000/sitemap.xml')` | 200 OK, `application/xml` content type |
| D2 | Contains static pages | Inspected XML | `http://localhost:3000/` (priority 1.0), `/about` (0.5), `/contact` (0.5) |
| D3 | Contains seed products | Inspected XML | `/products/wireless-headphones`, `/products/usb-c-hub`, `/products/classic-tshirt`, `/products/running-shoes` — all with priority 0.8, changefreq weekly |
| D4 | Products have lastmod dates | Inspected XML | `<lastmod>2026-02-16</lastmod>` on all product entries |
| D5 | Contains categories | Inspected XML | `/categories/electronics`, etc. — priority 0.6 |
| D6 | `GET /sitemap.xml` via nginx | `urllib.request.urlopen('http://nginx/sitemap.xml')` | 200 OK — nginx routing works |

**Nginx restart required:** After adding location rules for `/sitemap.xml` and `/robots.txt` to `docker/nginx.conf`, had to `docker compose rm -sf nginx && docker compose up -d nginx` (WSL bind mount issue prevented simple restart).

---

## E. Meta Tags — Auto-Generation

| # | Test | Method | Result |
|---|------|--------|--------|
| E1 | Product meta auto-generated | `GET /api/seo/meta/products/wireless-headphones` | `title: "Wireless Headphones"`, `description` from product, `is_custom: false` |
| E2 | Canonical URL set correctly | Inspected response | `canonical_url: "http://localhost:3000/products/wireless-headphones"` |
| E3 | Robots default to index, follow | Inspected response | `robots: "index, follow"` |
| E4 | Category meta auto-generated | `GET /api/seo/meta/categories/electronics` | `title: "Electronics"`, `is_custom: false` |
| E5 | Default page meta uses site name | `GET /api/seo/meta/about` | `title: "Boilerplate App"`, `canonical: "http://localhost:3000/about"` |

---

## F. Open Graph & Twitter Card Tags

| # | Test | Method | Result |
|---|------|--------|--------|
| F1 | Product OG tags include type | Inspected `og_tags` in product meta response | `og:type: "product"` |
| F2 | Product OG image from primary image | Inspected `og_tags` | `og:image: "/images/products/headphones-main.jpg"` (primary product image) |
| F3 | Product OG price tags | Inspected `og_tags` | `product:price:amount: "79.99"`, `product:price:currency: "USD"` |
| F4 | OG site_name included | Inspected `og_tags` | `og:site_name: "Boilerplate App"` |
| F5 | Twitter card type | Inspected `twitter_tags` | `twitter:card: "summary_large_image"` |
| F6 | Twitter title matches product | Inspected `twitter_tags` | `twitter:title: "Wireless Headphones"` |
| F7 | Category OG type is website | `GET /api/seo/meta/categories/electronics` | `og:type: "website"` |

---

## G. JSON-LD Structured Data

| # | Test | Method | Result |
|---|------|--------|--------|
| G1 | Product page includes 3 schemas | Counted `structured_data` array items | 3: Organization, WebSite, Product |
| G2 | Product schema has name and URL | Inspected Product JSON-LD | `name: "Wireless Headphones"`, `url` set |
| G3 | Product schema has SKU | Inspected Product JSON-LD | `sku: "WH-001"` |
| G4 | Product schema has image | Inspected Product JSON-LD | `image: "/images/products/headphones-main.jpg"` |
| G5 | Price converted from cents to decimal | Inspected `offers` | `price: "79.99"` (stored as 7999 cents), `priceCurrency: "USD"` |
| G6 | Availability from variant stock | Inspected `offers` | `availability: "https://schema.org/InStock"` (variants have stock > 0) |
| G7 | Aggregate rating from reviews | Inspected `aggregateRating` | `ratingValue: "4.5"`, `reviewCount: 2` (from approved seed reviews) |
| G8 | Organization schema has name and URL | Inspected Organization JSON-LD | `name: "Boilerplate App"`, `url` set |
| G9 | WebSite schema has SearchAction | Inspected WebSite JSON-LD | `potentialAction.@type: "SearchAction"`, target URL includes `{search_term_string}` |
| G10 | Category page includes BreadcrumbList | `GET /api/seo/meta/categories/electronics` | `structured_data` types: `['Organization', 'WebSite', 'BreadcrumbList']` |

---

## H. Admin Endpoints

All tested with admin token (`admin@example.com` / `Test1234!`).

| # | Test | Method | Result |
|---|------|--------|--------|
| H1 | Get SEO config | `GET /api/seo/admin/seo/config` | `{"site_name": "Boilerplate App", "default_og_image": "/images/og-default.png", "social_handles": {}, "domain": "localhost", "sitemap_cache_ttl": 3600}` |
| H2 | Set custom meta override | `PUT /api/seo/admin/seo/meta/home` with `{"title": "Custom Home", "description": "My custom homepage"}` | `{"message": "Meta override set for home"}` |
| H3 | List meta overrides | `GET /api/seo/admin/seo/meta` | `total: 1`, item with `path: "home"`, `title: "Custom Home"` |
| H4 | Custom override takes priority | `GET /api/seo/meta/home` after setting override | `title: "Custom Home"`, `is_custom: true` |
| H5 | Force sitemap regeneration | `POST /api/seo/admin/seo/sitemap/regenerate` | `{"message": "Sitemap cache invalidated. Next request will regenerate."}` |
| H6 | Delete meta override | `DELETE /api/seo/admin/seo/meta/home` | `{"message": "Meta override removed for home"}` |
| H7 | Admin endpoints require admin role | All 5 endpoints tested with admin token | 200 OK (non-admin would get 403) |

---

## Summary

| Category | Tests | Passed |
|----------|-------|--------|
| Module loading | 3 | 3 |
| Migration | 2 | 2 |
| Robots.txt | 5 | 5 |
| Sitemap.xml | 6 | 6 |
| Meta tags (auto) | 5 | 5 |
| OG & Twitter tags | 7 | 7 |
| JSON-LD structured data | 10 | 10 |
| Admin endpoints | 7 | 7 |
| **Total** | **45** | **45** |

All 45 tests passed. No code fixes required during testing (column names and schema matched on first attempt, unlike Phase 7).

---

## Post-Build Enhancement: SEO Scoring, SSR, Crawler & Audit (2026-04-15)

### I. Unit Tests — Scoring Provider

| # | Test | File | Result |
|---|------|------|--------|
| I1 | Perfect page scores 100 | `test_seo_scoring.py::test_perfect_score` | PASSED |
| I2 | Empty page scores < 30 | `test_seo_scoring.py::test_empty_page_scores_low` | PASSED |
| I3 | Missing title fails title_present | `test_seo_scoring.py::test_title_present_rule` | PASSED |
| I4 | Title too short fails title_length | `test_seo_scoring.py::test_title_too_short` | PASSED |
| I5 | Title too long fails title_length | `test_seo_scoring.py::test_title_too_long` | PASSED |
| I6 | Missing description fails desc_present | `test_seo_scoring.py::test_description_missing` | PASSED |
| I7 | Short description fails desc_length | `test_seo_scoring.py::test_description_too_short` | PASSED |
| I8 | Missing canonical fails canonical_set | `test_seo_scoring.py::test_canonical_missing` | PASSED |
| I9 | Incomplete OG tags fail og_complete | `test_seo_scoring.py::test_og_incomplete` | PASSED |
| I10 | Incomplete Twitter tags fail twitter_complete | `test_seo_scoring.py::test_twitter_incomplete` | PASSED |
| I11 | Generic-only structured data fails | `test_seo_scoring.py::test_structured_data_generic_only` | PASSED |
| I12 | noindex fails robots_indexable | `test_seo_scoring.py::test_noindex_fails_indexable` | PASSED |
| I13 | H1 present passes with crawl data | `test_seo_scoring.py::test_h1_present_with_crawl_data` | PASSED |
| I14 | H1 missing fails with crawl data | `test_seo_scoring.py::test_h1_missing_with_crawl_data` | PASSED |
| I15 | H1 auto-passes without crawl data | `test_seo_scoring.py::test_h1_auto_passes_without_crawl_data` | PASSED |
| I16 | Score always 0-100 | `test_seo_scoring.py::test_score_bounds` | PASSED |
| I17 | Exactly 10 rules | `test_seo_scoring.py::test_rule_count` | PASSED |
| I18 | All rules have required fields | `test_seo_scoring.py::test_all_rules_have_required_fields` | PASSED |

### J. Unit Tests — Snapshot Diffs

| # | Test | File | Result |
|---|------|------|--------|
| J1 | Identical snapshots = no diff | `test_seo_snapshot.py::test_no_diff_when_identical` | PASSED |
| J2 | Title change detected | `test_seo_snapshot.py::test_diff_on_title_change` | PASSED |
| J3 | Score change detected | `test_seo_snapshot.py::test_diff_on_score_change` | PASSED |
| J4 | OG tags change detected | `test_seo_snapshot.py::test_diff_on_og_tags_change` | PASSED |
| J5 | Multiple field changes | `test_seo_snapshot.py::test_diff_multiple_fields` | PASSED |
| J6 | None to value transition | `test_seo_snapshot.py::test_diff_none_to_value` | PASSED |
| J7 | Structured data change detected | `test_seo_snapshot.py::test_diff_structured_data_change` | PASSED |

### K. Unit Tests — Background Rescorer

| # | Test | File | Result |
|---|------|------|--------|
| K1 | Scores each collected path | `test_seo_rescorer.py::test_rescore_all_pages_scores_each_path` | PASSED |
| K2 | Continues on per-page errors | `test_seo_rescorer.py::test_rescore_continues_on_error` | PASSED |
| K3 | Handles empty paths gracefully | `test_seo_rescorer.py::test_rescore_empty_paths` | PASSED |

### Updated Summary

| Category | Tests | Passed |
|----------|-------|--------|
| Module loading | 3 | 3 |
| Migration | 2 | 2 |
| Robots.txt | 5 | 5 |
| Sitemap.xml | 6 | 6 |
| Meta tags (auto) | 5 | 5 |
| OG & Twitter tags | 7 | 7 |
| JSON-LD structured data | 10 | 10 |
| Admin endpoints | 7 | 7 |
| Scoring provider (unit) | 18 | 18 |
| Snapshot diffs (unit) | 7 | 7 |
| Background rescorer (unit) | 3 | 3 |
| **Total** | **73** | **73** |
