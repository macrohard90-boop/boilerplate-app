# Phase 9: Frontend (Next.js)

**Estimate:** 6-8 hours
**Depends on:** Phase 4, Phase 5, Phase 7, Phase 8
**Category:** User interface

## Goal
Build the complete Next.js frontend using App Router: authentication pages, product catalog, shopping cart, checkout flow, user dashboard, admin panel, cookie consent banner, and responsive design. At the end of this phase, the application has a fully functional UI that consumes all backend APIs built in phases 3-8.

## Prerequisite Reading
Read `docs/ARCHITECTURE.md` sections 3 (Session & Auth), 6 (Payment Lifecycle), and 7 (Docker Compose — Next.js service) for frontend integration points. Review all API routes created in phases 3-8.

## Deliverables

1. **App Shell & Layout** (frontend/app/):
   - Root layout: global styles, fonts, metadata, providers
   - Navigation header: logo, nav links, cart icon (with item count), user menu
   - Footer: links, social media, legal pages
   - Responsive breakpoints: mobile (< 768px), tablet (768-1024px), desktop (> 1024px)
   - Dark/light mode support (optional, based on system preference)
   - Loading states and error boundaries for all pages

2. **Authentication pages** (frontend/app/auth/):
   - `/auth/login` — email/password form, OAuth buttons (Google, Apple, Microsoft, GitHub)
   - `/auth/register` — registration form with validation (password strength indicator)
   - `/auth/forgot-password` — email input, send reset link
   - `/auth/reset-password` — new password form (from email link with token)
   - `/auth/verify-email` — email verification confirmation page
   - Token management: store access token in memory, refresh token in httpOnly cookie
   - Auto-redirect: authenticated users → dashboard, unauthenticated → login
   - OAuth redirect handling: process callback, store tokens, redirect to dashboard

3. **Product catalog pages** (frontend/app/products/):
   - `/products` — product listing with grid/list view toggle
     - Filters: category, price range, availability, search
     - Sorting: price (low/high), name, newest, popularity
     - Pagination: load more or numbered pages
   - `/products/[slug]` — product detail page
     - Image gallery with thumbnails
     - Variant selector (size, color, etc.)
     - Price display (formatted from INT cents, with currency symbol)
     - Add to cart button (with variant and quantity selection)
     - Product reviews section (display + submit form)
     - Related products / "Frequently bought together" from recommendations
     - JSON-LD structured data (from SEO API)
   - `/categories/[slug]` — category page with product listing

4. **Shopping cart** (frontend/app/cart/):
   - `/cart` — cart page
     - Line items with product image, name, variant, quantity, price
     - Quantity adjustment (+/- buttons)
     - Remove item button
     - Discount code input and apply
     - Cart totals: subtotal, discount, tax, total (all formatted from INT cents)
     - "Continue shopping" and "Proceed to checkout" CTAs
   - Cart icon in header: shows item count, dropdown preview on hover/click
   - Guest cart: works without login, prompts login at checkout
   - Cart persistence: syncs with backend (PostgreSQL for auth, Redis for guest)

5. **Checkout flow** (frontend/app/checkout/):
   - `/checkout` — multi-step or single-page checkout
     - Step 1: Shipping address form (or saved address selection)
     - Step 2: Billing address (same as shipping checkbox)
     - Step 3: Payment — Stripe Elements integration (card input)
     - Step 4: Order review and confirmation
   - Stripe.js integration: load Stripe Elements, create payment intent, confirm payment
   - Order confirmation page: `/orders/[id]/confirmation`
   - Error handling: payment failures, stock issues, session expiry

6. **User dashboard** (frontend/app/dashboard/):
   - `/dashboard` — overview: recent orders, account summary
   - `/dashboard/orders` — order history (paginated, status badges)
   - `/dashboard/orders/[id]` — order detail (items, status, tracking, payment info)
   - `/dashboard/profile` — edit profile (name, email, password change)
   - `/dashboard/addresses` — saved addresses management
   - `/dashboard/wishlists` — wishlist management (view, remove items, move to cart)
   - `/dashboard/api-keys` — API key management (create, revoke, view scopes) — for M2M users
   - `/dashboard/privacy` — GDPR: consent management, data export request, account deletion

7. **Admin panel** (frontend/app/admin/):
   - `/admin` — admin dashboard overview (order count, revenue, active users)
   - `/admin/products` — product management (CRUD, bulk actions)
   - `/admin/orders` — order management (status updates, refunds)
   - `/admin/users` — user management (roles, status, search)
   - `/admin/analytics` — analytics dashboard (page views, sessions, traffic sources, UTM)
   - `/admin/gdpr` — GDPR dashboard (export requests, deletion requests, consent stats)
   - `/admin/seo` — SEO management (meta tag overrides, sitemap regeneration)
   - Protected: only accessible to admin role users

8. **Cookie consent banner** (frontend/components/):
   - Banner component: shown on first visit, persists choice
   - Cookie categories: necessary (always on), analytics, marketing, preferences
   - "Accept all" / "Reject non-essential" / "Customize" options
   - Integrates with `/api/gdpr/cookies` backend endpoint
   - Respects saved preferences (don't show banner if already set)
   - Blocks analytics/marketing scripts until consent granted

9. **SEO integration** (frontend/app/):
   - `generateMetadata()` in all page components: fetch meta from `/api/seo/meta/{path}`
   - Open Graph and Twitter Card tags in metadata
   - JSON-LD structured data embedded as `<script type="application/ld+json">`
   - Canonical URLs set per page
   - Dynamic sitemap: Next.js `sitemap.ts` proxies to backend `/sitemap.xml`
   - Robots: Next.js `robots.ts` proxies to backend `/robots.txt`

10. **Shared components** (frontend/components/):
    - `ProductCard` — reusable product card (image, name, price, rating)
    - `PriceDisplay` — formats INT cents to currency string (e.g., 1999 → "$19.99")
    - `Pagination` — reusable pagination component
    - `SearchBar` — product search with debounced input
    - `StarRating` — display and input star ratings
    - `AddressForm` — reusable address form with validation
    - `Modal` — reusable modal/dialog component
    - `Toast` — notification toasts for success/error messages
    - `LoadingSpinner` — consistent loading state
    - `ErrorBoundary` — graceful error display

11. **API client** (frontend/lib/):
    - Centralized API client with base URL configuration
    - Automatic token attachment (access token in Authorization header)
    - Token refresh interceptor: on 401, refresh tokens and retry
    - Error handling: parse backend error format `{error, message, details}`
    - Type-safe API functions matching backend endpoints

## Acceptance Criteria
- [ ] Login and registration work with email/password
- [ ] OAuth login works for at least one provider
- [ ] Product listing displays with filtering, sorting, pagination
- [ ] Product detail page shows variants, images, reviews, related products
- [ ] Price displays correctly (INT cents → formatted currency string)
- [ ] Cart operations work (add, update quantity, remove, apply discount)
- [ ] Guest cart works without authentication
- [ ] Cart merges on login (guest → authenticated)
- [ ] Checkout flow completes with Stripe payment
- [ ] Order confirmation page displays after successful payment
- [ ] Dashboard shows order history and account management
- [ ] Wishlist management works (add, remove, move to cart)
- [ ] Privacy page allows consent management, data export, account deletion
- [ ] Admin panel is protected (admin role only)
- [ ] Cookie consent banner appears on first visit and persists choice
- [ ] SEO meta tags render server-side (view source confirms)
- [ ] JSON-LD structured data present in page source
- [ ] Responsive design works on mobile, tablet, desktop
- [ ] Token refresh works transparently (no manual re-login needed)
- [ ] Error states handled gracefully (loading, empty, error)

## Implementation Notes
- Use Next.js App Router with Server Components where possible (better SEO, less client JS)
- Client Components only where interactivity needed (forms, cart, checkout)
- Stripe Elements: use `@stripe/stripe-js` and `@stripe/react-stripe-js`
- API calls from Server Components: use `fetch()` with backend internal URL
- API calls from Client Components: use API client with token handling
- Price formatting: create utility `formatPrice(cents: number, currency: string) → string`
- Image optimization: use Next.js `<Image>` component for product images
- Form validation: use React Hook Form or native validation
- State management: React Context for auth/cart state, no heavy state library needed
- CSS: Tailwind CSS or CSS Modules (maintain consistency with existing setup)

## Files to Create
- `frontend/app/auth/login/page.tsx` — Login page
- `frontend/app/auth/register/page.tsx` — Registration page
- `frontend/app/auth/forgot-password/page.tsx` — Forgot password page
- `frontend/app/auth/reset-password/page.tsx` — Reset password page
- `frontend/app/products/page.tsx` — Product listing
- `frontend/app/products/[slug]/page.tsx` — Product detail
- `frontend/app/categories/[slug]/page.tsx` — Category listing
- `frontend/app/cart/page.tsx` — Cart page
- `frontend/app/checkout/page.tsx` — Checkout flow
- `frontend/app/orders/[id]/confirmation/page.tsx` — Order confirmation
- `frontend/app/dashboard/page.tsx` — Dashboard overview
- `frontend/app/dashboard/orders/page.tsx` — Order history
- `frontend/app/dashboard/orders/[id]/page.tsx` — Order detail
- `frontend/app/dashboard/profile/page.tsx` — Profile management
- `frontend/app/dashboard/wishlists/page.tsx` — Wishlist management
- `frontend/app/dashboard/privacy/page.tsx` — GDPR/privacy management
- `frontend/app/admin/page.tsx` — Admin dashboard
- `frontend/app/admin/products/page.tsx` — Product management
- `frontend/app/admin/orders/page.tsx` — Order management
- `frontend/app/admin/users/page.tsx` — User management
- `frontend/app/admin/analytics/page.tsx` — Analytics dashboard
- `frontend/components/ProductCard.tsx` — Product card component
- `frontend/components/PriceDisplay.tsx` — Price formatter component
- `frontend/components/CookieBanner.tsx` — Cookie consent banner
- `frontend/components/Pagination.tsx` — Pagination component
- `frontend/components/SearchBar.tsx` — Search component
- `frontend/components/StarRating.tsx` — Rating component
- `frontend/lib/api.ts` — API client with auth handling
- `frontend/lib/auth-context.tsx` — Auth state provider
- `frontend/lib/cart-context.tsx` — Cart state provider
- `frontend/lib/format.ts` — Price formatting and utility functions
- Modified: `frontend/app/layout.tsx` — Add providers, navigation, footer
- Modified: `frontend/package.json` — Add Stripe, React Hook Form dependencies
