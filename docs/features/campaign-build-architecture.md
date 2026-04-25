# Campaign Pipeline — Full Build Architecture

> How we build the 13-stage, 97-story campaign pipeline. Workflows, dependencies, provider boundaries, build phases, and what goes where.

---

## The Core Insight

Out of 13 stages, only **2 require provider APIs** for core functionality (Stage 3: send, Stage 11: flow sends). Stage 4 needs provider webhooks. Everything else is our own DB, our own logic, our own analytics.

```
PROVIDER-DEPENDENT (3 stages):     OUR APP ONLY (10 stages):
  Stage 3:  Send email/SMS/WA       Stage 1:  Audience Discovery
  Stage 4:  Receive webhooks         Stage 2:  Campaign Creation
  Stage 11: Flow sends               Stage 5:  Website Attribution
                                     Stage 6:  On-Site Tracking
PROVIDER-OPTIONAL (1 stage):         Stage 7:  Campaign Analytics
  Stage 7:  Stats pull (enrichment)  Stage 8:  User Timeline
                                     Stage 9:  Effectiveness
                                     Stage 10: Flow Builder
                                     Stage 12: Flow Analytics
                                     Stage 13: Guardrails
```

The provider is a **delivery relay + webhook source**. The adapter interface is narrow: `send()` + `verify_webhook()` + optional `get_campaign_stats()`.

---

## What Already Exists (Built)

| Component | Status | Location |
|-----------|--------|----------|
| Audience segmentation engine (30+ filter types) | Complete | `modules/marketing/services/segment_service.py` |
| Campaign CRUD + A/B variants | Complete | `modules/marketing/services/campaign_service.py` |
| Email template engine (Jinja2 + DB storage) | Complete | `modules/gdpr/services/template_service.py` + `marketing/services/template_crud_service.py` |
| Email sending (transactional + marketing) | Complete | `modules/gdpr/services/email_send_service.py` |
| EmailProvider ABC + Brevo adapter | Complete | `modules/gdpr/interfaces/email_provider.py` + `adapters/brevo_adapter.py` |
| Console email adapter (dev) | Complete | `modules/gdpr/adapters/console_adapter.py` |
| Provider factory (config-driven) | Complete | `modules/gdpr/adapters/__init__.py` |
| Webhook route (Brevo signature verify) | Complete | `modules/gdpr/routes/webhook_routes.py` |
| Email audit trail (GDPR) | Complete | `gdpr.email_events` table |
| Consent + suppression management | Complete | `gdpr.email_preferences` + `gdpr.consent_records` |
| UTM tracking capture | Complete | `analytics.utm_tracking` table |
| Event tracking (product_viewed, add_to_cart, etc.) | Complete | `analytics.events` + `modules/tracking/services/event_service.py` |
| Customer metrics + RFM segments | Complete | `ecommerce.customer_metrics` |
| Payment webhooks (Stripe) | Complete | `modules/payments/services/webhook_service.py` |
| Abandoned cart tracking | Complete | `ecommerce.abandoned_cart_events` |
| Audience groups + presets | Complete | `marketing.audience_groups` + `marketing.audience_group_presets` |
| Communication type preferences | Complete | `marketing.communication_types` + `marketing.user_communication_preferences` |
| Retry queue (Redis) | Complete | `modules/gdpr/services/retry_service.py` |
| Module loader + feature toggles | Complete | `backend/core/module_loader.py` + `config.py` |
| Notifications module scaffold | Empty | `modules/notifications/` (gitkeep files only) |

---

## What Needs to Be Built

### New Database Tables (13 tables + 5 table modifications)

```sql
-- NEW TABLES
marketing.campaign_recipients          -- Who received what (insert-before-send)
marketing.campaign_link_clicks         -- Layer 1: email zone clicks from webhooks
marketing.campaign_attributions        -- Session-to-campaign linking
marketing.campaign_stats_summary       -- Pre-aggregated funnel metrics (30min refresh)
marketing.automation_flows             -- Flow definitions
marketing.automation_flow_steps        -- Steps within flows
marketing.automation_flow_connections  -- Non-linear step connections
marketing.flow_enrollments             -- Users currently in flows (runtime state)
marketing.flow_step_executions         -- Log of every step executed
marketing.messaging_config             -- Guardrail settings (freq cap, quiet hours, sunset)
marketing.message_pressure_log         -- Per-user message count for freq capping
analytics.page_click_interactions      -- Layer 2+3: landing page click coords (JS tracker)
analytics.engagement_scores            -- Engagement scoring with velocity + decay

-- MODIFIED TABLES
marketing.campaigns                    -- +attribution_window_days, +enable_heatmap, +medium, +goal_*, +last_reconciled_at
analytics.utm_tracking                 -- +campaign_id FK
analytics.events                       -- +campaign_id (nullable)
gdpr.email_webhook_events              -- +is_bot, +is_proxy flags
marketing.campaign_recipients          -- +flow_id, +flow_step_id (nullable)
```

### New Backend Services (~15 services)

| Service | Stage | Purpose |
|---------|-------|---------|
| `campaign_delivery_service.py` | 3 | Resolve audience, insert recipients, send via provider, track progress |
| `webhook_event_service.py` | 4 | Process open/click/bounce webhooks into campaign_recipients + campaign_link_clicks |
| `heatmap_service.py` | 4 | Link rewriting (zone params), mirror page rendering, aggregation |
| `attribution_service.py` | 5 | UTM detection middleware, cookie management, session-campaign linking |
| `engagement_scoring_service.py` | 6,8 | Weighted score computation with velocity + decay |
| `campaign_analytics_service.py` | 7 | Funnel queries, stats summary refresh, variant comparison |
| `user_timeline_service.py` | 8 | UNION ALL timeline query across all tables per user |
| `effectiveness_service.py` | 9 | Cross-campaign comparison, multi-touch attribution engine |
| `flow_builder_service.py` | 10 | Flow CRUD, validation, chain cycle detection |
| `flow_execution_service.py` | 11 | State machine: enrollment, step progression, goal checking |
| `flow_worker.py` | 11 | Background worker: advance Wait steps every 60s |
| `flow_analytics_service.py` | 12 | Per-flow funnels, step metrics, time-to-goal |
| `guardrails_service.py` | 13 | Frequency cap, quiet hours, sunset policy, fatigue detection |
| `reconciliation_service.py` | 4,7 | Pull provider stats every 6h, backfill missed webhooks |
| `stats_refresh_worker.py` | 7 | Refresh campaign_stats_summary every 30min |

### New Provider Interfaces + Adapters

| Interface | Methods | Adapters to Ship |
|-----------|---------|-----------------|
| `SmsProvider` (ABC) | `send_sms()`, `send_batch()`, `verify_webhook()` | Console, Brevo |
| `WhatsAppProvider` (ABC) | `send_template()`, `send_text()`, `verify_webhook()` | Console, Brevo |
| `EmailProvider` (extend) | +`supports_campaign_stats`, +`supports_click_tracking` | Already exists |

### New API Routes (~25 endpoints)

| Route Group | Endpoints | Stage |
|-------------|-----------|-------|
| Campaign delivery | POST send, GET progress | 3 |
| Webhook ingestion | POST /webhooks/email, /webhooks/sms, /webhooks/whatsapp | 4 |
| Campaign analytics | GET funnel, heatmap, variants, segments, timeline, revenue | 7 |
| User timeline | GET /users/{id}/timeline, /users/{id}/engagement | 8 |
| Effectiveness | GET cross-campaign, attribution, trends | 9 |
| Automation flows | CRUD flows, steps, activate/pause, clone | 10 |
| Flow monitoring | GET enrollments, step-stats, active-users | 11,12 |
| Guardrails config | GET/PUT frequency-cap, quiet-hours, sunset, pressure-dashboard | 13 |
| Notifications test | POST test-sms, test-whatsapp, GET message-log | SMS/WA |

### New Frontend Pages (~6 pages)

| Page | Stage |
|------|-------|
| Campaign Analytics Dashboard (funnel, heatmap, variants, segments) | 7 |
| User Profile Timeline | 8 |
| Effectiveness Dashboard (cross-campaign, attribution models, trends) | 9 |
| Automation Flow Builder (visual editor) | 10 |
| Flow Analytics Dashboard | 12 |
| Notifications Admin (SMS/WA test sends, message log, guardrail config) | 13, SMS/WA |

### Background Jobs (6 workers)

| Worker | Interval | Stage |
|--------|----------|-------|
| Flow Worker | 60 seconds | 11 |
| Stats Refresh | 30 minutes + on-demand | 7 |
| Webhook Reconciliation | 6 hours | 4 |
| Engagement Score Refresh | 30 minutes | 6,8 |
| Segment Membership Check | 15 minutes | 10,11 |
| Sunset Policy Check | Daily | 13 |

---

## Stage Dependency Graph

```
                    ┌─────────────────────┐
                    │ STAGE 13: Guardrails │ (config tables, no data deps)
                    │ freq cap, quiet hrs  │
                    └──────────┬──────────┘
                               │ gates
     ┌────────────┐            │            ┌────────────┐
     │ STAGE 1    │            │            │ STAGE 2    │
     │ Audience   │────────────┼───────────→│ Campaign   │
     │ Discovery  │            │            │ Creation   │
     └────────────┘            │            └─────┬──────┘
           ↑                   │                  │
           │                   ▼                  ▼
           │            ┌─────────────┐    ┌─────────────┐
           │            │ STAGE 3     │←───│ STAGE 10    │
           │            │ Delivery    │    │ Flow Builder│
           │            │ [PROVIDER]  │    └──────┬──────┘
           │            └──────┬──────┘           │
           │                   │                  │
           │                   ▼                  ▼
           │            ┌─────────────┐    ┌─────────────┐
           │            │ STAGE 4     │    │ STAGE 11    │
           │            │ Interaction │    │ Flow Engine │
           │            │ [WEBHOOKS]  │    │ [PROVIDER]  │
           │            └──────┬──────┘    └──────┬──────┘
           │                   │                  │
           │                   ▼                  │
           │            ┌─────────────┐           │
           │            │ STAGE 5     │           │
           │            │ Attribution │           │
           │            └──────┬──────┘           │
           │                   │                  │
           │                   ▼                  │
           │            ┌─────────────┐           │
           │            │ STAGE 6     │           │
           │            │ On-Site     │           │
           │            └──────┬──────┘           │
           │                   │                  │
           │         ┌─────────┴─────────┐        │
           │         ▼                   ▼        │
           │  ┌─────────────┐    ┌─────────────┐  │
           │  │ STAGE 7     │    │ STAGE 8     │  │
           │  │ Campaign    │    │ User        │  │
           │  │ Analytics   │    │ Timeline    │  │
           │  └──────┬──────┘    └─────────────┘  │
           │         │                            │
           │         ▼                            ▼
           │  ┌─────────────┐            ┌─────────────┐
           └──│ STAGE 9     │            │ STAGE 12    │
     feedback │ Effective-  │            │ Flow        │
              │ ness        │            │ Analytics   │
              └─────────────┘            └─────────────┘
```

---

## Build Phases (5 Phases)

### Phase A: Foundation (DB + Provider Interfaces)
**Goal:** All tables exist, all interfaces defined, console adapters work.
**Provider dependency:** None (Console adapters only).
**Can test:** Schema migrations run, factories return Console adapters.

| # | Deliverable | Files | Stories Covered |
|---|------------|-------|-----------------|
| A1 | Migration: campaign pipeline tables (13 new + 5 modifications) | `migrations/033_campaign_pipeline.sql` | — |
| A2 | Migration: update ensure_tables.py | `scripts/ensure_tables.py` | — |
| A3 | SmsProvider + WhatsAppProvider ABCs | `modules/notifications/interfaces/sms_provider.py`, `whatsapp_provider.py` | — |
| A4 | Console SMS + Console WA adapters | `modules/notifications/adapters/console_sms_adapter.py`, `console_whatsapp_adapter.py` | — |
| A5 | Provider factories (SMS + WA) | `modules/notifications/adapters/__init__.py` | — |
| A6 | Config additions (6 new env vars) | `backend/core/config.py`, `.env.template` | — |
| A7 | Module loader: add notifications to ALWAYS_ENABLED | `backend/core/module_loader.py` | — |
| A8 | /api/config: expose enable_sms, enable_whatsapp | `backend/main.py` | — |
| A9 | Frontend config: add 2 flags | `frontend/lib/config-context.tsx` | — |
| A10 | Extend EmailProvider: add capability properties | `modules/gdpr/interfaces/email_provider.py` | — |

**Estimated effort:** 2-3 days

---

### Phase B: Campaign Delivery Pipeline (Stages 3 + 4 + 13-config)
**Goal:** Admin can send a campaign to an audience, webhooks are processed, guardrails gate sends.
**Provider dependency:** EmailProvider (exists), SmsProvider, WhatsAppProvider.
**Can test:** Send campaign → recipients logged → webhooks processed → stats visible.

| # | Deliverable | Stories Covered | Dependencies |
|---|------------|-----------------|--------------|
| B1 | Guardrails config service (messaging_config CRUD, message_pressure_log updates) | US-13.1, 13.2, 13.5 | A1 |
| B2 | Guardrails admin routes (GET/PUT config endpoints) | US-13.1, 13.2 | B1 |
| B3 | Campaign delivery service (resolve audience → insert-before-send → send via provider → track progress) | US-3.1, 3.2, 3.3, 3.5 | A1, A3, A5, B1 |
| B4 | Link rewriting engine (UTM injection + zone param insertion for heatmap) | US-3.4, 4.3a | B3 |
| B5 | Webhook event service (process delivery/open/click/bounce into campaign_recipients + campaign_link_clicks) | US-4.1, 4.2, 4.4, 4.5, 4.6, 4.7 | A1, B3 |
| B6 | Expanded webhook routes (email + SMS + WhatsApp webhook endpoints) | US-4.1, 4.2 | B5, A3 |
| B7 | Reconciliation service (pull provider stats every 6h, backfill) | F10 | B5 |
| B8 | Campaign send API route (POST /admin/campaigns/{id}/send with medium support) | US-3.1-3.5 | B3 |
| B9 | Real-time delivery progress endpoint (GET /admin/campaigns/{id}/progress) | US-3.5 | B3, B5 |
| B10 | Brevo SMS + Brevo WA adapters | — | A3, A5 |
| B11 | Frequency cap + quiet hours enforcement in delivery service | US-13.1, 13.2, 13.7 | B1, B3 |
| B12 | Sunset policy check (daily worker) | US-13.3 | B1 |
| B13 | Auto-exclude converted users logic | US-13.10 | B3, B5 |

**Estimated effort:** 5-7 days

---

### Phase C: Attribution + Analytics (Stages 5 + 6 + 7 + 8 + 9)
**Goal:** Full conversion funnel visible. User timelines work. Cross-campaign comparison. Attribution models.
**Provider dependency:** None (all our DB). Optional stats pull for enrichment.
**Can test:** Click through from campaign → site visit attributed → purchase tracked → funnel shows end-to-end.

| # | Deliverable | Stories Covered | Dependencies |
|---|------------|-----------------|--------------|
| C1 | Attribution service (UTM middleware, cookie, session-campaign linking) | US-5.1, 5.2, 5.3, 5.4, 5.5 | B3 |
| C2 | Campaign-attributed event tagging (tag analytics.events with campaign_id) | US-6.1-6.5 | C1 |
| C3 | Attribution window per-user adjustment | US-6.6 | C1 |
| C4 | Engagement scoring service (weighted computation + velocity + decay) | US-8.3 | A1 |
| C5 | Engagement score refresh worker (every 30 min) | US-8.3 | C4 |
| C6 | Campaign stats summary table + refresh worker (every 30 min + on-demand) | F24, US-7.1 | B5 |
| C7 | Campaign analytics service (funnel, variants, segments, time distribution, revenue) | US-7.1-7.8 | C6 |
| C8 | Heatmap service (Layer 1 aggregation from campaign_link_clicks, Layer 2+3 from page_click_interactions) | US-4.3a-d, 7.2 | B4, B5 |
| C9 | Mirror page route + JS click tracker | US-4.3b | B4 |
| C10 | User timeline service (UNION ALL query, engagement graph) | US-8.1-8.5 | B5, C1, C4 |
| C11 | Multi-touch attribution engine (5 models, report-time computation) | US-9.2, 9.4 | C1 |
| C12 | Effectiveness service (cross-campaign ranking, trend lines, cohort analysis) | US-9.1, 9.3 | C6, C11 |
| C13 | Campaign analytics API routes | US-7.1-7.8 | C7, C8 |
| C14 | User timeline API route | US-8.1-8.5 | C10 |
| C15 | Effectiveness API routes | US-9.1-9.4 | C12 |
| C16 | Campaign audience engagement filters (US-1.8, US-1.9) | US-1.8, 1.9 | B5, C1 |
| C17 | Campaign analytics frontend page | US-7.1-7.8 | C13 |
| C18 | User timeline frontend component | US-8.1-8.5 | C14 |
| C19 | Effectiveness frontend dashboard | US-9.1-9.4 | C15 |
| C20 | Fatigue detection + deliverability health alerts | US-13.4, 13.9 | B5, C6 |
| C21 | Message pressure dashboard endpoint | US-13.7 | B11 |
| C22 | Dynamic content blocks in templates | US-13.8 | Existing template engine |
| C23 | Send time optimization (own model from historical open data) | US-13.6 | B5, C6 |

**Estimated effort:** 8-12 days

---

### Phase D: Automation Engine (Stages 10 + 11 + 12)
**Goal:** Admin can build, activate, and monitor multi-step flows. Flows fire on events.
**Provider dependency:** Same as Phase B (sends route through delivery pipeline).
**Can test:** Register user → Welcome flow triggers → Email sent → Wait 2 days → Branch on open → Next email.

| # | Deliverable | Stories Covered | Dependencies |
|---|------------|-----------------|--------------|
| D1 | Flow builder service (CRUD, validation, chain cycle detection) | US-10.1-10.9 | A1 |
| D2 | Flow builder API routes (CRUD, activate/pause/clone) | US-10.1-10.12 | D1 |
| D3 | Flow chaining logic (exit tag → trigger next, depth limit, cycle check) | US-10.10, F5 | D1 |
| D4 | Flow execution service (state machine: enroll, advance, branch, goal check) | US-11.1-11.6 | D1, B3 |
| D5 | Enrollment uniqueness constraint + check-and-insert | F21, US-11.1 | D4 |
| D6 | Flow worker (background, every 60s: advance expired Waits) | US-11.3 | D4 |
| D7 | Flow sends route through Stage 3 delivery pipeline | US-11.2 | D4, B3 |
| D8 | Consent + frequency cap enforcement in flow execution | US-11.6, 11.7 | D4, B1, B11 |
| D9 | Flow chaining execution (exit → enroll in next flow) | US-11.8 | D3, D4 |
| D10 | Segment membership check worker (every 15min for segment triggers) | US-10.1 (segment trigger) | D4 |
| D11 | Event trigger integration points (auth registration, order completion, cart abandonment) | US-10.1 (event trigger) | D4 |
| D12 | Flow analytics service (per-flow funnel, step metrics, time-to-goal, revenue) | US-12.1-12.6 | D4, C7 |
| D13 | Flow analytics API routes | US-12.1-12.6 | D12 |
| D14 | Starter flow templates (7 templates: welcome, cart abandon, post-purchase, win-back, browse abandon, momentum surge, review/NPS) | — | D1 |
| D15 | Flow builder frontend page (visual editor, step diagram) | US-10.11 | D2 |
| D16 | Flow analytics frontend dashboard | US-12.1-12.6 | D13 |

**Estimated effort:** 8-10 days

---

### Phase E: Extended Providers + Polish
**Goal:** Operators can swap email providers. Twilio SMS/WA available.
**Provider dependency:** New adapters for SES, Twilio, SendGrid.

| # | Deliverable | Stories Covered | Dependencies |
|---|------------|-----------------|--------------|
| E1 | SES email adapter (send, batch, suppression sync, SNS webhook handler) | — | A10 |
| E2 | SES setup documentation (domain verification, SNS topics, IAM) | — | E1 |
| E3 | Twilio SMS adapter | — | A3 |
| E4 | Twilio WhatsApp adapter | — | A3 |
| E5 | SendGrid email adapter | — | A10 |
| E6 | Notifications admin frontend (test sends, message log, automation rules) | — | B10, E3 |
| E7 | Provider capability detection in delivery service (auto-fallback for stats, STO, etc.) | — | A10, B3 |

**Estimated effort:** 5-7 days

---

## Total Build Scope

| Phase | Stages | Days (estimated) | Provider Dependent? |
|-------|--------|-------------------|---------------------|
| A: Foundation | Schema + Interfaces | 2-3 | No |
| B: Delivery Pipeline | 3, 4, 13 (partial) | 5-7 | Yes (send + webhooks) |
| C: Attribution + Analytics | 5, 6, 7, 8, 9, 13 (rest) | 8-12 | No (optional stats pull) |
| D: Automation Engine | 10, 11, 12 | 8-10 | Yes (flow sends reuse Phase B) |
| E: Extended Providers | Provider adapters | 5-7 | New providers |
| **Total** | **All 13 stages** | **28-39 days** | |

---

## Provider Boundary: What Each Adapter Must Implement

### EmailProvider (existing ABC — extend)

```
REQUIRED (all adapters):
  send_email(to_email, subject, html_content, ...) -> SendResult
  send_batch(recipients, subject, html_content, ...) -> list[SendResult]
  sync_suppression(suppressed_emails) -> SyncResult
  verify_webhook(payload, signature) -> WebhookEvent

OPTIONAL (provider-dependent):
  create_campaign(name, subject, html_content, ...) -> CampaignResult
  get_campaign_stats(provider_campaign_id) -> CampaignStats

CAPABILITY PROPERTIES (new):
  supports_campaign_stats: bool    # Brevo=True, SES=False
  supports_click_tracking: bool    # All=True (via config set for SES)
  supports_open_tracking: bool     # All=True (via config set for SES)
```

**What our app does regardless of provider:**
- Audience resolution (SQL against our DB)
- campaign_recipients INSERT-BEFORE-SEND (our table)
- Link rewriting with UTM + zone params (our logic, before handing HTML to provider)
- A/B variant splitting (our logic, send different content per variant)
- Consent/suppression filtering (our DB check)
- Campaign stats summary (our pre-aggregation, not provider's dashboard)
- Reconciliation (compare our aggregates against provider's, if available)

### SmsProvider (new ABC)

```
REQUIRED:
  send_sms(to_number, content, sender?, tags?) -> SmsSendResult
  send_batch(messages, sender?) -> list[SmsSendResult]
  verify_webhook(payload, signature) -> WebhookEvent

OPTIONAL:
  get_message_status(provider_message_id) -> str
```

### WhatsAppProvider (new ABC)

```
REQUIRED:
  send_template(to_number, template_name, language?, parameters?, media_url?) -> WhatsAppSendResult
  send_text(to_number, text) -> WhatsAppSendResult
  verify_webhook(payload, signature) -> WebhookEvent
```

---

## Workflow: How a Campaign Send Actually Works

### One-Off Campaign (Email)

```
ADMIN clicks "Send Campaign"
  │
  ▼
1. campaign_delivery_service.send_campaign(campaign_id)
  │
  ├─ a. Load campaign + variants + segments from marketing.campaigns
  ├─ b. Resolve segments → user_ids (segment_service.compute_segment_users)
  ├─ c. Filter: remove suppressed, unverified, no-consent, no-email
  ├─ d. Check guardrails: frequency cap, quiet hours per user
  │     └─ guardrails_service.check_send_eligibility(user_id, channel)
  │        └─ Query message_pressure_log → skip or delay if over cap
  ├─ e. Assign variant per user (by weight percentage)
  ├─ f. Render template per variant (template_service.render_template_db)
  ├─ g. Rewrite links: inject UTM params + zone position IDs (heatmap_service)
  │
  ▼
2. For each eligible recipient (batched):
  │
  ├─ a. INSERT campaign_recipients (status='sending') ← F20: INSERT-BEFORE-SEND
  ├─ b. Call provider: email_provider.send_email(to_email, subject, html)
  ├─ c. UPDATE campaign_recipients SET status='sent', provider_message_id=...
  ├─ d. UPDATE message_pressure_log (increment count for this user+channel)
  │
  ▼
3. Provider fires webhooks (async, minutes to hours later):
  │
  ├─ delivered → UPDATE campaign_recipients.delivered_at
  ├─ opened → UPDATE campaign_recipients.opened_at, INSERT campaign_link_clicks (if proxy → flag)
  ├─ click → INSERT campaign_link_clicks (URL, zone position, is_bot check)
  ├─ bounced → UPDATE campaign_recipients.status='bounced', update suppression
  │
  ▼
4. Every 30 min: Stats Refresh Worker
  │
  └─ REFRESH campaign_stats_summary (aggregate from campaign_recipients)
  │
  ▼
5. Every 6 hours: Reconciliation Worker
  │
  └─ IF provider.supports_campaign_stats:
       Pull provider stats, compare against our aggregates, backfill gaps
```

### Automation Flow Execution

```
EVENT fires (e.g., user.registered)
  │
  ▼
1. flow_execution_service.handle_event("user.registered", user_id)
  │
  ├─ Query: SELECT * FROM automation_flows
  │         WHERE trigger_type='event' AND trigger_config->>'event_name'='user.registered'
  │         AND status='active'
  │
  ├─ For each matching flow:
  │   ├─ Check: enrollment uniqueness (F21 — partial unique index)
  │   ├─ Check: re-entry policy (never / after N days / always)
  │   ├─ Check: chain depth limit (F5 — max 5)
  │   ├─ INSERT flow_enrollments (flow_id, user_id, status='active', current_step_id=first_step)
  │   └─ Execute first step immediately
  │
  ▼
2. execute_step(enrollment_id, step)
  │
  ├─ CASE step.type:
  │   │
  │   ├─ 'send':
  │   │   ├─ Check consent (US-11.6)
  │   │   ├─ Check frequency cap (US-11.7)
  │   │   ├─ Check quiet hours
  │   │   ├─ Route through Stage 3 delivery pipeline (same as campaign send)
  │   │   ├─ INSERT flow_step_executions (status='executed')
  │   │   └─ Check goal → if met, exit flow (status='goal_completed')
  │   │
  │   ├─ 'wait':
  │   │   ├─ Calculate resume_at from config (hours/days/"next weekday at 10am")
  │   │   ├─ INSERT flow_step_executions (status='waiting', resume_at=...)
  │   │   └─ (Flow Worker picks up when resume_at <= NOW())
  │   │
  │   ├─ 'branch':
  │   │   ├─ Evaluate condition (opened email? clicked? visited page? score > N?)
  │   │   ├─ Route to YES or NO path (if condition unevaluable → ELSE path)
  │   │   ├─ INSERT flow_step_executions (result={'branch': 'yes'|'no'})
  │   │   └─ Execute next step on chosen path
  │   │
  │   ├─ 'split':
  │   │   ├─ Random assignment by weight (50/50, 70/30, etc.)
  │   │   ├─ INSERT flow_step_executions (result={'path': 'A'|'B'})
  │   │   └─ Execute next step on assigned path
  │   │
  │   ├─ 'update':
  │   │   ├─ Apply action (tag user, update attribute, adjust score)
  │   │   ├─ INSERT flow_step_executions (status='executed')
  │   │   └─ Advance to next step
  │   │
  │   └─ 'webhook':
  │       ├─ POST to configured URL with user data
  │       ├─ INSERT flow_step_executions (result={response})
  │       └─ Advance to next step
  │
  ├─ After every step: Check flow Goal
  │   └─ If goal met → UPDATE enrollment status='goal_completed'
  │
  ├─ After every step: Check flow Timeout
  │   └─ If enrolled_at + timeout_days < NOW() → UPDATE status='timed_out'
  │
  └─ On flow exit: Check chaining
      └─ If exit_tag matches another flow's trigger → enroll in next flow
         (with chain_depth+1, chain_origin_flow_id)

BACKGROUND: Flow Worker (every 60 seconds)
  │
  └─ SELECT e.* FROM flow_enrollments e
     JOIN flow_step_executions fse ON fse.enrollment_id = e.id
     WHERE e.status = 'active'
       AND fse.status = 'waiting'
       AND fse.resume_at <= NOW()
     │
     └─ For each: execute_step(enrollment_id, next_step)
```

---

## Option Analysis: Three Ways to Build This

### Option 1: Provider-Heavy (Brevo Manages Campaigns)

Use Brevo's campaign API for sending. Brevo manages contacts, creates campaigns, handles delivery. We pull stats.

```
OUR APP                          BREVO
  Create campaign metadata   →   POST /emailCampaigns
  Sync contacts to list      →   POST /contacts/import
  Trigger send               →   POST /emailCampaigns/{id}/sendNow
  Receive webhooks           ←   Webhook events
  Pull stats periodically    →   GET /emailCampaigns/{id}/statistics
```

**Pros:** Less delivery code to write. Brevo handles contact dedup, bounce management.
**Cons:** Cannot use with SES/SendGrid/Postmark (they lack campaign APIs). Locked to providers with campaign management. Brevo rate limits (400 req/min on Starter). Can't control link rewriting (no heatmap zones). No automation stats API.
**Verdict:** Does NOT work for our architecture. We need link rewriting control (heatmap Layer 1) and provider-swappable delivery. And Brevo has zero automation stats API.

### Option 2: Provider-Light / Transactional Only (Recommended)

Use provider ONLY for transactional sends. We manage everything — recipients, delivery tracking, stats.

```
OUR APP                               PROVIDER
  Resolve audience ourselves
  Insert recipients ourselves
  Render templates ourselves
  Rewrite links ourselves
  For each recipient:
    send_email(to, subject, html) →   Delivers email
                                  ←   Webhook: delivered/opened/clicked/bounced
  Aggregate stats ourselves
  Compute funnels ourselves
  Run attribution ourselves
```

**Pros:** Works with ANY email provider (SES, SendGrid, Postmark, Brevo, Mailgun). Full control over link rewriting (heatmaps). Full control over recipient tracking. No dependency on provider campaign features. Provider is truly a dumb relay.
**Cons:** More code to write (delivery orchestration, batching, rate limiting). Must handle our own retry logic. Must implement our own bounce management (or sync from provider webhooks).
**Verdict:** This is the right approach. Matches our adapter pattern. Provider boundary is minimal and clean.

### Option 3: Hybrid (Provider for Email Campaigns, Transactional for Flows)

Use provider campaign API for one-off campaigns, transactional API for flow sends.

**Pros:** Leverages provider campaign features where available.
**Cons:** Two different delivery paths = two different tracking models = inconsistent analytics. The heatmap zone rewriting won't work with provider campaign API (provider controls link rewriting). More complex codebase.
**Verdict:** Unnecessary complexity. Option 2 gives us consistent behavior and full control.

---

## Recommended Approach: Option 2 (Provider-Light)

**The provider boundary is exactly 3 methods:**

```python
# This is ALL the provider does:
result = await provider.send_email(to_email, subject, html_content)
result = await provider.send_sms(to_number, content)
result = await provider.send_template(to_number, template_name, params)

# Plus receiving their webhooks:
event = await provider.verify_webhook(payload, signature)
```

**Everything else is ours:**
- Audience resolution → SQL against our DB
- Recipient tracking → INSERT into our campaign_recipients
- Link rewriting → Our logic before handing HTML to provider
- A/B splitting → Our logic, different content per call
- Stats computation → Our DB queries
- Attribution → Our middleware + cookies + DB
- Engagement scoring → Our algorithm
- Flow execution → Our state machine
- Guardrails → Our frequency cap, quiet hours, sunset logic
- Analytics → Our funnel queries, our dashboards

**This means:**
1. Switching from Brevo to SES = change one env var. Zero logic changes.
2. Switching from Brevo SMS to Twilio = change one env var. Zero logic changes.
3. Using Brevo for email + Twilio for SMS = two env vars. Both work simultaneously.
4. All analytics, attribution, flows, guardrails work identically regardless of provider.

---

## File Structure (Where Everything Goes)

```
modules/
  marketing/
    services/
      campaign_service.py           (EXISTS — extend with medium support)
      campaign_delivery_service.py  (NEW — resolve, filter, send, track)
      segment_service.py            (EXISTS — extend with engagement filters)
      attribution_service.py        (NEW — UTM detection, cookie, session linking)
      heatmap_service.py            (NEW — link rewriting, zone aggregation)
      campaign_analytics_service.py (NEW — funnel, stats summary, variants)
      user_timeline_service.py      (NEW — UNION ALL timeline per user)
      effectiveness_service.py      (NEW — cross-campaign, attribution models)
      engagement_scoring_service.py (NEW — weighted score + velocity + decay)
      flow_builder_service.py       (NEW — flow CRUD, validation, chaining)
      flow_execution_service.py     (NEW — state machine)
      flow_analytics_service.py     (NEW — per-flow funnels, step metrics)
      guardrails_service.py         (NEW — freq cap, quiet hours, sunset)
      reconciliation_service.py     (NEW — pull provider stats, backfill)
    workers/
      flow_worker.py                (NEW — advance Wait steps every 60s)
      stats_refresh_worker.py       (NEW — refresh campaign_stats_summary)
      engagement_refresh_worker.py  (NEW — recompute engagement scores)
      segment_check_worker.py       (NEW — check segment triggers)
      sunset_worker.py              (NEW — daily sunset policy check)
      reconciliation_worker.py      (NEW — 6h provider stats pull)
    routes/
      admin_routes.py               (EXISTS — extend)
      analytics_routes.py           (NEW — funnel, heatmap, timeline, effectiveness)
      flow_routes.py                (NEW — flow CRUD, monitoring)
    models/
      schemas.py                    (EXISTS — extend with new request/response types)

  notifications/
    interfaces/
      sms_provider.py               (NEW — SmsProvider ABC)
      whatsapp_provider.py          (NEW — WhatsAppProvider ABC)
    adapters/
      __init__.py                   (NEW — get_sms_provider, get_whatsapp_provider)
      console_sms_adapter.py        (NEW)
      console_whatsapp_adapter.py   (NEW)
      brevo_sms_adapter.py          (NEW)
      brevo_whatsapp_adapter.py     (NEW)
    routes/
      admin_routes.py               (NEW — test sends, message log)
      webhook_routes.py             (NEW — SMS + WA webhook ingestion)
    services/
      sms_send_service.py           (NEW)
      whatsapp_send_service.py      (NEW)

  gdpr/
    interfaces/
      email_provider.py             (EXISTS — add capability properties)
    adapters/
      brevo_adapter.py              (EXISTS — may need webhook parsing updates)
      ses_adapter.py                (NEW — Phase E)
      sendgrid_adapter.py           (NEW — Phase E)

frontend/
  app/admin/
    campaigns/
      [id]/analytics/page.tsx       (NEW — campaign funnel + heatmap)
    users/
      [id]/timeline/page.tsx        (NEW — user timeline)
    effectiveness/page.tsx          (NEW — cross-campaign dashboard)
    flows/
      page.tsx                      (NEW — flow list)
      [id]/page.tsx                 (NEW — flow builder)
      [id]/analytics/page.tsx       (NEW — flow analytics)
    notifications/page.tsx          (NEW — SMS/WA test + config)

migrations/
  033_campaign_pipeline.sql         (NEW — all 13 tables + modifications)

scripts/
  ensure_tables.py                  (EXISTS — add new tables)
```

---

## Critical Path: What to Build First for a Working MVP

If you want the fastest path to a demo-able campaign pipeline:

```
Week 1: Phase A (Foundation) + Phase B (B1-B6)
  → Admin can send a multi-medium campaign, webhooks are processed

Week 2: Phase B (B7-B13) + Phase C (C1-C6)
  → Attribution works, engagement scoring runs, stats summary refreshes

Week 3: Phase C (C7-C19)
  → Campaign analytics dashboard, user timeline, effectiveness dashboard

Week 4: Phase D (D1-D11)
  → Automation flows work, events trigger flows, flows send messages

Week 5: Phase D (D12-D16) + Phase E (E1-E4)
  → Flow analytics, SES adapter, Twilio adapters
```

---

*Generated 2026-04-25 — Campaign Build Architecture v1.0*
