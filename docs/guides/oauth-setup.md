# OAuth Provider Setup Guide

## Overview

OAuth lets users sign in with their existing Google, GitHub, Microsoft, or Apple account instead of creating a new password. You register your app with each provider, get a Client ID + Secret, and paste them into `.env`. No code changes needed — providers auto-enable when their env vars are populated.

### How It Works

When a user clicks "Sign in with Google":
1. Your server redirects the user to Google's login page
2. The user enters their Google password **on Google's site** (you never see it)
3. Google asks: "Your App wants to see your name and email. Allow?"
4. Google redirects back to your server with a one-time code
5. Your server exchanges that code for the user's name + email
6. You create or log in the user in your own database

### What Data Goes Where

| Data | Where it lives | Who sees it |
|------|---------------|-------------|
| User's Google/GitHub/MS/Apple password | Provider only | **NOT you** |
| User's name + email (from OAuth) | Provider sends to you | You store in your DB |
| User's activity on your site | Your DB only | **NOT the provider** |
| User's orders, cart, payments | Your DB only | **NOT the provider** |
| Client ID + Secret | Your `.env` file | You + the provider |

The provider only knows that a user signed into your app (basic analytics on their end) and your app's domain name. They get zero access to your business data.

### Cost

| Provider | Cost | Account Needed | Local Dev (HTTP) |
|----------|------|---------------|------------------|
| GitHub | Free | GitHub account | Works |
| Google | Free | Google Cloud (free tier) | Works |
| Microsoft | Free | Azure (free tier) | Works |
| Apple | $99/year | Apple Developer Program | Requires HTTPS |

---

## Callback URL

Each provider needs a **redirect/callback URL** — the URL where the provider sends the user after they authorize your app.

**Local development:**
```
http://localhost:8000/api/auth/oauth/{provider}/callback
```

**Production:**
```
https://yourdomain.com/api/auth/oauth/{provider}/callback
```

The callback URL is built from the `BACKEND_URL` environment variable in `.env`. For local dev this is `http://localhost:8000`. For production, update it to your public domain.

> **Important:** The callback URL registered in the provider's console must exactly match what `BACKEND_URL` produces. If they don't match, the OAuth flow will fail with a "redirect_uri mismatch" error.

---

## GitHub Setup (~2 minutes)

### 1. Go to GitHub Developer Settings

Navigate to: https://github.com/settings/developers

### 2. Create a New OAuth App

Click **"New OAuth App"** (not "New GitHub App" — those are different).

Fill in:
| Field | Value |
|-------|-------|
| Application name | Your app name (e.g., "My Store") |
| Homepage URL | `http://localhost` (or your production domain) |
| Authorization callback URL | `http://localhost:8000/api/auth/oauth/github/callback` |

Click **Register application**.

### 3. Get Credentials

- **Client ID** is shown on the app page
- Click **"Generate a new client secret"** to get the secret (shown once — copy it immediately)

### 4. Configure `.env`

```env
GITHUB_CLIENT_ID=your_client_id_here
GITHUB_CLIENT_SECRET=your_client_secret_here
```

### 5. Restart FastAPI

```bash
docker compose up -d --build fastapi
```

### 6. Verify

```bash
curl -s http://localhost/api/auth/oauth/providers
# Should include "github" in the list
```

### Production Update

When deploying, update the callback URL in GitHub developer settings to:
```
https://yourdomain.com/api/auth/oauth/github/callback
```

---

## Google Setup (~3 minutes)

### 1. Go to Google Cloud Console

Navigate to: https://console.cloud.google.com/apis/credentials

If you don't have a Google Cloud project yet, create one (free, no billing required for OAuth).

### 2. Configure OAuth Consent Screen

Before creating credentials, you need a consent screen:

1. Go to **APIs & Services > OAuth consent screen**
2. Choose **External** user type
3. Fill in:
   - App name: Your app name
   - User support email: Your email
   - Developer contact email: Your email
4. Scopes: Add `email`, `profile`, `openid`
5. Test users: Add your own email (while in "Testing" status, only listed users can log in)
6. Click **Save and Continue** through the remaining steps

### 3. Create OAuth Credentials

1. Go to **APIs & Services > Credentials**
2. Click **"+ Create Credentials" > "OAuth client ID"**
3. Application type: **Web application**
4. Name: Your app name
5. Authorized redirect URIs: Add `http://localhost:8000/api/auth/oauth/google/callback`
6. Click **Create**

### 4. Get Credentials

A dialog shows your **Client ID** and **Client Secret**. Copy both.

### 5. Configure `.env`

```env
GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your_client_secret
```

### 6. Restart FastAPI

```bash
docker compose up -d --build fastapi
```

### 7. Verify

```bash
curl -s http://localhost/api/auth/oauth/providers
# Should include "google" in the list
```

### Notes

- While the OAuth consent screen is in **"Testing"** status, only users you've added as test users can log in. To allow anyone, submit for verification (Google reviews your app — takes a few days). For local dev, "Testing" mode is fine.
- When deploying to production, add the production callback URL as an additional authorized redirect URI (you can keep the localhost one too).

---

## Microsoft Setup (~5 minutes)

### 1. Go to Azure Portal

Navigate to: https://portal.azure.com/#view/Microsoft_AAD_RegisteredApplications

You'll need a free Azure account. You do NOT need a paid subscription.

### 2. Register an Application

1. Click **"New registration"**
2. Fill in:
   - Name: Your app name
   - Supported account types: **"Accounts in any organizational directory and personal Microsoft accounts"** (this allows @outlook.com, @hotmail.com, work/school accounts)
   - Redirect URI: Select **Web**, enter `http://localhost:8000/api/auth/oauth/microsoft/callback`
3. Click **Register**

### 3. Get Client ID

The **Application (client) ID** is shown on the overview page. Copy it.

### 4. Create Client Secret

1. Go to **Certificates & secrets** in the left sidebar
2. Click **"New client secret"**
3. Description: "OAuth" (or anything)
4. Expiry: Choose an appropriate duration (24 months is the max)
5. Click **Add**
6. Copy the **Value** (shown once — the "Secret ID" is NOT what you need, copy the "Value" column)

### 5. Configure `.env`

```env
MICROSOFT_CLIENT_ID=your_application_client_id
MICROSOFT_CLIENT_SECRET=your_client_secret_value
```

### 6. Restart FastAPI

```bash
docker compose up -d --build fastapi
```

### 7. Verify

```bash
curl -s http://localhost/api/auth/oauth/providers
# Should include "microsoft" in the list
```

### Notes

- Microsoft client secrets **expire**. Set a calendar reminder to rotate them before expiry. The maximum is 24 months.
- The adapter uses the `common` tenant endpoint, which accepts both personal Microsoft accounts and work/school (Azure AD) accounts.

---

## Apple Setup (~10 minutes) — Deprioritized

> **Note:** Apple Sign In is deprioritized for now due to the $99/year Apple Developer Program requirement and the complexity of local testing (Apple requires HTTPS callback URLs). The adapter code is fully implemented and ready — it just needs credentials.

### Prerequisites

- **Apple Developer Program membership** ($99/year): https://developer.apple.com/programs/
- A registered **App ID** with "Sign in with Apple" capability
- HTTPS callback URL (Apple does not allow HTTP, even for localhost)

### 1. Configure App ID

1. Go to https://developer.apple.com/account/resources/identifiers/list
2. Create or select an App ID
3. Enable **"Sign in with Apple"** capability

### 2. Create a Services ID

1. Go to **Identifiers** > click **"+"**
2. Select **Services IDs** > Continue
3. Description: Your app name
4. Identifier: A reverse-domain identifier (e.g., `com.yourcompany.yourapp.auth`)
5. Register, then click into the newly created Services ID
6. Enable **Sign in with Apple**
7. Click **Configure**:
   - Primary App ID: Select the App ID from step 1
   - Domains: `yourdomain.com` (or `localhost` for dev — but HTTPS required)
   - Return URLs: `https://yourdomain.com/api/auth/oauth/apple/callback`
8. Save

The Services ID identifier is your **Client ID**.

### 3. Create a Key

1. Go to https://developer.apple.com/account/resources/authkeys/list
2. Click **"+"**
3. Key Name: "Sign in with Apple Key"
4. Enable **Sign in with Apple**, configure it with your Primary App ID
5. Click **Register**
6. Download the `.p8` key file (shown once — save it securely)
7. Note the **Key ID** shown on the page

### 4. Gather Your Identifiers

You need four values:
| Value | Where to find it |
|-------|-----------------|
| Client ID | The Services ID identifier (e.g., `com.yourcompany.yourapp.auth`) |
| Team ID | Top-right of developer portal, or Membership page |
| Key ID | Shown when you created the key |
| Client Secret (P8 key) | Contents of the downloaded `.p8` file |

### 5. Configure `.env`

```env
APPLE_CLIENT_ID=com.yourcompany.yourapp.auth
APPLE_TEAM_ID=YOUR_TEAM_ID
APPLE_KEY_ID=YOUR_KEY_ID
APPLE_CLIENT_SECRET=-----BEGIN PRIVATE KEY-----\nMIGTAg...your_p8_key_contents...\n-----END PRIVATE KEY-----
```

> **Note:** The `APPLE_CLIENT_SECRET` is the PEM-encoded private key from the `.p8` file. Replace newlines with `\n` to keep it on one line in `.env`. The adapter generates a short-lived JWT client secret from this key at runtime.

### 6. Add Missing Env Vars

The current `.env` is missing `APPLE_TEAM_ID` and `APPLE_KEY_ID`. Add them:

```env
APPLE_TEAM_ID=
APPLE_KEY_ID=
```

### 7. Restart FastAPI

```bash
docker compose up -d --build fastapi
```

### Known Limitations

- Apple only sends the user's name (first/last) on the **very first authorization**. If you miss it, you can't get it again without the user revoking and re-authorizing your app. The current adapter does not capture the name from the initial POST body — this is a known limitation to fix.
- Apple requires HTTPS for callback URLs, making local development harder. Options: use ngrok, mkcert for local HTTPS, or test on a staging server with a real domain.

---

## Sessions & Authorization Behavior

### App Session Lifetime

| Token | Lifetime | Configured in |
|-------|----------|---------------|
| Access token (JWT) | 15 minutes | `JWT_EXPIRY` in `.env` |
| Refresh token (Redis) | 7 days | `REFRESH_TOKEN_TTL` in `.env` |

The access token expires every 15 minutes but is silently refreshed using the httpOnly refresh token cookie. The user stays logged in for **7 days** unless they explicitly log out.

### Provider Authorization Memory

Once a user authorizes your app with a provider (e.g. GitHub), the provider **remembers this permanently**. On subsequent "Sign in with GitHub" clicks, the provider skips the consent screen and redirects back immediately.

This is controlled by the provider, not your app. To reset it:

| Provider | How to revoke |
|----------|---------------|
| GitHub | https://github.com/settings/applications → Revoke |
| Google | https://myaccount.google.com/permissions → Remove access |
| Microsoft | https://account.microsoft.com/consent → Remove |
| Apple | Settings → Apple ID → Password & Security → Apps Using Apple ID |

### Switching Accounts

OAuth uses whichever account is currently signed in on that browser. If a user wants to sign in with a different provider account, they must:
- Log out of the provider in their browser first, or
- Use a different browser / incognito window

This is standard OAuth behavior — your app does not control which account the provider uses.

### Post-Login Redirect

After OAuth completes, the user is redirected back to the page they were on before clicking "Sign in". If they were on a login/register page, they're sent to the homepage (`/`).

---

## Account Linking — How Multiple Providers Share One User

### Database Structure

The system uses two tables to manage OAuth users:

**`core.users`** — One row per person (regardless of how many providers they use):
```
┌──────────────────────────────────────────────────────────────────┐
│ id: c2a52378-...                                                 │
│ email: user@gmail.com                                            │
│ first_name: Adrian                                               │
│ last_name: Radoi                                                 │
│ password_hash: NULL  (no password — signed up via OAuth)         │
│ is_verified: true                                                │
│ role: customer                                                   │
└──────────────────────────────────────────────────────────────────┘
```

**`core.oauth_identities`** — One row per provider, all pointing to the same user:
```
┌───────────────────────────────────────┐
│ provider: github                       │
│ provider_user_id: 261656897            │
│ user_id: c2a52378  ──────┐             │
└──────────────────────────┤             │
                           ▼             │
                 ┌─────────────────┐     │
                 │  user@gmail.com │     │
                 │   (ONE user)    │     │
                 └─────────────────┘     │
                           ▲             │
┌──────────────────────────┤             │
│ provider: google                       │
│ provider_user_id: 11520373...          │
│ user_id: c2a52378  ──────┘             │
└───────────────────────────────────────┘
```

### Linking Logic

When a user clicks "Sign in with Google/GitHub/Microsoft", the system follows this decision tree:

```
1. Does an oauth_identity exist for this provider + provider_user_id?
   YES → Log in as that user (returning user, same provider)
   NO  ↓

2. Does a verified user exist with the same email?
   YES → Create an oauth_identity linking this provider to that existing user
         Log in as that user (new provider, existing account)
   NO  ↓

3. Create a brand new user + oauth_identity
   (first-time user, no matching email in the system)
```

### Key Points

- **One email = one user**, regardless of how many providers they use to sign in
- The `oauth_identities` table is a lookup table that maps "provider X, account Y" → "our user Z"
- If a user signs up with GitHub, then later signs in with Google using the same email, both providers link to the same user — no duplicate accounts
- If the provider returns a name and the user record has no name, the system backfills it automatically
- Users who sign up via OAuth have `password_hash = NULL` — they cannot use "forgot password" until they set a password
- OAuth users are automatically synced to Stripe as customers on sign-in (using `get_or_create_stripe_customer`)

### OAuth Sign-In Performance

Each OAuth sign-in involves sequential external API calls, which add latency:

| Step | External call | Typical latency |
|------|--------------|-----------------|
| 1. Token exchange | POST to provider (e.g. `github.com/login/oauth/access_token`) | ~500ms-1s |
| 2. User info fetch | GET to provider API (e.g. `api.github.com/user` + `/user/emails`) | ~500ms-1s |
| 3. Stripe customer sync | Stripe API — create or look up customer | ~500ms-1s (first time only) |

**Total: ~2-3 seconds on first sign-in, ~1.5-2 seconds on subsequent sign-ins** (Stripe becomes a fast DB lookup once the customer exists).

This latency is inherent to the OAuth flow — each step depends on the previous one. It only happens at sign-in, not on normal page loads.

**Future optimization ideas:**
- Run the Stripe sync asynchronously (background task) after redirecting the user — removes ~500ms from the sign-in flow
- Cache provider user info in Redis for short-lived sessions to skip the user info fetch on rapid re-auths
- Use a server in a US datacenter closer to GitHub/Google/Stripe APIs to reduce round-trip times

---

## Forgot Password for OAuth Users

OAuth users who signed up via Google/GitHub/Microsoft have `password_hash = NULL` — they never set a password. The forgot password flow works for them with **no special handling needed**:

1. User clicks "Forgot password" → enters their email
2. System generates a reset token (same as for password users)
3. User clicks the reset link → sets a new password
4. `password_hash` is updated from NULL to the new hash
5. User can now sign in with **both** OAuth and email+password

This is a feature, not a bug — it gives OAuth users a fallback login method if their provider has an outage.

### Email Provider Status

The app currently uses a **placeholder email provider** (`EMAIL_PROVIDER=placeholder` in `.env`). Password reset tokens are logged to the FastAPI console instead of being emailed:

```bash
# View reset tokens in logs
docker logs boilerplate-app-fastapi-1 --tail 50 | grep "reset token"
```

To send real emails, configure a provider (Mailgun, SendGrid, Postmark) in `.env`:
```env
EMAIL_PROVIDER=mailgun   # or sendgrid, postmark
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=your_user
SMTP_PASSWORD=your_password
```

---

## Verifying All Providers Work

After setting up providers and restarting FastAPI:

```bash
# Check which providers are registered
curl -s http://localhost/api/auth/oauth/providers | python3 -m json.tool

# Expected output (if all three priority providers are set up):
# {
#     "providers": ["github", "google", "microsoft"]
# }
```

Then test in the browser:
1. Go to `http://localhost/auth/login`
2. You should see OAuth buttons for each registered provider
3. Click one — you should be redirected to the provider's login page
4. After authorizing, you should be redirected back to your app, logged in

---

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| Provider not in `/oauth/providers` list | Env vars empty or not loaded | Check `.env`, restart FastAPI |
| "redirect_uri_mismatch" | Callback URL in provider console doesn't match `BACKEND_URL` | Ensure they match exactly (including http vs https, port, path) |
| "invalid_client" | Wrong Client ID or Secret | Double-check values in `.env`, no extra spaces |
| 500 on callback | Code exchange failed | Check FastAPI logs: `docker logs boilerplate-app-fastapi-1 --tail 50` |
| User created but no name | Provider didn't return name | Normal for Apple (after first auth); check provider's user info response |

---

## File Reference

| File | Purpose |
|------|---------|
| `modules/auth/interfaces/auth_provider.py` | `AuthProvider` ABC + `OAuthUserInfo` dataclass |
| `modules/auth/adapters/google.py` | Google OAuth adapter |
| `modules/auth/adapters/github_oauth.py` | GitHub OAuth adapter |
| `modules/auth/adapters/microsoft.py` | Microsoft OAuth adapter |
| `modules/auth/adapters/apple.py` | Apple OAuth adapter |
| `modules/auth/adapters/oidc.py` | Generic OIDC adapter |
| `modules/auth/services/oauth_service.py` | Provider registry, state tokens, account linking |
| `modules/auth/routes/oauth_routes.py` | OAuth redirect + callback endpoints |
| `frontend/app/auth/login/page.tsx` | Login page with OAuth buttons |
| `backend/core/config.py` | `backend_url` setting used for callback URLs |
