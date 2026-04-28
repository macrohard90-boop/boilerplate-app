-- 034: Event Definitions Registry
-- Central catalog of all analytics events with descriptions, payload schemas,
-- source code locations, and per-event enable/disable toggles.

-- UP

CREATE TABLE IF NOT EXISTS analytics.event_definitions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    description TEXT,
    category VARCHAR(50) NOT NULL,
    payload_schema JSONB NOT NULL DEFAULT '[]'::jsonb,
    source_locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    is_system BOOLEAN NOT NULL DEFAULT false,
    is_enabled BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_event_defs_name ON analytics.event_definitions(name);
CREATE INDEX IF NOT EXISTS idx_event_defs_category ON analytics.event_definitions(category);
CREATE INDEX IF NOT EXISTS idx_event_defs_enabled ON analytics.event_definitions(is_enabled);

-- Seed all known events
-- Categories: auth, browse, cart, checkout, engagement, discount, lifecycle, admin

-- ── Auth (7) ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('login_completed', 'Fired when a user successfully logs in via email/password', 'auth',
 '[{"field":"method","type":"string","description":"Login method (email)"}]',
 '[{"file":"frontend/app/auth/login/page.tsx","line":75,"snippet":"trackEvent(\"login_completed\", { method: \"email\" })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('login_failed', 'Fired when a login attempt fails', 'auth',
 '[{"field":"method","type":"string","description":"Login method attempted"}]',
 '[{"file":"frontend/app/auth/login/page.tsx","line":78,"snippet":"trackEvent(\"login_failed\", { method: \"email\" })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('oauth_started', 'Fired when a user clicks an OAuth provider button to begin authentication', 'auth',
 '[{"field":"provider","type":"string","description":"OAuth provider ID (google, github, etc.)"}]',
 '[{"file":"frontend/app/auth/login/page.tsx","line":152,"snippet":"trackEvent(\"oauth_started\", { provider: p.id })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('signup_completed', 'Fired when a new user successfully registers', 'auth',
 '[{"field":"method","type":"string","description":"Registration method (email)"}]',
 '[{"file":"frontend/app/auth/register/page.tsx","line":48,"snippet":"trackEvent(\"signup_completed\", { method: \"email\" })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('signup_failed', 'Fired when a registration attempt fails', 'auth',
 '[]',
 '[{"file":"frontend/app/auth/register/page.tsx","line":51,"snippet":"trackEvent(\"signup_failed\")"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('logout', 'Fired when a user logs out', 'auth',
 '[]',
 '[{"file":"frontend/components/Header.tsx","line":204,"snippet":"trackEvent(\"logout\")"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('cookie_consent_given', 'Fired when a user accepts cookie consent', 'auth',
 '[{"field":"analytics","type":"boolean","description":"Analytics cookies accepted"},{"field":"marketing","type":"boolean","description":"Marketing cookies accepted"}]',
 '[{"file":"frontend/components/ConsentModal.tsx","line":68,"snippet":"trackEvent(\"cookie_consent_given\", { analytics: toggles.analytics_cookies, marketing: toggles.marketing_cookies })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

-- ── Browse (8) ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('product_viewed', 'Fired when a user views a product detail page', 'browse',
 '[{"field":"product_id","type":"UUID","description":"Product ID"},{"field":"product_name","type":"string","description":"Product name"}]',
 '[{"file":"frontend/app/products/[slug]/ProductDetailClient.tsx","line":151,"snippet":"trackEvent(\"product_viewed\", { product_id: p.id, product_name: p.name })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('out_of_stock_viewed', 'Fired when a user views a product that is out of stock', 'browse',
 '[{"field":"product_id","type":"UUID","description":"Product ID"},{"field":"variant_id","type":"UUID","description":"Out-of-stock variant ID"}]',
 '[{"file":"frontend/app/products/[slug]/ProductDetailClient.tsx","line":160,"snippet":"trackEvent(\"out_of_stock_viewed\", { product_id: p.id, variant_id: variant.id })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('variant_selected', 'Fired when a user selects a different product variant', 'browse',
 '[{"field":"product_id","type":"UUID","description":"Product ID"},{"field":"variant_id","type":"UUID","description":"Selected variant ID"},{"field":"variant_name","type":"string","description":"Variant display name"}]',
 '[{"file":"frontend/app/products/[slug]/ProductDetailClient.tsx","line":386,"snippet":"trackEvent(\"variant_selected\", { product_id: product.id, variant_id: v.id, variant_name: v.name })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('category_browsed', 'Fired when a user views a product category page', 'browse',
 '[{"field":"category_id","type":"UUID","description":"Category ID"},{"field":"category_name","type":"string","description":"Category name"}]',
 '[{"file":"frontend/app/categories/[slug]/CategoryPageClient.tsx","line":66,"snippet":"trackEvent(\"category_browsed\", { category_id: category.id, category_name: category.name })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('search_performed', 'Fired when a user submits a product search query', 'browse',
 '[{"field":"query","type":"string","description":"Search query text"}]',
 '[{"file":"frontend/app/products/ProductsPageClient.tsx","line":125,"snippet":"trackEvent(\"search_performed\", { query: q })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('search_no_results', 'Fired when a product search returns zero results', 'browse',
 '[{"field":"query","type":"string","description":"Search query that returned no results"}]',
 '[{"file":"frontend/app/products/ProductsPageClient.tsx","line":108,"snippet":"trackEvent(\"search_no_results\", { query: search })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('sort_changed', 'Fired when a user changes the product sort order', 'browse',
 '[{"field":"sort_value","type":"string","description":"Selected sort option value"}]',
 '[{"file":"frontend/app/products/ProductsPageClient.tsx","line":131,"snippet":"trackEvent(\"sort_changed\", { sort_value: val })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('filter_used', 'Fired when a user applies a product filter (e.g. category)', 'browse',
 '[{"field":"filter_type","type":"string","description":"Type of filter applied"},{"field":"filter_value","type":"string","description":"Filter value selected"}]',
 '[{"file":"frontend/app/products/ProductsPageClient.tsx","line":146,"snippet":"trackEvent(\"filter_used\", { category_id: id, category_name: cat?.name })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

-- ── Cart (7) ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('add_to_cart', 'Fired when a user adds a product to their cart', 'cart',
 '[{"field":"product_id","type":"UUID","description":"Product added"},{"field":"variant_id","type":"UUID","description":"Variant added"},{"field":"quantity","type":"number","description":"Quantity added"},{"field":"price","type":"number","description":"Unit price in cents"}]',
 '[{"file":"frontend/lib/cart-context.tsx","line":112,"snippet":"trackEvent(\"add_to_cart\", { product_id: productId, variant_id: variantId, quantity, price })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('high_value_cart', 'Fired when the cart total exceeds $100 (10000 cents)', 'cart',
 '[{"field":"cart_total","type":"number","description":"Cart total in cents"},{"field":"item_count","type":"number","description":"Number of items in cart"}]',
 '[{"file":"frontend/lib/cart-context.tsx","line":119,"snippet":"trackEvent(\"high_value_cart\", { cart_total: data.total, item_count: data.item_count })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('cart_quantity_changed', 'Fired when a user changes the quantity of an item in their cart', 'cart',
 '[{"field":"product_id","type":"UUID","description":"Product modified"},{"field":"old_qty","type":"number","description":"Previous quantity"},{"field":"new_qty","type":"number","description":"New quantity"}]',
 '[{"file":"frontend/lib/cart-context.tsx","line":159,"snippet":"trackEvent(\"cart_quantity_changed\", { product_id: productId, old_qty, new_qty })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('remove_from_cart', 'Fired when a user removes an item from their cart', 'cart',
 '[{"field":"product_id","type":"UUID","description":"Product removed"}]',
 '[{"file":"frontend/lib/cart-context.tsx","line":200,"snippet":"trackEvent(\"remove_from_cart\", { product_id: productId })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('cart_cleared', 'Fired when a user empties their entire cart', 'cart',
 '[{"field":"item_count","type":"number","description":"Number of items that were in the cart"}]',
 '[{"file":"frontend/lib/cart-context.tsx","line":244,"snippet":"trackEvent(\"cart_cleared\", { item_count: prev.item_count })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('empty_cart_viewed', 'Fired when a user views an empty cart page', 'cart',
 '[]',
 '[{"file":"frontend/app/cart/page.tsx","line":46,"snippet":"trackEvent(\"empty_cart_viewed\")"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('cart_viewed', 'Fired when a user views their cart with items', 'cart',
 '[{"field":"item_count","type":"number","description":"Number of items in cart"},{"field":"cart_total","type":"number","description":"Cart total in cents"}]',
 '[{"file":"frontend/app/cart/page.tsx","line":48,"snippet":"trackEvent(\"cart_viewed\", { item_count: cart.item_count, cart_total: cart.total })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

-- ── Checkout (6) ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('checkout_started', 'Fired when a user initiates checkout from the cart page', 'checkout',
 '[{"field":"cart_total","type":"number","description":"Cart total in cents"},{"field":"item_count","type":"number","description":"Number of items"}]',
 '[{"file":"frontend/app/cart/page.tsx","line":178,"snippet":"trackEvent(\"checkout_started\", { cart_total: cart.total, item_count: cart.item_count })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('checkout_step_viewed', 'Fired when a checkout step is displayed to the user', 'checkout',
 '[{"field":"step","type":"number","description":"Checkout step number (1-3)"},{"field":"cart_total","type":"number","description":"Cart total in cents"}]',
 '[{"file":"frontend/app/checkout/page.tsx","line":231,"snippet":"trackEvent(\"checkout_step_viewed\", { step, cart_total: cart.total })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('checkout_abandoned', 'Fired when a user navigates away from checkout before completing', 'checkout',
 '[{"field":"step","type":"number","description":"Step where user abandoned"},{"field":"cart_total","type":"number","description":"Cart total in cents"},{"field":"items_abandoned","type":"number","description":"Number of items left"}]',
 '[{"file":"frontend/app/checkout/page.tsx","line":238,"snippet":"trackEvent(\"checkout_abandoned\", { step, cart_total: cart.total, items_abandoned: cart.item_count })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('payment_submitted', 'Fired when the user submits the payment form', 'checkout',
 '[{"field":"order_id","type":"UUID","description":"Order being paid for"}]',
 '[{"file":"frontend/app/checkout/page.tsx","line":68,"snippet":"trackEvent(\"payment_submitted\", { order_id: orderId })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('payment_failed', 'Fired when a payment attempt fails', 'checkout',
 '[{"field":"order_id","type":"UUID","description":"Order that failed"},{"field":"error_code","type":"string","description":"Stripe error code"}]',
 '[{"file":"frontend/app/checkout/page.tsx","line":80,"snippet":"trackEvent(\"payment_failed\", { order_id: orderId, error_code: stripeError.code })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('purchase_completed', 'Fired when an order is successfully placed (redirect to Stripe or free order)', 'checkout',
 '[{"field":"order_id","type":"UUID","description":"Completed order ID"},{"field":"order_total","type":"number","description":"Order total in cents"},{"field":"currency","type":"string","description":"Currency code"},{"field":"items_count","type":"number","description":"Number of items purchased"}]',
 '[{"file":"frontend/app/checkout/page.tsx","line":355,"snippet":"trackEvent(\"purchase_completed\", { total: cart.total, currency: cart.currency, items_count: cart.item_count })"},{"file":"frontend/app/checkout/page.tsx","line":376,"snippet":"trackEvent(\"purchase_completed\", { order_id: result.order_id, total: cart.total })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

-- ── Engagement (3) ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('return_visit', 'Fired when a returning user visits after 1+ days away', 'engagement',
 '[{"field":"days_since_last","type":"number","description":"Days since last visit"}]',
 '[{"file":"frontend/lib/page-duration-tracker.tsx","line":232,"snippet":"trackEvent(\"return_visit\", { days_since_last: daysSince })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('long_session', 'Fired when a user session exceeds 10 minutes', 'engagement',
 '[{"field":"duration_sec","type":"number","description":"Session duration in seconds (600)"}]',
 '[{"file":"frontend/lib/page-duration-tracker.tsx","line":239,"snippet":"trackEvent(\"long_session\", { duration_sec: 600 })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

-- ── Discount (3) ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('coupon.exhausted', 'System event fired when a coupon reaches its max_uses limit during checkout', 'discount',
 '[{"field":"coupon_code","type":"string","description":"Coupon code that was exhausted"},{"field":"max_uses","type":"number","description":"Maximum usage limit"},{"field":"uses_count","type":"number","description":"Final usage count"}]',
 '[{"file":"modules/ecommerce/services/discount_service.py","snippet":"record_event(db, session_id, \"coupon.exhausted\", ...)"}]',
 true)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('coupon_applied', 'Fired when a coupon code is successfully applied to the cart', 'discount',
 '[{"field":"code","type":"string","description":"Coupon code applied"},{"field":"discount_amount","type":"number","description":"Discount amount in cents"}]',
 '[{"file":"frontend/lib/cart-context.tsx","line":220,"snippet":"trackEvent(\"coupon_applied\", { code, discount_amount: data.discount_amount })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('coupon_failed', 'Fired when a coupon code validation fails', 'discount',
 '[{"field":"code","type":"string","description":"Coupon code that failed"}]',
 '[{"file":"frontend/lib/cart-context.tsx","line":225,"snippet":"trackEvent(\"coupon_failed\", { code })"}]',
 false)
ON CONFLICT (name) DO NOTHING;

-- ── Lifecycle (4) — Backend system events ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('user.registered', 'System event fired when a new user account is created (triggers automation flows)', 'lifecycle',
 '[{"field":"email","type":"string","description":"New user email"},{"field":"first_name","type":"string","description":"User first name"}]',
 '[{"file":"modules/auth/routes/auth_routes.py","line":176,"snippet":"await fire_event_for_flows(db, \"user.registered\", str(new_user.id), {\"email\": email, \"first_name\": first_name})"}]',
 true)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('order.completed', 'System event fired when a Stripe payment succeeds and order is marked completed', 'lifecycle',
 '[{"field":"order_id","type":"UUID","description":"Completed order ID"},{"field":"amount","type":"number","description":"Payment amount in cents"}]',
 '[{"file":"modules/payments/services/webhook_service.py","line":171,"snippet":"await fire_event_for_flows(db, \"order.completed\", user_id, {\"order_id\": str(order_id), \"amount\": amount})"}]',
 true)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('cart.abandoned', 'System event fired by the order reaper when a cart is inactive for too long', 'lifecycle',
 '[{"field":"cart_id","type":"UUID","description":"Abandoned cart ID"}]',
 '[{"file":"modules/payments/services/order_reaper.py","line":168,"snippet":"await fire_event_for_flows(db, \"cart.abandoned\", user_id, {\"cart_id\": str(cart_id)})"}]',
 true)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('segment.entered', 'System event fired by the segment check worker when a user enters a new audience segment', 'lifecycle',
 '[{"field":"segment_id","type":"UUID","description":"Segment the user entered"}]',
 '[{"file":"modules/marketing/workers/segment_check_worker.py","line":83,"snippet":"await fire_event_for_flows(db, \"segment.entered\", user_id, {\"segment_id\": str(segment_id)})"}]',
 true)
ON CONFLICT (name) DO NOTHING;

-- ── Admin (13) — Admin CRUD actions tracked server-side ──

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.product_created', 'Fired when an admin creates a new product', 'admin',
 '[{"field":"product_id","type":"UUID","description":"Created product ID"},{"field":"product_name","type":"string","description":"Product name"},{"field":"status","type":"string","description":"Product status"},{"field":"base_price","type":"number","description":"Base price in cents"}]',
 '[{"file":"modules/ecommerce/routes/product_routes.py","snippet":"record_event(db, ..., \"admin.product_created\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.product_updated', 'Fired when an admin updates a product', 'admin',
 '[{"field":"product_id","type":"UUID","description":"Updated product ID"},{"field":"product_name","type":"string","description":"Product name"}]',
 '[{"file":"modules/ecommerce/routes/product_routes.py","snippet":"record_event(db, ..., \"admin.product_updated\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.product_deleted', 'Fired when an admin deletes a product', 'admin',
 '[{"field":"product_id","type":"UUID","description":"Deleted product ID"}]',
 '[{"file":"modules/ecommerce/routes/product_routes.py","snippet":"record_event(db, ..., \"admin.product_deleted\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.variant_created', 'Fired when an admin creates a product variant', 'admin',
 '[{"field":"product_id","type":"UUID","description":"Parent product ID"},{"field":"variant_name","type":"string","description":"Variant name"},{"field":"stock_quantity","type":"number","description":"Initial stock quantity"}]',
 '[{"file":"modules/ecommerce/routes/product_routes.py","snippet":"record_event(db, ..., \"admin.variant_created\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.category_created', 'Fired when an admin creates a category', 'admin',
 '[{"field":"category_id","type":"UUID","description":"Created category ID"},{"field":"category_name","type":"string","description":"Category name"}]',
 '[{"file":"modules/ecommerce/routes/category_routes.py","snippet":"record_event(db, ..., \"admin.category_created\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.category_updated', 'Fired when an admin updates a category', 'admin',
 '[{"field":"category_id","type":"UUID","description":"Updated category ID"},{"field":"category_name","type":"string","description":"Category name"}]',
 '[{"file":"modules/ecommerce/routes/category_routes.py","snippet":"record_event(db, ..., \"admin.category_updated\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.category_deleted', 'Fired when an admin deletes a category', 'admin',
 '[{"field":"category_id","type":"UUID","description":"Deleted category ID"}]',
 '[{"file":"modules/ecommerce/routes/category_routes.py","snippet":"record_event(db, ..., \"admin.category_deleted\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.coupon_created', 'Fired when an admin creates a coupon/discount', 'admin',
 '[{"field":"coupon_code","type":"string","description":"Coupon code"},{"field":"type","type":"string","description":"Discount type"},{"field":"value","type":"number","description":"Discount value"}]',
 '[{"file":"modules/ecommerce/routes/discount_routes.py","snippet":"record_event(db, ..., \"admin.coupon_created\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.coupon_updated', 'Fired when an admin updates a coupon/discount', 'admin',
 '[{"field":"discount_id","type":"UUID","description":"Discount ID"},{"field":"coupon_code","type":"string","description":"Coupon code"}]',
 '[{"file":"modules/ecommerce/routes/discount_routes.py","snippet":"record_event(db, ..., \"admin.coupon_updated\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.coupon_deactivated', 'Fired when an admin deactivates a coupon/discount', 'admin',
 '[{"field":"discount_id","type":"UUID","description":"Discount ID"},{"field":"coupon_code","type":"string","description":"Coupon code"}]',
 '[{"file":"modules/ecommerce/routes/discount_routes.py","snippet":"record_event(db, ..., \"admin.coupon_deactivated\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.template_created', 'Fired when an admin creates an email template', 'admin',
 '[{"field":"template_id","type":"UUID","description":"Template ID"},{"field":"template_name","type":"string","description":"Template name"},{"field":"category","type":"string","description":"Template category"}]',
 '[{"file":"modules/marketing/routes/admin_routes.py","snippet":"record_event(db, ..., \"admin.template_created\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.template_updated', 'Fired when an admin updates an email template', 'admin',
 '[{"field":"template_id","type":"UUID","description":"Template ID"},{"field":"template_name","type":"string","description":"Template name"}]',
 '[{"file":"modules/marketing/routes/admin_routes.py","snippet":"record_event(db, ..., \"admin.template_updated\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('admin.template_deleted', 'Fired when an admin deletes an email template', 'admin',
 '[{"field":"template_id","type":"UUID","description":"Template ID"}]',
 '[{"file":"modules/marketing/routes/admin_routes.py","snippet":"record_event(db, ..., \"admin.template_deleted\", ...)"}]',
 false)
ON CONFLICT (name) DO NOTHING;

-- DOWN
DROP TABLE IF EXISTS analytics.event_definitions CASCADE;
