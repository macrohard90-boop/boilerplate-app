# Email Provider Research & Decision Log

> Researched: 2026-04-17
> Decision: Brevo (free tier) as default provider, adapter pattern for swapping

## Decision Summary

- **Default provider:** Brevo (free tier: 300 emails/day, 100K contacts, transactional + marketing)
- **Architecture:** Adapter pattern — `EmailProvider` interface with swappable implementations
- **Default adapters:** `ConsoleAdapter` (dev), `BrevoAdapter` (production default)
- **Template approach:** HTML templates built in-app (Jinja2), rendered server-side, sent via Brevo API
- **Data strategy:** Minimal local storage. Campaigns metadata + ESP foreign key only. Stats pulled from Brevo API on demand. No individual send logs stored locally.
- **Split provider support:** Architecture supports `TRANSACTIONAL_EMAIL_PROVIDER` + `MARKETING_EMAIL_PROVIDER` via config, but defaults to single provider for simplicity.

---

## Why Brevo

| Factor | Brevo | Runner-up |
|--------|-------|-----------|
| Free tier | 300/day (~9K/mo), permanent, 100K contacts | Sender.net (15K/mo but marketing-focused) |
| Transactional + Marketing | Both in one API | Most others require two services |
| API completeness | Full campaign, contact, stats API | SendGrid comparable but no permanent free tier |
| Webhooks | Full events (delivered, opened, clicked, bounced) | MailerLite only has subscriber lifecycle events |
| Data offloading | Stores all send logs, manages bounces/unsubscribes | All major ESPs do this |
| Cost at scale | $9/mo (20K), $69/mo (100K) | AWS SES cheaper but requires building everything |

## Cost Progression

| Volume | Brevo Cost |
|--------|-----------|
| < 300/day (~9K/mo) | **$0 (free forever)** |
| 20K/mo | $9/mo (Starter) |
| 40K/mo | $18/mo |
| 100K/mo | $69/mo |

---

## Provider Comparison Table

### Pricing

| Provider | Free Tier | Cost at 50K/mo | Cost at 100K/mo | Transactional + Marketing |
|----------|-----------|---------------|-----------------|--------------------------|
| **Brevo** | 300/day (~9K/mo), permanent, 100K contacts | $29-69 | ~$69 | Yes — full platform |
| **AWS SES** | 3K/mo (12 months only) | $5 | $10 | Partial — no campaign mgmt |
| **SendGrid** | 60-day trial only | ~$20 | ~$20+ | Yes, but marketing is separate product |
| **Resend** | 3K/mo, permanent | $20 | $90 | Yes, but campaigns are new/immature |
| **Mailgun** | 100/day, permanent | ~$35 | ~$90 | Partial — no campaign builder |
| **Postmark** | 100/mo | ~$55 | ~$90 | Yes, but no list management |
| **MailerLite** | 12K/mo to 500 subs | $50-73 (10K subs) | $289 (50K subs) | **No** — marketing only, needs MailerSend |
| **Mailchimp** | 500/mo to 250 contacts | ~$40+ | ~$80+ | Yes, but transactional requires $20+/mo plan |

### Free Tiers (Permanent Only)

| Provider | Free Emails/Month | Free Contacts | Transactional | Marketing | Forced Branding |
|----------|-------------------|---------------|---------------|-----------|-----------------|
| Sender.net | 15,000 | 2,500 | Yes | Yes | Yes |
| SendPulse | 15,000 + 12,000 SMTP | 500 | Yes | Yes | Yes |
| MailerLite | 12,000 | 500 | No | Yes | Yes |
| EmailOctopus | 10,000 | 2,500 | No | Yes | Yes |
| **Brevo** | **~9,000 (300/day)** | **100,000** | **Yes** | **Yes** | Yes |
| Mailtrap | 4,000 (150/day) | N/A | Yes | No | No |
| Loops | 4,000 | 1,000 | Yes | Yes | Yes |
| Resend | 3,000 (100/day) | 1,000 | Yes | Yes | No |
| Mailgun | ~3,000 (100/day) | N/A | Yes | No | No |
| Postmark | 100 | N/A | Yes | No | No |

### API Capabilities for Data Offloading

| Provider | Campaign Stats API | Per-Message Logs | Bounce/Suppression API | Webhooks | Data Retention |
|----------|-------------------|-----------------|----------------------|----------|---------------|
| **Brevo** | Yes | Yes (30 days events) | Yes | Full (delivered, opened, clicked, bounced) | 24 months (unlimited if <10M events) |
| SendGrid | Yes | 3-30 days | Yes | Full | 30 days (paid add-on for more) |
| Postmark | Yes (tag-based) | 45 days | Yes (indefinite) | Full | Indefinite (aggregate), 45 days (per-message) |
| Mailgun | Yes (tag-based) | 2-30 days | Yes | Full | 1 year daily, lifetime monthly |
| Mailchimp | Yes | 7-30 days | Yes | Full | Indefinite (aggregate) |
| AWS SES | CloudWatch only | **Not stored** (build your own) | Yes | Via SNS (extra setup) | 2 weeks (without custom pipeline) |
| Resend | Per-email only | 1-7 days | Yes | Full | Very short (1-7 days by plan) |

---

## Regional Email Deliverability

### Key Finding: Region matters for edge cases, not for US/Canada/Europe

| Region | Inbox Placement | Dominant Inboxes | Notes |
|--------|----------------|-----------------|-------|
| **US/Canada** | ~85% | Gmail (75%), Outlook, Yahoo | All major ESPs work well |
| **Europe** | ~89% | Gmail, Outlook, GMX, Web.de, Orange | Higher than US (GDPR = cleaner lists) |
| **India** | ~85-90% | Gmail (82-96%) | Any ESP that delivers to Gmail works |
| **Latin America** | ~75-87% | Hotmail/Outlook, Gmail | Local ISPs have higher failure rates |
| **China** | **30-60%** | QQ Mail, 163.com, Sina Mail | **No Western ESP works.** Need Alibaba DirectMail or Tencent Cloud SES |
| **Japan** | Moderate-Low | Gmail, Yahoo Japan, Docomo, au | Mobile carriers block aggressively |
| **Russia** | Moderate | Mail.ru, Yandex | Local reputation systems |
| **South Korea** | Moderate | Naver Mail, Daum/Kakao | Naver is dominant, not Gmail |
| **Australia/NZ** | ~90%+ | Gmail, Outlook | Highest open rates globally |

### China Requires a Separate Provider

Western ESPs cannot reliably deliver to Chinese inboxes (QQ, 163.com). If targeting China:
- **Alibaba Cloud DirectMail** — powers Taobao, Tmall
- **Tencent Cloud SES** — 97% delivery rate, best for QQ Mail
- Foreign IPs are throttled to 20K-40K emails/day by Chinese ISPs
- Content censorship can trigger blacklisting
- Data localization (PIPL) requires China-based infrastructure

### ESP Regional Strengths

| ESP | Best For | Weaknesses |
|-----|----------|------------|
| AWS SES | Asia-Pacific (30 regions, per-region IP pools) | Not available in China |
| Brevo | Europe (EU-native, data stays in EU) | No APAC data centers |
| SendGrid | US (largest volume), EU available | Declining deliverability in tests |
| Postmark | US transactional (98.7% inbox) | US-only infrastructure |
| Resend | Multi-region (US, EU, Asia, SA) | Built on AWS SES underneath |

### Regional Compliance Laws

| Region | Law | Consent Model | Key Requirement |
|--------|-----|--------------|-----------------|
| US | CAN-SPAM | Opt-out | Physical address, unsubscribe within 10 days |
| Canada | CASL | Opt-in (strictest in Americas) | Express consent, honor unsubscribe within 10 days |
| EU | GDPR + ePrivacy | Opt-in (explicit) | Time-stamped consent records, right to deletion |
| Germany/Austria | GDPR + national | Double opt-in required | Stricter than base GDPR |
| UK | UK GDPR + PECR | Opt-in | Soft opt-in for existing customers |
| Brazil | LGPD | Opt-in | Privacy-by-design, incident reporting |
| China | PIPL | Opt-in + data localization | Data must be stored in China |
| Japan | APPI | Opt-in | Cross-border transfer rules |
| South Korea | PIPA | Opt-in (very strict) | Subject must start with "(AD)", no sending 9PM-8AM |
| Australia | Spam Act | Opt-in | Unsubscribe within 5 working days |

**Golden rule:** If you implement GDPR-level consent (explicit opt-in, records, easy unsubscribe) + CASL rigor (physical address, functional unsubscribe), you're compliant in nearly every jurisdiction.

---

## Splitting Transactional + Marketing Providers

### When to Split

| Stage | Approach | Why |
|-------|----------|-----|
| < 5K contacts | Single provider | Low volume = low risk, simplicity wins |
| 5K-50K contacts | Single provider with stream separation | Risk starts to matter but one vendor is easier |
| 50K+ contacts | Two specialized providers | Marketing reputation can damage transactional delivery |

### Best Combos If You Split Later

| Transactional | Marketing | Monthly Cost |
|---------------|-----------|-------------|
| Resend ($20) | MailerLite (free) | $20/mo |
| AWS SES ($1) | Brevo ($9) | $10/mo |
| Postmark ($15) | MailerLite (free) | $15/mo |
| MailerSend ($7) | MailerLite (free) | $7/mo |

### Architecture Support

The boilerplate supports both modes via `.env`:
```
# Single provider (default)
EMAIL_PROVIDER=brevo

# Split providers (when needed)
TRANSACTIONAL_EMAIL_PROVIDER=postmark
MARKETING_EMAIL_PROVIDER=mailerlite
```

---

## What Your App Stores vs What the ESP Stores

| Data | Your App | ESP (Brevo) |
|------|----------|-------------|
| Email templates | Source code (version controlled) | Rendered version (optional) |
| Campaign metadata + ESP ID | Yes (small table) | Full campaign data |
| Individual send records | **No** | Yes, full logs |
| Open/click/delivery events | **No** (pull aggregate stats from API) | Yes, per-recipient |
| Bounce/unsubscribe lists | **No** | Yes, automatically maintained |
| Subscriber lists | Optional (sync to ESP) | Yes, with segments |
| User email preferences | Yes (in users table) | Synced from your app |
| Cached campaign stats | Yes (refreshed from API on demand) | Authoritative source |

---

## AWS SES Deep Dive (Why It's So Cheap)

AWS SES is just a delivery pipe — $0.10 per 1,000 emails. No dashboard, no campaign builder, no subscriber lists, no open/click tracking by default, no scheduling, no templates, no bounce management UI. You build everything yourself. Makes sense at 1M+ emails/month with an engineering team. Not practical for a boilerplate.

## Deliverability: Provider vs Self-Hosted

| Approach | Inbox Placement |
|----------|----------------|
| Postmark | ~98-99% |
| Brevo | ~95-97% |
| SendGrid | ~93-97% |
| Your own server (no setup) | ~20-50% |

You need a provider. Emails sent directly from a VPS IP will land in spam.

---

## Sources

Research conducted April 2026 across official provider documentation, pricing pages, deliverability benchmarks, and independent reviews. Key sources include provider APIs (Brevo, SendGrid, Postmark, Mailgun, Resend, MailerLite, Mailchimp, AWS SES), EmailToolTester comparisons, Email Deliverability Report benchmarks, and regional compliance guides from Stripo, GetResponse, and Didomi.
