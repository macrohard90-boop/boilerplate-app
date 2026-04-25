# Provider Architecture — Feasibility & Cost-Benefit Analysis

> **Context:** The campaign pipeline user journey (v3.1, 13 stages, 97 stories) defines exactly what we need from messaging providers. This document evaluates how to architect the provider layer so it's swappable, multi-channel, and cost-effective.

---

## What Our Pipeline Needs From Providers

From the journey map, the provider layer must support:

| Capability | Used By | Hard Requirement? |
|-----------|---------|-------------------|
| Send transactional email | Auth (welcome, reset), Orders, Flows | Yes |
| Send campaign/bulk email | Stage 3 (Delivery) | Yes |
| Delivery webhooks (sent, delivered, bounced) | Stage 4 (Interaction Tracking) | Yes |
| Open tracking webhooks | Stage 4, Stage 7 (Analytics) | Yes |
| Click tracking webhooks (with URL) | Stage 4, Stage 7, Heatmap Layer 1 | Yes |
| Pull campaign stats (reconciliation, F10) | Stage 4 condition, Stage 7 | Yes |
| Send SMS | Stage 3 (multi-medium), Stage 11 (flow sends) | If SMS enabled |
| SMS delivery receipts | Stage 4 | If SMS enabled |
| Send WhatsApp (template + session) | Stage 3 (multi-medium), Stage 11 | If WhatsApp enabled |
| WhatsApp delivery/read receipts | Stage 4 | If WhatsApp enabled |
| Contact sync | Stage 3 (sync before send) | Provider-dependent |
| A/B variant delivery | Stage 2, Stage 7 | We control splitting; provider just sends |
| Link rewriting (UTM + zone params) | Stage 3 (US-3.4), Heatmap Layer 1 | We do this ourselves |
| Template rendering | Stage 3 | We do this ourselves (Jinja2) |
| Audience resolution / segmentation | Stage 1 | We do this ourselves (SQL) |
| Campaign management / scheduling | Stage 2, Stage 3 | We do this ourselves |

**Key insight:** We already build campaign management, segmentation, template rendering, A/B splitting, and scheduling ourselves. The provider is fundamentally just a **delivery relay + webhook source**. This means we don't need (or benefit from) provider-side campaign management — we need cheap, reliable delivery with good webhooks.

---

## What We Already Have (Existing Codebase)

The adapter pattern is already proven in the codebase:

```
EmailProvider (ABC)                 PaymentProvider (ABC)
├── send_email()                    ├── create_checkout_session()
├── send_batch()                    ├── create_subscription()
├── sync_suppression()              ├── handle_webhook()
├── verify_webhook()                └── ... (7 more methods)
├── create_campaign() [optional]
└── get_campaign_stats() [optional]

Factory: get_email_provider(email_type)
  - "console" → ConsoleAdapter
  - "brevo"   → BrevoAdapter
  - Supports split: transactional vs marketing provider
```

Config already supports:
- `email_provider` (console/brevo)
- `transactional_email_provider` (override)
- `marketing_email_provider` (override)
- `brevo_api_key`, `brevo_webhook_secret`
- `email_retry_max_attempts`, `email_retry_interval`

**The interface already has optional capability methods** (`create_campaign`, `get_campaign_stats`) with `NotImplementedError` fallback. This is exactly the right pattern for providers with varying feature sets.

---

## The Four Architecture Options

### Option A: Brevo All-In-One

> Use Brevo for email + SMS + WhatsApp. One API, one billing relationship.

```
┌──────────────────────────┐
│ Your App (campaigns,     │
│ templates, segmentation, │
│ scheduling, analytics)   │
└────────┬─────────────────┘
         │ All channels
         ▼
  ┌──────────────┐
  │    Brevo     │
  │  Email       │
  │  SMS         │
  │  WhatsApp    │
  └──────────────┘
```

**Monthly Cost Estimates:**

| Scale | Contacts | Emails/mo | SMS/mo | WhatsApp/mo | Brevo Email | Brevo SMS (US) | Brevo WA | Total |
|-------|----------|-----------|--------|-------------|-------------|----------------|----------|-------|
| Small | 2K | 10K | 500 | 200 | $25 | ~$7 | ~$5 | **~$37/mo** |
| Medium | 25K | 100K | 5K | 2K | $69 | ~$65 | ~$50 | **~$184/mo** |
| Large | 100K | 500K | 25K | 10K | ~$280 | ~$325 | ~$250 | **~$855/mo** |

**Pros:**
- Simplest integration (one SDK, one webhook endpoint, one auth key)
- Brevo already implemented in codebase
- Unlimited contacts (unique among providers)
- Native campaign stats API for reconciliation (F10)
- SMS + WhatsApp in same API
- Free tier (300 emails/day) covers bootstrapping

**Cons:**
- SMS/WhatsApp pricing is higher than dedicated providers (~2x Twilio for SMS)
- SMS feature set is limited (no short codes, limited number provisioning)
- WhatsApp feature set is basic (limited interactive message types)
- Vendor lock-in to one provider across all channels
- Brevo rate limits can be restrictive (400 req/min on Starter)
- Advanced email features (A/B, STO) locked to Business plan ($69+)
- If Brevo has an outage, ALL channels go down

**Best for:** Operators who want simplest setup, small-to-medium scale, minimal DevOps.

---

### Option B: Brevo Email + Twilio SMS/WhatsApp

> Brevo for email (proven), Twilio for SMS + WhatsApp (best-in-class messaging).

```
┌──────────────────────────┐
│ Your App (campaigns,     │
│ templates, segmentation, │
│ scheduling, analytics)   │
└───┬────────────┬─────────┘
    │ Email      │ SMS + WhatsApp
    ▼            ▼
┌────────┐  ┌─────────┐
│ Brevo  │  │ Twilio  │
│ Email  │  │ SMS     │
│        │  │ WhatsApp│
└────────┘  └─────────┘
```

**Monthly Cost Estimates:**

| Scale | Brevo Email | Twilio SMS (US) | Twilio WA | Total |
|-------|-------------|-----------------|-----------|-------|
| Small | $25 | ~$5 ($0.0079+surcharge × 500) | ~$5 | **~$35/mo** |
| Medium | $69 | ~$55 ($0.011 × 5K) | ~$50 | **~$174/mo** |
| Large | ~$280 | ~$275 ($0.011 × 25K) | ~$250 | **~$805/mo** |

**Pros:**
- Best-in-class SMS provider (Twilio): 60+ country coverage, short codes, 10DLC, toll-free, alphanumeric sender ID
- Best-in-class WhatsApp (Twilio as BSP): full interactive messages, buttons, lists, catalog
- Email stays on proven Brevo integration
- Independent failure domains (email outage doesn't affect SMS/WA)
- Twilio documentation and SDK are industry gold standard
- 10DLC campaign registration built into Twilio (US compliance)

**Cons:**
- Two billing relationships, two dashboards, two webhook formats
- Twilio is the most expensive SMS provider (~30-50% more than Plivo)
- Two adapters to maintain
- Webhook signature verification differs between providers

**Best for:** Operators who need reliable multi-channel with strong SMS/WhatsApp features (e.g., US-based businesses needing 10DLC compliance).

---

### Option C: Amazon SES Email + Twilio SMS/WhatsApp

> SES for email (cheapest), Twilio for SMS + WhatsApp (best-in-class). Maximum cost optimization.

```
┌──────────────────────────┐
│ Your App (campaigns,     │
│ templates, segmentation, │
│ scheduling, analytics)   │
└───┬────────────┬─────────┘
    │ Email      │ SMS + WhatsApp
    ▼            ▼
┌────────┐  ┌─────────┐
│  SES   │  │ Twilio  │
│ Email  │  │ SMS     │
│        │  │ WhatsApp│
└────────┘  └─────────┘
```

**Monthly Cost Estimates:**

| Scale | SES Email | Dedicated IP | Twilio SMS | Twilio WA | Total |
|-------|-----------|-------------|------------|-----------|-------|
| Small | $1 | $0 (shared pool) | ~$5 | ~$5 | **~$11/mo** |
| Medium | $10 | $25 (1 dedicated IP) | ~$55 | ~$50 | **~$140/mo** |
| Large | $50 | $50 (2 IPs) | ~$275 | ~$250 | **~$625/mo** |

**Pros:**
- Email delivery is 10-20x cheaper than any other provider
- SES deliverability is excellent (Amazon's IP reputation)
- At 500K emails/mo: $50 vs Brevo's $280 = **$230/mo savings on email alone**
- Scales to millions of emails without pricing jumps
- AWS uptime SLA (99.9%)
- Twilio handles SMS/WhatsApp (best-in-class)

**Cons:**
- SES has NO campaign management — but we don't need it (we built our own)
- SES has NO contact management — but we don't need it
- SES webhook integration is more complex (events go to SNS → HTTPS, not direct webhook)
- SES has NO built-in open/click tracking — must enable via "configuration sets" (supported, just needs config)
- Requires AWS account (some operators may resist AWS dependency)
- SES production access requires manual approval (1-3 days)
- SES does NOT provide campaign-level stats API — reconciliation (F10) must use our own aggregates only
- Two providers to manage (SES + Twilio)

**Best for:** Cost-conscious operators at medium-to-large scale. Engineering-comfortable teams.

---

### Option D: Full Adapter Abstraction (Template-Portable)

> Ship the template with interface definitions + Console/Brevo defaults. Operator picks providers per channel at deploy time.

```
┌──────────────────────────────────┐
│ Your App                         │
│ ┌──────────┐ ┌──────────┐       │
│ │EmailProv │ │ SmsProv  │       │
│ │ (ABC)    │ │ (ABC)    │       │
│ └──┬───┬───┘ └──┬───┬───┘       │
│    │   │        │   │           │
│ Console Brevo Console Twilio    │
│    │   SES      │   Brevo      │
│    │   SendGrid │   Plivo      │
│    │            │   Vonage     │
│ ┌──────────┐                    │
│ │WhatsApp  │                    │
│ │Provider  │                    │
│ │ (ABC)    │                    │
│ └──┬───┬───┘                    │
│ Console Twilio                  │
│    │   Brevo                    │
│    │   Meta Direct              │
└──────────────────────────────────┘
```

**Config (.env):**
```bash
# Channel toggles
ENABLE_SMS=false
ENABLE_WHATSAPP=false

# Provider selection per channel
EMAIL_PROVIDER=brevo              # brevo | ses | sendgrid | console
SMS_PROVIDER=console              # twilio | brevo | plivo | vonage | console
WHATSAPP_PROVIDER=console         # twilio | brevo | meta_direct | console

# Split transactional vs marketing (optional)
TRANSACTIONAL_EMAIL_PROVIDER=     # override for transactional
MARKETING_EMAIL_PROVIDER=         # override for marketing
```

**What ships in the template:**

| Channel | Interface | Adapters Included | Adapters Documented (DIY) |
|---------|-----------|-------------------|--------------------------|
| Email | `EmailProvider` (exists) | Console, Brevo (exist) | SES, SendGrid |
| SMS | `SmsProvider` (new) | Console (new) | Twilio, Brevo, Plivo |
| WhatsApp | `WhatsAppProvider` (new) | Console (new) | Twilio, Brevo, Meta Direct |

**Pros:**
- Maximum template portability — operator picks their own stack
- No vendor lock-in at any layer
- Console adapters enable development/testing without any provider account
- Follows the exact same pattern as existing EmailProvider + PaymentProvider
- Adding a new provider = one new file implementing the ABC
- Each channel can use a different provider (email=SES, SMS=Twilio, WA=Meta Direct)
- Channel toggles gate everything (ENABLE_SMS=false → no SMS code loads)

**Cons:**
- More interfaces to design and maintain
- Console-only doesn't test real delivery (but that's the point of dev mode)
- Operator must configure at least one real provider per enabled channel
- Documentation burden: must explain how to set up each provider option

**Best for:** A reusable template repository where different deployments have different needs. This is your use case.

---

## Cost Comparison Summary

### Email Only (All Options)

| Volume | Brevo | SendGrid | Mailgun | SES | SES + Dedicated IP | Postmark |
|--------|-------|----------|---------|-----|-------------------|----------|
| 10K/mo | $25 | $20 | $0-35 | $1 | $26 | $15 |
| 100K/mo | $69 | $90 | $90 | $10 | $35 | $110 |
| 500K/mo | ~$280 | ~$350 | ~$400 | $50 | $75 | ~$450 |
| 1M/mo | ~$500 | ~$600 | ~$700 | $100 | $150 | ~$800 |

### Full Stack: Email + SMS (500/mo US) + WhatsApp (200/mo)

| Scale | Option A (Brevo All) | Option B (Brevo+Twilio) | Option C (SES+Twilio) | Option D depends on choices |
|-------|---------------------|------------------------|----------------------|----------------------------|
| Small | **~$37/mo** | ~$35/mo | **~$11/mo** | Config-dependent |
| Medium | **~$184/mo** | ~$174/mo | **~$140/mo** | Config-dependent |
| Large | **~$855/mo** | ~$805/mo | **~$625/mo** | Config-dependent |

### Savings of SES vs Brevo for Email (annualized)

| Volume | Brevo/yr | SES/yr | Annual Savings |
|--------|----------|--------|---------------|
| 10K/mo | $300 | $12 | **$288** |
| 100K/mo | $828 | $120 | **$708** |
| 500K/mo | $3,360 | $600 | **$2,760** |
| 1M/mo | $6,000 | $1,200 | **$4,800** |

---

## Self-Hosted Email: Not Recommended

Evaluated: Postal, Mailtrain, Listmonk, Mautic. Verdict: **None fit the boilerplate template.**

| Option | Why Not |
|--------|---------|
| **Postal** (self-hosted SMTP) | Fresh IP = 6-8 weeks of poor deliverability. 8-15 hrs/month maintenance. IP blacklist = total email outage. Dangerous on single VPS. |
| **Mailtrain** (self-hosted campaigns) | Duplicates our campaign management. Adds Node.js + MySQL. Development stalled. |
| **Listmonk** (self-hosted campaigns) | Duplicates our campaign management. Lighter than Mailtrain but still redundant. |
| **Mautic** (self-hosted marketing) | Replaces our ENTIRE marketing module. PHP + MySQL + RabbitMQ. 15-25 hrs/month. Needs 16-32GB RAM. Incompatible with "deploy in 24 hours." |

**Bottom line:** We already build the "hard" parts (campaigns, segmentation, templates, analytics). We need a dumb relay, not another campaign manager. SES at $0.10/1K emails is cheaper than running your own SMTP server when you account for VPS overhead + labor.

---

## Adapter Interface Design

Based on the existing `EmailProvider` pattern, here are the new interfaces:

### SmsProvider (new ABC)

```python
@dataclass
class SmsSendResult:
    success: bool
    provider_message_id: str | None = None
    provider: str = ""
    error: str | None = None

class SmsProvider(ABC):
    @abstractmethod
    async def send_sms(
        self, to_number: str, content: str, *,
        sender: str | None = None,
        tags: list[str] | None = None,
    ) -> SmsSendResult: ...

    @abstractmethod
    async def send_batch(
        self, messages: list[dict], *,  # [{to_number, content}]
        sender: str | None = None,
    ) -> list[SmsSendResult]: ...

    @abstractmethod
    async def verify_webhook(
        self, payload: bytes, signature: str,
    ) -> WebhookEvent: ...

    # Optional: not all providers support delivery status pull
    async def get_message_status(
        self, provider_message_id: str,
    ) -> str:
        raise NotImplementedError
```

### WhatsAppProvider (new ABC)

```python
@dataclass
class WhatsAppSendResult:
    success: bool
    provider_message_id: str | None = None
    provider: str = ""
    error: str | None = None

class WhatsAppProvider(ABC):
    @abstractmethod
    async def send_template(
        self, to_number: str, template_name: str, *,
        language: str = "en",
        parameters: dict | None = None,
        media_url: str | None = None,
    ) -> WhatsAppSendResult: ...

    @abstractmethod
    async def send_text(
        self, to_number: str, text: str,
    ) -> WhatsAppSendResult: ...

    @abstractmethod
    async def verify_webhook(
        self, payload: bytes, signature: str,
    ) -> WebhookEvent: ...
```

### Extended EmailProvider (additions to existing ABC)

```python
# Add to existing EmailProvider:
    @property
    def supports_campaign_stats(self) -> bool:
        """Whether provider has a campaign stats pull API (for reconciliation)."""
        return False

    @property
    def supports_click_tracking(self) -> bool:
        """Whether provider rewrites links and fires click webhooks."""
        return True  # Most do

    @property
    def supports_open_tracking(self) -> bool:
        """Whether provider injects tracking pixel and fires open webhooks."""
        return True  # Most do
```

### Factory Pattern (extended)

```python
# modules/notifications/adapters/__init__.py

def get_sms_provider() -> SmsProvider:
    name = settings.sms_provider
    if name == "console": return ConsoleSmsAdapter()
    if name == "twilio": return TwilioSmsAdapter()
    if name == "brevo": return BrevoSmsAdapter()
    if name == "plivo": return PlivoSmsAdapter()
    raise ValueError(f"Unknown SMS provider: {name}")

def get_whatsapp_provider() -> WhatsAppProvider:
    name = settings.whatsapp_provider
    if name == "console": return ConsoleWhatsAppAdapter()
    if name == "twilio": return TwilioWhatsAppAdapter()
    if name == "brevo": return BrevoWhatsAppAdapter()
    raise ValueError(f"Unknown WhatsApp provider: {name}")
```

---

## Recommendation

### For the boilerplate template: **Option D (Full Adapter Abstraction)**

Ship with:

| What | Implementation |
|------|---------------|
| **Interfaces** | `EmailProvider` (exists), `SmsProvider` (new), `WhatsAppProvider` (new) |
| **Default email** | Brevo adapter (exists) — free tier, zero config needed beyond API key |
| **Default SMS** | Console adapter (new) — logs to stdout in dev |
| **Default WhatsApp** | Console adapter (new) — logs to stdout in dev |
| **Factories** | Config-driven selection via `.env` (exists for email, extend for SMS/WA) |
| **Channel toggles** | `ENABLE_SMS`, `ENABLE_WHATSAPP` (from SMS/WA plan) |

### Priority adapters to build (beyond Console defaults):

| Priority | Adapter | Why | Effort |
|----------|---------|-----|--------|
| **P0** | Console SMS + Console WA | Dev/testing. Already partially built in notifications module scaffold. | 1 day |
| **P1** | Brevo SMS + Brevo WA | Simplest upgrade from Console — same API key as email. One provider for everything. | 1-2 days |
| **P2** | SES Email adapter | 10-20x cheaper than Brevo for email at scale. Biggest cost savings. | 2-3 days |
| **P3** | Twilio SMS + Twilio WA | Best-in-class messaging. Full number provisioning, 10DLC, interactive WA. | 2-3 days |
| **P4** | SendGrid Email adapter | Industry standard alternative. Simpler webhooks than SES. | 1-2 days |

### Recommended deployment configurations:

| Business Type | Email | SMS | WhatsApp | Monthly Cost (25K contacts, 100K emails, 5K SMS, 2K WA) |
|--------------|-------|-----|----------|--------------------------------------------------------|
| **Bootstrapping** | Brevo (free tier) | Off | Off | **$0** (under 300/day) |
| **Small business** | Brevo Starter | Brevo SMS | Off | **~$134/mo** |
| **Growing business** | Brevo Business | Twilio | Twilio | **~$174/mo** |
| **Cost-optimized** | SES | Twilio | Twilio | **~$140/mo** |
| **Max savings** | SES | Plivo | Off | **~$75/mo** |
| **Enterprise** | SES (dedicated IP) | Twilio | Meta Direct | **~$120/mo** |

---

## Build Order (if approved)

1. Define `SmsProvider` + `WhatsAppProvider` ABCs → `modules/notifications/interfaces/`
2. Build Console adapters → `modules/notifications/adapters/console_*.py`
3. Build Brevo adapters → `modules/notifications/adapters/brevo_*.py`
4. Wire factories + config → `modules/notifications/adapters/__init__.py`, `config.py`
5. Build send services → `modules/notifications/services/sms_send_service.py`, `whatsapp_send_service.py`
6. Wire admin test routes → `modules/notifications/routes/admin_routes.py`
7. Build SES email adapter (P2) → `modules/gdpr/adapters/ses_adapter.py`
8. Build Twilio adapters (P3) → `modules/notifications/adapters/twilio_*.py`
9. Frontend admin page → `frontend/app/admin/notifications/page.tsx`

This aligns with the existing SMS/WhatsApp plan at `~/.claude/plans/hidden-imagining-stream.md` and extends it with the multi-provider architecture.

---

*Generated 2026-04-25 — Provider Architecture Feasibility Study v1.0*
