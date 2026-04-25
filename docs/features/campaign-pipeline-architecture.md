# Campaign Pipeline & Conversion Funnel — Full Architecture Research

> Updated 2026-04-25. Complete Brevo API deep dive + multi-dimensional funnel architecture.

---

## Decision Context

The user needs to understand the full architecture for:
1. Campaign send pipeline (currently broken — sends to zero recipients)
2. Event-driven automations (welcome sequences, cart abandonment, post-purchase drips, branching workflows)
3. Multi-channel messaging (email + SMS + WhatsApp)
4. **Multi-dimensional conversion funnel** (not just per-campaign — group-level, user-level, cross-campaign, time-based)
5. **Momentum-based engagement scoring** — trigger campaigns when users are "hot"
6. **Campaign effectiveness tracking** — did this campaign actually work?
7. How Brevo fits into all of this

**Key decision:** User is okay depending on Brevo for delivery infrastructure, but wants to understand exactly what Brevo can/cannot provide for the multi-dimensional analytics layer.

---

## Current System Inventory

### What Works Today

| System | Status | Key Files |
|--------|--------|-----------|
| User registration | Working | `modules/auth/routes/auth_routes.py:95-181` |
| Email verification | Working | `frontend/app/verify-email/page.tsx` + `VerifyEmailContent.tsx` |
| Consent collection (post-login modal) | Working | `frontend/components/ConsentModal.tsx`, `frontend/app/dashboard/layout.tsx:47-56` |
| Cookie banner | Working | `frontend/components/CookieBanner.tsx` |
| Privacy dashboard | Working | `frontend/app/dashboard/privacy/page.tsx` |
| Email send pipeline (consent check → render → send → audit) | Working | `modules/gdpr/services/email_send_service.py` |
| Brevo transactional email adapter | Working | `modules/gdpr/adapters/brevo_adapter.py` |
| Console email adapter (dev) | Working | `modules/gdpr/adapters/console_adapter.py` |
| Audience segments (filter-based + SQL metrics) | Working | `modules/marketing/services/segment_service.py` |
| Campaign creation + A/B variants | Working | `modules/marketing/services/campaign_service.py` |
| Analytics tracking (page views, events, sessions) | Working | `modules/tracking/` |
| UTM tracking | Working | `analytics.utm_tracking` table |
| Ecommerce orders | Working | `ecommerce.orders` + `ecommerce.order_items` |
| Cart tracking + abandonment detection | Working | `ecommerce.cart` with status field |
| Custom metrics (SQL editor + is_audience toggle) | Working | `analytics.saved_metrics` table |
| RFM scoring | Working (manual) | `scripts/compute_rfm.py`, `ecommerce.customer_metrics` |
| Admin resend verification | Working | `modules/auth/routes/admin_routes.py:114-179` |

### What's Broken

| Issue | Root Cause | Location |
|-------|-----------|----------|
| **Campaign sends to zero recipients** | `campaign_service.send_campaign()` calls `provider.create_campaign()` without resolving segments to recipient list. `list_ids` parameter is NEVER passed. | `campaign_service.py:295` |
| **No Brevo contact sync** | Users are never created in Brevo's contact database | No code exists |
| **Webhook opened/clicked events ignored** | `webhook_processing_service.py` only processes bounce/delivery/complaint. Opens and clicks are received but discarded. | `webhook_processing_service.py:71-78` |
| **Webhook payload not stored** | `email_webhook_events.payload` column exists but is never populated | `webhook_processing_service.py:56-68` |
| **No campaign_recipients table** | No per-user record of who received which campaign/variant | Table doesn't exist |
| **Orders not pushed to Brevo** | We never call `POST /v3/orders/status` so Brevo's revenue attribution has zero data | No code exists |
| **Events not being fired** | `add_to_cart`, `product_viewed`, `search_performed`, `checkout_abandoned` are seeded as audience presets but never actually tracked | Only `checkout_started` fires |
| **UTM not linked to campaigns** | `utm_campaign` is text, no FK to `marketing.marketing_campaigns` | No join exists |
| **No engagement scoring** | Only RFM (purchase-based, manual). No real-time behavioral score. | No code exists |

---

## Consent System (Verified — Works Correctly)

### 6 Consent Types (defined in `frontend/lib/consent-types.ts`)

| Key | Category | Default | Required |
|-----|----------|---------|----------|
| `transactional_email` | email | true | YES |
| `marketing_email` | email | false | NO |
| `third_party_sharing` | data | false | NO |
| `analytics` | analytics | false | NO |
| `cookies_analytics` | cookies | false | NO |
| `cookies_marketing` | cookies | false | NO |

### Consent Collection Flow

1. **Signup** — No consent collected. JWT has `consent=[]`. Welcome email sent with `force=True`.
2. **First dashboard visit** — `ConsentModal` pops up automatically (checked via `localStorage.consent_modal_completed`). User toggles preferences, clicks "Save Preferences".
3. **Each consent type POSTed** to `/api/gdpr/consent` → append-only row in `gdpr.consent_records` + audit log in `gdpr.consent_audit_log`.
4. **Cookie prefs synced** to `/api/gdpr/cookies`.
5. **On next token refresh** — JWT `consent[]` populated from `gdpr.consent_records`.
6. **Ongoing** — User manages via Dashboard > Privacy page. Email unsubscribe via RFC 8058 HMAC token (30-day validity).

### Campaign Eligibility Filters (in `segment_service.py`)

Every campaign audience query applies these base filters:
- `is_verified = TRUE` (default, overridable by passing `is_verified: false`)
- `marketing_email = TRUE` (from `gdpr.email_preferences`)
- `suppressed_at IS NULL`
- `is_active = TRUE`
- `deleted_at IS NULL`

---

## Audience Engine

### Two Paths to Build an Audience

**Path A: Filter-Based Segments** (Segment Builder UI)
- RFM segments, order count, device type, browser, page views, event counts, referral source, signup age, role, verification status
- Stored in `marketing.audience_segments` with `filters` JSON
- Computed dynamically via `segment_service._build_segment_query()`

**Path B: SQL-Backed Audience Metrics** (Custom Metrics tab)
- Admin writes SQL in Custom Metrics editor
- Toggles `is_audience=true` → validates SQL returns `user_id` column
- Stored in `analytics.saved_metrics` table
- Exposed to Campaign Wizard via `/tracking/admin/metrics/audience-metrics`
- Grouped by `group_name`, drag-and-drop reorderable

### The 4 "Get Started" Presets

Hardcoded as `STARTER_QUERIES` in `frontend/app/admin/analytics/custom-metrics.tsx:128-164`. They load into the SQL editor when clicked but are NOT stored in DB. They're analytics-focused (don't return `user_id`).

---

## Brevo API — Complete Deep Dive (April 2026)

### 1. Transactional Email API

**Endpoint:** `POST /v3/smtp/email`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sender` | `{email, name}` | Yes (unless templateId) | Must be verified sender |
| `to` | `[{email, name}]` | Yes | Recipients array |
| `cc` / `bcc` | `[{email, name}]` | No | Carbon/blind copy |
| `subject` | string | Yes (unless templateId) | Subject line |
| `htmlContent` | string | One of 3* | Inline HTML |
| `htmlUrl` | string | One of 3* | Remote HTML URL |
| `templateId` | integer | One of 3* | Brevo template ID |
| `textContent` | string | No | Plain text fallback |
| `params` | object | No | Template variable substitution `{{params.KEY}}` |
| `headers` | object | No | Custom email headers; `sender.ip` for dedicated IP |
| `tags` | string[] | No | Categorization for filtering |
| `replyTo` | `{email, name}` | No | Reply-to address |
| `attachment` | array | No | URL or base64-encoded; many file types supported |
| `scheduledAt` | string | No | UTC ISO 8601; up to 72hrs ahead |
| `batchId` | UUIDv4 | No | Group scheduled messages |
| `messageVersions` | array | No | Batch send — personalized variants |

*One of `htmlContent`, `htmlUrl`, or `templateId` required.

**messageVersions (batch send):**
- Max 2,000 total recipients per request
- Max 99 recipients per version
- Each version can customize: `to`, `cc`, `bcc`, `replyTo`, `subject`, `params`, `htmlContent`, `textContent`
- Individual `params` max 100KB, cumulative max 1000KB
- `templateId` customizable per version only if global `templateId` provided

**Response:** `201` with `messageId` (and `messageIds` for batch)

**Rate limits:** 1,000 RPS (Free/Starter/Standard), 2,000 RPS (Professional/Enterprise), 6,000 RPS (Enterprise extended)

**Other transactional email endpoints:**
- `GET /v3/smtp/statistics/aggregatedReport` — aggregate stats (90-day max window)
- `GET /v3/smtp/statistics/reports` — daily breakdown (30-day max window)
- `GET /v3/smtp/statistics/events` — unaggregated per-message events (filterable by email, 90-day max)
- `GET /v3/smtp/blockedContacts` — blocked contact list
- `POST/GET/PUT/DELETE /v3/smtp/templates` — full template CRUD
- `POST /v3/smtp/templates/{id}/sendTest` — send template to test list

### 2. Campaign Email API

**Create:** `POST /v3/emailCampaigns`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `name` | string | Yes | Campaign name |
| `subject` | string | Yes (if !abTesting) | Subject line |
| `sender` | `{email, name}` | Yes | Verified sender |
| `htmlContent` / `htmlUrl` / `templateId` | — | One required | Content source (mutually exclusive) |
| `recipients.listIds` | int[] | Yes | **Brevo list IDs** (contacts must be in Brevo) |
| `recipients.exclusionListIds` | int[] | No | Lists to exclude |
| `recipients.segmentIds` | int[] | No | Brevo segments (UI-created only) |
| `scheduledAt` | string | No | UTC ISO 8601 |
| `replyTo` | string | No | Reply-to email |
| `toField` | string | No | Personalized "To" field |
| `tag` | string | No | Tag for filtering |
| `footer` | string | No | Footer HTML |
| `header` | string | No | Header HTML |
| `utmCampaign` | string | No | UTM campaign value |
| `params` | object | No | Template variables |
| `sendAtBestTime` | boolean | No | Brevo optimizes send time per contact |
| `inlineImageActivation` | boolean | No | Embed images inline |
| `mirrorActive` | boolean | No | "View in browser" link |
| `attachmentUrl` | string | No | Attachment from URL |

**A/B Testing fields (when `abTesting=true`):**
- `subjectA`, `subjectB` — both mandatory, must be unique
- `splitRule` — test group size percentage
- `winnerCriteria` — `open` or `click`
- `winnerDelay` — test duration in hours (max 168 = 7 days)
- Requirement: `sendAtBestTime` must be false; must have sent at least 1 regular campaign first
- Min 5,000 recipients for statistically relevant results

**Campaign operations:**
- `POST /v3/emailCampaigns/{id}/sendNow` — send immediately
- `POST /v3/emailCampaigns/{id}/sendTest` — send to test list
- `POST /v3/emailCampaigns/{id}/sendReport` — send stats report to email
- `PUT /v3/emailCampaigns/{id}/status` — update status (suspend, archive, etc.)

**Campaign status lifecycle:** draft → scheduled → queued → sent → archive

**Campaign statistics** (`GET /v3/emailCampaigns/{id}` with `statistics` param):

| Stat Block | Fields | Available On |
|-----------|--------|-------------|
| `globalStats` | sent, delivered, hardBounces, softBounces, viewed, uniqueViews, opensRate, appleMppOpens, clickers, uniqueClicks, complaints, unsubscriptions | Single + List |
| `linksStats` | Per-URL: `{url: {clicks, uniqueClicks}}` | Single only |
| `statsByDomain` | Per email domain breakdown | Single + List |
| `statsByDevice` | desktop, mobile, tablet, unknown — viewed, uniqueViews, clickers, uniqueClicks | **Single only** |
| `statsByBrowser` | Per browser breakdown | **Single only** |

**List endpoint** (`GET /v3/emailCampaigns`):
- `startDate`/`endDate` filtering (max 2 years, only when `status=sent`)
- `globalStats` only returns data for events in last **6 months** — use single campaign endpoint for older
- `statsByDevice` and `statsByBrowser` NOT available on list endpoint

**Open rate change (Feb 2025):** Now includes Apple MPP opens by default. Can exclude for "real human" interactions. Bot activity also included since July 2025.

### 3. Contacts API

**CRUD:**
- `POST /v3/contacts` — create (email, attributes, listIds, updateEnabled, emailBlacklisted, smsBlacklisted)
- `GET /v3/contacts/{identifier}` — get by email (URL-encoded), phone, id, ext_id
- `PUT /v3/contacts/{identifier}` — update attributes, lists
- `DELETE /v3/contacts/{identifier}` — delete contact

**`updateEnabled` flag:** When `true` on create, if contact shares an identifier (email, SMS, ext_id, whatsapp, landline) with an existing contact, the two are **force-merged**.

**Identifiers supported:** `email_id`, `phone_id`, `ext_id`, `whatsapp_id`, `landline_number_id`, `contact_id` (Brevo internal)

**Standard attributes:** EMAIL, FIRSTNAME, LASTNAME, SMS, WHATSAPP, EXT_ID, plus custom attributes (text, number, date, boolean, category)

**Custom attribute management:** `GET/POST/PUT/DELETE /v3/contacts/attributes`
- Max 200 custom attributes per account

**Bulk import:** `POST /v3/contacts/import`
- CSV or JSON format, max 10MB
- `listIds` to add imported contacts to lists
- `updateExistingContacts` flag
- Returns background process ID; notify URL called on completion

**Bulk export:** `POST /v3/contacts/export`

**Double opt-in:** `POST /v3/contacts/doubleOptinConfirmation` — sends DOI confirmation email with template

**Rate limits:** 10 RPS (Free/Starter/Standard), 20 RPS (Professional/Enterprise), 60 RPS (Enterprise extended)

### 4. Lists API

- `POST /v3/contacts/lists` — create list
- `GET /v3/contacts/lists` — list all lists
- `GET /v3/contacts/lists/{listId}` — get list details
- `PUT /v3/contacts/lists/{listId}` — update list
- `DELETE /v3/contacts/lists/{listId}` — delete list
- `POST /v3/contacts/lists/{listId}/contacts/add` — add contacts to list
- `POST /v3/contacts/lists/{listId}/contacts/remove` — remove contacts from list
- `GET /v3/contacts/lists/{listId}/contacts` — get contacts in list

**Key facts:**
- **Static lists only** — dynamic lists deprecated January 2025, converted to static
- Max 300 lists (general), 600 lists (Enterprise)
- For dynamic audience grouping, Brevo recommends segments (but segments are UI-created only)

### 5. Segments API

- `GET /v3/contacts/segments` — READ-ONLY via API
- **Cannot CREATE, EDIT, or DELETE segments via API** — UI only
- Max 100 conditions per segment
- Segments auto-update as contact data changes (unlike static lists)

### 6. Per-Contact Campaign Stats

**Endpoint:** `GET /v3/contacts/{identifier}/campaignStats`

**Returns per contact:**
- `messagesSent` — all campaigns sent to this contact
- `delivered` — successful deliveries
- `opened` — opens with timestamp + IP per event
- `clicked` — link clicks with URL + timestamp per event
- `hardBounces` / `softBounces`
- `complaints` (spam)
- `unsubscriptions`
- `transacAttributes` — associated order data (order ID, date, price)

**Limitations:**
- Date range defaults to last 90 days
- Custom `startDate`/`endDate` allowed, but window **cannot exceed 90 days** per call
- Must page through 90-day windows for full history

### 7. Transactional SMS API

**Endpoint:** `POST /v3/transactionalSMS/send` (NEW — old `/sms` deprecated May 2025)

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `sender` | string | Yes | Alphanumeric max 11 chars OR numeric max 15 chars |
| `recipient` | string | Yes | Mobile number with country code |
| `content` | string | Yes | Message text; >160 chars = multiple SMS |
| `type` | string | Yes | `transactional` or `marketing` |
| `tag` | string | No | Categorization |
| `webUrl` | URL | No | Webhook for delivery events |
| `unicodeEnabled` | boolean | No | Unicode content support |
| `organisationPrefix` | string | No | Brand name prepended |

**Response:** `201` with `messageId`

**Statistics endpoints:**
- `GET /v3/transactionalSMS/statistics/aggregatedReport` — totals (requests, delivered, bounces, etc.)
- `GET /v3/transactionalSMS/statistics/reports` — daily breakdown
- `GET /v3/transactionalSMS/statistics/events` — per-message events (filterable by phoneNumber, event type)

**Rate limits:** 150 RPS (standard), 200 RPS (Professional), 250 RPS (Enterprise extended)

### 8. SMS Campaign API

- `POST/GET/PUT/DELETE /v3/smsCampaigns` — full CRUD
- Create fields: name, sender, content, `recipients.listIds`, scheduledAt
- `POST /v3/smsCampaigns/{id}/sendNow` — send immediately
- `POST /v3/smsCampaigns/{id}/sendTest` — test send
- Max 300 SMS campaigns (general), 600 (Enterprise)

### 9. WhatsApp API

**Send:** `POST /v3/whatsapp/sendMessage`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `senderNumber` | string | Yes | WhatsApp number with country code (Brevo-provisioned) |
| `contactNumbers` | string[] | Yes | Recipient phone numbers |
| `templateId` | integer | Yes (first msg) | **Required for first message to a contact** |
| `text` | string | No | Free-form text (only after initial template message) |

**Requirements:**
- WhatsApp Business Account must be set up in Brevo UI
- Facebook + WhatsApp Business account signup required
- Templates must be created in Brevo dashboard UI
- Fetch templateIds via `GET /v3/whatsappCampaigns/template-list`

**Activity tracking:** `GET /v3/whatsapp/statistics/events` — past 30 days or custom range

**WhatsApp Campaign endpoints also exist** (separate from transactional)

### 10. Events API (Custom Events)

**Push single:** `POST /v3/events`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `event_name` | string | Yes | Max 255 chars; alphanumeric, hyphens, underscores |
| `event_date` | string | No | ISO 8601; defaults to now |
| `identifiers` | object | Yes | At least one: `email_id`, `phone_id`, `ext_id`, `whatsapp_id`, `contact_id`, `landline_number_id` |
| `contact_properties` | object | No | Updates contact attributes alongside event |
| `event_properties` | object | No | Arbitrary key-value; 255-char key limit; **50KB total max** |

**Push batch:** `POST /v3/events/batch`
- Max **200 events** per request
- Max **512KB** payload
- Partial success possible (207 response with per-event breakdown)
- Events that pass validation are processed even when others fail

**Query:** `GET /v3/events`
- Filter by: `contact_id[]`, `event_name[]`, `object_type[]`, `startDate`, `endDate`
- Default range: last 6 months
- Max 10,000 results per query
- **Note:** Only returns YOUR custom events, NOT Brevo's own email engagement events

**Automation trigger:** Events matching UI-configured "Custom event" triggers automatically enter contacts into workflows.

**Rate limits:** 10 RPS (standard), 20 RPS (Professional), 60 RPS (Enterprise extended)

### 11. Ecommerce / Orders API

**Single order:** `POST /v3/orders/status`

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `id` | string | Yes | Your order ID |
| `createdAt` | string | Yes | UTC ISO 8601 |
| `updatedAt` | string | Yes | UTC ISO 8601 |
| `status` | string | Yes | Order status (e.g., "completed", "shipped") |
| `amount` | number | Yes | Order total |
| `products` | array | Yes | Each: `productId` (req), `price` (req), `quantity` or `quantityFloat`, `variantId` (opt) |
| `identifiers` | object | Yes | At least one: `email_id`, `phone_id`, `ext_id`, `loyalty_subscription_id` |
| `billing` | object | No | address, city, countryCode, phone, postCode, paymentMethod, region |
| `coupons` | string[] | No | Promo codes (case-insensitive) |
| `metaInfo` | object | No | Custom metadata (strings, ints, booleans) |
| `historical` | boolean | No | Default `true` — **won't trigger automations**. Set `false` for live orders. |

**Batch orders:** `POST /v3/orders/status/batch`
- Up to **1,000 orders** per request OR **5MB** payload
- Returns `202` with `batchId` and `count`
- `historical` flag applies to entire batch

**Rate limits:** 5 RPS (standard), 10 RPS (Professional), 15 RPS (Enterprise)

### 12. Revenue Attribution API

**Multi-campaign aggregate:** `GET /v3/ecommerce/attribution/metrics`
- Query params: `periodFrom`, `periodTo` (RFC3339), `emailCampaignId[]`, `smsCampaignId[]`, `automationWorkflowEmailId[]`, `automationWorkflowSmsId[]`
- Response: `results` array per source + `totals` object
- Behavior when omitting all IDs: **undocumented** (may return all sources, unconfirmed)

**Per-campaign detail:** `GET /v3/ecommerce/attribution/metrics/{conversionSource}/{conversionSourceId}`
- `conversionSource` enum: `email_campaign`, `sms_campaign`, `automation_workflow_email`, `automation_workflow_sms`
- Returns: `ordersCount`, `revenue`, `averageBasket`, `newCustomersCount`

**Product-level:** `GET /v3/ecommerce/attribution/products/{conversionSource}/{conversionSourceId}`
- Returns: `products` array with per-product `ordersCount` + `revenue`

**Attribution model:** Last-click, **fixed 48-hour window**. Matches order email to contact, looks for last clicked campaign/automation within 48hrs before order.

### 13. Products API

- `POST /v3/products` — create/update product (upsert with `updateEnabled: true`)
- `POST /v3/products/batch` — batch create/update (100 for insert, 1000 for upsert)
- `GET /v3/products/{productId}` — get product details (now includes `brand`, `description` as of March 2026)
- Products require `id` + `name`; support images (max 5MB, re-hosted to S3), `metaInfo` (max 20 keys, ~1000KB)

**Categories:**
- `POST /v3/categories` — create/update category (upsert)
- `GET /v3/categories` — list all categories

**Rate limits:** 2 RPS (standard), 4 RPS (Professional)

### 14. Automation/Workflows — THE CRITICAL LIMITATION

**Workflow CREATION is UI-only. Workflow TRIGGERING is API-capable.**

**What you CAN do via API:**
- Trigger workflow entry by pushing custom events (`POST /v3/events`)
- Trigger workflow entry by adding contacts to lists
- Trigger workflow entry by updating contact attributes
- Get revenue attribution metrics for workflows (`GET /v3/ecommerce/attribution/metrics/automation_workflow_email/{id}`)

**What you CANNOT do via API:**
- Create, edit, list, activate/deactivate, or delete workflow definitions
- Export/import workflow definitions between Brevo accounts
- Get workflow statistics (entered, completed, per-step dropoff) — **UI only**
- Remove a contact from a running workflow
- Create segments (read-only via API)

**Workflow sharing:** Classic editor supports "Share a workflow" — exports a sharable link that others can import. But this is manual, not API-driven, and only works with the classic editor.

**Community status (Jan 2025):** Users explicitly requested workflow API. Brevo has not built it.

**Platform quotas:** Max 50 active workflows (general), 500 (Enterprise)

### 15. Webhooks

**CRUD:** `POST/GET/PUT/DELETE /v3/webhooks`
- Max **40 webhooks total** (marketing + transactional combined)

**Transactional email events (15 types):**

| Event | Key Fields Beyond Standard |
|-------|---------------------------|
| `request` (sent) | `template_id`, `tags`, `sending_ip`, `mirror_link`, `X-Mailin-custom` |
| `delivered` | Standard only |
| `opened` | `user_agent`, `device_used` |
| `unique_opened` | `user_agent`, `device_used` |
| `click` | **`link`** (clicked URL), `user_agent`, `device_used` |
| `soft_bounce` | `reason` |
| `hard_bounce` | `reason` |
| `spam` | Minimal |
| `invalid_email` | Minimal |
| `blocked` | Minimal |
| `error` | Minimal |
| `unsubscribed` | `user_agent`, `device_used`, `sending_ip` |
| `deferred` | `reason` |
| `proxy_open` | `user_agent`, `device_used` |
| `unique_proxy_open` | `link`, `user_agent`, `device_used`, `sender_email` |

**Standard fields on all transactional webhooks:** `email`, `message-id`, `subject`, `ts_epoch` (ms UTC), `ts_event` (sec UTC), `date` (CET/CEST), `contact_id` (0 if not in Brevo), `tags`

**Marketing email events (11 types):**

| Event | Key Fields Beyond Standard |
|-------|---------------------------|
| `opened` | `camp_id`, `campaign name`, `segment_ids` |
| `click` | **`URL`** (clicked URL), `camp_id`, `segment_ids` |
| `hardBounce` | `reason`, `sending_ip` |
| `softBounce` | `reason`, `sending_ip` |
| `delivered` | `sending_ip` |
| `unsubscribed` | `list_id[]`, `segment_ids`, `sending_ip` |
| `spam` | `reason` |
| `listAddition` | `list_id[]` |
| `contactUpdated` | `content[]` (modified fields) |
| `contactDeleted` | `list_id[]` |
| `proxy_open` | Standard marketing fields |

**Standard fields on all marketing webhooks:** `id`, `camp_id`, `email`, `campaign name`, `date_sent`, `date_event`, `event`, `tag`, `segment_ids`, `ts_sent` (UTC), `ts_event` (UTC)

**Important difference:** Transactional click webhook field = `link`, Marketing click webhook field = `URL`

**Transactional SMS webhook events:** `sent`, `accepted`, `delivered`, `replied` (with `reply` text), `soft_bounce`, `hard_bounce`, `subscribe`, `unsubscribed`, `skip`, `bl` (blacklisted), `rej` (rejected)

**SMS webhook standard fields:** `to`, `messageId`, `date`, `tag`, `type` ("marketing" or "transactional")

**Inbound email webhook:** `inboundEmailProcessed` — JSON payload with `items[]` array of parsed emails

**Conversations webhooks:** Configured in Brevo UI (Conversations > Settings). Events: `conversationFragment`, `conversationFinished`, chat blocked by contact form.

**Timing notes:**
- Transactional: `ts_epoch` (ms UTC), `ts_event` (sec UTC), `date` (CET/CEST)
- Marketing: `ts_sent`/`ts_event` (UTC), `date_sent`/`date_event` (local TZ), `date` (CET/CEST)

### 16. Senders

- `POST/GET/PUT/DELETE /v3/senders` — sender CRUD + verification
- Domain authentication: DKIM, SPF, DMARC via DNS records
- Dedicated IPs available (use `sender.ip` header in transactional email)

### 17. CRM / Deals API

- `POST /v3/crm/deals` — create deal (with `pipeline`, `deal_stage`, `deal_owner`)
- `PATCH /v3/crm/deals/{id}` — update deal (PATCH replaces `linkedCompaniesIds` and `linkedContactIds`)
- `GET /v3/crm/pipeline/details/{pipelineID}` — get pipeline stages
- Companies, Tasks, Notes also under `/v3/crm/` namespace
- Can trigger automations on deal stage updates

### 18. Loyalty API (Professional/Enterprise)

Base path: `/v3/loyalty/`

- **Balance:** `GET /loyalty/balance/programs/{pid}/subscriptions/{cid}/balances`
- **Tier:** `GET /loyalty/balance/programs/{pid}/subscriptions/{cid}/tier` (includes `nextTierThreshold`, `currentBalance`)
- **Vouchers:** `GET /loyalty/balance/programs/{pid}/subscriptions/{cid}/vouchers`
- **Transactions:** `GET /loyalty/balance/programs/{pid}/subscriptions/{cid}/transactions`
- **Create transaction:** Two-phase: create → complete/cancel. Use `autoComplete: true` for instant rewards.
- **Enroll contact first** — 422 if not subscribed
- Points-based or cashback programs, tiers, voucher codes

### 19. Master/Sub-Accounts (Corporate)

- `POST /v3/corporate/subaccount` — create sub-account
- `GET /v3/corporate/subaccount` — list all sub-accounts
- `GET /v3/corporate/subaccount/{id}` — get sub-account details
- `PUT /v3/corporate/subaccount/{id}/applications` — enable/disable applications per sub-account
- White-label: custom branding, DKIM, dedicated IPs, separate API keys per sub-account

### 20. Inbound Email Parsing

- Requires dedicated subdomain (e.g., `reply.yourdomain.com`)
- Brevo receives email → parses with ML (MailClark technology) → sends structured JSON to your webhook
- Uses state-of-the-art algorithms to extract actual message from raw email, convert to Markdown
- Configured via standard webhook CRUD endpoints with `inbound` type

---

## Complete Rate Limits Table

### General (Free / Starter / Standard)

| Endpoint | RPH | RPS |
|----------|-----|-----|
| `POST /v3/smtp/email` | 3,600,000 | 1,000 |
| `GET /v3/smtp/emails` | 7,200 | 2 |
| `POST /v3/transactionalSMS/send` | 540,000 | 150 |
| `POST /v3/events` | 36,000 | 10 |
| `POST /v3/orders/status` | 18,000 | 5 |
| `POST /v3/products` | 7,200 | 2 |
| All `/v3/smtp/{…}` (other) | 300 | — |
| All `/v3/contacts/{…}` | 36,000 | 10 |
| All `/v3/loyalty/{…}` | 600 | — |
| All other endpoints | 100 | — |

### Advanced (Professional / Enterprise)

| Endpoint | RPH | RPS |
|----------|-----|-----|
| `POST /v3/smtp/email` | 7,200,000 | 2,000 |
| `GET /v3/smtp/emails` | 10,800 | 3 |
| `POST /v3/transactionalSMS/send` | 720,000 | 200 |
| `POST /v3/events` | 72,000 | 20 |
| `POST /v3/orders/status` | 36,000 | 10 |
| `POST /v3/products` | 14,400 | 4 |
| All `/v3/smtp/{…}` (other) | 600 | — |
| All `/v3/contacts/{…}` | 72,000 | 20 |
| All `/v3/loyalty/{…}` | 1,200 | — |
| All other endpoints | 200 | — |

### Extended (Enterprise Only)

| Endpoint | RPS |
|----------|-----|
| `POST /v3/smtp/email` | 6,000 |
| `POST /v3/transactionalSMS/send` | 250 |
| `POST /v3/orders/status` | 15 |
| All `/v3/contacts/{…}` | 60 |
| `POST /v3/events` | 60 |

### Rate limit headers on all responses:
- `x-sib-ratelimit-limit`
- `x-sib-ratelimit-remaining`
- `x-sib-ratelimit-reset`

---

## Platform Quotas

| Resource | General | Enterprise |
|----------|---------|-----------|
| Email campaigns (total created) | 10,000 | 50,000 |
| SMS campaigns (total created) | 300 | 600 |
| Scheduled campaigns (simultaneous) | 150 | 300 |
| Media storage | 2 GB | 5 GB |
| **Active automation workflows** | **50** | **500** |
| Stored contacts | 5,000,000 | 900,000,000 |
| Custom contact attributes | 200 | 200 |
| Contact lists | 300 | 600 |
| Contact folders | 300 | 300 |
| Webhooks (marketing + transactional) | 40 | 40 |

---

## Brevo Reporting — What's Available vs Not Available via API

| Capability | Available? | Endpoint | Limitations |
|-----------|-----------|----------|-------------|
| Per-campaign aggregate stats | Yes | `GET /emailCampaigns/{id}` | — |
| Per-link click breakdown | Yes | `linksStats` on single campaign | Not on list endpoint |
| Per-device / per-browser | Yes | `statsByDevice`, `statsByBrowser` | **Single campaign endpoint only** |
| Per-domain stats | Yes | `statsByDomain` | List endpoint: 6-month max |
| **Cross-campaign aggregation** | **No** | Must iterate + sum | No native aggregate |
| **Contact engagement history** | Partial | `GET /contacts/{id}/campaignStats` | **90-day window per call** |
| **Automation workflow stats** | **No** | — | **UI only, zero API** |
| Revenue per campaign | Yes | `GET /ecommerce/attribution/metrics/{source}/{id}` | Last-click 48hr only |
| Revenue multi-campaign | Partial | `GET /ecommerce/attribution/metrics` | Must specify campaign IDs |
| Custom event history | Yes | `GET /v3/events` | Custom events only, 6-month default |
| Transactional email events per contact | Yes | `GET /smtp/statistics/events` | 90-day max, transactional only |
| **Pre-built dashboards** | **No** | — | **UI only (Pro/Enterprise)** |
| **Real-time stats** | **No** | Use webhooks | Eventual consistency, no SLA |

---

## The 3 Architecture Options

### Option A: Brevo as Dumb Pipe (We Build Everything)

```
Our DB (single source of truth)
  → query audience → user_ids → emails/phones
  → render template from our DB
  → send via Brevo transactional API (/smtp/email, /transactionalSMS)
  → receive webhooks (delivered, opened, clicked)
  → log everything in our DB
  → build conversion funnel from our data
```

**We build:** Workflow engine (delays, branching, state machine), click tracking, link rewriting, funnel dashboard
**Brevo does:** SMTP delivery, SMS delivery, deliverability management
**Pros:** Full control, provider-swappable, version-controlled, zero manual setup per deployment, full DB access at send time
**Cons:** Must build workflow engine with branching logic, delayed queue, state management

### Option B: Brevo as CRM (Brevo Manages Everything)

```
Our DB → sync contacts → Brevo Contacts
       → sync attributes → Brevo Attributes
       → build automations in Brevo UI
       → Brevo handles workflow execution
       → we pull stats via API
```

**We build:** Contact sync layer, attribute sync, order push
**Brevo does:** Workflow execution, delays, branching, deliverability, click tracking, open tracking
**Pros:** No workflow engine to build, Brevo handles complex branching
**Cons:** Two sources of truth, sync complexity, automations live in Brevo's UI, not template-portable, manual workflow setup per deployment

### Option C: Hybrid (Push Events → Brevo Executes Pre-Built Workflows)

```
Our DB → push custom events via POST /v3/events
       → Brevo automation engine matches events to UI-built workflows
       → Brevo executes workflow (delays, branches, sends)
       → Brevo fires webhooks back to us
       → we store events + build funnel from our data
```

**We build:** Event pushing, contact sync, webhook processing, funnel dashboard
**Brevo does:** Workflow execution, delays, conditional splits, email/SMS/WhatsApp sends
**Pros:** Minimal automation code, Brevo handles complex workflow logic
**Cons:** Workflows UI-only, not exportable, not version-controlled, manual setup per deployment

### Realistic Hybrid Approach (User's Direction)

Lean on Brevo for **delivery + open/click tracking + revenue attribution**. Build our own **intelligence layer** (scoring, attribution, funnels, dashboards).

| Brevo Handles | We Build |
|---------------|----------|
| Email/SMS/WhatsApp delivery | Campaign → recipient mapping |
| Open/click tracking (via webhooks) | Store webhook events (expand existing processing) |
| Contact storage + sync | UTM campaign → marketing_campaigns FK link |
| Per-campaign stats (pull periodically) | Cross-campaign aggregation layer |
| Revenue attribution (we push orders) | Engagement/momentum scoring |
| Bounce/spam suppression | Multi-touch attribution engine |
| | User journey timeline |
| | Multi-dimensional funnel dashboard |

---

## Multi-Dimensional Conversion Funnel Architecture

### The 5 Dashboard Views Required

**View 1 — Campaign-Level Funnel** (per campaign)
```
Sent → Delivered → Opened → Clicked → Visited Site → Engaged → Converted → Revenue
```

**View 2 — Segment/Group-Level** (compare audiences across campaigns)
"How did Champions respond vs At-Risk users across all campaigns this month?"

**View 3 — User-Level Journey Timeline** (full event stream per user)
```
Apr 10 09:22  Campaign "Spring Sale" delivered
Apr 10 09:47  Opened email
Apr 10 10:03  Clicked → /products/item-X
Apr 10 10:05  Browsed product page (2m 14s)
Apr 10 10:06  Added to cart
Apr 10 10:07  Session ended (abandoned)
Apr 12 14:31  Returned via direct visit
Apr 12 14:35  Purchased $89.00 → attributed to "Spring Sale"
```

**View 4 — Cross-Campaign Attribution** (which campaigns drove revenue)
All campaigns ranked by attributed conversions/revenue under configurable attribution model.

**View 5 — Time-Based Trends** (engagement over time)
Rolling engagement rates, conversion rates, revenue trends. Detect list fatigue, seasonality.

### Multi-Touch Attribution Models

| Model | Credit Distribution | Best For |
|-------|-------------------|----------|
| Last-Click | 100% to final touchpoint | Short sales cycles |
| First-Touch | 100% to first touchpoint | Awareness measurement |
| Linear | Equal split across all touches | Fair baseline |
| Time-Decay | More weight to recent touches | Long nurture cycles |
| U-Shaped | 40% first + 40% last + 20% middle | Balanced B2C |

**Design principle:** Store raw events with timestamps. Compute attribution at **report time**, not collection time. This lets you retroactively switch models without reprocessing.

### Attribution Window

The timer starts on the email click (or open). Standard windows: 5 days (Klaviyo default), 7 days, 30 days. Store as configurable parameter applied at query time.

### The "Returning Visitor" Problem

User clicks campaign → browses → leaves → returns 2 days later → purchases. Solution:
1. **Authenticated users:** server-side user_id links all sessions
2. **Anonymous users:** first-party cookie storing campaign_id with configurable TTL (7 days)
3. Store click event + purchase event with timestamps; join at report time

---

## Momentum / Engagement Scoring

### Why RFM Is Not Enough

RFM (which we have) is **backward-looking** — only knows past purchases. Momentum scoring is **forward-looking**: detects when someone is actively engaging and likely to convert, even if they haven't bought yet.

### Proposed Scoring Weights

| Behavior | Points | Signal |
|----------|--------|--------|
| Product page view | +10 | High intent |
| Add to cart | +12 | Very high intent |
| Email click (tracked link) | +6 | Active engagement |
| Site visit (non-product) | +2 | Browsing |
| Email open | +2 | Weak (unreliable post-Apple MPP) |
| Cart abandonment (no buy) | +8 | "Almost there" |
| Purchase completed | +15 | Conversion |
| Checkout started | +10 | Very high intent |
| **30 days of inactivity** | **-25% of total** | **Decay** |

### Three Trigger Types

1. **Threshold:** Score crosses N → trigger campaign (e.g., score > 50 → "hot lead" offer)
2. **Velocity:** Score increases by N in 7 days → user accelerating → targeted outreach
3. **Decay:** Score drops 30% in 14 days → user cooling → re-engagement campaign

### Data Sources for Scoring (all in our DB already)

| Source | Table | Signal |
|--------|-------|--------|
| Page views | `analytics.page_views` | Site engagement + duration |
| Custom events | `analytics.events` | Cart adds, product views (once fired) |
| Sessions | `analytics.analytics_sessions` | Visit frequency |
| Email engagement | `gdpr.email_webhook_events` | Opens, clicks (once stored) |
| Orders | `ecommerce.orders` | Purchase behavior |
| RFM | `ecommerce.customer_metrics` | Historical purchase pattern |

---

## Gaps To Fix (Priority Order)

| # | Gap | Impact | Fix |
|---|-----|--------|-----|
| 1 | Campaign sends to zero recipients | Campaigns don't work at all | Fix `campaign_service.send_campaign()` to resolve segments → recipients → `send_batch()` |
| 2 | No `campaign_recipients` table | Can't track who received what | New table: campaign_id, user_id, variant_label, email, sent_at, provider_message_id |
| 3 | Opened/clicked webhooks ignored | Can't track email engagement | Expand `webhook_processing_service.py` to store opened + clicked events |
| 4 | No Brevo contact sync | Campaign sends via Brevo API need contacts in Brevo | Build contact sync service |
| 5 | Orders not pushed to Brevo | Brevo revenue attribution is empty | Call `POST /v3/orders/status` after order completion |
| 6 | Events not being fired | Funnel has holes between "clicked" and "purchased" | Add `add_to_cart`, `product_viewed`, `checkout_abandoned` events |
| 7 | UTM not linked to campaigns | Can't attribute site visits to campaigns | Add `campaign_id` FK or resolve via `utm_campaign` text |
| 8 | No engagement scoring | Can't detect "hot" non-buyers | New table + computation worker |
| 9 | No funnel endpoint | No conversion visualization | Build funnel API + dashboard |
| 10 | Webhook payload not stored | Can't debug delivery issues | Populate `email_webhook_events.payload` |

---

## Stored Plans Reference

- **SMS/WhatsApp Multi-Channel Plan:** `/home/rootuser/.claude/plans/hidden-imagining-stream.md`
- **Business Lifecycle Plan (BP1-BP8):** `/home/rootuser/projects/boilerplate-app/docs/features/business-lifecycle-plan.md`
- **Analytics Dashboard Fixes:** `/home/rootuser/.claude/plans/buzzing-hugging-whale.md`

---

## Open Questions (User Has Not Yet Decided)

1. **Which option for automations?** User is okay with Brevo dependency but hasn't finalized. Leaning toward realistic hybrid: Brevo for delivery/tracking, we build intelligence layer.
2. **How complex do branching workflows need to be?** Simple triggers (code-driven) vs multi-step survey funnels (Brevo UI or custom workflow engine).
3. **What attribution model?** Brevo's 48hr last-click is limited. Multi-touch attribution requires our own engine.
4. **Priority order:** Fix campaign pipeline first? Or build automations first?
5. **Momentum scoring thresholds:** What point values and trigger thresholds make sense for the specific business?
6. **The multi-dimensional funnel is not optional** — Brevo cannot provide cross-campaign aggregation, user timelines, or custom attribution. We must build all 5 dashboard views regardless of option chosen.

---

## Sources

- [Brevo API Getting Started](https://developers.brevo.com/docs/getting-started)
- [Brevo API Rate Limits](https://developers.brevo.com/docs/api-limits)
- [Brevo Platform Quotas](https://developers.brevo.com/docs/platform-quotas)
- [Brevo Transactional Webhooks](https://developers.brevo.com/docs/transactional-webhooks)
- [Brevo Marketing Webhooks](https://developers.brevo.com/docs/marketing-webhooks)
- [Brevo Events API](https://developers.brevo.com/docs/event-endpoints)
- [Brevo eCommerce Orders](https://developers.brevo.com/docs/import-your-orders)
- [Brevo Products](https://developers.brevo.com/docs/import-your-products)
- [Brevo WhatsApp Messages](https://developers.brevo.com/docs/whatsapp-messages)
- [Brevo Transactional SMS](https://developers.brevo.com/docs/transactional-sms-endpoints)
- [Brevo Contact Management](https://developers.brevo.com/docs/synchronise-contact-lists)
- [Brevo Loyalty API](https://developers.brevo.com/docs/loyalty-overview)
- [Brevo Inbound Email Parsing](https://developers.brevo.com/docs/inbound-parse-webhooks)
- [Brevo Conversations Webhooks](https://developers.brevo.com/docs/conversations-webhooks)
- [Brevo Automation Community Thread](https://community.brevo.com/t/api-reference-for-automation/2895)
- [Brevo Campaign Report API](https://developers.brevo.com/reference/get-email-campaign)
- [Brevo Contact Stats API](https://developers.brevo.com/reference/get-contact-stats)
- [Brevo Revenue Attribution API](https://developers.brevo.com/reference/get-attribution-metrics-for-one-or-more-brevo-campaigns-or-workflows)
- [Brevo Create Campaign API](https://developers.brevo.com/reference/create-email-campaign)
- [Brevo A/B Testing](https://help.brevo.com/hc/en-us/articles/4523165348626-Create-an-A-B-test-campaign)
- [Brevo Sub-Account Management](https://developers.brevo.com/reference/create-a-new-sub-account-under-a-master-account)
- [Brevo Changelog March 2026](https://developers.brevo.com/changelog/2026/3/25)
