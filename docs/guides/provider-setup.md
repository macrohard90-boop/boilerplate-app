# Email, SMS & WhatsApp Provider Setup Guide

This application supports multiple providers for each communication channel. Choose one provider per channel and configure the corresponding environment variables.

## Provider Matrix

| Channel | Console (dev) | Brevo | AWS SES | SendGrid | Twilio |
|---------|:---:|:---:|:---:|:---:|:---:|
| **Email** | Y | Y | Y | Y | - |
| **SMS** | Y | Y | - | - | Y |
| **WhatsApp** | Y | Y | - | - | Y |

## Quick Start

1. Pick a provider for each channel
2. Set the env vars in `.env`
3. Rebuild: `docker compose up -d --build`

---

## Email Providers

### Console (Development)

Logs emails to stdout. No external dependencies.

```env
EMAIL_PROVIDER=console
```

### Brevo (Sendinblue)

Full-featured: transactional + marketing emails, contact lists, webhooks.

**Setup:**
1. Sign up at [https://app.brevo.com](https://app.brevo.com)
2. Go to **Settings > SMTP & API > API Keys** and create an API key
3. For webhooks: **Settings > Webhooks**, add your endpoint URL and copy the signing secret

```env
EMAIL_PROVIDER=brevo
BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxx
BREVO_WEBHOOK_SECRET=your-webhook-signing-secret
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Your App Name
```

**Cost:** Free tier: 300 emails/day. Paid: from $9/mo for 5,000 emails.

### AWS SES

Best for high-volume sending at low cost. Requires domain verification.

**Setup:**
1. Open the [SES console](https://console.aws.amazon.com/ses/)
2. **Verified identities > Create identity** — verify your sending domain (DNS records)
3. Create IAM credentials with `ses:SendEmail`, `ses:PutSuppressedDestination` permissions
4. If you're in the SES sandbox, request production access via **Account dashboard > Request production access**
5. (Optional) Create a **Configuration Set** for open/click tracking via SNS

```env
EMAIL_PROVIDER=ses
AWS_REGION=us-east-1
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SES_CONFIGURATION_SET=               # Optional: enables open/click tracking
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Your App Name
```

**Webhook setup (SES events via SNS):**
1. In the SES console, create or edit a Configuration Set
2. Add an SNS destination for events: Delivery, Bounce, Complaint, Open, Click
3. Create an SNS topic subscription pointing to your webhook endpoint: `POST /api/gdpr/email/webhook`
4. Confirm the SNS subscription (SNS sends a confirmation request to your endpoint)

**Cost:** ~$0.10 per 1,000 emails. Free tier: 62,000/month when sent from EC2.

### SendGrid

Good balance of features and deliverability. Simple API key setup.

**Setup:**
1. Sign up at [https://app.sendgrid.com](https://app.sendgrid.com)
2. Go to **Settings > API Keys > Create API Key** (Full Access or restricted to Mail Send)
3. **Settings > Sender Authentication** — verify your sending domain
4. For webhooks: **Settings > Mail Settings > Event Webhook**, enable and point to your endpoint

```env
EMAIL_PROVIDER=sendgrid
SENDGRID_API_KEY=SG.xxxxxxxxxxxxxxxxxxxx
SENDGRID_WEBHOOK_SECRET=              # For Event Webhook signature verification
FROM_EMAIL=noreply@yourdomain.com
FROM_NAME=Your App Name
```

**Webhook endpoint:** `POST /api/gdpr/email/webhook`

**Cost:** Free tier: 100 emails/day. Paid: from $20/mo for 50,000 emails.

### Split Providers (Transactional vs Marketing)

You can use different providers for transactional (order confirmations, password resets) and marketing (campaigns, newsletters) emails:

```env
EMAIL_PROVIDER=ses                    # Default fallback
TRANSACTIONAL_EMAIL_PROVIDER=ses      # Fast, cheap, high deliverability
MARKETING_EMAIL_PROVIDER=brevo        # Rich campaign features, contact management
```

When a split provider is empty, it falls back to `EMAIL_PROVIDER`.

---

## SMS Providers

### Console (Development)

Logs SMS messages to stdout.

```env
SMS_PROVIDER=console
ENABLE_SMS=true
```

### Brevo

Sends SMS via Brevo's transactional SMS API.

**Setup:**
1. In Brevo, go to **Campaigns > SMS** and set up your sender name
2. Top up SMS credits in **Settings > Plans and pricing > SMS credits**

```env
ENABLE_SMS=true
SMS_PROVIDER=brevo
BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxx    # Same key as email
BREVO_SMS_SENDER=MyApp                     # 3-11 alphanumeric characters
```

**Cost:** Pay-per-SMS, varies by country. US: ~$0.015/SMS.

### Twilio

Industry standard for SMS. Supports short codes, 10DLC, toll-free, alphanumeric sender IDs.

**Setup:**
1. Sign up at [https://www.twilio.com](https://www.twilio.com)
2. Get your **Account SID** and **Auth Token** from the [console dashboard](https://console.twilio.com/)
3. Buy a phone number: **Phone Numbers > Manage > Buy a number**
4. For US A2P messaging, register a 10DLC brand and campaign

```env
ENABLE_SMS=true
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_SMS_FROM=+15551234567           # Your Twilio phone number
```

**Webhook setup:**
1. In the Twilio console, go to your phone number's configuration
2. Under **Messaging > A message comes in**, set the webhook URL: `POST /api/notifications/sms/webhook`
3. Under **Messaging > Status callback URL**, set the same endpoint for delivery receipts

**Cost:** ~$0.0079/SMS (US). Phone number: $1/mo.

---

## WhatsApp Providers

### Console (Development)

Logs WhatsApp messages to stdout.

```env
WHATSAPP_PROVIDER=console
ENABLE_WHATSAPP=true
```

### Brevo

WhatsApp Business via Brevo's API. Requires Brevo WhatsApp add-on.

**Setup:**
1. In Brevo, activate WhatsApp under **Apps > WhatsApp**
2. Connect your WhatsApp Business Account
3. Get your Brevo-provisioned WhatsApp number

```env
ENABLE_WHATSAPP=true
WHATSAPP_PROVIDER=brevo
BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxx
BREVO_WHATSAPP_NUMBER=+14155551234
```

### Twilio

WhatsApp Business API via Twilio. Uses the same Twilio credentials as SMS.

**Setup:**
1. In the Twilio console, go to **Messaging > Try it out > Send a WhatsApp message** to set up your sandbox
2. For production: apply for a WhatsApp Business Profile via **Messaging > Senders > WhatsApp senders**
3. Get your Twilio-provisioned WhatsApp number

```env
ENABLE_WHATSAPP=true
WHATSAPP_PROVIDER=twilio
TWILIO_ACCOUNT_SID=ACxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_AUTH_TOKEN=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TWILIO_WHATSAPP_FROM=+14155238886      # Your Twilio WhatsApp number
```

**Template messages:** Twilio uses Content SIDs (e.g., `HXxxxxxxxx`) for pre-approved WhatsApp templates. Create templates in **Messaging > Content Editor** and use the Content SID as the `template_name` parameter.

**Webhook setup:**
1. In the Twilio console, configure your WhatsApp sender's webhook URL
2. Set callback URL to: `POST /api/notifications/whatsapp/webhook`

**Cost:** WhatsApp conversations: $0.005-$0.08 depending on category and country.

---

## Recommended Configurations

### Development / Staging

```env
EMAIL_PROVIDER=console
SMS_PROVIDER=console
WHATSAPP_PROVIDER=console
```

### Small Business (< 10k emails/month)

```env
EMAIL_PROVIDER=brevo
SMS_PROVIDER=brevo
WHATSAPP_PROVIDER=brevo
BREVO_API_KEY=xkeysib-xxx
```

Single vendor, simple billing, free tier covers most small businesses.

### High-Volume E-commerce

```env
EMAIL_PROVIDER=ses
TRANSACTIONAL_EMAIL_PROVIDER=ses
MARKETING_EMAIL_PROVIDER=brevo
SMS_PROVIDER=twilio
WHATSAPP_PROVIDER=twilio
```

SES for cheap high-volume transactional, Brevo for campaign management, Twilio for reliable SMS/WhatsApp.

### Enterprise / Multi-Region

```env
EMAIL_PROVIDER=sendgrid
SMS_PROVIDER=twilio
WHATSAPP_PROVIDER=twilio
```

SendGrid for global deliverability, Twilio for worldwide SMS/WhatsApp coverage.

---

## Webhook Endpoints

| Channel | Endpoint | Provider Formats |
|---------|----------|-----------------|
| Email | `POST /api/gdpr/email/webhook` | Brevo (JSON), SES (SNS JSON), SendGrid (JSON array) |
| SMS | `POST /api/notifications/sms/webhook` | Brevo (JSON), Twilio (form-encoded) |
| WhatsApp | `POST /api/notifications/whatsapp/webhook` | Brevo (JSON), Twilio (form-encoded) |

All webhook handlers auto-detect the format based on the configured provider. Set up your provider's webhook/callback URL to point to the corresponding endpoint.

## Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| `Unknown email provider: xxx` | Typo in EMAIL_PROVIDER | Check value matches: console, brevo, ses, sendgrid |
| `Unknown SMS provider: xxx` | Typo in SMS_PROVIDER | Check value matches: console, brevo, twilio |
| SES sends fail with credentials error | Bad IAM keys or wrong region | Verify AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION |
| SES sends fail with "Email address not verified" | Domain not verified or still in sandbox | Verify domain in SES console; request production access |
| SendGrid returns 403 | API key lacks Mail Send permission | Create a new key with Full Access or Mail Send scope |
| Twilio returns 401 | Bad Account SID or Auth Token | Copy fresh credentials from Twilio console dashboard |
| Twilio WhatsApp fails with 21608 | Template not approved | Use sandbox for testing or submit template for approval |
