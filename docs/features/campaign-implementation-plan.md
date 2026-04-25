# Campaign Pipeline — Staged Implementation Plan

> Master build plan for the campaign + automation system. 10 stages, each independently testable.
> Based on: architecture walkthrough (v1.0), Brevo API deep dive, provider feasibility study, campaign build architecture.

---

## Reference Documents

| Document | Location | Contains |
|----------|----------|----------|
| Architecture Walkthrough | `docs/diagrams/campaign-architecture-walkthrough.html` | Full payload flows, medium paths, attribution loop, guardrails |
| Campaign Build Architecture | `docs/features/campaign-build-architecture.md` | What exists, what to build, phase breakdown, file structure |
| Provider Feasibility | `docs/features/provider-architecture-feasibility.md` | Option D (adapter abstraction), cost analysis, interface designs |
| Brevo API Deep Dive | `docs/features/campaign-pipeline-architecture.md` | All 20 Brevo API sections, rate limits, webhooks, quotas |
| User Journey Map | `docs/diagrams/campaign-user-journey.html` | 13 stages, 97 user stories, all conditions and data flows |
| SMS/WA Plan | `~/.claude/plans/hidden-imagining-stream.md` | Notifications module detailed plan (superseded by this doc) |

---

## Architecture Decisions (Locked In)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Provider role | **Dumb delivery relay** | We manage everything; provider just sends + fires webhooks |
| Provider architecture | **Option D: Full adapter abstraction** | Ship interfaces + Console/Brevo defaults, operator picks per channel |
| Campaign management | **Our own** | Template rendering, segmentation, scheduling, A/B — all ours |
| Automation engine | **Our own state machine** | Brevo's automation API is zero (UI-only). We build the flow engine. |
| Analytics | **Our own** | Brevo can't do cross-campaign aggregation, user timelines, or multi-touch attribution |
| Attribution | **5 models, computed at report time** | Store raw touches, apply model at query time |
| Delivery pattern | **INSERT-BEFORE-SEND (F20)** | Insert recipient row before provider call to prevent webhook race |
| Email sending | **Transactional API (not Campaign API)** | `POST /v3/smtp/email` per recipient — gives us full link control for heatmaps |
| SMS sending | **`POST /v3/transactionalSMS/send`** | Brevo transactional SMS endpoint, 150 RPS |
| WhatsApp sending | **`POST /v3/whatsapp/sendMessage`** | Template-based (Meta-approved), first message must use template |

---

## Gaps to Fix First (from existing codebase audit)

These are bugs/gaps in the EXISTING code that must be fixed before building new features:

| # | Gap | Impact | Fixed In |
|---|-----|--------|----------|
| 1 | Campaign sends to zero recipients | Campaigns don't work at all | Stage 3 |
| 2 | No `campaign_recipients` table | Can't track who received what | Stage 1 |
| 3 | Opened/clicked webhooks ignored | Can't track email engagement | Stage 4 |
| 4 | Webhook payload not stored | Can't debug delivery issues | Stage 4 |
| 5 | UTM not linked to campaigns | Can't attribute site visits to campaigns | Stage 5 |
| 6 | Events not being fired | `add_to_cart`, `product_viewed` not tracked | Stage 5 |
| 7 | No engagement scoring | Can't detect "hot" non-buyers | Stage 6 |
| 8 | No funnel endpoint | No conversion visualization | Stage 7 |

---

## The 10 Stages

```
STAGE 1: Database Foundation          ← tables + schema
STAGE 2: Provider Layer               ← SMS/WA interfaces + adapters
STAGE 3: Campaign Delivery Pipeline   ← the core send engine
STAGE 4: Webhook Processing           ← receive + process provider events
STAGE 5: Attribution + Event Tagging  ← link messages to site activity
STAGE 6: Engagement Scoring           ← behavioral scoring engine
STAGE 7: Campaign Analytics           ← ⚠️ PLANNING MODE before frontend
STAGE 8: Automation Flow Engine       ← the state machine
STAGE 9: Guardrails + Admin UI        ← freq cap, quiet hours, notifications page
STAGE 10: Extended Providers + Polish ← SES, Twilio adapters
```

**Dependencies:**
```
Stage 1 ──→ Stage 2 ──→ Stage 3 ──→ Stage 4 ──→ Stage 5 ──→ Stage 6
                              │                       │            │
                              │                       ▼            ▼
                              └─────────────→ Stage 8 ──→ Stage 7
                                                          ▲
                                               Stage 9 ───┘
                                               Stage 10 (independent)
```

---

## Stage 1: Database Foundation

**Goal:** All new tables exist. Schema supports the full pipeline.
**Testable:** Migration runs, `ensure_tables.py` passes, tables queryable.
**Depends on:** Nothing.

### Deliverables

| # | What | File |
|---|------|------|
| 1.1 | Migration: notifications schema (message_log, automation_rules) | `migrations/032_notifications_schema.sql` |
| 1.2 | Migration: campaign pipeline tables (13 new + 5 modifications) | `migrations/033_campaign_pipeline.sql` |
| 1.3 | Update ensure_tables.py with all new tables | `scripts/ensure_tables.py` |
| 1.4 | Config additions (6 SMS/WA env vars) | `backend/core/config.py`, `.env.template` |
| 1.5 | Module loader: notifications → ALWAYS_ENABLED | `backend/core/module_loader.py` |
| 1.6 | Notifications module config.py | `modules/notifications/config.py` |

### New Tables (Stage 1)

```sql
-- notifications schema
notifications.message_log              -- SMS/WA send audit trail
notifications.automation_rules         -- event → channel dispatch rules

-- campaign pipeline tables
marketing.campaign_recipients          -- who received what (insert-before-send)
marketing.campaign_link_clicks         -- Layer 1: email zone clicks from webhooks
marketing.campaign_attributions        -- session-to-campaign linking
marketing.campaign_stats_summary       -- pre-aggregated funnel metrics
marketing.automation_flows             -- flow definitions
marketing.automation_flow_steps        -- steps within flows
marketing.automation_flow_connections  -- non-linear step connections
marketing.flow_enrollments             -- users currently in flows
marketing.flow_step_executions         -- log of every step executed
marketing.messaging_config             -- guardrail settings
marketing.message_pressure_log         -- per-user message count for freq capping
analytics.page_click_interactions      -- Layer 2+3: landing page clicks
analytics.engagement_scores            -- engagement scoring

-- modifications to existing tables
ALTER marketing.campaigns ADD COLUMN medium VARCHAR(20) DEFAULT 'email';
ALTER marketing.campaigns ADD COLUMN goal_event VARCHAR(100);
ALTER marketing.campaigns ADD COLUMN goal_window_days INT DEFAULT 7;
ALTER marketing.campaigns ADD COLUMN attribution_window_days INT DEFAULT 7;
ALTER marketing.campaigns ADD COLUMN enable_heatmap BOOLEAN DEFAULT false;
ALTER marketing.campaigns ADD COLUMN last_reconciled_at TIMESTAMPTZ;
ALTER marketing.campaigns ADD COLUMN reconciliation_delta JSONB;
ALTER analytics.utm_tracking ADD COLUMN campaign_id UUID;
ALTER analytics.events ADD COLUMN campaign_id UUID;
ALTER core.users ADD COLUMN phone VARCHAR(32);
ALTER core.users ADD COLUMN whatsapp_number VARCHAR(32);
```

### Config Additions

```python
# backend/core/config.py — add after enable_marketing_emails
enable_sms: bool = False
enable_whatsapp: bool = False
sms_provider: str = "console"           # console | brevo
whatsapp_provider: str = "console"      # console | brevo
brevo_sms_sender: str = "MyApp"         # 3-11 alphanumeric
brevo_whatsapp_number: str = ""         # Brevo-provisioned WA sender
```

---

## Stage 2: Provider Layer (SMS + WhatsApp)

**Goal:** Provider interfaces defined. Console + Brevo adapters work. Factory returns correct adapter.
**Testable:** `get_sms_provider()` returns ConsoleSmsAdapter. Manual test send logs to stdout.
**Depends on:** Stage 1 (config).

### Deliverables

| # | What | File |
|---|------|------|
| 2.1 | SmsProvider ABC + SmsSendResult dataclass | `modules/notifications/interfaces/sms_provider.py` |
| 2.2 | WhatsAppProvider ABC + WhatsAppSendResult dataclass | `modules/notifications/interfaces/whatsapp_provider.py` |
| 2.3 | Console SMS adapter | `modules/notifications/adapters/console_sms_adapter.py` |
| 2.4 | Console WhatsApp adapter | `modules/notifications/adapters/console_whatsapp_adapter.py` |
| 2.5 | Brevo SMS adapter | `modules/notifications/adapters/brevo_sms_adapter.py` |
| 2.6 | Brevo WhatsApp adapter | `modules/notifications/adapters/brevo_whatsapp_adapter.py` |
| 2.7 | Provider factory (get_sms_provider, get_whatsapp_provider) | `modules/notifications/adapters/__init__.py` |
| 2.8 | SMS send service (send + fire_and_forget) | `modules/notifications/services/sms_send_service.py` |
| 2.9 | WhatsApp send service | `modules/notifications/services/whatsapp_send_service.py` |
| 2.10 | Extend EmailProvider with capability properties | `modules/gdpr/interfaces/email_provider.py` |

### Brevo API Endpoints Used

| Adapter | Endpoint | Rate Limit |
|---------|----------|------------|
| Brevo SMS | `POST /v3/transactionalSMS/send` | 150 RPS |
| Brevo WA | `POST /v3/whatsapp/sendMessage` | Standard |
| Brevo Email | `POST /v3/smtp/email` (existing) | 1,000 RPS |

### Interface Design (from feasibility study)

```python
# SmsProvider ABC
send_sms(to_number, content, *, sender?, tags?) -> SmsSendResult
send_batch(messages, *, sender?) -> list[SmsSendResult]
verify_webhook(payload, signature) -> WebhookEvent

# WhatsAppProvider ABC
send_template(to_number, template_name, *, language?, parameters?, media_url?) -> WhatsAppSendResult
send_text(to_number, text) -> WhatsAppSendResult
verify_webhook(payload, signature) -> WebhookEvent
```

---

## Stage 3: Campaign Delivery Pipeline

**Goal:** Admin can send a campaign to a resolved audience via any channel. Messages are logged with INSERT-BEFORE-SEND.
**Testable:** Send campaign → campaign_recipients populated → provider called → status updated.
**Depends on:** Stage 1 (tables), Stage 2 (adapters).

### Deliverables

| # | What | File |
|---|------|------|
| 3.1 | Campaign delivery service (resolve audience → filter → render → rewrite → batch send) | `modules/marketing/services/campaign_delivery_service.py` |
| 3.2 | Link rewriting engine (UTM injection + zone params for heatmap) | `modules/marketing/services/link_rewriting_service.py` |
| 3.3 | Short URL service (for SMS tracking links) | `modules/marketing/services/short_url_service.py` |
| 3.4 | Short URL redirect route | `modules/marketing/routes/redirect_routes.py` |
| 3.5 | Campaign send API route | `modules/marketing/routes/admin_routes.py` (extend) |
| 3.6 | Campaign progress tracking (Redis) | In campaign_delivery_service.py |
| 3.7 | Campaign progress endpoint | `modules/marketing/routes/admin_routes.py` (extend) |
| 3.8 | Update /api/config with enable_sms, enable_whatsapp | `backend/main.py` |
| 3.9 | Frontend config-context additions | `frontend/lib/config-context.tsx` |

### The Send Loop (from architecture walkthrough, Section 2, Step 7)

```
For each eligible recipient (batched, 50 at a time):
  1. INSERT campaign_recipients (status='sending')        ← F20
  2. Render template (Jinja2 from DB)
  3. Rewrite links (email: UTM+zones, SMS: short URL, WA: button suffix)
  4. Call provider.send_*(to, content)
  5. UPDATE campaign_recipients (status='sent', provider_message_id=...)
  6. INSERT message_pressure_log
  7. Update Redis progress counter
```

### Recipient Filtering Pipeline (from walkthrough, Section 2, Step 3)

```
1. Channel availability (has email? has phone? has whatsapp_number?)
2. Suppression check (gdpr.email_preferences / user_communication_preferences)
3. Consent check (marketing consent for channel)
4. Already-received check (prevent duplicates on retry)
5. Sunset policy check (engagement within N days)
```

---

## Stage 4: Webhook Processing

**Goal:** Incoming webhooks from all providers update campaign_recipients. Click data stored with zone positions.
**Testable:** Send campaign → Brevo fires webhook → campaign_recipients.delivered_at populated.
**Depends on:** Stage 3 (campaign_recipients exist).

### Deliverables

| # | What | File |
|---|------|------|
| 4.1 | Expand email webhook processing (opens, clicks, bounces → campaign_recipients) | `modules/gdpr/services/webhook_processing_service.py` (extend) |
| 4.2 | Campaign link click recording (extract zone position from URL) | `modules/marketing/services/webhook_event_service.py` |
| 4.3 | Bot/proxy detection for opens (Apple MPP, corporate proxies) | In webhook_event_service.py |
| 4.4 | SMS webhook route | `modules/notifications/routes/webhook_routes.py` |
| 4.5 | WhatsApp webhook route | `modules/notifications/routes/webhook_routes.py` |
| 4.6 | Store full webhook payload | `modules/gdpr/services/webhook_processing_service.py` (fix) |
| 4.7 | Reconciliation service (pull provider stats every 6h) | `modules/marketing/services/reconciliation_service.py` |
| 4.8 | Stats summary refresh worker (every 30 min) | `modules/marketing/workers/stats_refresh_worker.py` |

### Brevo Webhook Events to Process

| Channel | Event | What We Do |
|---------|-------|-----------|
| Email | `delivered` | UPDATE campaign_recipients.delivered_at |
| Email | `opened` / `unique_opened` | UPDATE opened_at + bot check |
| Email | `click` | UPDATE clicked_at + INSERT campaign_link_clicks (with _zp zone) |
| Email | `hard_bounce` / `soft_bounce` | UPDATE status='bounced' + suppress |
| Email | `spam` | UPDATE status='complained' + suppress |
| Email | `proxy_open` | Flag as proxy (Apple MPP) |
| SMS | `delivered` | UPDATE campaign_recipients.delivered_at |
| SMS | `hard_bounce` | UPDATE status='bounced' |
| WA | `delivered` | UPDATE delivered_at |
| WA | `read` | UPDATE opened_at (reliable — blue ticks) |

### Key: Webhook field differences (from Brevo API doc)

```
Transactional email click: field name = "link"
Marketing email click:     field name = "URL"
SMS delivery:              field name = "messageId" (integer)
Email delivery:            field name = "message-id" (string with angle brackets)
```

---

## Stage 5: Attribution + Event Tagging

**Goal:** User clicks in message → arrives on site → browsing is tagged with campaign_id → conversions attributed.
**Testable:** Click email link → visit site → purchase → campaign_attributions row created.
**Depends on:** Stage 4 (clicks tracked).

### Deliverables

| # | What | File |
|---|------|------|
| 5.1 | Attribution middleware (UTM capture, cookie, session-campaign linking) | `modules/marketing/services/attribution_service.py` |
| 5.2 | Attribution middleware registration (FastAPI middleware) | `backend/main.py` or `modules/marketing/routes/__init__.py` |
| 5.3 | Campaign-attributed event tagging (tag analytics.events with campaign_id) | In attribution_service.py |
| 5.4 | Conversion recording (order completed → campaign_attributions insert) | `modules/marketing/services/conversion_service.py` |
| 5.5 | Multi-touch attribution engine (5 models, report-time computation) | `modules/marketing/services/attribution_engine.py` |
| 5.6 | Fire missing events: add_to_cart, product_viewed, checkout_abandoned | Various tracking integration points |
| 5.7 | Link UTM tracking to campaigns (campaign_id FK on utm_tracking) | In attribution_service.py |

### Attribution Flow (from walkthrough, Section 5)

```
1. User clicks link → arrives with UTM params
2. Attribution middleware:
   a. Extract UTM params + _cid + _rid from URL
   b. Set attribution cookie (_attr = {campaign_id, medium, first_touch_at, last_touch_at, touches})
   c. INSERT analytics.utm_tracking (with campaign_id FK)
3. During browsing: analytics.events tagged with campaign_id from cookie
4. On conversion: INSERT marketing.campaign_attributions with touch_sequence
5. At report time: apply attribution model (last-click, first-touch, linear, time-decay, U-shaped)
```

---

## Stage 6: Engagement Scoring

**Goal:** Every user has a computed engagement score with velocity and decay.
**Testable:** Score refresh worker runs → engagement_scores table populated → segment filters can use score.
**Depends on:** Stage 5 (events tagged with campaigns).

### Deliverables

| # | What | File |
|---|------|------|
| 6.1 | Engagement scoring service (weighted computation + velocity + decay) | `modules/marketing/services/engagement_scoring_service.py` |
| 6.2 | Engagement score refresh worker (every 30 min) | `modules/marketing/workers/engagement_refresh_worker.py` |
| 6.3 | Segment filter extension (score_above, velocity filter) | `modules/marketing/services/segment_service.py` (extend) |

### Scoring Formula (from walkthrough, Section 5)

```
score = Σ(event_weight × recency_decay × frequency_boost)

Weights: email_opened=2, clicked=5, wa_read=3, page_viewed=1,
         product_viewed=2, add_to_cart=8, purchase=20
Decay: weight × 2^(-days_since_event / 14)   (half-life = 14 days)
Boost: if 3+ actions in 7 days → 1.5x multiplier
```

---

## Stage 7: Campaign Analytics Dashboard

> **⚠️ ENTER PLANNING MODE before building the frontend for this stage.**
> The user wants to discuss the conversion funnel dashboard design interactively before implementation.
> Backend API endpoints can be built first, but STOP before the frontend page.

**Goal:** Admin sees campaign funnel, variant comparison, heatmap, revenue attribution.
**Testable:** API returns correct stats. Frontend dashboard visualizes them.
**Depends on:** Stages 4 (webhooks), 5 (attribution), 6 (scoring).

### Deliverables

| # | What | File |
|---|------|------|
| 7.1 | Campaign analytics service (funnel, variants, segments, time, revenue) | `modules/marketing/services/campaign_analytics_service.py` |
| 7.2 | Heatmap service (Layer 1 zone aggregation) | `modules/marketing/services/heatmap_service.py` |
| 7.3 | User timeline service (UNION ALL across tables per user) | `modules/marketing/services/user_timeline_service.py` |
| 7.4 | Effectiveness service (cross-campaign ranking, trends) | `modules/marketing/services/effectiveness_service.py` |
| 7.5 | Campaign analytics API routes | `modules/marketing/routes/analytics_routes.py` |
| 7.6 | User timeline API route | `modules/marketing/routes/analytics_routes.py` |
| 7.7 | Effectiveness API routes | `modules/marketing/routes/analytics_routes.py` |
| 7.8 | **⚠️ PLANNING MODE** → Campaign analytics frontend page | `frontend/app/admin/campaigns/[id]/analytics/page.tsx` |
| 7.9 | **⚠️ PLANNING MODE** → User timeline frontend component | `frontend/app/admin/users/[id]/timeline/page.tsx` |
| 7.10 | **⚠️ PLANNING MODE** → Effectiveness dashboard | `frontend/app/admin/effectiveness/page.tsx` |

### The 5 Dashboard Views (from Brevo API doc, Section "Multi-Dimensional Conversion Funnel")

```
View 1: Campaign-Level Funnel      Sent → Delivered → Opened → Clicked → Visited → Converted → Revenue
View 2: Segment/Group-Level        Compare audiences across campaigns
View 3: User-Level Timeline        Full event stream per user (campaign + site + purchase)
View 4: Cross-Campaign Attribution  All campaigns ranked by attributed revenue (5 models)
View 5: Time-Based Trends           Rolling engagement rates, conversion rates, list fatigue detection
```

---

## Stage 8: Automation Flow Engine

**Goal:** Admin can create flows, activate them, and events trigger user enrollment + step execution.
**Testable:** Register user → Welcome flow triggers → email sent → wait 2 days → branch on open → next step.
**Depends on:** Stage 3 (delivery pipeline — flow sends reuse it).

### Deliverables

| # | What | File |
|---|------|------|
| 8.1 | Flow builder service (CRUD, validation, chain cycle detection) | `modules/marketing/services/flow_builder_service.py` |
| 8.2 | Flow execution service (state machine: enroll, advance, branch, goal) | `modules/marketing/services/flow_execution_service.py` |
| 8.3 | Flow worker (background, every 60s: advance expired Waits) | `modules/marketing/workers/flow_worker.py` |
| 8.4 | Enrollment uniqueness (F21: partial unique index check-and-insert) | In flow_execution_service.py |
| 8.5 | Chain depth limit (F5: max 5, cycle detection at activation) | In flow_builder_service.py |
| 8.6 | Event trigger integration (auth, payments, cart abandonment) | Various trigger points |
| 8.7 | Segment membership check worker (every 15 min) | `modules/marketing/workers/segment_check_worker.py` |
| 8.8 | Flow CRUD API routes | `modules/marketing/routes/flow_routes.py` |
| 8.9 | Flow monitoring API routes | `modules/marketing/routes/flow_routes.py` |
| 8.10 | Starter flow templates (welcome, cart abandon, post-purchase, win-back) | Seed data in migration or service |
| 8.11 | Flow analytics service | `modules/marketing/services/flow_analytics_service.py` |
| 8.12 | Flow analytics API routes | `modules/marketing/routes/flow_routes.py` |
| 8.13 | Flow builder frontend (visual editor) | `frontend/app/admin/flows/` |
| 8.14 | Flow analytics frontend | `frontend/app/admin/flows/[id]/analytics/page.tsx` |

### Step Types (from walkthrough, Section 3)

| Type | What It Does | Advances |
|------|-------------|----------|
| `send` | Send email/SMS/WA via delivery pipeline | Immediately after send |
| `wait` | Pause for duration / until date / until event | Flow Worker picks up at resume_at |
| `branch` | Evaluate condition → route YES or NO | Immediately to chosen path |
| `split` | Random A/B assignment by weight | Immediately to assigned path |
| `update` | Tag user, set attribute, adjust score | Immediately |
| `webhook` | POST to external URL | Immediately after response |

### Event Trigger Points to Wire

| Event | Trigger Location | File |
|-------|-----------------|------|
| `user.registered` | After welcome email send | `modules/auth/routes/auth_routes.py:~168` |
| `order.completed` | After order confirmation email | `modules/payments/services/webhook_service.py:~141` |
| `cart.abandoned` | Cart abandonment check (existing or new worker) | `modules/ecommerce/services/cart_service.py` |
| `segment.entered` | Segment membership check worker | New worker |

---

## Stage 9: Guardrails + Notifications Admin UI

**Goal:** Frequency caps, quiet hours, sunset policy enforce on every send. Admin can test SMS/WA, see message log, configure guardrails.
**Testable:** Set freq cap to 1/week → send 2 campaigns → second one skipped for capped users.
**Depends on:** Stage 3 (delivery pipeline), Stage 8 (flow sends).

### Deliverables

| # | What | File |
|---|------|------|
| 9.1 | Guardrails service (frequency cap, quiet hours, sunset, fatigue) | `modules/marketing/services/guardrails_service.py` |
| 9.2 | Integrate guardrails into delivery pipeline | `modules/marketing/services/campaign_delivery_service.py` (extend) |
| 9.3 | Sunset policy check worker (daily) | `modules/marketing/workers/sunset_worker.py` |
| 9.4 | Notifications admin routes (test-sms, test-whatsapp, message-log, automation-rules) | `modules/notifications/routes/admin_routes.py` |
| 9.5 | Notifications routes __init__.py | `modules/notifications/routes/__init__.py` |
| 9.6 | Automation service (fire_notification_event for simple event→channel dispatch) | `modules/notifications/services/automation_service.py` |
| 9.7 | Guardrails config API (GET/PUT messaging_config) | In notifications admin routes |
| 9.8 | Message pressure dashboard endpoint | In notifications admin routes |
| 9.9 | Admin layout: add Notifications nav item | `frontend/app/admin/layout.tsx` |
| 9.10 | Notifications admin page (test send, message log, automation rules, guardrails config) | `frontend/app/admin/notifications/page.tsx` |

### Guardrails Check Order (from walkthrough, Section 6)

```
1. Consent check → SKIP if no consent
2. Suppression check → SKIP if suppressed
3. Frequency cap → SKIP if over cap
4. Quiet hours → DEFER to morning
5. Sunset policy → SKIP if inactive
6. Fatigue detection → SKIP or reduce frequency
```

---

## Stage 10: Extended Providers + Polish

**Goal:** Operators can use SES for email and Twilio for SMS/WA. All formatters pass. Build clean.
**Testable:** Set `EMAIL_PROVIDER=ses` → emails send via SES. Set `SMS_PROVIDER=twilio` → SMS via Twilio.
**Depends on:** Stage 2 (interfaces defined).

### Deliverables

| # | What | File |
|---|------|------|
| 10.1 | SES email adapter | `modules/gdpr/adapters/ses_adapter.py` |
| 10.2 | Twilio SMS adapter | `modules/notifications/adapters/twilio_sms_adapter.py` |
| 10.3 | Twilio WhatsApp adapter | `modules/notifications/adapters/twilio_whatsapp_adapter.py` |
| 10.4 | SendGrid email adapter | `modules/gdpr/adapters/sendgrid_adapter.py` |
| 10.5 | Provider setup documentation | `docs/guides/provider-setup.md` |
| 10.6 | Black formatting pass | All Python files |
| 10.7 | Next.js build verification | `npx next build` |
| 10.8 | Update ARCHITECTURE.md with new schemas, interfaces, workers | `docs/ARCHITECTURE.md` |

---

## Build Order Summary

| Stage | What | New Files | Est. Effort | Provider Needed? |
|-------|------|-----------|-------------|-----------------|
| 1 | Database Foundation | 3 migrations, config updates | 1 day | No |
| 2 | Provider Layer | 10 files (interfaces, adapters, services) | 2 days | No (Console only) |
| 3 | Campaign Delivery Pipeline | 7 files (delivery service, link rewriting, routes) | 3-4 days | Yes (sends) |
| 4 | Webhook Processing | 5 files (webhook expansion, reconciliation, worker) | 2-3 days | Yes (webhooks) |
| 5 | Attribution + Event Tagging | 6 files (middleware, conversion, attribution engine) | 3-4 days | No |
| 6 | Engagement Scoring | 3 files (service, worker, segment extension) | 1-2 days | No |
| 7 | Campaign Analytics | 7+ files (services, routes, **⚠️ PLANNING MODE** for frontend) | 5-7 days | No |
| 8 | Automation Flow Engine | 14 files (state machine, workers, routes, frontend) | 6-8 days | Yes (flow sends) |
| 9 | Guardrails + Admin UI | 8 files (guardrails, admin routes, frontend) | 3-4 days | No |
| 10 | Extended Providers | 5 files (SES, Twilio, SendGrid, docs) | 3-4 days | New providers |
| **Total** | | **~70 files** | **~30-40 days** | |

---

## Key Brevo API Integration Points

### What We Call (Our App → Brevo)

| When | Endpoint | Rate Limit | Notes |
|------|----------|------------|-------|
| Send email | `POST /v3/smtp/email` | 1,000 RPS | Per-recipient transactional send (NOT campaign API) |
| Send SMS | `POST /v3/transactionalSMS/send` | 150 RPS | Per-recipient |
| Send WhatsApp | `POST /v3/whatsapp/sendMessage` | Standard | Template-based, first msg must be template |
| Pull campaign stats | `GET /v3/emailCampaigns/{id}` | 100 RPH | Reconciliation only, every 6h |
| Pull SMS stats | `GET /v3/transactionalSMS/statistics/events` | Standard | Reconciliation |

### What Brevo Calls (Brevo → Our App)

| Webhook | Our Endpoint | What We Do |
|---------|-------------|-----------|
| Email delivered/opened/clicked/bounced | `POST /api/gdpr/webhooks/email` | Update campaign_recipients |
| SMS delivered/bounced | `POST /api/notifications/webhooks/sms` | Update campaign_recipients |
| WA delivered/read | `POST /api/notifications/webhooks/whatsapp` | Update campaign_recipients |

### What We Do NOT Use from Brevo

| Brevo Feature | Why We Skip It |
|--------------|---------------|
| `POST /v3/emailCampaigns` (Campaign API) | We manage campaigns ourselves. Campaign API requires contacts in Brevo + controls link rewriting (blocks our heatmap zones). |
| Brevo Contacts / Lists | We manage our own user DB. No sync needed since we use transactional API. |
| Brevo Segments | API is read-only. We have our own 30+ filter segmentation engine. |
| Brevo Automations | Zero API (UI-only). We build our own flow engine. |
| Brevo Revenue Attribution | Fixed 48hr last-click only. We build 5-model attribution. |
| `POST /v3/events` (push events to Brevo) | No benefit — we don't use Brevo automations or reporting. |
| `POST /v3/orders/status` (push orders to Brevo) | No benefit — Brevo's attribution is too limited. |

---

## Reminders & Notes

1. **⚠️ PLANNING MODE** before building the conversion funnel frontend (Stage 7.8-7.10). The user wants to discuss dashboard design interactively before implementation.

2. **Console-first development.** Stages 1-2 work entirely with Console adapters (log to stdout). No Brevo key needed for initial development.

3. **Each stage is independently testable.** Don't move to the next stage until the current one works end-to-end.

4. **The delivery pipeline (Stage 3) is the most critical.** Both campaigns and automations route through it. Get it right.

5. **Background workers** (stats refresh, flow worker, engagement scoring, sunset check, segment check, reconciliation) should be registerable as FastAPI startup tasks with configurable intervals.

---

*Generated 2026-04-25 — Campaign Implementation Plan v1.0*
