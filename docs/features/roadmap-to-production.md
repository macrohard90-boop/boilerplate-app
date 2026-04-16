# Roadmap to Production — From Local to Cloud to Spin-Off

> Committed to memory: 2026-04-16

## Current State: Honest Assessment

### Fully Implemented (6/10 modules)
| Module | Routes | Tests | Status |
|--------|--------|-------|--------|
| Auth | 4 files | Partial | Complete — OAuth, JWT, RBAC, sessions |
| Payments | 4 files | Excellent | Complete — Stripe checkout, webhooks, subscriptions |
| E-commerce | 8 files | Good | Complete — orders, subscriptions, carts, discounts |
| Tracking | 2 files | Partial | Complete — pageviews, events, sessions, UTM |
| GDPR | 6 files | **NONE** | Complete code, zero test coverage |
| SEO | 2 files | Excellent | Complete — audit, keywords, GEO, AI advisors |

### Not Implemented (4/10 modules)
| Module | Status | Priority |
|--------|--------|----------|
| Notifications | Skeleton only, no config.py, marked "Required (core)" | **BLOCKING** — orders need email |
| Recommendations | Skeleton only, env vars defined but no code | Medium |
| Chatbot | Skeleton only, toggle exists (disabled) | Low |
| Marketing | Skeleton only, toggle exists | Low |

### Critical Gaps Before Cloud
1. **Notifications module** — No email provider. Orders complete but no confirmation emails sent. Must build before cloud testing.
2. **GDPR tests** — Compliance-critical module with zero tests.
3. **Auth unit tests** — Core module lacks dedicated test coverage.

---

## Phase A: Pre-Cloud Completion (Local)

### A1. Notifications Module (BLOCKING)
Build the notifications module so orders/subscriptions actually send emails:
- Email provider interface + adapters (SMTP, Mailgun, SendGrid, Postmark)
- Transactional email templates (order confirmation, subscription welcome, password reset)
- Notification preferences per user
- Admin route for viewing sent notifications
- Toggle: `ENABLE_NOTIFICATIONS` (though marked always-on in CLAUDE.md)
- Tests: unit + integration

### A2. Missing Test Coverage
- GDPR module: full test suite (consent, deletion, export, cookie management)
- Auth module: dedicated unit tests for login, OAuth, session, RBAC
- Tracking module: unit tests for event/pageview/session services

---

## Phase B: Cloud Deployment (Google Cloud)

### B1. Infrastructure Setup
- Google Cloud VM (e2-medium or similar) or Cloud Run
- Docker Compose deployment on the VM
- Domain + SSL (Let's Encrypt via Certbot or Cloud Load Balancer)
- PostgreSQL: either in Docker or Cloud SQL
- Redis: either in Docker or Memorystore
- Environment configuration (.env with production values)
- CI/CD: GitHub Actions → deploy on push to main

### B2. Stripe Production Testing
- Switch to Stripe live mode (or use Stripe test mode with real webhook delivery)
- Configure Stripe webhook endpoint URL pointing to cloud instance
- Test full payment flow:
  - [ ] One-time product purchase → webhook → order created → email sent
  - [ ] Subscription signup → webhook → subscription active → welcome email
  - [ ] Subscription renewal → invoice.paid webhook → confirmation email
  - [ ] Failed payment → invoice.payment_failed webhook → retry email
  - [ ] Subscription cancellation → customer.subscription.deleted → confirmation
  - [ ] Refund → charge.refunded webhook → order status updated

### B3. User Lifecycle Testing
- [ ] Registration (email + password)
- [ ] OAuth login (Google, GitHub at minimum)
- [ ] Email verification flow
- [ ] Password reset flow
- [ ] Profile update
- [ ] Role assignment (admin, user)
- [ ] Session management (login, logout, expiry)
- [ ] Account deletion (GDPR right to be forgotten)
- [ ] Data export (GDPR right to access)

### B4. Analytics Module Testing
- [ ] Pageview tracking fires on navigation
- [ ] Custom events tracked (add to cart, purchase, etc.)
- [ ] Session attribution (UTM, referral)
- [ ] Admin analytics dashboard shows real data
- [ ] GDPR consent respected (no tracking before consent)

### B5. GDPR Consent Testing
- [ ] Cookie banner appears for new visitors
- [ ] Consent choices persisted
- [ ] Analytics only fires after consent
- [ ] Consent withdrawal stops tracking
- [ ] Data export produces complete user data
- [ ] Account deletion removes all PII
- [ ] Email preferences respected

### B6. SEO/GEO Module Testing
- [ ] Sitemap.xml generates correctly with real pages
- [ ] Robots.txt serves correctly
- [ ] Meta tags render in SSR HTML (view-source check)
- [ ] SEO scoring runs on all pages
- [ ] GEO scoring runs on all pages
- [ ] SEO Advisor returns suggestions (Claude CLI or Anthropic API)
- [ ] GEO Advisor returns suggestions with AI Insights
- [ ] Keyword research returns suggestions
- [ ] Page audit generates complete report

---

## Phase C: Conversion & A/B Testing Module (NEW)

### C1. Conversion Module
A dedicated module for tracking conversion events and funnels:
```
modules/conversion/
  adapters/       # Provider implementations
  interfaces/     # Conversion tracking contracts
  models/         # Funnel, Goal, ConversionEvent schemas
  routes/         # Admin + public API
  services/       # Funnel analysis, goal tracking
  config.py       # ENABLE_CONVERSION toggle
```

Core features:
- **Conversion goals**: define what counts as a conversion (purchase, signup, page visit)
- **Funnel tracking**: define step sequences, measure drop-off at each step
- **Attribution**: which traffic source/campaign drove the conversion
- **Revenue attribution**: tie conversions to monetary value
- **Admin dashboard**: conversion rates, funnel visualization, trends over time

### C2. A/B Testing Engine
Either part of conversion module or its own:
```
modules/ab_testing/ (or modules/conversion/services/ab_testing_service.py)
```

Core features:
- **Experiment definition**: control vs variant(s), traffic split percentage
- **Variant assignment**: deterministic (user_id hash) so users see consistent experience
- **Goal tracking**: which variant converts better
- **Statistical significance**: chi-squared or Bayesian calculation
- **Live stats dashboard**: real-time variant performance
- **Auto-winner**: optionally auto-promote winning variant after significance reached

What to A/B test:
- **Pages**: different layouts, copy, CTAs (requires frontend variant rendering)
- **Products**: different pricing, images, descriptions
- **Checkout flow**: different step counts, form layouts
- **Email subject lines**: different transactional email variants

### C3. Humblytics Research
- Scrape/analyze humblytics.com to understand their approach to:
  - Privacy-focused analytics (cookieless?)
  - Conversion tracking methodology
  - A/B testing UX patterns
  - Dashboard design for live stats
  - How they handle statistical significance
- Extract applicable patterns for our implementation

---

## Phase D: Template Spin-Off Validation

### D1. The Core Test
Can we take this boilerplate and spin up 3 completely different businesses?

**Test Case 1: Shoe Store (E-commerce)**
- `APP_TEMPLATE=ecommerce`
- `ENABLE_PRODUCTS=true`, `ENABLE_SUBSCRIPTIONS=false`
- Custom UI: product grid, size selector, brand filtering
- Custom branding: colors, logo, fonts

**Test Case 2: Events Platform**
- `APP_TEMPLATE=ecommerce` (tickets are products)
- `ENABLE_PRODUCTS=true`, `ENABLE_SUBSCRIPTIONS=true` (season passes)
- Custom UI: calendar view, venue maps, event cards
- Custom branding: different theme entirely

**Test Case 3: SaaS Tool**
- `APP_TEMPLATE=saas`
- `ENABLE_PRODUCTS=false`, `ENABLE_SUBSCRIPTIONS=true`
- Custom UI: pricing page, feature comparison, dashboard
- Custom branding: minimal, professional

### D2. What Needs to Exist for Spin-Off
1. **Theme system** — CSS variables / Tailwind config that changes per instance
2. **Template switching** — `APP_TEMPLATE` env var controls which frontend pages load
3. **Content customization** — Site name, description, homepage layout configurable
4. **Component library** — Shared components that adapt to theme (buttons, cards, nav)
5. **Seed data scripts** — Per-template seed data (shoe products, event listings, SaaS plans)
6. **Deployment script** — `./deploy.sh` that provisions a new instance from template

### D3. Plan of Action for Spin-Off
1. Create a `templates/` directory with per-template overrides
2. Build theme configuration system (colors, fonts, layout preferences in .env or JSON)
3. Create template-specific page variants (homepage, product listing)
4. Build `spin-off.sh` script: copies repo, applies template config, seeds data
5. Test: spin up shoe store, verify everything works, tear down
6. Test: spin up events platform from same base, verify independence
7. Document the customization surface for each template type

---

## Execution Order

```
1. Build Notifications module (A1)          — BLOCKING for cloud testing
2. Write missing tests (A2)                 — GDPR, Auth, Tracking
3. Deploy to Google Cloud (B1)              — Infrastructure + Docker
4. Stripe end-to-end testing (B2)           — Webhooks, orders, emails
5. User lifecycle testing (B3)              — Auth flows on cloud
6. Analytics testing (B4)                   — Real traffic data
7. GDPR testing (B5)                        — Compliance verification
8. SEO/GEO testing (B6)                     — Real-world page analysis
9. Research Humblytics (C3)                 — Inform conversion design
10. Build Conversion module (C1)            — Goals, funnels, attribution
11. Build A/B Testing engine (C2)           — Experiments, live stats
12. Template spin-off validation (D1-D3)    — 3 test businesses
```

After step 8: **"Basic Application" is complete.**
After step 11: **Full analytics + optimization platform.**
After step 12: **Production-ready template system.**
