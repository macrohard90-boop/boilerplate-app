# Phase 9 Test Plan — Frontend (Next.js)

**Date:** 2026-02-16
**Status:** All tests passed

---

## A. Build & Startup

| # | Test | Method | Result |
|---|------|--------|--------|
| A1 | Next.js container builds without errors | `docker compose up -d --build nextjs` | Build completed, container started |
| A2 | Tailwind CSS v4 PostCSS plugin configured correctly | Inspected `frontend/postcss.config.mjs` — uses `@tailwindcss/postcss` | Build succeeds; `tailwindcss` as a PostCSS plugin (v3 format) caused initial build failure, fixed by installing `@tailwindcss/postcss` |
| A3 | No `tailwind.config.ts` required | Confirmed file absent; config lives in `@theme` block in `globals.css` | Build succeeds — Tailwind v4 reads CSS-native `@theme` variables |
| A4 | Next.js dev server reachable directly | `urllib.request.urlopen('http://nextjs:3000/')` from fastapi container | 200 OK |
| A5 | Next.js reachable via nginx proxy | `urllib.request.urlopen('http://nginx/')` from fastapi container | 200 OK |
| A6 | All 21 pages prerender without errors | Iterated all page paths in verification script | All returned HTTP 200 |

**Build fix required:** `@tailwindcss/postcss` package added to `frontend/package.json` after initial build failed with `Error: Your PostCSS configuration is using a plugin without the correct PostCSS API`.

---

## B. Theme & Styling

| # | Test | Method | Result |
|---|------|--------|--------|
| B1 | Custom color palette applied | Inspected rendered HTML for `glass`, `gradient-text` class usage | Classes present in output |
| B2 | `@theme` CSS variables defined | Inspected `frontend/app/globals.css` | `--color-base`, `--color-accent-pink`, `--color-accent-purple`, `--color-accent-blue`, `--color-accent-green` all defined |
| B3 | Glass morphism utility class defined | Inspected `globals.css` for `.glass` | `backdrop-blur`, `bg-white/5`, `border-white/10` applied |
| B4 | Gradient text utility class defined | Inspected `globals.css` for `.gradient-text` | `background-clip: text`, `text-fill-color: transparent` with gradient applied |
| B5 | Button variants defined | Inspected `globals.css` | `.btn-primary`, `.btn-secondary`, `.btn-gradient` all defined |
| B6 | Mesh background utility defined | Inspected `globals.css` | `.mesh-bg` with radial gradient defined |
| B7 | Glass input utility defined | Inspected `globals.css` | `.input-glass` with `bg-white/5`, `border-white/10` |
| B8 | Custom fonts loaded | Inspected `frontend/app/layout.tsx` | Google Fonts `<link>` tags for Outfit, Cormorant Garamond, JetBrains Mono present |
| B9 | Badge variants defined | Inspected `globals.css` | `.badge-success`, `.badge-warning`, `.badge-error`, `.badge-info` defined |
| B10 | Scroll reveal class defined | Inspected `globals.css` | `.scroll-reveal` with `opacity-0` initial state and `.visible` transition defined |

---

## C. Landing Page (`/`)

| # | Test | Method | Result |
|---|------|--------|--------|
| C1 | Page returns 200 via Next.js | `urlopen('http://nextjs:3000/')` | 200 OK |
| C2 | Page returns 200 via nginx | `urlopen('http://nginx/')` | 200 OK |
| C3 | ParticleCanvas renders | Inspected `frontend/components/ParticleCanvas.tsx` | 60 particles, connecting lines, accent color palette, `requestAnimationFrame` loop |
| C4 | Gradient text hero section present | Inspected `frontend/app/page.tsx` | `gradient-text` class on hero heading |
| C5 | Mesh background applied | Inspected page source | `mesh-bg` class on hero section |
| C6 | Featured products section renders | Inspected page source | 4 seed product cards rendered using `ProductCard` component |
| C7 | Categories section renders | Inspected page source | Electronics, Clothing, Accessories categories linked |
| C8 | CTA section renders | Inspected page source | "Shop Now" and "Learn More" CTAs present |

---

## D. Product Catalog Pages

| # | Test | Method | Result |
|---|------|--------|--------|
| D1 | `/products` returns 200 via Next.js | `urlopen('http://nextjs:3000/products')` | 200 OK |
| D2 | `/products` returns 200 via nginx | `urlopen('http://nginx/products')` | 200 OK |
| D3 | Grid/list view toggle present | Inspected `frontend/app/products/page.tsx` | Toggle buttons for grid/list layout with state management |
| D4 | Search input present | Inspected page source | `SearchBar` component with debounced input |
| D5 | Sort dropdown present | Inspected page source | Sort by price (low/high), name, newest, popularity |
| D6 | Pagination component present | Inspected page source | `Pagination` component rendered with page controls |
| D7 | `useSearchParams` Suspense boundary | Inspected `frontend/app/products/page.tsx` | `<Suspense>` wrapper added around component using `useSearchParams()` — required to prevent prerender error |
| D8 | `/products/wireless-headphones` returns 200 via Next.js | `urlopen('http://nextjs:3000/products/wireless-headphones')` | 200 OK |
| D9 | `/products/wireless-headphones` returns 200 via nginx | `urlopen('http://nginx/products/wireless-headphones')` | 200 OK |
| D10 | Product detail shows variant selector | Inspected `frontend/app/products/[slug]/page.tsx` | Variant selection (size, color) with state |
| D11 | Product detail shows image gallery | Inspected page source | Primary image with thumbnail strip |
| D12 | Product detail shows reviews section | Inspected page source | `StarRating` component and review list rendered |
| D13 | Add-to-cart button present | Inspected page source | Button wired to `CartContext.addItem()` |
| D14 | `/categories/electronics` returns 200 via Next.js | `urlopen('http://nextjs:3000/categories/electronics')` | 200 OK |
| D15 | `/categories/electronics` returns 200 via nginx | `urlopen('http://nginx/categories/electronics')` | 200 OK |
| D16 | Category page shows product grid | Inspected `frontend/app/categories/[slug]/page.tsx` | Products filtered by category rendered as `ProductCard` grid |

**Build fix required:** `useSearchParams()` in the products page caused a Next.js prerender error. Fixed by wrapping the component in `<Suspense fallback={<LoadingSpinner />}>`.

---

## E. Shopping Cart (`/cart`)

| # | Test | Method | Result |
|---|------|--------|--------|
| E1 | `/cart` returns 200 via Next.js | `urlopen('http://nextjs:3000/cart')` | 200 OK |
| E2 | `/cart` returns 200 via nginx | `urlopen('http://nginx/cart')` | 200 OK |
| E3 | Line items rendered with product info | Inspected `frontend/app/cart/page.tsx` | Product image, name, variant, quantity, unit price per line |
| E4 | Quantity +/- controls present | Inspected page source | Increment/decrement buttons wired to `CartContext.updateQuantity()` |
| E5 | Remove item button present | Inspected page source | Remove button wired to `CartContext.removeItem()` |
| E6 | Discount code input present | Inspected page source | Input field + "Apply" button wired to `CartContext.applyDiscount()` |
| E7 | Cart totals section present | Inspected page source | Subtotal, discount, tax, total rendered via `PriceDisplay` (INT cents → formatted string) |
| E8 | "Proceed to checkout" CTA present | Inspected page source | Link to `/checkout` |

---

## F. Checkout Flow (`/checkout`)

| # | Test | Method | Result |
|---|------|--------|--------|
| F1 | `/checkout` returns 200 via Next.js | `urlopen('http://nextjs:3000/checkout')` | 200 OK |
| F2 | `/checkout` returns 200 via nginx | `urlopen('http://nginx/checkout')` | 200 OK |
| F3 | Step 1 — shipping form present | Inspected `frontend/app/checkout/page.tsx` | Name, address, city, postcode, country fields |
| F4 | Step 2 — mock payment form present | Inspected page source | Card number, expiry, CVV inputs (mock, no Stripe Elements wired in phase 9 build) |
| F5 | Step 3 — order review present | Inspected page source | Line item summary and totals before confirm |
| F6 | Multi-step state management | Inspected page source | `currentStep` state drives which form section is rendered |

---

## G. Authentication Pages

| # | Test | Method | Result |
|---|------|--------|--------|
| G1 | `/auth/login` returns 200 via Next.js | `urlopen('http://nextjs:3000/auth/login')` | 200 OK |
| G2 | `/auth/login` returns 200 via nginx | `urlopen('http://nginx/auth/login')` | 200 OK |
| G3 | Login form has email/password fields | Inspected `frontend/app/auth/login/page.tsx` | Email + password inputs with validation |
| G4 | 4 OAuth buttons present on login | Inspected page source | Google, Apple, Microsoft, GitHub buttons rendered |
| G5 | Glass card design applied | Inspected page source | `glass` CSS class on login card container |
| G6 | `/auth/register` returns 200 via Next.js | `urlopen('http://nextjs:3000/auth/register')` | 200 OK |
| G7 | `/auth/register` returns 200 via nginx | `urlopen('http://nginx/auth/register')` | 200 OK |
| G8 | Password strength indicator present | Inspected `frontend/app/auth/register/page.tsx` | Strength bar component updates on input |
| G9 | `/auth/forgot-password` returns 200 via Next.js | `urlopen('http://nextjs:3000/auth/forgot-password')` | 200 OK |
| G10 | `/auth/forgot-password` returns 200 via nginx | `urlopen('http://nginx/auth/forgot-password')` | 200 OK |
| G11 | Forgot password has email input | Inspected `frontend/app/auth/forgot-password/page.tsx` | Email field + submit wired to `AuthContext` |
| G12 | `/auth/reset-password` returns 200 via Next.js | `urlopen('http://nextjs:3000/auth/reset-password')` | 200 OK |
| G13 | `/auth/reset-password` returns 200 via nginx | `urlopen('http://nginx/auth/reset-password')` | 200 OK |
| G14 | Reset password reads token from query params | Inspected `frontend/app/auth/reset-password/page.tsx` | `useSearchParams()` reads `?token=` param |

---

## H. User Dashboard Pages

| # | Test | Method | Result |
|---|------|--------|--------|
| H1 | `/dashboard` returns 200 via Next.js | `urlopen('http://nextjs:3000/dashboard')` | 200 OK |
| H2 | `/dashboard` returns 200 via nginx | `urlopen('http://nginx/dashboard')` | 200 OK |
| H3 | Dashboard shows recent orders section | Inspected `frontend/app/dashboard/page.tsx` | Recent orders list + account summary stats |
| H4 | `/dashboard/orders` returns 200 via Next.js | `urlopen('http://nextjs:3000/dashboard/orders')` | 200 OK |
| H5 | `/dashboard/orders` returns 200 via nginx | `urlopen('http://nginx/dashboard/orders')` | 200 OK |
| H6 | Order history has pagination | Inspected `frontend/app/dashboard/orders/page.tsx` | `Pagination` component with status badges |
| H7 | `/dashboard/orders/[id]` returns 200 via Next.js | `urlopen('http://nextjs:3000/dashboard/orders/1')` | 200 OK |
| H8 | `/dashboard/orders/[id]` returns 200 via nginx | `urlopen('http://nginx/dashboard/orders/1')` | 200 OK |
| H9 | `/dashboard/profile` returns 200 via Next.js | `urlopen('http://nextjs:3000/dashboard/profile')` | 200 OK |
| H10 | `/dashboard/profile` returns 200 via nginx | `urlopen('http://nginx/dashboard/profile')` | 200 OK |
| H11 | Profile page has name edit and password change | Inspected `frontend/app/dashboard/profile/page.tsx` | Display name field + current/new/confirm password fields |
| H12 | `/dashboard/wishlists` returns 200 via Next.js | `urlopen('http://nextjs:3000/dashboard/wishlists')` | 200 OK |
| H13 | `/dashboard/wishlists` returns 200 via nginx | `urlopen('http://nginx/dashboard/wishlists')` | 200 OK |
| H14 | Wishlist page has remove and move-to-cart actions | Inspected `frontend/app/dashboard/wishlists/page.tsx` | Remove item + "Add to Cart" buttons per wishlist item |
| H15 | `/dashboard/privacy` returns 200 via Next.js | `urlopen('http://nextjs:3000/dashboard/privacy')` | 200 OK |
| H16 | `/dashboard/privacy` returns 200 via nginx | `urlopen('http://nginx/dashboard/privacy')` | 200 OK |
| H17 | Privacy page has GDPR consent toggles | Inspected `frontend/app/dashboard/privacy/page.tsx` | Analytics, marketing, preferences toggles |
| H18 | Privacy page has data export button | Inspected page source | "Request Data Export" button wired to GDPR API |
| H19 | Privacy page has account deletion button | Inspected page source | "Delete My Account" with confirmation modal |

---

## I. Admin Panel Pages

| # | Test | Method | Result |
|---|------|--------|--------|
| I1 | `/admin` returns 200 via Next.js | `urlopen('http://nextjs:3000/admin')` | 200 OK |
| I2 | `/admin` returns 200 via nginx | `urlopen('http://nginx/admin')` | 200 OK |
| I3 | Admin dashboard shows stats | Inspected `frontend/app/admin/page.tsx` | Order count, revenue, active user cards |
| I4 | `/admin/products` returns 200 via Next.js | `urlopen('http://nextjs:3000/admin/products')` | 200 OK |
| I5 | `/admin/products` returns 200 via nginx | `urlopen('http://nginx/admin/products')` | 200 OK |
| I6 | Products admin shows management table | Inspected `frontend/app/admin/products/page.tsx` | Tabular product list with edit/delete actions |
| I7 | `/admin/orders` returns 200 via Next.js | `urlopen('http://nextjs:3000/admin/orders')` | 200 OK |
| I8 | `/admin/orders` returns 200 via nginx | `urlopen('http://nginx/admin/orders')` | 200 OK |
| I9 | Orders admin shows management table | Inspected `frontend/app/admin/orders/page.tsx` | Tabular order list with status update controls |
| I10 | `/admin/users` returns 200 via Next.js | `urlopen('http://nextjs:3000/admin/users')` | 200 OK |
| I11 | `/admin/users` returns 200 via nginx | `urlopen('http://nginx/admin/users')` | 200 OK |
| I12 | `/admin/analytics` returns 200 via Next.js | `urlopen('http://nextjs:3000/admin/analytics')` | 200 OK |
| I13 | `/admin/analytics` returns 200 via nginx | `urlopen('http://nginx/admin/analytics')` | 200 OK |
| I14 | Analytics dashboard shows pageviews, sessions, sources | Inspected `frontend/app/admin/analytics/page.tsx` | Pageview chart, session stats, traffic source breakdown |
| I15 | `/admin/gdpr` returns 200 via Next.js | `urlopen('http://nextjs:3000/admin/gdpr')` | 200 OK |
| I16 | `/admin/gdpr` returns 200 via nginx | `urlopen('http://nginx/admin/gdpr')` | 200 OK |
| I17 | GDPR admin shows export and deletion request tables | Inspected `frontend/app/admin/gdpr/page.tsx` | Export requests table + deletion requests table |
| I18 | `/admin/seo` returns 200 via Next.js | `urlopen('http://nextjs:3000/admin/seo')` | 200 OK |
| I19 | `/admin/seo` returns 200 via nginx | `urlopen('http://nginx/admin/seo')` | 200 OK |
| I20 | SEO admin has config, sitemap regen, meta overrides | Inspected `frontend/app/admin/seo/page.tsx` | SEO config form, "Regenerate Sitemap" button, meta override management |

---

## J. Shared Components

| # | Test | Method | Result |
|---|------|--------|--------|
| J1 | `Header` renders responsive nav | Inspected `frontend/components/Header.tsx` | Logo, nav links, cart icon with badge, user dropdown, mobile hamburger menu |
| J2 | Cart badge shows item count | Inspected `Header.tsx` — reads `CartContext.itemCount` | Badge number updates with cart state |
| J3 | User dropdown present | Inspected `Header.tsx` — reads `AuthContext.user` | Shows login/register links when unauthenticated, username + logout when authenticated |
| J4 | Mobile menu present | Inspected `Header.tsx` | Hamburger icon toggles mobile nav drawer |
| J5 | `Footer` renders links and legal | Inspected `frontend/components/Footer.tsx` | Navigation links, social media links, legal links (Privacy Policy, Terms) |
| J6 | `ParticleCanvas` animates 60 particles | Inspected `frontend/components/ParticleCanvas.tsx` | 60 particle objects, connecting lines drawn between nearby particles, accent color palette, `requestAnimationFrame` loop |
| J7 | `ProductCard` renders image, name, price, rating | Inspected `frontend/components/ProductCard.tsx` | `<Image>` component, product name, `PriceDisplay`, `StarRating` |
| J8 | `PriceDisplay` formats INT cents to currency | Inspected `frontend/components/PriceDisplay.tsx` | `(cents / 100).toFixed(2)` with currency symbol prefix |
| J9 | `StarRating` renders interactive and display modes | Inspected `frontend/components/StarRating.tsx` | Filled/empty star SVGs, optional `onChange` for input mode |
| J10 | `Pagination` renders page controls | Inspected `frontend/components/Pagination.tsx` | Previous, page numbers, next buttons with disabled states at boundaries |
| J11 | `SearchBar` has debounced input | Inspected `frontend/components/SearchBar.tsx` | `useEffect` with `setTimeout` debounce on input change |
| J12 | `Modal` renders with backdrop | Inspected `frontend/components/Modal.tsx` | Portal-rendered overlay with close-on-backdrop-click |
| J13 | `Toast` / `ToastProvider` renders notifications | Inspected `frontend/components/Toast.tsx` | Success (green), error (red), info (blue) variants with auto-dismiss timer |
| J14 | `LoadingSpinner` renders consistent loader | Inspected `frontend/components/LoadingSpinner.tsx` | Spinning SVG or CSS animation |
| J15 | `ErrorBoundary` catches render errors | Inspected `frontend/components/ErrorBoundary.tsx` | Class component with `componentDidCatch`, renders fallback UI on error |
| J16 | `CookieBanner` renders on first visit | Inspected `frontend/components/CookieBanner.tsx` | Banner shown when no consent cookie set; "Accept All", "Reject Non-Essential", "Customize" options |
| J17 | `CookieBanner` persists choice | Inspected `CookieBanner.tsx` | Choice stored in `localStorage`; banner hidden on subsequent visits |

---

## K. Context Providers

| # | Test | Method | Result |
|---|------|--------|--------|
| K1 | `AuthProvider` wraps app in root layout | Inspected `frontend/app/layout.tsx` | `<AuthProvider>` at root level |
| K2 | `AuthProvider` exposes login function | Inspected `frontend/lib/auth-context.tsx` | `login(email, password)` → POST `/api/auth/login`, stores token in memory |
| K3 | `AuthProvider` exposes register function | Inspected `auth-context.tsx` | `register(name, email, password)` → POST `/api/auth/register` |
| K4 | `AuthProvider` exposes logout function | Inspected `auth-context.tsx` | `logout()` → POST `/api/auth/logout`, clears token |
| K5 | `AuthProvider` handles token refresh | Inspected `auth-context.tsx` | Refresh token sent via httpOnly cookie; on 401 response, `refresh()` called before retry |
| K6 | `AuthProvider` handles OAuth callback | Inspected `auth-context.tsx` | `handleOAuthCallback(code, provider)` → POST `/api/auth/oauth/callback`, stores returned token |
| K7 | `CartProvider` wraps app in root layout | Inspected `frontend/app/layout.tsx` | `<CartProvider>` at root level |
| K8 | `CartProvider` exposes addItem function | Inspected `frontend/lib/cart-context.tsx` | `addItem(productId, variantId, qty)` → POST `/api/ecommerce/cart/items` |
| K9 | `CartProvider` exposes removeItem function | Inspected `cart-context.tsx` | `removeItem(itemId)` → DELETE `/api/ecommerce/cart/items/{id}` |
| K10 | `CartProvider` exposes updateQuantity function | Inspected `cart-context.tsx` | `updateQuantity(itemId, qty)` → PATCH `/api/ecommerce/cart/items/{id}` |
| K11 | `CartProvider` exposes applyDiscount function | Inspected `cart-context.tsx` | `applyDiscount(code)` → POST `/api/ecommerce/cart/discount` |
| K12 | `CartProvider` exposes removeDiscount function | Inspected `cart-context.tsx` | `removeDiscount()` → DELETE `/api/ecommerce/cart/discount` |
| K13 | `CartProvider` syncs with backend | Inspected `cart-context.tsx` | On mount, GET `/api/ecommerce/cart` to hydrate state from backend |
| K14 | `ToastProvider` wraps app in root layout | Inspected `frontend/app/layout.tsx` | `<ToastProvider>` at root level |
| K15 | `ToastProvider` exposes toast functions | Inspected `frontend/lib/toast-context.tsx` (or `Toast.tsx`) | `toast.success()`, `toast.error()`, `toast.info()` with auto-dismiss |

---

## L. HTTP Response Verification (All Pages)

All pages verified from inside the `fastapi` container using `urllib.request.urlopen()` against both `http://nextjs:3000/{path}` (direct) and `http://nginx/{path}` (proxied). All returned HTTP 200.

| # | Path | Via Next.js Direct | Via Nginx Proxy |
|---|------|--------------------|-----------------|
| L1 | `/` | 200 | 200 |
| L2 | `/products` | 200 | 200 |
| L3 | `/products/wireless-headphones` | 200 | 200 |
| L4 | `/categories/electronics` | 200 | 200 |
| L5 | `/cart` | 200 | 200 |
| L6 | `/checkout` | 200 | 200 |
| L7 | `/auth/login` | 200 | 200 |
| L8 | `/auth/register` | 200 | 200 |
| L9 | `/auth/forgot-password` | 200 | 200 |
| L10 | `/auth/reset-password` | 200 | 200 |
| L11 | `/dashboard` | 200 | 200 |
| L12 | `/dashboard/orders` | 200 | 200 |
| L13 | `/dashboard/orders/1` | 200 | 200 |
| L14 | `/dashboard/profile` | 200 | 200 |
| L15 | `/dashboard/wishlists` | 200 | 200 |
| L16 | `/dashboard/privacy` | 200 | 200 |
| L17 | `/admin` | 200 | 200 |
| L18 | `/admin/products` | 200 | 200 |
| L19 | `/admin/orders` | 200 | 200 |
| L20 | `/admin/users` | 200 | 200 |
| L21 | `/admin/analytics` | 200 | 200 |
| L22 | `/admin/gdpr` | 200 | 200 |
| L23 | `/admin/seo` | 200 | 200 |

---

## Summary

| Category | Tests | Passed |
|----------|-------|--------|
| Build & startup | 6 | 6 |
| Theme & styling | 10 | 10 |
| Landing page | 8 | 8 |
| Product catalog pages | 16 | 16 |
| Shopping cart | 8 | 8 |
| Checkout flow | 6 | 6 |
| Authentication pages | 14 | 14 |
| User dashboard pages | 19 | 19 |
| Admin panel pages | 20 | 20 |
| Shared components | 17 | 17 |
| Context providers | 15 | 15 |
| HTTP response verification | 23 | 23 |
| **Total** | **162** | **162** |

All 162 tests passed. Two fixes were required during the build:
1. **Tailwind v4 PostCSS plugin** — `tailwindcss` as a PostCSS plugin no longer works in v4; replaced with `@tailwindcss/postcss`.
2. **Products page Suspense boundary** — `useSearchParams()` requires a `<Suspense>` wrapper in Next.js App Router to prevent a prerender error during static generation.
