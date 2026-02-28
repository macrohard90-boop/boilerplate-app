# Shipping Rates & Tax Rates: Business Decision Guide

**Date:** 2026-02-28
**Status:** Analysis complete, implementation pending
**Audience:** App owner / deployer

---

## Current State in the App

Both are **structural placeholders** — the database fields exist but no calculation logic is built.

| Area | What Exists | What's Missing |
|------|------------|----------------|
| **Tax** | `orders.tax_amount` column (always 0), field in API responses, placeholder admin page | Tax rate tables, calculation logic, admin UI, Stripe Tax integration |
| **Shipping** | `orders.shipping_address` / `billing_address` (JSONB), address collection in checkout, `free_shipping` discount type | Shipping rate tables, cost calculation, method selection UI, no Stripe shipping integration |

Neither affects your checkout flow today — orders calculate as `total = subtotal - discount` with tax and shipping both at zero.

---

## TAX: Your Options as an App Owner

### Option 1: Stripe Tax (Let Stripe Calculate)

**How it works:** You flip on `automatic_tax` in your Stripe Checkout Sessions. Stripe calculates the correct sales tax / VAT / GST based on the customer's location, your registered addresses, and the product type. It adds tax to the total automatically.

**Cost:** 0.5% per transaction (on top of normal Stripe fees). On $10K/month revenue, that's $50/month.

**What you still have to do:**
- **Register** with each state/country where you have tax obligations (nexus)
- **File** tax returns with those authorities (monthly/quarterly)
- **Remit** (pay) the collected tax to the government yourself

Stripe calculates and collects. **You** file and pay. Stripe does NOT do that for you.

**Pros:**
- Near-zero dev work (a few lines of code)
- Accurate across 50 US states + international VAT/GST
- Stripe is liable if their calculations are wrong
- Handles multi-jurisdiction complexity automatically

**Cons:**
- 0.5% fee adds up at scale
- You lose control over how tax appears to customers
- Still need to file/remit yourself (or use a filing service like TaxJar)
- Only works within Stripe's payment flow

### Option 2: Calculate Your Own Tax (DIY)

**How it works:** You build tax rate tables in your database, write calculation logic in your order service, and add the tax amount to orders yourself. You pass the full amount (including tax) to Stripe as a single charge.

**You could also use a third-party tax API** (TaxJar, Avalara) for calculations without using Stripe Tax.

**Pros:**
- Full control over tax logic (exemptions, rounding, display)
- No per-transaction fee to Stripe for tax calculation
- Can implement inclusive pricing (tax baked into price) vs exclusive (tax added at checkout)
- Can decide to absorb tax on certain products as a business strategy

**Cons:**
- Tax rates change constantly (states update quarterly)
- Multi-state/international compliance is genuinely hard
- **You're liable** if calculations are wrong
- Significant dev effort to build and maintain

### Option 3: Don't Charge Tax (Absorb It)

**How it works:** You price your products to include tax and pay tax obligations out of your margins.

**Reality check:** This is legally fine in most jurisdictions — you're still required to *remit* tax, but you can choose to not charge customers extra for it. You'd price a $100 product at $100 and pay $8-10 in tax from your revenue.

**Pros:**
- Simplest customer experience (price = final price)
- Zero tax-related development
- Competitive advantage (lower apparent prices)

**Cons:**
- Eats into margins (8-10% in most US states)
- You still need to track nexus and file returns
- Unsustainable at scale if margins are thin

### Recommended Approach for This Boilerplate

For a **template app** that gets deployed to different businesses, the smartest approach is:

1. **Build a simple tax rate admin UI** — let the app owner define flat tax rates per region/country
2. **Wire the calculation into order_service** — multiply subtotal by rate
3. **Make Stripe Tax optional** — a config toggle (`tax_provider: "manual" | "stripe"`)
4. **Default to manual** — most small businesses start with flat rates

This way each deployment can choose: use simple flat rates, integrate Stripe Tax, or absorb tax entirely.

---

## SHIPPING: Your Options as an App Owner

### Option 1: Stripe Shipping Rates

**How it works:** You create shipping options in the Stripe Dashboard (e.g., "Standard $5", "Express $15", "Free"). These get presented to customers during Stripe Checkout.

**Critical limitation:** Fixed amounts only. You can't charge $5 for local and $25 for international based on address. Stripe's embedded checkout supports dynamic rates, but hosted checkout does not.

**Pros:**
- Zero dev work — configure in Stripe Dashboard
- Clean UX in Stripe Checkout
- No additional cost (included in Stripe)

**Cons:**
- Fixed rates only (no weight-based, no distance-based)
- Only works with Stripe Checkout (not your custom checkout flow)
- No carrier integration (can't get real USPS/UPS/FedEx quotes)
- Very basic — fine for digital products with flat shipping, bad for physical goods with varying weights

### Option 2: Build Your Own Shipping Rates

**How it works:** You create shipping zone/rate tables in your database. Admin sets rates like "US Domestic: $5.99", "Canada: $12.99", "EU: $19.99". Your checkout calculates shipping based on the customer's address.

**Pros:**
- Full control over pricing strategy
- Works with your custom checkout flow
- Can implement free shipping thresholds ("Free over $50")
- Can tie into your `free_shipping` discount type (which already exists but does nothing yet)
- No external dependencies

**Cons:**
- Dev time to build zone/rate management
- Manual rate maintenance (you set prices, not carriers)
- No real-time carrier quotes

### Option 3: Carrier API Integration (EasyPost / Shippo)

**How it works:** When customer enters their address at checkout, you call a shipping API that returns real-time quotes from USPS, UPS, FedEx, DHL, etc. Customer picks their preferred option.

**Cost:** EasyPost charges per-label (not per-quote). Shippo is similar. Typically $0.05-0.10 per label.

**Pros:**
- Real carrier rates (no guesswork)
- Rate shopping (automatically pick cheapest carrier)
- Label generation, tracking numbers
- International customs/duties handled

**Cons:**
- API integration complexity
- External dependency (API downtime = checkout blocked)
- Overkill for most small e-commerce sites
- Only makes sense if you're actually shipping physical goods at volume

### Option 4: Free Shipping / Digital Only

**How it works:** If your deployed apps sell digital products, subscriptions, or services — shipping doesn't apply. You skip it entirely.

The app already supports this — subscription checkout skips the shipping address step.

### Recommended Approach for This Boilerplate

1. **Build a simple shipping zone/rate admin UI** — flat rates per region (domestic, international, free tier)
2. **Add shipping calculation to checkout** — look up rate by customer's country/state
3. **Support free shipping threshold** — "Free shipping on orders over $X" (ties into existing `free_shipping` discount type)
4. **Make it optional** — `enable_shipping: bool` toggle. Digital-only businesses disable it entirely.

Skip carrier API integration for the template — it's deployment-specific and most template users won't need it.

---

## Comparison Matrix

| Decision | Impact on Revenue | Dev Effort | Ongoing Maintenance |
|----------|------------------|------------|-------------------|
| Stripe Tax | -0.5% per transaction | Low (hours) | Low (Stripe maintains rates) |
| DIY Tax (flat rates) | None (pass to customer) | Medium (1-2 days) | Medium (update rates quarterly) |
| Absorb Tax | -8-10% margin hit | None | Low (still must file) |
| Stripe Shipping (fixed) | Shipping revenue | Very low | Very low |
| DIY Shipping (zones) | Shipping revenue | Medium (1-2 days) | Low (update rates as needed) |
| Carrier API (EasyPost) | Accurate shipping revenue | High (3-5 days) | Medium (API changes, carrier updates) |

**Key takeaway:** For a boilerplate template, build the **simple self-managed versions** (flat tax rates + shipping zones) with config toggles. Let each deployment decide whether to upgrade to Stripe Tax or carrier APIs based on their specific needs. The template should work out of the box with manual rates and zero external dependencies beyond Stripe for payments.

---

## Tax Compliance Reality Check

Regardless of which tax option you choose, if you're selling in the US:

- **Economic nexus threshold**: $100K in sales in a state = you must register and collect tax there
- **You must file returns** even if using Stripe Tax (Stripe calculates, you remit)
- **TaxJar** (owned by Stripe) can automate filing for $19-699/month if needed
- **International VAT/GST** is a whole separate layer — 101 countries require it on cross-border e-commerce

This is a business/legal decision, not just a technical one.

---

## Third-Party Provider Comparison

### Tax Providers

| Provider | Best For | Pros | Cons | Cost |
|----------|----------|------|------|------|
| **Stripe Tax** | Stripe-native businesses | Simple integration, global coverage, real-time | Limited to Stripe, no auto-filing/remittance | 0.5% per txn |
| **TaxJar** | US small-to-medium sellers | US tax filing automation (AutoFile), real-time, affordable | US-only, limited to 50K orders/month max tier | $19-$699/month |
| **Avalara (AvaTax)** | Enterprise/Global | Most comprehensive, 75 countries, all tax types | Expensive, overkill for small businesses | Custom pricing |
| **TaxCloud** | Multi-channel sellers | Works with Stripe, PayPal, Square | US-only, basic reporting | Free tier available |
| **Manual/Custom** | Simple flat-rate needs | Full control, no ongoing fees | Compliance risk, hard to scale | Dev time only |

### Shipping Providers

| Service | Type | Best For | Cost |
|---------|------|----------|------|
| **Stripe Shipping** | Fixed rates | Simple tiers, Stripe Checkout only | Free (included) |
| **EasyPost** | Shipping API | Developers, carrier rate shopping | Per-label (~$0.05-0.10) |
| **ShipStation** | Platform + API | Multi-channel sellers | $99.99+/month |
| **Shippo** | Shipping API | Growing businesses | Per-label pricing |
| **Manual/Flat rates** | DIY | Zone-based flat pricing | Dev time only |

---

## Files Referenced

| File | Relevance |
|------|-----------|
| `migrations/002_ecommerce_schema.sql` | `orders.tax_amount`, `orders.shipping_address` columns |
| `modules/ecommerce/services/order_service.py` | `tax_amount` hardcoded to 0, no shipping cost |
| `modules/payments/services/checkout_service.py` | Returns `tax_amount: 0`, accepts shipping address |
| `modules/ecommerce/services/cart_service.py` | No tax or shipping in cart totals |
| `modules/ecommerce/services/discount_service.py` | `free_shipping` type exists but comment says "handled at shipping level" (not built) |
| `frontend/app/admin/catalog/shipping/page.tsx` | Placeholder "Coming soon" |
| `frontend/app/admin/catalog/tax/page.tsx` | Placeholder "Coming soon" |
| `frontend/app/checkout/page.tsx` | Collects address, no shipping/tax calculation |
