# Full Customer Lifecycle — Business Process Plan

> Generated 2026-04-18 after deep-dive analysis of all modules: analytics/tracking, e-commerce/payments, marketing/recommendations, auth/GDPR/notifications.

---

## Current System Inventory

| Capability | Status | Revenue Impact |
|---|---|---|
| Real-time analytics (page views, sessions, events, engagement scoring) | **Complete** | Measurement |
| UTM campaign tracking + referral source attribution | **Complete** | Acquisition insight |
| Full e-commerce flow (browse → cart → checkout → Stripe payment) | **Complete** | Core revenue |
| Subscription billing (trial, recurring, cancellation) | **Complete** | Recurring revenue |
| Discount/coupon system (%, fixed, free shipping, per-product) | **Complete** | Conversion lever |
| Email delivery pipeline (consent, template, send, retry, audit) | **Complete** | Communication channel |
| Marketing campaigns (create → send → track stats) | **Complete** | Outbound marketing |
| Audience segmentation (3-tier consent filtering) | **Complete** | Targeting |
| Wishlist system | **Complete** | Intent signal |
| Customer metrics table (order_count, total_spent, last_purchase) | **Schema only** | Segmentation |
| RFM segmentation field | **Schema only** | Targeting |
| Cart abandonment detection (order reaper + abandoned_cart_events table) | **Partial** | Recovery |
| Recommendations module | **Stub only** | Cross-sell |
| Conversion funnel analysis | **Data exists, no endpoint** | Optimization |

---

## The 8 Business Processes

### BP1: Conversion Funnel Engine

**Goal:** "Where are we losing customers and why?"

We track every page view, every event, every session. But we have **no way to visualize or act on funnel drop-off**. This is the highest-leverage gap.

**What it does:**
- Define named funnels (e.g., "Product Purchase": homepage → product page → add to cart → checkout → payment)
- Calculate step-by-step conversion rates with drop-off percentages
- Segment by device, traffic source, UTM campaign, time period
- Identify which pages/steps lose the most users
- Admin dashboard tab showing funnel visualization

**Revenue lever:** If checkout conversion is 2% and we identify that 40% drop off at shipping address, fixing that one step could double revenue.

**Existing infrastructure:**
- `analytics.page_views` — page-level tracking with duration
- `analytics.events` — custom event tracking (event_type + event_data JSONB)
- `analytics.analytics_sessions` — session lifecycle with page_count
- `analytics.referral_sources` + `analytics.utm_tracking` — attribution
- Admin analytics dashboard — can add a "Funnels" tab

**What needs to be built:**
- Funnel definition schema (name, steps[], date filters)
- Backend endpoint: `GET /api/admin/analytics/funnels` — calculate step-by-step drop-off
- Frontend: Funnel visualization component in analytics dashboard
- Pre-built funnels: "Purchase Funnel", "Registration Funnel", "Subscription Funnel"

---

### BP2: Abandoned Cart Recovery

**Goal:** "The customer wanted to buy. Help them finish."

The infrastructure is 90% built. We have: cart tracking, abandoned_cart_events table, email delivery pipeline, campaign system, consent checking. We just need to **wire the trigger**.

**What it does:**
- Detect carts inactive for 1hr / 6hr / 24hr (configurable)
- Send timed email sequence: reminder → discount incentive → last chance
- Track recovery rate (abandoned → recovered → converted)
- Include cart contents in email with "Complete Your Purchase" CTA
- Auto-generate personalized discount codes for recovery emails
- Respect GDPR consent (marketing_email must be granted)

**Revenue lever:** Industry average recovery rate is 5-15%. On 100 abandoned carts/month, that's 5-15 additional sales for zero acquisition cost.

**Existing infrastructure:**
- `ecommerce.cart` with status field (active, abandoned, recovered, converted, expired)
- `ecommerce.abandoned_cart_events` table (cart_id, user_id, abandoned_at, reminder_count, status)
- `ecommerce.cart_items` — full cart contents available
- Email delivery pipeline (`send_email_fire_and_forget`)
- Discount code system with per-customer limits and auto-generation capability
- Order reaper already detects stale checkouts

**What needs to be built:**
- Cart abandonment detector background task (check cart updated_at vs threshold)
- `cart_abandonment.html` email template with cart items and CTA
- Recovery discount auto-generation service
- Timed email sequence (1hr, 6hr, 24hr with configurable delays)
- Recovery tracking: update abandoned_cart_events status on cart re-engagement
- Admin dashboard: recovery metrics (abandoned count, reminded count, recovered count, recovery rate)

---

### BP3: RFM Customer Segmentation + Automated Campaigns

**Goal:** "Talk to each customer segment differently."

The `customer_metrics` table already has `order_count`, `total_spent`, `last_purchase_at`, and an `rfm_segment` field. It's never calculated or used.

**What it does:**
- Calculate RFM scores nightly (Recency, Frequency, Monetary value)
- Segment customers: Champions, Loyal, At-Risk, Hibernating, Lost, New
- Trigger automated campaigns per segment:
  - **Champions**: Early access, referral program invite, VIP perks
  - **At-Risk** (no purchase in 30+ days): "We miss you" + discount
  - **New** (1 purchase): "Welcome" drip sequence with product education
  - **Hibernating** (60+ days): Win-back campaign with steep discount
  - **Lost** (90+ days): Final "come back" email, then suppress

**Revenue lever:** Targeted messaging converts 3-5x better than blast emails. A "we miss you" email to at-risk customers with a 10% coupon is the highest-ROI marketing spend.

**Existing infrastructure:**
- `ecommerce.customer_metrics` table with `order_count`, `total_spent`, `last_purchase_at`, `rfm_segment`
- `ecommerce.orders` — full order history for RFM calculation
- Marketing campaign system — audience segmentation with consent tiers
- Email delivery pipeline with consent checking
- Discount code system for personalized offers

**What needs to be built:**
- RFM scoring algorithm (background task, nightly or on-demand)
- Segment definitions (configurable thresholds for R, F, M scores)
- `GET /api/admin/analytics/segments` — segment overview with counts
- Segment-based audience filtering in `audience_service`
- Automated campaign trigger rules per segment
- Email templates: `win_back.html`, `vip_welcome.html`, `milestone.html`
- Admin UI: segment dashboard with customer counts, revenue per segment

---

### BP4: Post-Purchase Email Sequences

**Goal:** "The sale is not the end, it's the beginning."

Currently we send order confirmation and payment receipt. Then silence. This is a massive missed opportunity.

**What it does:**
- **Day 0**: Order confirmation (exists)
- **Day 3**: "How's your order?" — shipping/delivery check-in
- **Day 7**: Review request — "Rate your purchase"
- **Day 14**: Cross-sell — "Customers who bought X also liked Y"
- **Day 30**: Replenishment reminder (for consumable products)
- **Day 60**: Loyalty check-in — "You've been with us N months"

Each step is a template + trigger rule. Skippable based on consent + suppression.

**Revenue lever:** Post-purchase sequences drive 20-40% of repeat revenue in e-commerce. A single "customers also bought" email converts at 5-10%.

**Existing infrastructure:**
- `ecommerce.orders` with `created_at` for timing
- `ecommerce.order_items` with `product_snapshot` for product details
- Email delivery pipeline with fire-and-forget
- Template engine (Jinja2) with base template
- Consent checking at send time

**What needs to be built:**
- Email sequence engine (define steps: delay_days, template_id, conditions)
- Sequence runner background task (check orders, send next step)
- Templates: `delivery_checkin.html`, `review_request.html`, `cross_sell.html`, `replenishment.html`
- Sequence state tracking (which step has each order reached?)
- Admin UI: sequence editor, performance metrics per step
- Opt-out per sequence (not just global marketing opt-out)

---

### BP5: Product Recommendations Engine

**Goal:** "Show each customer what they're most likely to buy."

The recommendations module exists as a stub. We have the data to power it: page views, purchase history, cart contents, wishlists.

**What it does:**
- **"Frequently Bought Together"** — co-purchase analysis from order_items
- **"Customers Also Viewed"** — session-based page view correlation
- **"Recommended For You"** — based on browse history + purchase history
- **"Trending Now"** — most-viewed/most-purchased in last 7 days
- API endpoints for product pages, cart page, email templates
- Admin dashboard showing recommendation performance (impressions → clicks → purchases)

**Revenue lever:** Amazon attributes 35% of revenue to recommendations. Even a basic implementation can lift average order value 10-30%.

**Existing infrastructure:**
- `analytics.page_views` — browse history per user
- `analytics.events` — custom events (product_view, add_to_cart)
- `ecommerce.order_items` — purchase history with product_id
- `ecommerce.cart_items` — current cart contents
- `ecommerce.wishlists` + `wishlist_items` — saved intent
- `modules/recommendations/` — stub directory ready for implementation

**What needs to be built:**
- Co-purchase matrix computation (batch job from order_items)
- View correlation computation (batch job from page_views + events)
- `GET /api/recommendations/product/{id}` — related products
- `GET /api/recommendations/user` — personalized recommendations
- `GET /api/recommendations/trending` — popular items
- Frontend: recommendation carousel component
- Email integration: inject recommendations into post-purchase emails
- Performance tracking: impression → click → purchase attribution

---

### BP6: Loyalty & Rewards Program

**Goal:** "Give customers a reason to come back."

No loyalty system exists yet. This creates a retention flywheel.

**What it does:**
- Points system: earn points per dollar spent (configurable ratio)
- Bonus points for: first purchase, reviews, referrals, birthday
- Tier system: Bronze → Silver → Gold → Platinum (based on lifetime spend)
- Tier perks: free shipping thresholds, exclusive discounts, early access
- Points redemption: convert to store credit / discounts at checkout
- Loyalty dashboard in user profile showing points balance, tier, history
- Admin dashboard showing program metrics (enrollment rate, redemption rate, ROI)

**Revenue lever:** Loyalty members spend 12-18% more than non-members. The perceived "loss" of unredeemed points drives repeat visits.

**Existing infrastructure:**
- `ecommerce.customer_metrics` — lifetime spend, order count (basis for tier calculation)
- `ecommerce.discount_codes` — can generate loyalty reward discounts
- User dashboard — can add loyalty section
- Admin dashboard — can add loyalty metrics tab

**What needs to be built:**
- New schema: `loyalty.points_ledger`, `loyalty.tiers`, `loyalty.rewards`
- Points accrual service (hook into order completion webhook)
- Tier calculation service (nightly batch or on-demand)
- Points redemption at checkout (integrate with discount system)
- `GET /api/loyalty/balance` — user's points and tier
- `POST /api/loyalty/redeem` — convert points to discount
- Frontend: loyalty dashboard page, checkout integration
- Email templates: `points_earned.html`, `tier_upgrade.html`
- Admin: program configuration, metrics dashboard
- Toggle: `ENABLE_LOYALTY` with 4-layer gating

---

### BP7: Smart Campaign Triggers (Event-Driven Marketing)

**Goal:** "The right message at the right moment."

Currently campaigns are manual (admin creates and sends). We need **automated triggers** based on user behavior.

**What it does:**
- Define trigger rules: "When [event] happens, send [template] after [delay]"
- Built-in triggers:
  - **Welcome sequence**: Registration → Day 1, 3, 7 emails
  - **Browse abandonment**: Viewed product 3+ times without purchasing → email with product
  - **Wishlist price drop**: Product on wishlist goes on sale → notify
  - **Milestone**: 5th purchase → thank you + bonus discount
  - **Win-back**: No visit in 30 days → re-engagement email
  - **Birthday**: If DOB stored → birthday discount
- Trigger engine runs as background task, checks conditions, respects consent
- Admin UI to create/edit/enable triggers with preview

**Revenue lever:** Triggered emails have 8x higher open rates and 6x higher revenue per email than batch campaigns.

**Existing infrastructure:**
- `analytics.events` — custom event tracking
- `analytics.page_views` — browse behavior
- `ecommerce.wishlists` — saved products
- Marketing campaign system — audience + send
- Email delivery pipeline — consent + template + retry
- Background task infrastructure (asyncio)

**What needs to be built:**
- Trigger definition schema: `marketing.automation_triggers` (event_type, conditions, template_id, delay, enabled)
- Trigger evaluation engine (background task, polls events/conditions)
- Trigger execution log (prevent duplicate sends)
- `GET/POST/PUT /api/marketing/admin/triggers` — CRUD
- Frontend: trigger builder UI in admin marketing page
- Pre-built trigger templates (welcome, browse abandon, milestone)
- Toggle: can be part of `ENABLE_MARKETING` or separate `ENABLE_AUTOMATION`

---

### BP8: Conversion Rate Optimization Toolkit

**Goal:** "Test everything, assume nothing."

We have detailed analytics but no way to experiment.

**What it does:**
- **A/B testing for emails**: Split audience, different subject lines or content, measure open/click/conversion
- **Campaign performance comparison**: Which campaign drove the most revenue (not just opens)?
- **Landing page analytics**: Which entry pages convert best? (Data exists in page engagement endpoint)
- **Discount effectiveness**: Which coupon codes drove the most incremental revenue?
- **Channel attribution**: Which UTM source has the best cost-per-acquisition?

**Revenue lever:** Systematic A/B testing typically improves conversion rates 2-5% per quarter, compounding over time.

**Existing infrastructure:**
- `analytics.page_views` with entry_count and bounce_count per page
- `analytics.utm_tracking` — campaign attribution
- `marketing.campaigns` with `stats_cache` — delivery metrics
- `ecommerce.discount_codes` with `uses_count` — discount usage
- `ecommerce.orders` — revenue attribution

**What needs to be built:**
- A/B test schema: `marketing.ab_tests` (name, variants[], metric, status)
- Variant assignment service (consistent hashing by user_id)
- Revenue attribution: link campaign → discount → order → revenue
- `GET /api/admin/analytics/attribution` — channel ROI analysis
- `GET /api/admin/analytics/discount-effectiveness` — discount ROI
- Frontend: A/B test creator, results dashboard with statistical significance
- Campaign comparison view in admin marketing page

---

## Implementation Priority (Revenue Impact vs Effort)

| Priority | Process | Effort | Revenue Impact | Why This Order |
|---|---|---|---|---|
| 1 | BP2: Abandoned Cart Recovery | Low | High | 90% infrastructure exists, just wire triggers + templates |
| 2 | BP1: Conversion Funnel Engine | Medium | High | Need visibility before optimizing anything else |
| 3 | BP3: RFM Segmentation + Auto Campaigns | Medium | High | customer_metrics table exists, need calculation + triggers |
| 4 | BP4: Post-Purchase Sequences | Low | Medium | Just templates + trigger rules, email pipeline exists |
| 5 | BP7: Smart Campaign Triggers | Medium | High | Unlocks automation, makes BP3/BP4 more powerful |
| 6 | BP5: Product Recommendations | High | High | Needs new algorithms, but huge revenue lift |
| 7 | BP8: CRO Toolkit (A/B Testing) | Medium | Medium | Compounds over time, but not urgent |
| 8 | BP6: Loyalty Program | High | Medium | New schema, new UI, but powerful retention |

---

## Stripe Setup Requirements

The Stripe integration is **fully functional** for payments. What's needed for end-to-end testing:

1. **Stripe test keys** — `STRIPE_SECRET_KEY` and `STRIPE_PUBLISHABLE_KEY` set to test mode keys in `.env`
2. **Webhook endpoint** — needs public URL or Stripe CLI forwarding for `POST /webhook`
3. **Product sync** — local products need `stripe_product_id` and `stripe_price_id` populated

Once Stripe test keys are configured, the full purchase flow works: browse → cart → checkout → PaymentIntent → webhook → order complete → email.

---

## Cross-Cutting Concerns

### Data Sources Available for All BPs

| Data Source | Table/System | What It Provides |
|---|---|---|
| Page views | `analytics.page_views` | Browse behavior, time on page, entry/exit pages |
| Custom events | `analytics.events` | Add-to-cart, product views, form submissions |
| Sessions | `analytics.analytics_sessions` | Session depth, duration, device |
| User agents | `analytics.user_agents` | Device type, browser, OS |
| Referral sources | `analytics.referral_sources` | Traffic source, medium |
| UTM tracking | `analytics.utm_tracking` | Campaign attribution |
| Orders | `ecommerce.orders` + `order_items` | Purchase history, revenue |
| Cart | `ecommerce.cart` + `cart_items` | Current intent, abandonment |
| Wishlists | `ecommerce.wishlists` | Saved intent signals |
| Customer metrics | `ecommerce.customer_metrics` | Lifetime value, RFM fields |
| Email events | `gdpr.email_events` | Delivery, opens, clicks, bounces |
| Consent | `gdpr.consent_records` | Marketing permission |
| User engagement | Admin analytics enriched users | Engagement scoring (high/medium/low) |

### Toggle-First Requirements

Any new business process that has UI components must follow the 4-layer toggle pattern:

```
Layer 1: .env / config.py          → ENABLE_FEATURE=true/false
Layer 2: Backend routes             → Conditional route registration or 404
Layer 3: /api/config endpoint       → Expose flag to frontend
Layer 4: Frontend UI                → Conditional rendering via useConfig()
```

### GDPR Compliance

All email-sending business processes must:
- Check `marketing_email` consent before sending
- Check suppression status
- Include consent snapshot in email event log
- Include one-click unsubscribe link (RFC 8058)
- Respect communication type preferences where applicable
